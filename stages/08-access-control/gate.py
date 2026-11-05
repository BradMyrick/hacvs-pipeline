#!/usr/bin/env python3
"""Stage 8 gate — exhaustive access matrix, enforced + concordant."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_lib"))
from gate_common import parse_args, load_json, require_files, go  # noqa: E402

eng = parse_args()
failures = require_files(eng, [
    "artifacts/ACCESS_CONTROL_MATRIX.json",
    "artifacts/ACCESS_CONTROL_MATRIX.md",
    "artifacts/access-concordance.json",
])
evidence = [
    "artifacts/ACCESS_CONTROL_MATRIX.json",
    "artifacts/ACCESS_CONTROL_MATRIX.md",
    "artifacts/access-control-results.ndjson",
]
details = {}

matrix = eng / "artifacts" / "ACCESS_CONTROL_MATRIX.json"
if matrix.exists():
    try:
        m = load_json(matrix)
    except Exception as exc:  # noqa: BLE001
        failures.append(f"matrix unparseable: {exc}")
        m = {}
    details = m.get("summary", {})
    if not m.get("rows"):
        failures.append("empty access matrix (no public/external entry points — suspicious)")
    public_mut = [r for r in m.get("rows", [])
                  if r.get("state_changing") and "PUBLIC" in (r.get("allowed_roles") or [])]
    details["public_state_changing_rows"] = len(public_mut)
    details["public_rows_for_expert_ratification"] = [
        f"{r['contract']}.{r['function_signature']}" for r in public_mut[:10]
    ]

conc = eng / "artifacts" / "access-concordance.json"
if conc.exists():
    try:
        c = load_json(conc)
        details["concordance"] = c
        if c.get("uncovered"):
            failures.append(
                f"{len(c['uncovered'])} matrix rows without executable tests: "
                + "; ".join(c["uncovered"][:4])
            )
    except Exception as exc:  # noqa: BLE001
        failures.append(f"access-concordance.json unparseable: {exc}")

res = eng / "artifacts" / "access-control-results.ndjson"
if res.exists():
    text = res.read_text()
    last = None
    for line in text.splitlines():
        try:
            last = json.loads(line)
        except Exception:
            continue
    if last is not None:
        failed = [t for t in (last.get("test_results") or [])
                  if t.get("status") != "Success"]
        details["tests_failed"] = len(failed)
        if failed:
            failures.append(
                f"{len(failed)} access-control tests failed: "
                + "; ".join(f"{t.get('contract')}::{t.get('test')}" for t in failed[:4])
            )

go(failures, evidence, details)
