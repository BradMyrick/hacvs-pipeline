#!/usr/bin/env python3
"""Stage 6 gate — 100% pass on all applicable compliance suites."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_lib"))
from gate_common import parse_args, load_json, require_files, go  # noqa: E402

eng = parse_args()
failures = require_files(eng, ["artifacts/compliance-summary.json"])
evidence = ["artifacts/compliance-summary.json", "artifacts/compliance-results.ndjson"]
details = {}

p = eng / "artifacts" / "compliance-summary.json"
if p.exists():
    try:
        summary = load_json(p)
    except Exception as exc:  # noqa: BLE001
        failures.append(f"compliance-summary.json unparseable: {exc}")
        summary = {}
    details = summary
    if summary.get("skipped_reason"):
        details["skipped"] = True
    elif not summary.get("passed_all", False):
        fails = summary.get("failed_tests", [])
        failures.append(
            f"compliance failures: {summary.get('failed', '?')} "
            f"(first: {fails[:3]})"
        )

go(failures, evidence, details)
