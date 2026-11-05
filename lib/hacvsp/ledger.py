"""GATE_LEDGER.json — binary verdicts, append-only history, cadence rollup.

Fail-closed semantics:
  * verdicts are only ever appended (history is evidence);
  * the *latest* verdict for a stage is authoritative;
  * a cadence is GO only if every stage in it has latest decision == GO;
  * anything missing, errored, or ambiguous is PENDING/NO_GO, never assumed GO.
"""
from __future__ import annotations

import datetime
import json
import subprocess
from pathlib import Path

from . import spec

LEDGER_NAME = "GATE_LEDGER.json"


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def ledger_path(eng_dir: Path) -> Path:
    return eng_dir / LEDGER_NAME


def load(eng_dir: Path) -> dict:
    p = ledger_path(eng_dir)
    if not p.exists():
        return {
            "spec_version": spec.load_spec()["version"],
            "verdicts": [],
            "overall": {"pr_commit_tier": "PENDING", "release_gate_tier": "PENDING"},
        }
    return json.loads(p.read_text())


def append(eng_dir: Path, record: dict) -> dict:
    led = load(eng_dir)
    led["spec_version"] = spec.load_spec()["version"]
    record.setdefault("timestamp", _now())
    led["verdicts"].append(record)
    led["overall"] = rollup(led)
    ledger_path(eng_dir).write_text(json.dumps(led, indent=2) + "\n")
    return led


def latest(led: dict, stage: int) -> dict | None:
    hits = [v for v in led["verdicts"] if v["stage"] == stage]
    return hits[-1] if hits else None


def rollup(led: dict) -> dict:
    out = {}
    for cadence in ("pr_commit_tier", "release_gate_tier"):
        orders = spec.cadence_stages(cadence)
        verdicts = [latest(led, n) for n in orders]
        if any(v is None for v in verdicts):
            out[cadence] = "PENDING"
        elif all(v["decision"] == "GO" for v in verdicts):
            out[cadence] = "GO"
        else:
            out[cadence] = "NO_GO"
    return out


def target_commit(eng_dir: Path) -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(eng_dir / "target"), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except Exception:
        return "unknown"


def render_table(led: dict) -> str:
    rows = []
    for s in spec.stages():
        n = s["order"]
        v = latest(led, n)
        decision = v["decision"] if v else "--"
        ts = v.get("timestamp", "")[:16] if v else ""
        note = ""
        if v and v["decision"] == "NO_GO":
            fails = v.get("failures") or v.get("details", {}).get("failures") or []
            note = "; ".join(fails)[:80]
        rows.append(f"{n:>2}  {decision:<6} {ts:<16} {s['stage'][:52]:<52} {note}")
    overall = led.get("overall", {})
    lines = [
        "================================================================",
        " HACVSP GATE LEDGER — binary verdicts (latest authoritative)",
        "================================================================",
        *rows,
        "----------------------------------------------------------------",
        f" PR tier:      {overall.get('pr_commit_tier', 'PENDING')}",
        f" RELEASE tier: {overall.get('release_gate_tier', 'PENDING')}",
        "================================================================",
    ]
    return "\n".join(lines)
