#!/usr/bin/env python3
"""Stage 14 gate — complete, signed, drift-free assurance bundle."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_lib"))
from gate_common import parse_args, load_json, require_files, go  # noqa: E402

SPEC_BUNDLE = [
    "SECURITY_ASSURANCE.md",
    "artifacts/sbom.cyclonedx.json",
    "artifacts/ACCESS_CONTROL_MATRIX.json",
    "artifacts/EVENT_EMISSION_AUDIT.json",
    "artifacts/kontrol-proofs.json",
    "artifacts/mutation-report.json",
    "artifacts/mythril-results.json",
    "artifacts/provenance.intoto.jsonl",
    "signatures/bundle-attestation.sig",
]
MANDATORY_SECTIONS = [
    "Executive Summary & Target Commit",
    "Verification Methodology & Stage-by-Stage Results",
    "Active Suppressions & Exceptions Inventory",
    "Coverage Exceptions Audit",
    "On-Chain Deployment & Bytecode Verification Mapping",
]

eng = parse_args()
failures = []
evidence = []
details = {}

for rel in SPEC_BUNDLE:
    if (eng / rel).exists():
        evidence.append(rel)
    else:
        failures.append(f"published bundle missing: {rel}")

sa = eng / "SECURITY_ASSURANCE.md"
if sa.exists():
    text = sa.read_text()
    details["mandatory_sections"] = {}
    for sec in MANDATORY_SECTIONS:
        present = sec.lower() in text.lower()
        details["mandatory_sections"][sec] = present
        if not present:
            failures.append(f"SECURITY_ASSURANCE.md missing section: {sec}")
else:
    failures.append("SECURITY_ASSURANCE.md missing")

manifest = eng / "artifacts" / "bundle-manifest.json"
if manifest.exists():
    try:
        m = load_json(manifest)
        details["bundle_digest"] = m.get("bundle_digest")
        details["manifest_missing"] = m.get("missing", [])
        if m.get("missing"):
            failures.append(f"bundle manifest reports missing: {m['missing']}")
    except Exception as exc:  # noqa: BLE001
        failures.append(f"bundle-manifest.json unparseable: {exc}")
else:
    failures.append("bundle-manifest.json missing")

sig = eng / "signatures" / "bundle-attestation.sig"
if not sig.exists():
    # allowed only in explicit dry-run mode — recorded, still surfaced
    details["signature"] = "absent (dry-run?)"
else:
    details["signature"] = "present"

go(failures, evidence, details)
