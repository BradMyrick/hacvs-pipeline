"""UI actions — every write is one atomic file change + an activity-log line."""
from __future__ import annotations

import datetime
import json
import os
import subprocess
from pathlib import Path

from .. import spec
from . import sign

REVIEW_REQUIRED_SECTIONS = {
    "THREAT_MODEL.md": ["Actor Matrix", "Trust Boundaries", "Economic Vectors", "MEV Exposure"],
    "SPEC_AUDIT.md": ["Invariant Completeness", "Whitepaper Concordance"],
    "MANUAL_REVIEW_SIGNOFF.md": ["High-Risk Assembly", "Internal Accounting",
                                 "Suppression Audit", "Signature"],
}


def eng_dir(slug: str) -> Path:
    return spec.REPO_ROOT / "engagements" / slug


def activity(slug: str, msg: str) -> None:
    ts = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    log = eng_dir(slug) / "activity.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "a") as f:
        f.write(f"{ts}  {msg}\n")


def _atomic_write(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text)
    os.replace(tmp, path)


def add_suppression(slug: str, fields: dict, justification: str, reviewer: str) -> dict:
    """Append a signed suppression entry to the target's governance file."""
    import subprocess as sp
    commit = sp.run(["git", "-C", str(eng_dir(slug) / "target"), "rev-parse", "HEAD"],
                    capture_output=True, text=True).stdout.strip() or "0" * 40
    entry = {
        "tool": fields["tool"], "finding_id": fields["finding_id"],
        "file": fields.get("file", ""), "line_range": fields.get("line_range", ""),
        "git_commit_hash": commit,
        "justification": justification,
        "reviewer": reviewer,
    }
    entry["reviewer_signature"] = sign.sign_digest(
        sign.canonical_entry_digest(entry))
    supp = eng_dir(slug) / "target" / ".security-suppressions.json"
    entries = json.loads(supp.read_text()) if supp.exists() else []
    entries.append(entry)
    _atomic_write(supp, json.dumps(entries, indent=2) + "\n")
    activity(slug, f"SIGNED suppression {entry['tool']}/{entry['finding_id']} "
                   f"@{entry['file']}:{entry['line_range']}")
    return entry


def reject_finding(slug: str, finding_id: str, title: str, note: str) -> None:
    p = eng_dir(slug) / "review" / "FIXTASKS.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    header = p.exists()
    with open(p, "a") as f:
        if not header:
            f.write("# Fix Tasks (dashboard-rejected findings)\n\n")
        f.write(f"- [ ] `{finding_id}` — {title} — {note}\n")
    activity(slug, f"REJECTED {finding_id} -> FIXTASKS ({note[:60]})")


def save_review_doc(slug: str, doc: str, content: str) -> list[str]:
    if doc not in REVIEW_REQUIRED_SECTIONS:
        raise ValueError(f"unknown review doc: {doc}")
    p = eng_dir(slug) / "review" / doc
    p.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(p, content)
    missing = [s for s in REVIEW_REQUIRED_SECTIONS[doc]
               if s.lower() not in content.lower()]
    activity(slug, f"SAVED review/{doc} (missing sections: {len(missing)})")
    return missing


def do_signoff(slug: str, reviewer: str) -> dict:
    """Sign MANUAL_REVIEW_SIGNOFF.md — the same flow stage 13's runner verifies."""
    signoff = eng_dir(slug) / "review" / "MANUAL_REVIEW_SIGNOFF.md"
    if not signoff.exists():
        raise FileNotFoundError("MANUAL_REVIEW_SIGNOFF.md not drafted yet")
    content = signoff.read_text()
    missing = [s for s in REVIEW_REQUIRED_SECTIONS["MANUAL_REVIEW_SIGNOFF.md"]
               if s.lower() not in content.lower()]
    if missing:
        raise ValueError(f"sign-off blocked: missing sections {missing}")
    sig = sign.sign_digest(
        __import__("hashlib").sha256(content.encode()).hexdigest())
    sigdir = eng_dir(slug) / "signatures"
    sigdir.mkdir(exist_ok=True)
    _atomic_write(sigdir / "manual-signoff.sig", sig + "\n")
    activity(slug, f"SIGNED-OFF by {reviewer} (stage-13 sign-off)")
    return {"reviewer": reviewer, "signature_file": "signatures/manual-signoff.sig"}


def run_stage(slug: str, n: int, detach: bool = False) -> None:
    """Launch the exact CLI invocation, detached from the UI process."""
    cmd = [str(spec.REPO_ROOT / "bin" / "hacvsp"), "stage", str(n),
           "--engagement", slug]
    if detach:
        cmd.append("--detach")
    log = eng_dir(slug) / "logs" / "ui-actions.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "ab") as lf:
        subprocess.Popen(cmd, stdout=lf, stderr=lf, start_new_session=True,
                         cwd=str(spec.REPO_ROOT))
    activity(slug, f"UI action: stage {n} run (detach={detach})")


def regen_draft(slug: str, doc: str) -> None:
    """Regenerate a review doc from engagement evidence (replaces content)."""
    from . import drafts
    gen = drafts.DRAFTS.get(doc)
    if gen is None:
        raise ValueError(f"no draft generator for {doc}")
    p = eng_dir(slug) / "review" / doc
    p.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(p, gen(slug))
    activity(slug, f"REGENERATED draft review/{doc} from evidence")


def save_workspace(slug: str, doc: str, sections: list[str]) -> list[str]:
    """Assemble the doc from section bodies (order preserved on the page)."""
    parts = []
    for body in sections:
        body = body.strip("\n")
        if body.startswith("## "):
            parts.append(body)
        else:
            # first section is preamble or already has its header stripped
            parts.append(body)
    content = "\n\n".join(parts) + "\n"
    if not content.lstrip().startswith("#"):
        content = f"# {doc}\n\n{content}"
    return save_review_doc(slug, doc, content)
