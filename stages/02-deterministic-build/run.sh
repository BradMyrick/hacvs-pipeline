#!/usr/bin/env bash
# Stage 2 — deterministic build & bytecode size validation (PR tier)
# Gate: bit-for-bit reproducible bytecode; EIP-170 (24576B runtime) and
#       EIP-3860 (49152B initcode) limits.
set -uo pipefail
ENG="${ENGAGEMENT_DIR:-/engagement}"
TARGET="$ENG/target"; ART="$ENG/artifacts"
mkdir -p "$ART"
stage_fail=0
note() { echo "[stage-02] $*"; }
fail() { echo "[stage-02] FAIL: $*" | tee "$ART/stage-02-failures.txt" >&2; stage_fail=1; }

cd "$TARGET" || { fail "target/ missing"; exit 1; }

# --- Spec-locked compiler settings (via_ir, runs 200, ipfs metadata, solc pin)
note "verifying foundry.toml against SPEC compiler settings"
source /pipeline/docker/pins.env 2>/dev/null || true
grep -qE "^\s*solc_version\s*=\s*\"${SOLC_VERSION}\"" foundry.toml \
  || fail "foundry.toml solc_version is not pinned to ${SOLC_VERSION} (SPEC lock)"
solc --version | grep -q "Version: ${SOLC_VERSION}" \
  || fail "container solc is not ${SOLC_VERSION} — toolchain pin drift"
python3 - "$TARGET/foundry.toml" <<'PY' || fail "foundry.toml does not match SPEC (via_ir=true, optimizer_runs=200, bytecode_hash=ipfs)"
import sys, re
src = open(sys.argv[1]).read()
checks = [
    (r"^\s*via_ir\s*=\s*true", "via_ir = true"),
    (r"^\s*optimizer_runs\s*=\s*200", "optimizer_runs = 200"),
    (r"^\s*bytecode_hash\s*=\s*[\"']ipfs[\"']", "bytecode_hash = ipfs"),
    (r"^\s*optimizer\s*=\s*true", "optimizer = true"),
]
missing = [desc for pat, desc in checks if not re.search(pat, src, re.M)]
if missing:
    print("missing compiler settings: " + ", ".join(missing)); sys.exit(1)
PY

# --- Double clean build (separate out dirs; nothing is deleted)
note "build #1 (out-a)"
forge build --build-info --force --out out-a || fail "forge build #1 failed"
note "build #2 (out-b)"
forge build --build-info --force --out out-b || fail "forge build #2 failed"

note "comparing out-a vs out-b byte-for-byte"
if diff -r out-a out-b > "$ART/reproducibility.diff" 2>&1; then
  note "builds are bit-for-bit identical"
else
  fail "builds differ — see artifacts/reproducibility.diff"
fi

# --- Bytecode sizes (runtime vs initcode) vs EIP-170 / EIP-3860
python3 - "$TARGET" "$ART" <<'PY' || fail "bytecode size extraction failed"
import json, pathlib, sys
target, art = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
sizes = {}
for f in sorted(target.glob("out-a/**/*.json")):
    if f.name.endswith(".json") and f.stem != ".solidity_metadata":
        try:
            data = json.loads(f.read_text())
        except Exception:
            continue
        rt = (data.get("deployedBytecode", {}).get("object") or "").replace("0x", "")
        ic = (data.get("bytecode", {}).get("object") or "").replace("0x", "")
        if not rt and not ic:
            continue
        name = f.relative_to(target).as_posix()
        entry = {"runtime_bytes": len(rt)//2, "initcode_bytes": len(ic)//2}
        entry["eip170_violation"] = entry["runtime_bytes"] > 24576
        entry["eip3860_violation"] = entry["initcode_bytes"] > 49152
        sizes[name] = entry
(art / "bytecode-sizes.json").write_text(json.dumps(sizes, indent=2) + "\n")
viol = {k: v for k, v in sizes.items() if v["eip170_violation"] or v["eip3860_violation"]}
print(json.dumps({"contracts": len(sizes), "violations": len(viol)}))
sys.exit(1 if viol else 0)
PY

# --- Canonical AST (build-info ASTs with paths relativized)
python3 - "$TARGET" "$ART" <<'PY' || fail "canonical AST extraction failed"
import json, pathlib, sys
target, art = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
canon = {"sources": {}}
for bi in sorted(target.glob("out-a/build-info/*.json")) or sorted(target.glob("out*/build-info/*.json")):
    data = json.loads(bi.read_text())
    for name, src in (data.get("output", {}).get("sources") or {}).items():
        rel = str(pathlib.Path(name).relative_to(target)) if str(name).startswith(str(target)) else name
        canon["sources"][rel] = src.get("ast", {})
if not canon["sources"]:
    print("no AST sources found in build-info"); sys.exit(1)
(art / "canonical-ast.json").write_text(json.dumps(canon, sort_keys=True, indent=1) + "\n")
print(f"canonical AST: {len(canon['sources'])} sources")
PY

# --- Reproducible manifest (hashes of all build artifacts)
( cd "$TARGET" && find out-a -type f | sort \
  | xargs sha256sum ) > "$ART/reproducible-manifest.sha256" \
  || fail "manifest generation failed"

exit $stage_fail
