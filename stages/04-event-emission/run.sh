#!/usr/bin/env bash
# Stage 4 — event completeness & indexing verification (PR tier)
# Gate: zero missing events on critical state mutations; identifiers indexed.
set -uo pipefail
ENG="${ENGAGEMENT_DIR:-/engagement}"
TARGET="$ENG/target"; ART="$ENG/artifacts"
mkdir -p "$ART"
stage_fail=0
note() { echo "[stage-04] $*"; }
fail() { echo "[stage-04] FAIL: $*" | tee "$ART/stage-04-failures.txt" >&2; exit 1; }

cd "$TARGET" || { fail "target/ missing"; exit 1; }

note "building fresh build-info for AST extraction (always — stale ASTs are false evidence)"
forge build --build-info --force || fail "forge build for AST failed"

note "extracting mutation graph + event emission audit"
python3 /pipeline/tools/event-audit/event_audit.py \
  --build-info "$TARGET/out/build-info" \
  --suppressions .security-suppressions.json \
  --out "$ART/EVENT_EMISSION_AUDIT.json" \
  || fail "event audit engine failed"

note "slither cross-check (event detectors recorded)"
slither . --json "$ART/slither-events.json" 2>/dev/null || true

note "summary:"
python3 -c "import json;d=json.load(open('$ART/EVENT_EMISSION_AUDIT.json'));print(json.dumps(d.get('summary',{}),indent=2))" 2>/dev/null || true

note "AiWrangler MCP note: the pipeline agent triages the mutation graph via the"
note "aiwrangler MCP server (0.1.5) and acknowledges human-severity findings;"
note "acknowledgement records are stored in review/aiwrangler-acks.json (stage 13)."

exit $stage_fail
