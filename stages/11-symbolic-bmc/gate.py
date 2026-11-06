#!/usr/bin/env python3
"""Stage 11 gate — all bounded paths proven safe; zero bytecode vulns."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_lib"))
from gate_common import parse_args, load_json, require_files, go  # noqa: E402

eng = parse_args()
failures = require_files(eng, [
    "artifacts/symbolic-summary.json",
    "artifacts/mythril-summary.json",
    "artifacts/mythril-results.json",   # spec published bundle artifact
])
evidence = [
    "artifacts/smt-build.log",
    "artifacts/hevm-results.txt",
    "artifacts/symbolic-summary.json",
    "artifacts/mythril-results.json",
    "artifacts/mythril-summary.json",
]
details = {}

sym = eng / "artifacts" / "symbolic-summary.json"
if sym.exists():
    try:
        s = load_json(sym)
    except Exception as exc:  # noqa: BLE001
        s = {}
        failures.append(f"symbolic-summary.json unparseable: {exc}")
    details["smtchecker"] = s.get("smtchecker")
    details["hevm"] = s.get("hevm")
    if (s.get("smtchecker") or {}).get("counterexamples", 1) != 0:
        failures.append("SMTChecker reported counterexamples (bmc/chc)")
    hevm = s.get("hevm") or {}
    if hevm.get("failing", 0) != 0:
        failures.append(f"hevm failing proofs: {hevm.get('failing')}")
    if hevm.get("passing", 0) == 0:
        failures.append("hevm proved nothing (no proof corpus found — "
                        "add test/proofs/ with test_Proof_* properties)")

myth = eng / "artifacts" / "mythril-summary.json"
if myth.exists():
    try:
        m = load_json(myth)
    except Exception as exc:  # noqa: BLE001
        m = {}
        failures.append(f"mythril-summary.json unparseable: {exc}")
    details["mythril"] = {k: m.get(k) for k in ("total_issues",)}
    unmit = m.get("unmitigated_high_critical", [])
    details["mythril_unmitigated"] = len(unmit)
    if unmit:
        failures.append(
            f"mythril unmitigated high/critical: "
            + "; ".join(f"{u.get('swc')}:{u.get('title', '')[:40]}" for u in unmit[:4])
        )

go(failures, evidence, details)
