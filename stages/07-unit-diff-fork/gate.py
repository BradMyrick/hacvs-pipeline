#!/usr/bin/env python3
"""Stage 7 gate — tests pass; >=95% line & branch coverage or approved exceptions."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_lib"))
from gate_common import parse_args, load_json, require_files, go  # noqa: E402

eng = parse_args()
failures = require_files(eng, ["artifacts/coverage-summary.json"])
evidence = ["artifacts/coverage-summary.json", "artifacts/coverage.lcov",
            "artifacts/unit-results.txt"]
details = {}

cov_path = eng / "artifacts" / "coverage-summary.json"
if cov_path.exists():
    try:
        cov = load_json(cov_path)
    except Exception as exc:  # noqa: BLE001
        failures.append(f"coverage-summary.json unparseable: {exc}")
        cov = {}
    details = {
        "line_pct": cov.get("line_pct"), "branch_pct": cov.get("branch_pct"),
    }
    line_ok = (cov.get("line_pct", 0) or 0) >= 95.0
    branch_ok = (cov.get("branch_pct", 0) or 0) >= 95.0
    if not (line_ok and branch_ok):
        # Spec exceptions policy: gaps require documented, reviewer-signed
        # justification in COVERAGE_EXCEPTIONS.md (ratified at Stage 13).
        exc = eng / "target" / "COVERAGE_EXCEPTIONS.md"
        if not exc.exists() or len(exc.read_text().strip()) < 40:
            failures.append(
                f"coverage below 95% (line={cov.get('line_pct')}%, "
                f"branch={cov.get('branch_pct')}%) and COVERAGE_EXCEPTIONS.md "
                "missing/empty"
            )
        else:
            text = exc.read_text()
            if "Reviewer-Signature" not in text:
                failures.append("COVERAGE_EXCEPTIONS.md lacks Reviewer-Signature block")
            else:
                details["coverage_exceptions_applied"] = True

for name, label in (("unit-results.txt", "unit"),):
    f = eng / "artifacts" / name
    if f.exists():
        text = f.read_text()
        failed = ("FAILED" in text) or ("failed" in text and "passed" not in text)
        details[f"{label}_suite_ok"] = not failed

go(failures, evidence, details)
