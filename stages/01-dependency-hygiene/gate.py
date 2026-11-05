#!/usr/bin/env python3
"""Stage 1 gate — supply chain & dependency hygiene."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_lib"))
from gate_common import parse_args, load_json, require_files, go  # noqa: E402

eng = parse_args()
failures = require_files(eng, [
    "artifacts/sbom.cyclonedx.json",
    "artifacts/dependency-checksums.sha256",
    "artifacts/dependency-summary.json",
])
evidence = [
    "artifacts/sbom.cyclonedx.json",
    "artifacts/dependency-checksums.sha256",
    "artifacts/dependency-summary.json",
]

summary_path = eng / "artifacts" / "dependency-summary.json"
details = {}
if summary_path.exists():
    try:
        summary = load_json(summary_path)
    except Exception as exc:  # noqa: BLE001
        failures.append(f"dependency-summary.json unparseable: {exc}")
        summary = {}
    details = {
        "submodule_issues": summary.get("submodule_issues"),
        "floating_dependencies": summary.get("floating_dependencies"),
        "trivy": summary.get("trivy"),
        "suppressed_cves": summary.get("suppressed", []),
    }
    if summary.get("submodule_issues", 1) != 0:
        failures.append("submodules not pinned/initialized (see submodule-status)")
    if summary.get("floating_dependencies", 1) != 0:
        failures.append("floating dependencies detected (missing lockfiles)")
    t = summary.get("trivy", {})
    # Spec gate: zero unreviewed CVEs in third-party libraries.
    if t.get("critical", 1) != 0 or t.get("high", 1) != 0 or t.get("medium", 1) != 0:
        failures.append(
            f"unreviewed CVEs: critical={t.get('critical')} high={t.get('high')} "
            f"medium={t.get('medium')} (suppress via signed .security-suppressions.json "
            "entries with tool=trivy)"
        )
    if "trivy_error" in summary:
        failures.append(f"trivy parse error: {summary['trivy_error']}")
else:
    failures.append("dependency-summary.json missing")

go(failures, evidence, details)
