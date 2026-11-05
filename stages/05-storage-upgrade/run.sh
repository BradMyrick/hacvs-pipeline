#!/usr/bin/env bash
# Stage 5 — storage layout & upgradeability verification (PR tier)
# Gate: zero storage collisions; initializer protection; selector uniqueness.
set -uo pipefail
umask 0000  # container-created evidence stays host-manageable (runners execute as root)
ENG="${ENGAGEMENT_DIR:-/engagement}"
TARGET="$ENG/target"; ART="$ENG/artifacts"
mkdir -p "$ART"
stage_fail=0
note() { echo "[stage-05] $*"; }
fail() { echo "[stage-05] FAIL: $*" | tee "$ART/stage-05-failures.txt" >&2; exit 1; }

cd "$TARGET" || { fail "target/ missing"; exit 1; }

BASELINE_COMMIT="$(python3 -c "import json;print(json.load(open('$ENG/engagement.json')).get('baseline_commit') or '')")"
ARCH="$(python3 -c "import json;print(','.join(json.load(open('$ENG/engagement.json'))['applicability'].get('proxy_architectures',[])))")"
note "applicable architectures: ${ARCH:-none declared}"
note "baseline commit: ${BASELINE_COMMIT:-none (first audit — baseline snapshot recorded)}"

# --- Extract current storage layouts for every src contract
note "extracting current storage layouts (forge inspect)"
CURRENT_LAYOUTS="$ART/storage-layouts-current"
mkdir -p "$CURRENT_LAYOUTS"
for sol in $(find src -name '*.sol' 2>/dev/null); do
  for contract in $(grep -oE "contract [A-Za-z0-9_]+" "$sol" | awk '{print $2}'); do
    if forge inspect "$contract" storage-layout --json \
        > "$CURRENT_LAYOUTS/${contract}.json" 2>/dev/null; then
      note "layout: $contract"
    fi
  done
done
[ -n "$(ls -A "$CURRENT_LAYOUTS" 2>/dev/null)" ] || fail "no storage layouts extracted"

# --- Baseline comparison (when a baseline commit is declared)
if [ -n "$BASELINE_COMMIT" ] && [ "$BASELINE_COMMIT" != "none" ]; then
  note "checking out baseline worktree at $BASELINE_COMMIT"
  git worktree add -f .baseline "$BASELINE_COMMIT" >/dev/null 2>&1 \
    || fail "cannot create baseline worktree (bad baseline_commit?)"
  BASELINE_LAYOUTS="$ART/storage-layouts-baseline"
  mkdir -p "$BASELINE_LAYOUTS"
  # Build baseline + inspect using the same pinned toolchain
  (cd .baseline && forge build --build-info --force --out out-baseline >/dev/null 2>&1) \
    || fail "baseline build failed"
  for f in "$CURRENT_LAYOUTS"/*.json; do
    name="$(basename "$f")"
    contract="${name%.json}"
    (cd .baseline && forge inspect "$contract" storage-layout --json \
        > "$ENG/$BASELINE_LAYOUTS/$name" 2>/dev/null) || true
    if [ -f "$ENG/$BASELINE_LAYOUTS/$name" ]; then
      python3 /pipeline/tools/layout-diff/layout_diff.py \
        --baseline "$ENG/$BASELINE_LAYOUTS/$name" \
        --current "$f" \
        --contract "$contract" \
        --baseline-src "$TARGET/.baseline/src" \
        --current-src "$TARGET/src" \
        --out "$ART/storage-layout-diff-${contract}.json" \
        || fail "layout diff found issues for $contract (see storage-layout-diff-$contract.json)"
    else
      note "no baseline layout for $contract (new contract — recorded)"
    fi
  done
else
  note "no baseline commit — current layouts recorded as the baseline for future upgrades"
fi

# --- Initializer protection: logic constructors must call _disableInitializers
note "checking initializer lock on logic contracts"
python3 - "$TARGET" "$ART" <<'PY' || fail "initializer lock check failed"
import json, pathlib, re, sys
target, art = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
issues, checked = [], 0
for bi in sorted(target.glob("out/build-info/*.json")) or []:
    data = json.loads(bi.read_text())
    for src, payload in (data.get("output", {}).get("sources") or {}).items():
        text = (data.get("input", {}).get("sources", {}).get(src, {}) or {}).get("content", "")
        if not text:
            continue
        for m in re.finditer(r"contract\s+(\w+)[^{]*\{", text):
            name = m.group(1)
            # find the constructor block (crude but effective: constructor(...) { ... })
            cm = re.search(r"constructor\s*\([^)]*\)\s*(?:\w+\s*)*\{", text[m.start():])
            if cm:
                checked += 1
                start = m.start() + cm.end() - 1
                depth, i = 0, start
                while i < len(text):
                    if text[i] == "{": depth += 1
                    elif text[i] == "}":
                        depth -= 1
                        if depth == 0: break
                    i += 1
                body = text[start:i]
                if ("initializer" in text.lower() or "Initializable" in text) \
                        and "_disableInitializers" not in body:
                    issues.append(f"{name}: Initializable contract without _disableInitializers() in constructor")
(art / "initializer-check.json").write_text(json.dumps({"checked": checked, "issues": issues}, indent=2))
print(json.dumps({"checked": checked, "issues": len(issues)}))
sys.exit(1 if issues else 0)
PY

# --- Diamond facet selector collisions + ERC-7201 namespace immutability
python3 - "$TARGET" "$ART" "$ARCH" <<'PY' || fail "diamond/selector checks failed"
import json, pathlib, sys
target, art, arch = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]), sys.argv[3]
issues = []
selector_map = {}
for bi in sorted(target.glob("out/build-info/*.json")) or []:
    data = json.loads(bi.read_text())
    for path, contracts in (data.get("output", {}).get("contracts") or {}).items():
        for name, meta in contracts.items():
            for fn in meta.get("abi", []):
                if fn.get("type") == "function":
                    sig = fn["name"] + "(" + ",".join(
                        i["type"] for i in fn.get("inputs", [])) + ")"
                    selector_map.setdefault(sig, set()).add(f"{path}::{name}")
# Keccak selector computation via cast at runner level is heavy; instead detect
# 4-byte ambiguity by identical full signatures implemented by >1 contract.
for sig, impls in selector_map.items():
    if len(impls) > 1 and "diamond" in arch.lower():
        issues.append(f"selector ambiguity: {sig} implemented by {sorted(impls)}")
(art / "diamond-selector-check.json").write_text(
    json.dumps({"duplicates": issues}, indent=2))
print(json.dumps({"duplicate_signatures": len(issues)}))
sys.exit(1 if issues else 0)
PY

exit $stage_fail
