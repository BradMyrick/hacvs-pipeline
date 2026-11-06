#!/usr/bin/env python3
"""Stage 12 gate — zero failed Kontrol proofs; coverage-enforced non-vacuity."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_lib"))
from gate_common import parse_args, load_json, require_files, go  # noqa: E402

eng = parse_args()
failures = require_files(eng, [
    "artifacts/kontrol-proofs.json",
    "artifacts/kontrol-coverage.json",
])
evidence = ["artifacts/kontrol-proofs.json", "artifacts/kontrol-coverage.json",
            "artifacts/kontrol-prove.log", "artifacts/kontrol-build.log"]
details = {}

proofs_path = eng / "artifacts" / "kontrol-proofs.json"
if proofs_path.exists():
    try:
        proofs = load_json(proofs_path)
    except Exception as exc:  # noqa: BLE001
        failures.append(f"kontrol-proofs.json unparseable: {exc}")
        proofs = {}
    details = {k: proofs.get(k) for k in ("total", "failed_count", "coverage_pct")}
    if proofs.get("total", 0) == 0:
        failures.append("zero Kontrol proofs ran (check kontrol_match in engagement.json "
                        "and that test/proofs/* exist)")
    if proofs.get("failed_count", 1) != 0:
        failures.append(f"{proofs.get('failed_count')} failed proofs: "
                        + ", ".join(proofs.get("failed", [])[:5]))
    cov = proofs.get("coverage_pct")
    vac = eng / "review" / "KONTROL_VACUITY.md"
    vac_text = vac.read_text() if vac.exists() else ""
    if cov is None:
        # no CLI coverage metric in this Kontrol: non-vacuity must be carried by
        # an explicit acknowledgment in the vacuity doc
        if "coverage: tool-unavailable" not in vac_text:
            failures.append(
                "no CLI coverage metric (kontrol 1.0.255); vacuity doc must "
                "state 'coverage: tool-unavailable' with per-rule rationale")
    elif cov < proofs.get("coverage_min_pct", 90):
        failures.append(f"node/rule coverage {cov}% below floor {proofs.get('coverage_min_pct')}% "
                        "(non-vacuity enforcement)")

vac = eng / "review" / "KONTROL_VACUITY.md"
if vac.exists():
    text = vac.read_text()
    details["vacuity_doc"] = "present"
    proof_names = (proofs.get("passed") or []) + (proofs.get("failed") or [])
    missing = [p for p in proof_names if p not in text]
    if missing:
        failures.append(
            "KONTROL_VACUITY.md lacks rationale for proofs: " + ", ".join(missing[:5])
        )
    evidence.append("review/KONTROL_VACUITY.md")
else:
    failures.append("review/KONTROL_VACUITY.md missing (non-vacuity documentation)")

go(failures, evidence, details)
