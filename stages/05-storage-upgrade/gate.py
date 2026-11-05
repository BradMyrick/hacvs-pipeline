#!/usr/bin/env python3
"""Stage 5 gate — storage collision freedom + initializer protection."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_lib"))
from gate_common import parse_args, go  # noqa: E402

eng = parse_args()
failures: list[str] = []
evidence: list[str] = []
details: dict = {}

layouts = eng / "artifacts" / "storage-layouts-current"
if not layouts.exists() or not list(layouts.glob("*.json")):
    failures.append("no storage layouts extracted (artifacts/storage-layouts-current)")
else:
    details["layouts_extracted"] = [p.name for p in layouts.glob("*.json")]
    evidence.append("artifacts/storage-layouts-current/")

for diff in sorted((eng / "artifacts").glob("storage-layout-diff-*.json")):
    evidence.append(f"artifacts/{diff.name}")
    try:
        report = json.loads(diff.read_text())
    except Exception as exc:  # noqa: BLE001
        failures.append(f"{diff.name} unparseable: {exc}")
        continue
    if report.get("collisions"):
        failures.append(f"{diff.name}: {len(report['collisions'])} storage collisions")
    if report.get("gap_issues"):
        failures.append(f"{diff.name}: __gap integrity violated")
    if report.get("namespace_issues"):
        failures.append(f"{diff.name}: ERC-7201 namespace drift")

init = eng / "artifacts" / "initializer-check.json"
if init.exists():
    try:
        data = json.loads(init.read_text())
        details["initializer_checked"] = data.get("checked")
        if data.get("issues"):
            failures.extend(f"initializer: {i}" for i in data["issues"])
        evidence.append("artifacts/initializer-check.json")
    except Exception as exc:  # noqa: BLE001
        failures.append(f"initializer-check.json unparseable: {exc}")
else:
    failures.append("initializer-check.json missing")

sel = eng / "artifacts" / "diamond-selector-check.json"
if sel.exists():
    try:
        data = json.loads(sel.read_text())
        details["duplicate_signatures"] = len(data.get("duplicates", []))
        if data.get("duplicates"):
            failures.extend(f"selector: {d}" for d in data["duplicates"][:5])
        evidence.append("artifacts/diamond-selector-check.json")
    except Exception as exc:  # noqa: BLE001
        failures.append(f"diamond-selector-check.json unparseable: {exc}")
else:
    failures.append("diamond-selector-check.json missing")

go(failures, evidence, details)
