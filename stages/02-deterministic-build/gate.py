#!/usr/bin/env python3
"""Stage 2 gate — deterministic build & bytecode size limits."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_lib"))
from gate_common import parse_args, load_json, require_files, go  # noqa: E402

eng = parse_args()
failures = require_files(eng, [
    "artifacts/bytecode-sizes.json",
    "artifacts/canonical-ast.json",
    "artifacts/reproducible-manifest.sha256",
])
evidence = [
    "artifacts/bytecode-sizes.json",
    "artifacts/canonical-ast.json",
    "artifacts/reproducible-manifest.sha256",
]
details = {}

diff_file = eng / "artifacts" / "reproducibility.diff"
if diff_file.exists():
    diff = diff_file.read_text().strip()
    details["reproducible"] = diff == ""
    if diff:
        failures.append("build not reproducible (artifacts/reproducibility.diff non-empty)")
    evidence.append("artifacts/reproducibility.diff")
else:
    failures.append("reproducibility.diff missing (did the runner complete?)")

sizes_path = eng / "artifacts" / "bytecode-sizes.json"
if sizes_path.exists():
    try:
        sizes = load_json(sizes_path)
    except Exception as exc:  # noqa: BLE001
        failures.append(f"bytecode-sizes.json unparseable: {exc}")
        sizes = {}
    viol = {k: v for k, v in sizes.items()
            if v.get("eip170_violation") or v.get("eip3860_violation")}
    details["contracts"] = len(sizes)
    details["size_violations"] = list(viol)
    if viol:
        failures.append(
            f"{len(viol)} contract(s) violate EIP-170/EIP-3860: {list(viol)[:5]}"
        )
else:
    failures.append("bytecode-sizes.json missing")

ast_path = eng / "artifacts" / "canonical-ast.json"
if ast_path.exists():
    try:
        n = len(load_json(ast_path).get("sources", {}))
        details["ast_sources"] = n
        if n == 0:
            failures.append("canonical-ast.json contains no sources")
    except Exception as exc:  # noqa: BLE001
        failures.append(f"canonical-ast.json unparseable: {exc}")

# Spec artifact 'out/build-info/*.json': the reproducible build evidence itself.
build_info = list((eng / "target").glob("out*/build-info/*.json"))
details["build_info_files"] = len(build_info)
if not build_info:
    failures.append("no build-info JSONs under target (out/build-info/*.json)")

go(failures, evidence, details)
