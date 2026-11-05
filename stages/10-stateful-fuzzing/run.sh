#!/usr/bin/env bash
# Stage 10 — property-based testing & stateful fuzzing (RELEASE tier, long-running)
# Gate: zero invariant violations across all active engines at target runs/depth.
set -uo pipefail
umask 0000  # container-created evidence stays host-manageable (runners execute as root)
ENG="${ENGAGEMENT_DIR:-/engagement}"
TARGET="$ENG/target"; ART="$ENG/artifacts"
mkdir -p "$ART"
stage_fail=0
note() { echo "[stage-10] $*"; }
fail() { echo "[stage-10] FAIL: $*" | tee "$ART/stage-10-failures.txt" >&2; exit 1; }

cd "$TARGET" || { fail "target/ missing"; exit 1; }

ENGINES="$(python3 -c "import json;print(' '.join(json.load(open('$ENG/engagement.json'))['applicability'].get('fuzz_engines',['forge','echidna','medusa'])))")"
INV_RUNS="${HACVSP_INV_RUNS:-100000}"
INV_DEPTH="${HACVSP_INV_DEPTH:-500}"
note "engines: ${ENGINES} | invariant runs=${INV_RUNS} depth=${INV_DEPTH}"

if [[ "$ENGINES" == *forge* ]]; then
  note "forge invariant engine"
  forge test --match-contract Invariant \
    --fuzz-runs "$INV_RUNS" --depth "$INV_DEPTH" \
    --json > "$ART/invariant-results.ndjson" 2> "$ART/invariant-stderr.txt" \
    || fail "forge invariant run failed (violations or crash — see invariant-results.ndjson)"
else
  note "forge invariants NOT in declared engine set (recorded)"
fi

if [[ "$ENGINES" == *echidna* ]]; then
  note "echidna engine"
  ECH_TARGET="$(python3 -c "import json;print(json.load(open('$ENG/engagement.json'))['applicability'].get('echidna_contract',''))")"
  ECH_CFG="fuzz/echidna.yaml"
  [ -f "$ECH_CFG" ] || { 
    note "no fuzz/echidna.yaml in target — using scaffold default"
    ECH_CFG="/pipeline/templates/workstation/fuzz/echidna.yaml"
  }
  if [ -n "$ECH_TARGET" ]; then
    echidna . --contract "$ECH_TARGET" --config "$ECH_CFG" --format json \
      > "$ART/echidna-results.json" 2> "$ART/echidna-stderr.txt" \
      || fail "echidna run failed — see echidna-results.json"
  else
    note "no echidna_contract declared in engagement.json — engine skipped (recorded)"
  fi
fi

if [[ "$ENGINES" == *medusa* ]]; then
  note "medusa engine"
  MED_CFG="fuzz/medusa.json"
  [ -f "$MED_CFG" ] || {
    note "no fuzz/medusa.json in target — using scaffold default"
    MED_CFG="/pipeline/templates/workstation/fuzz/medusa.json"
  }
  medusa fuzz --config "$MED_CFG" > "$ART/medusa-results.json" 2> "$ART/medusa-stderr.txt" \
    || fail "medusa run failed — see medusa-stderr.txt"
fi

# Consolidate
python3 - "$ART" "$ENGINES" <<'PY' || fail "fuzz consolidation failed"
import json, pathlib, sys
art, engines = pathlib.Path(sys.argv[1]), sys.argv[2].split()
summary = {"engines": {}, "violations": []}
# forge invariants
if "forge" in engines:
    last = None
    for line in (art / "invariant-results.ndjson").read_text().splitlines():
        try: last = json.loads(line)
        except Exception: continue
    if last is None:
        summary["engines"]["forge"] = {"present": False}
    else:
        failed = [t for t in (last.get("test_results") or []) if t.get("status") != "Success"]
        summary["engines"]["forge"] = {"present": True, "failed": len(failed)}
        summary["violations"] += [f"forge:{t.get('contract')}::{t.get('test')}" for t in failed]
# echidna
if "echidna" in engines:
    f = art / "echidna-results.json"
    if f.exists() and f.stat().st_size:
        try:
            data = json.loads(f.read_text())
            bad = [t for t in (data.get("tests") or [])
                   if t.get("status") not in ("passing", "fuzzing", "passed", None)]
            summary["engines"]["echidna"] = {"present": True, "failed": len(bad)}
            summary["violations"] += [f"echidna:{t.get('name')}" for t in bad]
        except Exception as exc:
            summary["engines"]["echidna"] = {"present": True, "parse_error": str(exc)}
            summary["violations"].append("echidna:results-unparseable")
    else:
        summary["engines"]["echidna"] = {"present": False}
# medusa
if "medusa" in engines:
    f = art / "medusa-results.json"
    raw = f.read_text() if f.exists() and f.stat().st_size else ""
    present = bool(raw)
    failed_flags = [s for s in ("\"FAILED\"", "falsified", "FAILED_ON_CALL", "ARITHMETIC_UNDERFLOW")
                    if s in raw]
    summary["engines"]["medusa"] = {"present": present,
                                    "failure_signals": failed_flags}
    if failed_flags:
        summary["violations"] += [f"medusa:{s}" for s in failed_flags]
(art / "fuzzing-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps(summary, indent=2))
sys.exit(1 if summary["violations"] else 0)
PY

exit $stage_fail
