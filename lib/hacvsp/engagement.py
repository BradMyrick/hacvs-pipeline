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


def create(name: str, repo: str, commit: str | None = None, subdir: str | None = None) -> Path:
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

    repo_dir = eng / "repo"
    print(f"==> cloning {repo} (recursive submodules) into {repo_dir}")
    subprocess.run(
        ["git", "clone", "--recurse-submodules", repo, str(repo_dir)],
        check=True,
    )
    if subdir:
        sub = repo_dir / subdir
        if not sub.is_dir():
            raise FileNotFoundError(
                f"--subdir {subdir!r} not found in repo "
                f"(available: {', '.join(d.name for d in repo_dir.iterdir() if d.is_dir())})"
            )
        # target symlinks into the clone: every stage runner and git command
        # keeps working (git resolves the physical path up to repo/.git)
        target = eng / "target"
        target.symlink_to(f"repo/{subdir}", target_is_directory=True)  # relative: must resolve inside the container mount too
        workdir = sub
        print(f"==> engagement targets monorepo subdir: {subdir}")
    else:
        target = eng / "target"
        target.symlink_to("repo", target_is_directory=True)  # relative, same reason
        workdir = repo_dir
    if commit:
        subprocess.run(["git", "-C", str(workdir), "checkout", commit], check=True)
    # Record the immutable pin
    sha = subprocess.run(
        ["git", "-C", str(target), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()

    meta = json.loads((eng / "engagement.json").read_text())
    meta.update(
        {
            "name": slug,
            "target": {"repo": repo, "commit": sha, "subdir": subdir},
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


def repin(slug: str, commit: str | None = None) -> Path:
    """Move an engagement to a new target commit (fetch + checkout + submodules)."""
    eng = path(slug)
    repo_dir = eng / "repo" if (eng / "repo").exists() else eng / "target"
    subprocess.run(["git", "-C", str(repo_dir), "fetch", "--recurse-submodules", "origin"], check=True)
    if commit:
        subprocess.run(["git", "-C", str(repo_dir), "checkout", commit], check=True)
    subprocess.run(
        ["git", "-C", str(repo_dir), "submodule", "update", "--init", "--recursive"],
        check=True,
    )
    sha = subprocess.run(
        ["git", "-C", str(repo_dir), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    meta = load_meta(eng)
    meta["target"]["commit"] = sha
    save_meta(eng, meta)
    print(f"==> engagement {slug} re-pinned at {sha}")
    return eng
