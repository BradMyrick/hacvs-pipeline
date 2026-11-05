#!/usr/bin/env bash
# Stage 3 — spec linting & static analysis (PR tier)
# Gate: zero unsuppressed static warnings; 100% of suppression entries
#       cryptographically signed and structurally valid.
set -uo pipefail
ENG="${ENGAGEMENT_DIR:-/engagement}"
TARGET="$ENG/target"; ART="$ENG/artifacts"
mkdir -p "$ART"
stage_fail=0
note() { echo "[stage-03] $*"; }
fail() { echo "[stage-03] FAIL: $*" | tee -a "$ART/stage-03-failures.txt" >&2; stage_fail=1; }

cd "$TARGET" || { fail "target/ missing"; exit 1; }

note "tool versions"
slither --version 2>/dev/null | head -1 || fail "slither unavailable"
aderyn --version 2>/dev/null || note "aderyn version query non-zero (recorded)"
scribble --version 2>/dev/null || fail "scribble unavailable"

# --- Scribble: parse & validate inline specification annotations
note "scribble annotation instrumentation (spec parsing)"
mkdir -p /tmp/scribble-out
if scribble src --output-mode flat --output /tmp/scribble-out/instrumented.sol \
    > "$ART/scribble-output.txt" 2>&1; then
  note "scribble annotations parsed OK"
else
  rc=$?
  if grep -qi "no annotations" "$ART/scribble-output.txt" 2>/dev/null; then
    note "no scribble annotations found (recorded — not a gate failure)"
  else
    fail "scribble failed to parse annotations (rc=$rc) — see artifacts/scribble-output.txt"
  fi
fi
ANNOTATIONS=$(grep -c "/// #if" -r src 2>/dev/null | awk -F: '{s+=$2} END {print s+0}')
note "annotation directives found in src/: ${ANNOTATIONS}"

# --- Slither (JSON + SARIF + triage checklist)
note "slither analysis"
slither . \
  --json "$ART/slither-report.json" \
  --sarif "$ART/slither-report.sarif" \
  --checklist > "$ART/slither-checklist.md" 2> "$ART/slither-stderr.txt" \
  || note "slither exited non-zero (findings present or config error — aggregator will judge)"

# --- Aderyn (SARIF)
note "aderyn analysis"
aderyn . --output "$ART/aderyn-report.sarif" > "$ART/aderyn-stdout.txt" 2>&1 \
  || fail "aderyn failed — see artifacts/aderyn-stdout.txt"

# --- Normalize + suppression governance
note "SARIF aggregation + suppression gating"
python3 /pipeline/tools/sarif-aggregator/sarif_aggregator.py \
  --slither-json "$ART/slither-report.json" \
  --sarif "$ART/aderyn-report.sarif" \
  --suppressions .security-suppressions.json \
  --out "$ART/static-analysis-summary.json" \
  || fail "sarif aggregator failed"

note "summary:"
python3 -c "import json;d=json.load(open('$ART/static-analysis-summary.json'));print(json.dumps({k:d[k] for k in ('totals','invalid_suppressions') if k in d},indent=2))" 2>/dev/null || true

exit $stage_fail
