#!/usr/bin/env python3
"""Stage 4 gate — zero missing events; correct indexing."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_lib"))
from gate_common import parse_args, load_json, require_files, go  # noqa: E402

eng = parse_args()
failures = require_files(eng, ["artifacts/EVENT_EMISSION_AUDIT.json"])
evidence = ["artifacts/EVENT_EMISSION_AUDIT.json"]
details = {}

audit_path = eng / "artifacts" / "EVENT_EMISSION_AUDIT.json"
if audit_path.exists():
    try:
        audit = load_json(audit_path)
    except Exception as exc:  # noqa: BLE001
        failures.append(f"EVENT_EMISSION_AUDIT.json unparseable: {exc}")
        audit = {}
    summary = audit.get("summary", {})
    details = summary
    # Spec gate: zero missing events on state-modifying functions.
    missing = audit.get("missing_events", [])
    if summary.get("missing_event_failures", 1) != 0:
        failures.append(
            f"{summary.get('missing_event_failures')} function(s) mutate critical "
            f"state without emitting: "
            + "; ".join(
                f"{m.get('contract')}.{m.get('function')} ({m.get('writes')})"
                for m in missing[:4]
            )
        )
    idx = audit.get("indexing_warnings", [])
    if summary.get("indexing_warnings", 1) != 0:
        failures.append(
            f"{summary.get('indexing_warnings')} indexing warnings "
            "(actor/target identifiers must be indexed topics)"
        )
    for m in missing:
        evidence.append(
            f"missing-event: {m.get('contract')}.{m.get('function')}"
        )
else:
    failures.append("EVENT_EMISSION_AUDIT.json missing")

go(failures, evidence, details)
