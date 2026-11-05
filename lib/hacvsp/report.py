"""Render SECURITY_ASSURANCE.md draft from the gate ledger (stage 14 finalizes)."""
from __future__ import annotations

import json
from pathlib import Path

from . import ledger, spec


def _suppressions_table(eng_dir: Path) -> str:
    supp_path = eng_dir / "target" / ".security-suppressions.json"
    if not supp_path.exists():
        return "_No suppressions file present._\n"
    try:
        entries = json.loads(supp_path.read_text())
    except Exception as exc:  # noqa: BLE001
        return f"_Unparseable suppressions file: {exc}_\n"
    if not entries:
        return "_No active suppressions._\n"
    rows = ["| Tool | Rule ID | File:Lines | Justification | Reviewer | Commit |",
            "|---|---|---|---|---|---|"]
    for e in entries:
        rows.append(
            f"| {e.get('tool','?')} | {e.get('finding_id','?')} "
            f"| {e.get('file','?')}:{e.get('line_range','?')} "
            f"| {e.get('justification','?')[:60]} "
            f"| {e.get('reviewer','?')} | {str(e.get('git_commit_hash','?'))[:12]} |"
        )
    return "\n".join(rows) + "\n"


def render_draft(eng_dir: Path) -> Path:
    led = ledger.load(eng_dir)
    meta = json.loads((eng_dir / "engagement.json").read_text())
    lines = [
        "# SECURITY_ASSURANCE.md (DRAFT — finalized by Stage 14)",
        "",
        "## Executive Summary & Target Commit",
        "",
        f"- Engagement: `{meta['name']}`",
        f"- Target: `{meta['target']['repo']}` @ `{meta['target']['commit']}`",
        f"- Pipeline: {meta['spec_version']} (fail-closed, dual-cadence)",
        f"- Overall: PR tier **{led['overall']['pr_commit_tier']}**, "
        f"Release tier **{led['overall']['release_gate_tier']}**",
        "",
        "## Verification Methodology & Stage-by-Stage Results",
        "",
        "| # | Stage | Cadence | Verdict | Failures |",
        "|---|---|---|---|---|",
    ]
    for s in spec.stages():
        v = ledger.latest(led, s["order"])
        dec = v["decision"] if v else "PENDING"
        fails = "; ".join(v.get("failures", []))[:80] if v else ""
        lines.append(f"| {s['order']} | {s['stage']} | {s['cadence']} | {dec} | {fails} |")
    lines += [
        "",
        "## Active Suppressions & Exceptions Inventory",
        "",
        _suppressions_table(eng_dir),
        "## Coverage Exceptions Audit",
        "",
        "_Populated from COVERAGE_EXCEPTIONS.md at Stage 14._",
        "",
        "## On-Chain Deployment & Bytecode Verification Mapping",
        "",
        "_Populated at Stage 14 (Sourcify/explorer exact-match results)._",
        "",
    ]
    out = eng_dir / "review" / "SECURITY_ASSURANCE.draft.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines))
    return out
