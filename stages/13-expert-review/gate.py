#!/usr/bin/env python3
"""Stage 13 gate — signed expert approval certifying coverage & completeness."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_lib"))
from gate_common import parse_args, load_json, require_files, go  # noqa: E402

eng = parse_args()
failures = require_files(eng, [
    "artifacts/expert-review-summary.json",
    "artifacts/suppression-ratification.json",
])
evidence = [
    "review/THREAT_MODEL.md", "review/SPEC_AUDIT.md",
    "review/MANUAL_REVIEW_SIGNOFF.md",
    "artifacts/suppression-ratification.json",
]
details = {}

p = eng / "artifacts" / "expert-review-summary.json"
if p.exists():
    try:
        s = load_json(p)
    except Exception as exc:  # noqa: BLE001
        s = {}
        failures.append(f"expert-review-summary.json unparseable: {exc}")
    details = s
    for name, present in (s.get("deliverables") or {}).items():
        if not present:
            failures.append(f"expert deliverable missing: {name}")
    if not s.get("signature_verified"):
        failures.append(
            "expert signature not cryptographically verified "
            "(cosign verify-blob against KODR_PUBKEY)"
        )

rat = eng / "artifacts" / "suppression-ratification.json"
if rat.exists():
    try:
        r = load_json(rat)
        details["unratified_suppressions"] = r.get("unratified_prefixes", [])
        if r.get("unratified_prefixes"):
            failures.append(
                f"{len(r['unratified_prefixes'])} suppressions not ratified in signoff: "
                + ", ".join(r["unratified_prefixes"][:5])
            )
    except Exception as exc:  # noqa: BLE001
        failures.append(f"suppression-ratification.json unparseable: {exc}")

go(failures, evidence, details)
