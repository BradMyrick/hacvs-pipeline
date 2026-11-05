#!/usr/bin/env bash
# Stage 6 — standards compliance & conformance suite (PR tier)
# Gate: 100% pass across all applicable reference standard compliance suites.
set -uo pipefail
ENG="${ENGAGEMENT_DIR:-/engagement}"
TARGET="$ENG/target"; ART="$ENG/artifacts"
mkdir -p "$ART"
stage_fail=0
note() { echo "[stage-06] $*"; }
fail() { echo "[stage-06] FAIL: $*" | tee "$ART/stage-06-failures.txt" >&2; exit 1; }

cd "$TARGET" || { fail "target/ missing"; exit 1; }

ERCS="$(python3 -c "import json;print('\n'.join(json.load(open('$ENG/engagement.json'))['applicability'].get('erc_standards',[])))")"
note "applicable standards: ${ERCS:-NONE DECLARED}"

if [ -z "$ERCS" ]; then
  fail "engagement.json applicability.erc_standards is empty — declare standards or 'NONE' explicitly at intake"
fi
if [ "$ERCS" = "NONE" ]; then
  note "no ERC standards applicable (explicitly declared) — recording and passing"
  printf '{"applicable": [], "passed": true, "skipped_reason": "declared NONE at intake"}\n' \
    > "$ART/compliance-summary.json"
  exit $stage_fail
fi

[ -d test/compliance ] || fail "test/compliance/ missing — scaffold provides canonical suites (templates/workstation)"

note "running compliance suite"
forge test --match-path 'test/compliance/*' -vv --json > "$ART/compliance-results.ndjson" 2> "$ART/compliance-stderr.txt" \
  || fail "forge test (compliance) failed — see artifacts/compliance-results.ndjson"

python3 - "$ART" "$ERCS" <<'PY' || fail "compliance summary evaluation failed"
import json, pathlib, sys
art, ercs = pathlib.Path(sys.argv[1]), sys.argv[2].splitlines()
summary = {"applicable": ercs, "total": 0, "passed": 0, "failed": 0,
           "failed_tests": [], "per_standard": {}}
last = None
for line in (art / "compliance-results.ndjson").read_text().splitlines():
    try:
        last = json.loads(line)
    except Exception:
        continue
if last is None:
    print("no forge --json output"); sys.exit(1)
for suite in (last.get("test_results") or []):
    summary["total"] += 1
    status = suite.get("status", "")
    if status == "Success":
        summary["passed"] += 1
    else:
        summary["failed"] += 1
        summary["failed_tests"].append(
            f"{suite.get('contract')}::{suite.get('test')}")
    for erc in ercs:
        if erc.lower().replace("-", "") in (suite.get("contract", "") + suite.get("test", "")).lower().replace("-", ""):
            bucket = summary["per_standard"].setdefault(erc, {"pass": 0, "fail": 0})
            bucket["pass" if status == "Success" else "fail"] += 1
missing = [erc for erc in ercs
           if erc not in summary["per_standard"]
           and erc.upper() not in ("NONE",)]
if missing:
    summary["failed"] += len(missing)
    summary["failed_tests"] += [f"NO SUITE FOR {m} (test/compliance/)" for m in missing]
summary["passed_all"] = summary["failed"] == 0 and summary["total"] > 0
(art / "compliance-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps({k: summary[k] for k in ("total", "passed", "failed", "passed_all")}))
sys.exit(0 if summary["passed_all"] else 1)
PY

exit $stage_fail
