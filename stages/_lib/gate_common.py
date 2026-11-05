"""Shared gate-evaluator machinery for stages/NN-*/gate.py.

Every gate.py must print a single JSON object on stdout:
  {"decision": "GO"|"NO_GO", "failures": [...], "evidence": [...], "details": {}}

Fail-closed rules baked in here:
  * a missing artifact file -> NO_GO
  * an unparseable JSON artifact -> NO_GO
  * any evaluator exception -> NO_GO (caught by lib.hacvsp.main._gate_eval)
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> Path:
    p = argparse.ArgumentParser()
    p.add_argument("--engagement-dir", required=True)
    args = p.parse_args()
    return Path(args.engagement_dir).resolve()


def artifact(eng_dir: Path, rel: str) -> Path:
    """Resolve spec artifact names like artifacts/foo.json within the engagement."""
    p = eng_dir / rel
    if not p.exists():
        # Some spec names are globs (e.g. out/build-info/*.json) — handled by callers.
        pass
    return p


def load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def require_files(eng_dir: Path, rels: list[str]) -> list[str]:
    failures = []
    for rel in rels:
        p = eng_dir / rel
        if not p.exists():
            failures.append(f"missing artifact: {rel}")
    return failures


def emit(decision: str, failures: list[str], evidence: list[str], details: dict) -> None:
    print(json.dumps({
        "decision": decision,
        "failures": failures,
        "evidence": evidence,
        "details": details,
    }))


def go(failures: list[str], evidence: list[str], details: dict) -> None:
    emit("GO" if not failures else "NO_GO", failures, evidence, details)
