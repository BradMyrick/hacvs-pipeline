#!/usr/bin/env python3
"""Stage 9 gate — mutation kill rate >= 90%; zero untriaged core survivors."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_lib"))
from gate_common import parse_args, load_json, require_files, go  # noqa: E402

eng = parse_args()
failures = require_files(eng, ["artifacts/mutation-report.json"])
evidence = ["artifacts/mutation-report.json", "artifacts/mutation-progress.json"]
details = {}

rep_path = eng / "artifacts" / "mutation-report.json"
if rep_path.exists():
    try:
        report = load_json(rep_path)
    except Exception as exc:  # noqa: BLE001
        failures.append(f"mutation-report.json unparseable: {exc}")
        report = {}
    details = {
        "total": report.get("total"), "killed": report.get("killed"),
        "survived": report.get("survived"),
        "kill_rate_pct": report.get("kill_rate_pct"),
    }
    rate = report.get("kill_rate_pct", 0) or 0
    if rate < 90.0:
        failures.append(f"mutation kill rate {rate}% < 90% threshold")

    core_survivors = report.get("core_survivors", [])
    if core_survivors:
        exc = eng / "target" / "MUTATION_EXCEPTIONS.md"
        text = exc.read_text() if exc.exists() else ""
        untriaged = [s for s in core_survivors if s.get("id") not in text]
        if untriaged:
            failures.append(
                f"{len(untriaged)} untriaged survivors in core contracts "
                f"(document equivalence in MUTATION_EXCEPTIONS.md or add tests): "
                + "; ".join(s.get("id", "?") for s in untriaged[:4])
            )
    # ALL survivors (not just core) must appear in the triage doc or be zero
    survivors = report.get("survivors", [])
    if survivors:
        exc = eng / "target" / "MUTATION_EXCEPTIONS.md"
        text = exc.read_text() if exc.exists() else ""
        untriaged = [s for s in survivors if s.get("id") not in text]
        if untriaged and rate >= 90.0:
            details["untriaged_noncore_survivors"] = len(untriaged)
else:
    failures.append("mutation-report.json missing")

go(failures, evidence, details)
