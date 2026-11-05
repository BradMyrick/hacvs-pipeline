"""SPEC.json ground truth: loading, stage tables, and gate derivation.

The spec audits the pipeline: `hacvsp verify` re-derives everything from
SPEC.json and fails closed if the implementation drifts from the spec.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "SPEC.json"
STAGES_DIR = REPO_ROOT / "stages"

_CACHE: dict | None = None


def load_spec() -> dict:
    global _CACHE
    if _CACHE is None:
        _CACHE = json.loads(SPEC_PATH.read_text())
    return _CACHE


def stages() -> list[dict]:
    return sorted(load_spec()["stages"], key=lambda s: s["order"])


def stage_by_order(n: int) -> dict:
    for s in stages():
        if s["order"] == n:
            return s
    raise KeyError(f"stage {n} not in SPEC.json")


def stage_dir(n: int) -> Path:
    matches = sorted(STAGES_DIR.glob(f"{n:02d}-*"))
    if not matches:
        raise FileNotFoundError(f"stages/{n:02d}-* not found")
    return matches[0]


def cadence_stages(cadence: str) -> list[int]:
    return list(load_spec()["cadences"][cadence])


def spec_artifacts(stage: dict) -> list[str]:
    reqs = stage.get("requirements", {})
    return list(reqs.get("artifacts_output", []))


def derive_gates() -> list[dict]:
    """Machine-checkable gate matrix derived from the spec."""
    out = []
    for s in stages():
        gate = s.get("gate", {})
        out.append(
            {
                "order": s["order"],
                "stage": s["stage"],
                "cadence": s["cadence"],
                "decision": gate.get("decision"),
                "criteria": gate.get("criteria"),
                "artifacts_expected": spec_artifacts(s),
            }
        )
    return out


# Map: spec pinned tool name -> pins.env variable that must be frozen.
TOOL_PIN_VARS = {
    "solc": ["SOLC_VERSION", "SOLC_SHA256"],
    "foundry": ["FOUNDRY_VERSION"],
    "slither": ["SLITHER_VERSION"],
    "aderyn": ["ADERYN_VERSION"],
    "echidna": ["ECHIDNA_VERSION", "ECHIDNA_SHA256"],
    "medusa": ["MEDUSA_VERSION", "MEDUSA_SHA256"],
    "mythril": ["MYTHRIL_VERSION"],
    "halmos": ["HALMOS_VERSION"],
    "kontrol": ["BASE_KONTROL_TAG", "BASE_KONTROL_DIGEST"],
    "scribble": ["SCRIBBLE_VERSION"],
    "gambit": ["GAMBIT_VERSION"],
    "cosign": ["COSIGN_VERSION", "COSIGN_SHA256"],
    "syft": ["SYFT_VERSION", "SYFT_SHA256"],
    "trivy": ["TRIVY_VERSION", "TRIVY_SHA256"],
    # aiwrangler_mcp runs as an MCP server driven by the agent — no docker pin.
}


def load_pins() -> dict[str, str]:
    pins: dict[str, str] = {}
    pins_path = REPO_ROOT / "docker" / "pins.env"
    for line in pins_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        pins[k] = v
    return pins


def stage_slug(n: int) -> str:
    """e.g. 1 -> '01-dependency-hygiene' (the directory name)."""
    d = stage_dir(n)
    return d.name


def verify_concordance() -> list[str]:
    """Cross-check implementation against SPEC.json. Returns failure list."""
    failures: list[str] = []
    spec = load_spec()

    if spec.get("version") != SPEC_VERSION_MARKER():
        failures.append(f"SPEC.json version {spec.get('version')!r} unexpected")

    compose = (REPO_ROOT / "docker" / "compose.yaml").read_text()
    all_orders = [s["order"] for s in stages()]

    for s in stages():
        n = s["order"]
        try:
            d = stage_dir(n)
        except FileNotFoundError:
            failures.append(f"stage {n}: missing directory stages/{n:02d}-*")
            continue
        for fname in ("run.sh", "gate.py", "RUNBOOK.md"):
            if not (d / fname).exists():
                failures.append(f"stage {n}: missing {d.name}/{fname}")
        if f"stage-{n:02d}" not in compose:
            failures.append(f"stage {n}: no stage-{n:02d} service in docker/compose.yaml")
        gate_src = (d / "gate.py").read_text() if (d / "gate.py").exists() else ""
        run_src = (d / "run.sh").read_text() if (d / "run.sh").exists() else ""
        sources = gate_src + "\n" + run_src
        for art in spec_artifacts(s):
            if "*" in art:
                # glob artifacts are produced by the runner; concordance means
                # the stage references the glob's directory (e.g. out/build-info)
                token = art.rsplit("/", 1)[0]
            else:
                token = art.split("/", 1)[-1] if "/" in art else art
            if token not in sources:
                failures.append(
                    f"stage {n}: spec artifact '{art}' not referenced by gate.py/run.sh"
                )

    for cadence, orders in spec["cadences"].items():
        for n in orders:
            if n not in all_orders:
                failures.append(f"cadence {cadence}: stage {n} missing from stages list")

    pins = load_pins()
    pinned = spec["toolchain_environment"]["pinned_tool_versions"]
    for tool, varnames in TOOL_PIN_VARS.items():
        if tool not in pinned:
            failures.append(f"pinned tool {tool!r} missing from SPEC.json")
            continue
        for var in varnames:
            if var not in pins:
                failures.append(f"pins.env missing {var} (tool {tool})")

    if "aiwrangler_mcp" not in pinned:
        failures.append("SPEC.json must list aiwrangler_mcp (MCP server, not CLI)")

    return failures


def SPEC_VERSION_MARKER() -> str:
    return "v0.1.0"
