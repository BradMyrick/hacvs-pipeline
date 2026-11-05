"""Engagement workspaces: engagements/<slug>/ — the unit of audit work.

Layout:
  engagement.json      metadata, target pin, applicability decisions
  intake.md            the expert questionnaire (filled with the client/expert)
  GATE_LEDGER.json     binary verdicts
  .env                 0600 secrets (HACVSP_FORK_RPC, COSIGN_KEY, ...) - never committed
  target/              the audited repo, cloned at a pinned commit
  artifacts/           stage evidence (spec-named)
  logs/                raw stage execution logs
  review/              stage-13 expert deliverables + suppression ratifications
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import datetime
from pathlib import Path

from . import spec

REPO_ROOT = spec.REPO_ROOT
ENGAGEMENTS = REPO_ROOT / "engagements"
TEMPLATE = ENGAGEMENTS / "_template"


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9-]+", "-", name.lower()).strip("-")
    return slug or "engagement"


def list_engagements() -> list[str]:
    if not ENGAGEMENTS.exists():
        return []
    return sorted(
        d.name for d in ENGAGEMENTS.iterdir()
        if d.is_dir() and d.name != "_template"
        and (d / "engagement.json").exists()
    )


def path(slug: str) -> Path:
    p = ENGAGEMENTS / slug
    if not p.is_dir():
        raise FileNotFoundError(f"engagement {slug!r} not found (engagements/{slug})")
    return p


def create(name: str, repo: str, commit: str | None = None) -> Path:
    slug = slugify(name)
    eng = ENGAGEMENTS / slug
    if eng.exists():
        raise FileExistsError(f"engagement {slug!r} already exists")
    if not TEMPLATE.exists():
        raise FileNotFoundError("engagements/_template missing")
    shutil.copytree(TEMPLATE, eng)

    # .env from example, 0600, secrets policy
    env_example = eng / ".env.example"
    if env_example.exists():
        (eng / ".env").write_text(env_example.read_text())
        os.chmod(eng / ".env", 0o600)

    target = eng / "target"
    print(f"==> cloning {repo} (recursive submodules) into {target}")
    subprocess.run(
        ["git", "clone", "--recurse-submodules", repo, str(target)],
        check=True,
    )
    if commit:
        subprocess.run(["git", "-C", str(target), "checkout", commit], check=True)
    # Record the immutable pin
    sha = subprocess.run(
        ["git", "-C", str(target), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()

    meta = json.loads((eng / "engagement.json").read_text())
    meta.update(
        {
            "name": slug,
            "target": {"repo": repo, "commit": sha},
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
            "spec_version": spec.load_spec()["version"],
        }
    )
    (eng / "engagement.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(f"==> engagement ready: {eng}")
    print(f"    target pinned at commit {sha}")
    print(f"    next: fill intake.md + engagement.json applicability, then run stages 1-7")
    return eng


def load_meta(eng_dir: Path) -> dict:
    return json.loads((eng_dir / "engagement.json").read_text())


def save_meta(eng_dir: Path, meta: dict) -> None:
    (eng_dir / "engagement.json").write_text(json.dumps(meta, indent=2) + "\n")
