#!/usr/bin/env bash
# Stage 8 — access control & privilege matrix validation (RELEASE tier)
# Gate: zero unauthorized callers on privileged state transitions;
#       100% matrix<->test concordance.
set -uo pipefail
ENG="${ENGAGEMENT_DIR:-/engagement}"
TARGET="$ENG/target"; ART="$ENG/artifacts"
mkdir -p "$ART"
stage_fail=0
note() { echo "[stage-08] $*"; }
fail() { echo "[stage-08] FAIL: $*" | tee "$ART/stage-08-failures.txt" >&2; exit 1; }

cd "$TARGET" || { fail "target/ missing"; exit 1; }

forge build --build-info --force || fail "forge build failed"

note "extracting access matrix from ASTs"
python3 /pipeline/tools/access-matrix/access_matrix.py \
  --build-info "$TARGET/out/build-info" \
  --out-json "$ART/ACCESS_CONTROL_MATRIX.json" \
  --out-md "$ART/ACCESS_CONTROL_MATRIX.md" \
  --harness "$TARGET/test/access-control/GeneratedAccessMatrix.t.sol" \
  || fail "access matrix extraction failed"

note "running access-control assertion suite (declared + generated + manual)"
forge test --match-path 'test/access-control/*' -vv --json \
  > "$ART/access-control-results.ndjson" 2> "$ART/access-control-stderr.txt" \
  || fail "access-control tests failed (or harness unwired: check test/access-control/GeneratedAccessMatrix.t.sol)"

python3 - "$ART" <<'PY' || fail "matrix/test concordance check failed"
import json, pathlib, sys
art = pathlib.Path(sys.argv[1])
matrix = json.loads((art / "ACCESS_CONTROL_MATRIX.json").read_text())
rows = [r for r in matrix["rows"] if r["state_changing"]]
harness = pathlib.Path("/engagement/target/test/access-control/GeneratedAccessMatrix.t.sol")
manual = pathlib.Path("/engagement/target/test/access-control/ManualAccessMatrix.t.sol")
h = harness.read_text() if harness.exists() else ""
m = manual.read_text() if manual.exists() else ""
uncovered = []
for r in rows:
    fname = f"matrix_{r['contract']}_{r['function']}".replace("[", "_").replace("]", "")
    if f"function {fname}" not in h and f"function {fname}" not in m:
        uncovered.append(f"{r['contract']}.{r['function_signature']}")
summary = {"rows": len(rows), "uncovered": uncovered,
           "concordant": not uncovered}
(art / "access-concordance.json").write_text(json.dumps(summary, indent=2))
print(json.dumps(summary))
sys.exit(1 if uncovered else 0)
PY

exit $stage_fail
