"""Engagement insights — the data layer shared by the hacvsp CLI and ui.

New CLI verbs (also used by scripting):
  hacvsp fleet [--json]                    every engagement + tier rollups
  hacvsp findings --engagement S [--json]  triage inbox (statics, survivors, gaps)
  hacvsp pending  --engagement S [--json]  ratification queue for stage 13
"""
from __future__ import annotations

import datetime
import json
from pathlib import Path

from . import engagement as eng_mod
from . import ledger as ledger_mod
from . import spec

REVIEW_DOCS = ("THREAT_MODEL.md", "SPEC_AUDIT.md", "MANUAL_REVIEW_SIGNOFF.md")


def _mtime(p: Path) -> float:
    return p.stat().st_mtime if p.exists() else 0.0


def _load_json(p: Path):
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:  # noqa: BLE001
        return None


def _slugs(root: Path) -> list[str]:
    engs = root / "engagements"
    if not engs.exists():
        return []
    return sorted(
        d.name for d in engs.iterdir()
        if d.is_dir() and d.name != "_template" and (d / "engagement.json").exists())


def fleet_data(repo_root: Path | None = None) -> list[dict]:
    root = repo_root or spec.REPO_ROOT
    now = datetime.datetime.now().timestamp()
    out = []
    for slug in _slugs(root):
        edir = root / "engagements" / slug
        meta = _load_json(edir / "engagement.json") or {}
        led = ledger_mod.load(edir)
        verdicts = {v["stage"]: v for v in led.get("verdicts", [])}
        last_stage = max((v["stage"] for v in led.get("verdicts", [])), default=0)
        last_ts = max(
            [_mtime(edir / "GATE_LEDGER.json")] +
            [_mtime(p) for p in (edir / "logs").glob("stage-*.log")]
        ) if (edir / "logs").exists() else _mtime(edir / "GATE_LEDGER.json")
        logs_active = [
            p.name for p in (edir / "logs").glob("stage-*.log")
            if now - _mtime(p) < 180
        ] if (edir / "logs").exists() else []
        out.append({
            "slug": slug,
            "target": (meta.get("target") or {}).get("repo", "?"),
            "commit": ((meta.get("target") or {}).get("commit") or "?")[:12],
            "pr_tier": led.get("overall", {}).get("pr_commit_tier", "PENDING"),
            "release_tier": led.get("overall", {}).get("release_gate_tier", "PENDING"),
            "stages_go": sum(1 for v in verdicts.values() if v["decision"] == "GO"),
            "stages_nogo": sum(1 for v in verdicts.values() if v["decision"] == "NO_GO"),
            "stages_pending": 14 - len(verdicts),
            "last_stage_run": last_stage,
            "last_activity": datetime.datetime.fromtimestamp(
                last_ts).isoformat(timespec="minutes") if last_ts else "-",
            "active_logs": logs_active,
        })
    return sorted(out, key=lambda e: -_mtime(root / "engagements" / e["slug"] / "GATE_LEDGER.json"))


def findings_data(slug: str, repo_root: Path | None = None) -> list[dict]:
    root = repo_root or spec.REPO_ROOT
    art = root / "engagements" / slug / "artifacts"
    items: list[dict] = []

    sa = _load_json(art / "static-analysis-summary.json") or {}
    for i, f in enumerate(sa.get("unsuppressed_findings", []) or []):
        items.append({
            "id": f"static-{i}",
            "kind": "static",
            "severity": f.get("severity", "?"),
            "title": f"{f.get('engine','?')}/{f.get('check','?')}",
            "where": f"{(f.get('file','?')).split('/')[-1]}:{f.get('lines','')}",
            "detail": f.get("description", "")[:160],
            "suppress_fields": {
                "tool": f.get("engine"), "finding_id": f.get("check"),
                "file": f.get("file"), "line_range": f.get("lines"),
            },
        })

    mr = _load_json(art / "mutation-report.json") or {}
    triage_doc = (root / "engagements" / slug / "target" / "MUTATION_EXCEPTIONS.md")
    triage_text = triage_doc.read_text() if triage_doc.exists() else ""
    for s in mr.get("survivors", []) or []:
        if f"#{s.get('id')}" in triage_text or str(s.get("id")) in triage_text.split():
            continue  # already triaged in MUTATION_EXCEPTIONS.md
        items.append({
            "id": f"mut-{s.get('id')}",
            "kind": "mutation-survivor",
            "severity": "medium" if s.get("contract_guess") else "low",
            "title": f"{s.get('op','?')} (mutant #{s.get('id')})",
            "where": f"{(s.get('file','?')).split('/')[-1]}:{s.get('loc','')}",
            "detail": f"{s.get('from','')} -> {s.get('to','')}",
            "suppress_fields": None,  # survivors are triaged in MUTATION_EXCEPTIONS.md
        })

    my = _load_json(art / "mythril-summary.json") or {}
    for i, u in enumerate(my.get("unmitigated_high_critical", []) or []):
        items.append({
            "id": f"mythril-{i}",
            "kind": "mythril",
            "severity": (u.get("severity") or "?").lower(),
            "title": f"SWC-{u.get('swc','?')}",
            "where": "-",
            "detail": u.get("title", ""),
            "suppress_fields": {"tool": "mythril", "finding_id": str(u.get("swc")),
                                "file": "", "line_range": ""},
        })

    cov = _load_json(art / "coverage-summary.json") or {}
    cov_doc = root / "engagements" / slug / "target" / "COVERAGE_EXCEPTIONS.md"
    cov_governed = cov_doc.exists() and "Reviewer-Signature" in cov_doc.read_text()
    if cov.get("below_threshold") and not cov_governed:
        items.append({
            "id": "coverage-gate",
            "kind": "coverage",
            "severity": "high",
            "title": f"coverage below gate: line {cov.get('line_pct')}% / branch {cov.get('branch_pct')}%",
            "where": "-",
            "detail": "COVERAGE_EXCEPTIONS.md must cover the delta (signed)",
            "suppress_fields": None,
        })

    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    items.sort(key=lambda x: order.get(x["severity"], 9))
    return items


def pending_data(slug: str, repo_root: Path | None = None) -> dict:
    root = repo_root or spec.REPO_ROOT
    edir = root / "engagements" / slug
    art = edir / "artifacts"
    review = edir / "review"
    target = edir / "target"

    docs = {d: (review / d).exists() for d in REVIEW_DOCS}

    digests = (_load_json(art / "static-analysis-summary.json") or {}) \
        .get("suppression_canonical_digests", []) or []
    signoff_text = ""
    if docs["MANUAL_REVIEW_SIGNOFF.md"]:
        signoff_text = (review / "MANUAL_REVIEW_SIGNOFF.md").read_text()
    unratified = [d[:12] for d in digests if d[:12] not in signoff_text]

    led = ledger_mod.load(edir)
    verdicts = {v["stage"]: v["decision"] for v in led.get("verdicts", [])}
    stages_1_12_go = all(verdicts.get(n) == "GO" for n in range(1, 13))

    exceptions = {}
    for name in ("COVERAGE_EXCEPTIONS.md", "MUTATION_EXCEPTIONS.md"):
        p = target / name
        text = p.read_text() if p.exists() else ""
        exceptions[name] = {
            "present": p.exists(),
            "signed": "Reviewer-Signature" in text,
        }

    vacuity = (review / "KONTROL_VACUITY.md").exists()

    return {
        "review_docs": docs,
        "unratified_suppression_digests": unratified,
        "suppression_count": len(digests),
        "exceptions": exceptions,
        "kontrol_vacuity_doc": vacuity,
        "stages_1_12_go": stages_1_12_go,
        "signoff_signed": (edir / "signatures" / "manual-signoff.sig").exists(),
    }
