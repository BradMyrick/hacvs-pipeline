"""Docker orchestration + fail-closed doctor.

Every stage executes via `docker compose run --rm stage-NN` with the
engagement mounted read-write and the pipeline mounted read-only. Doctor
verifies the hermetic guarantee before anything is allowed to run:
  * docker present and responsive
  * every *_DIGEST / *_SHA256 pin frozen (no UNPINNED) unless --allow-unpinned
  * built images exist locally and match their recorded digests
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from . import spec

REPO_ROOT = spec.REPO_ROOT
PINS_ENV = REPO_ROOT / "docker" / "pins.env"
COMPOSE = REPO_ROOT / "docker" / "compose.yaml"


def _compose_base(eng_dir: Path) -> list[str]:
    return [
        "docker", "compose",
        # compose file lives in docker/; all its relative paths (build context,
        # volume mounts) are written repo-root-relative, so pin the project
        # directory explicitly or they resolve against docker/ (the doubled
        # `docker/docker` failure mode).
        "--project-directory", str(REPO_ROOT),
        "--env-file", str(PINS_ENV),
        "-f", str(COMPOSE),
    ]


def run_stage(eng_dir: Path, n: int, detach: bool = False) -> int:
    """Run stage n inside its pinned container. Returns exit code."""
    eng_dir = eng_dir.resolve()
    env = dict(os.environ)
    env["ENGAGEMENT_DIR"] = str(eng_dir)

    cmd = _compose_base(eng_dir)
    if "HACVSP_INV_RUNS" in env:
        pass  # forwarded automatically via compose interpolation
    cmd += ["run", "--rm"]
    if detach:
        cmd += ["-d"]
    cmd += [f"stage-{n:02d}"]

    log_dir = eng_dir / "logs"
    log_dir.mkdir(exist_ok=True)
    log_path = log_dir / f"stage-{n:02d}.log"

    print(f"==> docker compose run stage-{n:02d} (engagement: {eng_dir.name})")
    print(f"    log: {log_path}")
    with open(log_path, "ab") as logf:
        proc = subprocess.run(cmd, env=env, stdout=logf, stderr=subprocess.STDOUT)
    if detach:
        print("    (detached — inspect with: hacvsp logs "
              f"{n} --engagement {eng_dir.name})")
    elif proc.returncode != 0:
        print(f"!! stage-{n:02d} runner FAILED (exit {proc.returncode}) — "
              f"see {log_path}", file=sys.stderr)
    return proc.returncode


def follow_logs(eng_dir: Path, n: int) -> int:
    eng_dir = eng_dir.resolve()
    env = dict(os.environ)
    env["ENGAGEMENT_DIR"] = str(eng_dir)
    log_path = eng_dir / "logs" / f"stage-{n:02d}.log"
    if not log_path.exists():
        print(f"no log yet: {log_path}", file=sys.stderr)
        return 1
    cmd = ["tail", "-n", "200", "-F", str(log_path)]
    return subprocess.run(cmd).returncode


def doctor(allow_unpinned: bool = False, allow_missing_images: bool = False) -> list[str]:
    """Fail-closed environment verification. Returns failure list."""
    failures: list[str] = []

    try:
        subprocess.run(["docker", "info"], capture_output=True, check=True)
    except Exception:
        failures.append("docker daemon not reachable")

    pins = spec.load_pins()
    unpinned = {k: v for k, v in pins.items() if v == "UNPINNED"}
    if unpinned and not allow_unpinned:
        failures.append(
            f"unfrozen pins in docker/pins.env: {', '.join(sorted(unpinned))} "
            "(run: make pin)"
        )
    elif unpinned:
        print(f"!! WARN bootstrap mode — unfrozen pins: {', '.join(sorted(unpinned))}")

    for img_var, dig_var in (
        ("TOOLS_IMAGE", "TOOLS_IMAGE_DIGEST"),
        ("KONTROL_IMAGE", "KONTROL_IMAGE_DIGEST"),
    ):
        image = pins.get(img_var, "")
        want = pins.get(dig_var, "UNPINNED")
        if want == "UNPINNED":
            continue
        if allow_missing_images:
            continue
        res = subprocess.run(
            ["docker", "image", "inspect", image, "--format", "{{.Id}}"],
            capture_output=True, text=True,
        )
        if res.returncode != 0:
            failures.append(f"image {image} not built/pulled (run: make build)")
        elif res.stdout.strip() != want:
            failures.append(
                f"image {image} digest {res.stdout.strip()} != pinned {want} "
                "(rebuild or re-pin)"
            )

    return failures
