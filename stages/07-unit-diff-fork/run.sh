#!/usr/bin/env bash
# Stage 7 — concrete unit, differential, and fork testing (PR tier)
# Gate: all tests pass; coverage >= 95% line & branch with approved exceptions.
set -uo pipefail
ENG="${ENGAGEMENT_DIR:-/engagement}"
TARGET="$ENG/target"; ART="$ENG/artifacts"
mkdir -p "$ART"
stage_fail=0
note() { echo "[stage-07] $*"; }
fail() { echo "[stage-07] FAIL: $*" | tee "$ART/stage-07-failures.txt" >&2; stage_fail=1; }

cd "$TARGET" || { fail "target/ missing"; exit 1; }

FORK_REQUIRED="$(python3 -c "import json;print(json.load(open('$ENG/engagement.json'))['applicability'].get('fork_tests_required', True))")"

# --- Full unit suite with gas report
note "forge test (full suite, gas report)"
forge test -vvv --gas-report --summary > "$ART/unit-results.txt" 2>&1 \
  || fail "unit tests failed — see artifacts/unit-results.txt"

# --- Differential suite
if compgen -G "test/differential/*" > /dev/null; then
  note "differential suite"
  forge test --match-path 'test/differential/*' -vv --json \
    > "$ART/differential-results.ndjson" 2>/dev/null \
    || fail "differential tests failed"
else
  note "no differential tests present (recorded — required for math-heavy core contracts; review at Stage 13)"
fi

# --- Fork suite (mainnet fork via RPC)
if compgen -G "test/fork/*" > /dev/null; then
  if [ -z "${HACVSP_FORK_RPC:-}" ]; then
    if [ "$FORK_REQUIRED" = "True" ]; then
      fail "test/fork/ exists and fork_tests_required=true but HACVSP_FORK_RPC is unset (engagement .env)"
    else
      note "fork tests present but not required and no RPC — skipped (recorded)"
    fi
  else
    note "fork suite (anvil fork via HACVSP_FORK_RPC)"
    forge test --match-path 'test/fork/*' -vv --fork-url "$HACVSP_FORK_RPC" --json \
      > "$ART/fork-results.ndjson" 2>/dev/null \
      || fail "fork tests failed"
  fi
fi

# --- Coverage
note "forge coverage"
forge coverage --match-path 'test/*' --report lcov --report-file "$ART/coverage.lcov" \
  > "$ART/coverage-stdout.txt" 2>&1 || fail "forge coverage failed"

python3 - "$ART" <<'PY' || fail "coverage summary failed"
import json, pathlib, re, sys
art = pathlib.Path(sys.argv[1])
lcov = art / "coverage.lcov"
lf = lh = brf = brh = 0
cur_file = None
per_file = {}
for line in lcov.read_text().splitlines():
    if line.startswith("SF:"):
        cur_file = line[3:].strip()
        per_file[cur_file] = {"LF": 0, "LH": 0, "BRF": 0, "BRH": 0}
    elif line == "end_of_record":
        cur_file = None
    elif cur_file:
        m = re.match(r"^(LF|LH|BRF|BRH):(\d+)", line)
        if m:
            key, val = m.group(1), int(m.group(2))
            per_file[cur_file][key] += val
            if key in ("LF",): lf += val
            if key in ("LH",): lh += val
            if key in ("BRF",): brf += val
            if key in ("BRH",): brh += val
line_pct = round(100.0 * lh / lf, 2) if lf else 0.0
branch_pct = round(100.0 * brh / brf, 2) if brf else 0.0
summary = {
    "line_pct": line_pct, "branch_pct": branch_pct,
    "line_hit": lh, "line_found": lf,
    "branch_hit": brh, "branch_found": brf,
    "thresholds": {"line": 95.0, "branch": 95.0},
    "below_threshold": line_pct < 95.0 or branch_pct < 95.0,
    "per_file": {k: v for k, v in per_file.items() if v["LF"] > 0},
}
(art / "coverage-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps({k: summary[k] for k in ("line_pct", "branch_pct", "below_threshold")}))
PY

note "unit/differential/fork suites complete; coverage summarized"

exit $stage_fail
