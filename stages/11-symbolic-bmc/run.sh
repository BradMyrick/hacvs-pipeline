#!/usr/bin/env bash
# Stage 11 — symbolic execution & bounded model checking (RELEASE tier)
# Dual BMC engines (solc SMTChecker + Halmos) + bytecode-level Mythril.
set -uo pipefail
ENG="${ENGAGEMENT_DIR:-/engagement}"
TARGET="$ENG/target"; ART="$ENG/artifacts"
mkdir -p "$ART"
stage_fail=0
note() { echo "[stage-11] $*"; }
fail() { echo "[stage-11] FAIL: $*" | tee "$ART/stage-11-failures.txt" >&2; stage_fail=1; }

cd "$TARGET" || { fail "target/ missing"; exit 1; }

# --- solc SMTChecker (bmc + chc via foundry model_checker profile)
note "SMTChecker build (bmc+chc, targets: assert,underflow,overflow,divByZero,balance)"
grep -q "\[profile.default.model_checker\]" foundry.toml \
  || fail "foundry.toml lacks [profile.default.model_checker] (scaffold provides spec settings)"
forge build --force > "$ART/smt-build.log" 2>&1 \
  || { grep -q "Counterexample" "$ART/smt-build.log" && fail "SMTChecker found counterexamples — see artifacts/smt-build.log" || fail "forge build (smt) failed"; }
if grep -q "Counterexample" "$ART/smt-build.log"; then
  fail "SMTChecker counterexamples present — see artifacts/smt-build.log"
fi
CE_COUNT=$(grep -c "Counterexample" "$ART/smt-build.log" || true)
note "SMTChecker counterexamples: ${CE_COUNT:-0}"

# --- Halmos: primary source-level bounded model checker over Foundry tests
note "halmos symbolic execution of Foundry tests"
halmos --loop 3 > "$ART/halmos-results.txt" 2>&1 \
  || fail "halmos reported failing proofs — see artifacts/halmos-results.txt"
HALMOS_FAIL=$(grep -cE "Failing tests:|FAILED" "$ART/halmos-results.txt" || true)
HALMOS_PASS=$(grep -cE "PASS" "$ART/halmos-results.txt" || true)
note "halmos: passing=${HALMOS_PASS:-0} failing=${HALMOS_FAIL:-0}"

python3 - "$ART" "${HALMOS_PASS:-0}" "${HALMOS_FAIL:-0}" "${CE_COUNT:-0}" <<'PY'
import json, pathlib, sys
art, p, f, ce = pathlib.Path(sys.argv[1]), *map(int, sys.argv[2:5])
(art / "symbolic-summary.json").write_text(json.dumps({
    "smtchecker": {"counterexamples": ce},
    "halmos": {"passing": p, "failing": f},
}, indent=2) + "\n")
PY

# --- Mythril: bytecode-level taint/path analysis
note "mythril bytecode-level analysis"
myth analyze src \
  --json --output "$ART/mythril-results.json" \
  --execution-timeout 600 --solver-timeout 30000 --strategy bfs \
  > "$ART/mythril-stdout.txt" 2>&1 \
  || note "mythril exited non-zero (issues found or timeout — parsed below)"

python3 - "$ART" <<'PY'
import json, pathlib, sys
art = pathlib.Path(sys.argv[1])
suppressed = set()
supp = pathlib.Path("/engagement/target/.security-suppressions.json")
if supp.exists():
    try:
        for e in json.loads(supp.read_text()):
            if e.get("tool") == "mythril":
                suppressed.add((e.get("finding_id"), str(e.get("file", ""))))
    except Exception:
        pass
issues = []
f = art / "mythril-results.json"
if f.exists() and f.stat().st_size:
    try:
        data = json.loads(f.read_text())
        issues = data.get("issues", [])
    except Exception as exc:
        print(f"mythril parse error: {exc}"); sys.exit(1)
unmitigated = []
for i in issues:
    sev = (i.get("severity") or "").title()
    if sev not in ("High", "Critical"):
        continue
    swc = str(i.get("swc-id") or i.get("check", "?"))
    fname = (i.get("source") or {}).get("filename", "") if isinstance(i.get("source"), dict) else ""
    if (swc, "") in suppressed or any(s[0] == swc and s[1] and s[1] in fname for s in suppressed):
        continue
    unmitigated.append({"severity": sev, "swc": swc,
                        "title": (i.get("description") or {}).get("head", "")[:100]
                        if isinstance(i.get("description"), dict) else str(i.get("description", ""))[:100]})
summary = {"total_issues": len(issues), "unmitigated_high_critical": unmitigated}
(art / "mythril-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps({"total": len(issues), "unmitigated": len(unmitigated)}))
sys.exit(1 if unmitigated else 0)
PY
[ $? -ne 0 ] && fail "mythril unmitigated high/critical issues — see artifacts/mythril-summary.json"

exit $stage_fail
