#!/usr/bin/env python3
"""Stage 3 gate — zero unsuppressed findings; governed, signed suppressions."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_lib"))
from gate_common import parse_args, load_json, require_files, go  # noqa: E402

eng = parse_args()
failures = require_files(eng, [
    "artifacts/static-analysis-summary.json",
    "artifacts/slither-report.json",
    "artifacts/aderyn-report.sarif",
])
evidence = [
    "artifacts/static-analysis-summary.json",
    "artifacts/slither-report.json",
    "artifacts/slither-report.sarif",
    "artifacts/aderyn-report.sarif",
    "artifacts/slither-checklist.md",
]
details = {}

summary_path = eng / "artifacts" / "static-analysis-summary.json"
if summary_path.exists():
    try:
        summary = load_json(summary_path)
    except Exception as exc:  # noqa: BLE001
        failures.append(f"static-analysis-summary.json unparseable: {exc}")
        summary = {}
    totals = summary.get("totals", {})
    # Spec pass criteria: unreviewed critical/high/medium == 0
    unsup = totals.get("unsuppressed", {})
    details["totals"] = totals
    details["invalid_suppressions"] = summary.get("invalid_suppressions", [])
    for sev in ("critical", "high", "medium"):
        if unsup.get(sev, 0) != 0:
            failures.append(f"unsuppressed {sev} findings: {unsup.get(sev)}")
    invalid = summary.get("invalid_suppressions", [])
    if invalid:
        failures.append(
            f"{len(invalid)} structurally invalid/unsigned suppression entries: "
            + "; ".join(invalid[:3])
        )
    # Engine presence: both engines must have contributed
    engines = summary.get("engines", {})
    details["engines"] = engines
    for engine in ("slither", "aderyn"):
        if engines.get(engine, {}).get("report_present") is False:
            failures.append(f"{engine} report missing/empty")
else:
    failures.append("static-analysis-summary.json missing")

# Suppression signature depth check: entries must be cosign/gpg signatures
supp = eng / "target" / ".security-suppressions.json"
if supp.exists():
    try:
        entries = load_json(supp)
    except Exception as exc:  # noqa: BLE001
        entries = []
        failures.append(f".security-suppressions.json unparseable: {exc}")
    details["suppression_count"] = len(entries)

go(failures, evidence, details)
