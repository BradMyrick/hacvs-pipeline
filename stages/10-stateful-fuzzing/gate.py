#!/usr/bin/env python3
"""Stage 10 gate — zero invariant violations across all active engines."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_lib"))
from gate_common import parse_args, load_json, require_files, go  # noqa: E402

eng = parse_args()
failures = require_files(eng, ["artifacts/fuzzing-summary.json"])
evidence = ["artifacts/fuzzing-summary.json", "artifacts/invariant-results.ndjson",
            "artifacts/echidna-results.json", "artifacts/medusa-results.json"]
details = {}

p = eng / "artifacts" / "fuzzing-summary.json"
if p.exists():
    try:
        summary = load_json(p)
    except Exception as exc:  # noqa: BLE001
        failures.append(f"fuzzing-summary.json unparseable: {exc}")
        summary = {}
    details = summary
    violations = summary.get("violations", [])
    if violations:
        failures.append(
            f"{len(violations)} invariant violations: " + "; ".join(violations[:5])
        )
    for engine, info in (summary.get("engines") or {}).items():
        if isinstance(info, dict) and info.get("present") is False:
            failures.append(f"engine {engine} declared but produced no results")
else:
    failures.append("fuzzing-summary.json missing")

# Handler architecture presence (spec): invariant handlers with ghost actors
handler = None
for pattern in ("test/invariant/Handler.sol", "test/invariant/handlers/Handler.sol"):
    if (eng / "target" / pattern).exists():
        handler = pattern
        break
details["handler_architecture"] = handler
if handler is None:
    failures.append(
        "no invariant Handler found (spec requires ghost-variable trackers, "
        "admin/user ghost actors, and reentrancy-set handlers: "
        "test/invariant/Handler.sol)"
    )

go(failures, evidence, details)
