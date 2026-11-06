"""Section-wise review workspace rendering: checklist cards + drafting room."""
from __future__ import annotations

import re

from .base import esc

SECTION_RE = re.compile(r"^## (.+)$", re.M)


def split_sections(content: str) -> list[dict]:
    """Split a review doc into sections keyed by '## Title'.

    Returns [{'title': str, 'body': str}] — body includes everything after the
    header until the next '## ' (leading prose before the first header becomes
    a 'preamble' section).
    """
    parts = SECTION_RE.split(content)
    sections = []
    if parts[0].strip():
        sections.append({"title": "Preamble", "body": parts[0]})
    for i in range(1, len(parts), 2):
        sections.append({"title": parts[i], "body": parts[i + 1] if i + 1 < len(parts) else ""})
    return sections


def _checklist_stats(body: str) -> tuple[int, int]:
    items = re.findall(r"^- \[( |x)\]", body, re.M)
    return sum(1 for c in items if c == "x"), len(items)


def review_workspace_page(slug: str, doc: str, content: str, warning: str = "") -> bytes:
    from .base import base
    sections = split_sections(content)
    total_checked = total_items = 0
    cards = []
    for i, sec in enumerate(sections):
        checked, items = _checklist_stats(sec["body"])
        total_checked += checked
        total_items += items
        pill = (f'<span class="pill ok">{checked}/{items}</span>' if items
                else '<span class="pill dim">free text</span>')
        cards.append(f"""
<section class="card" id="sec{i}">
  <header class="row" style="justify-content:space-between">
    <h3 style="margin:0">{esc(sec['title'])}</h3>{pill}
  </header>
  <textarea name="section{i}" rows="{max(10, min(22, sec['body'].count(chr(10)) + 4))}"
    class="mono-editor">{esc(sec['body'].rstrip() + chr(10))}</textarea>
</section>""")
    progress = (f"{total_checked}/{total_items} checklist items complete"
                if total_items else "free-form document")
    warn = (f'<div class="flash flash-warn">⚠ {esc(warning)}</div>' if warning else "")
    return base(f"{slug} · {doc}", f"""
{warn}
<div class="row" style="justify-content:space-between">
  <h1 style="margin:0">📝 {esc(doc)}</h1>
  <div class="row">
    <form method="post" action="/e/{slug}/regen-draft/{doc}"
          onsubmit="return confirm('Regenerate draft from evidence? Current edits to this document will be replaced.')">
      <button class="outline" type="submit">↻ regenerate from evidence</button>
    </form>
  </div>
</div>
<p class="dim" style="margin-top:.2rem">engagement <strong>{esc(slug)}</strong> ·
{progress} · checklist items are <code>- [ ]</code>/<code>- [x]</code> lines —
click-position editing happens in the text; the gate verifies content on save.</p>
<form method="post" action="/e/{slug}/save-workspace/{doc}">
  {''.join(cards)}
  <div class="row" style="margin-top:1rem">
    <button>💾 save document</button>
    <span class="dim">saves to engagements/{esc(slug)}/review/{esc(doc)}</span>
  </div>
</form>""", extra_css="""
.card{border:1px solid #ddd;border-radius:8px;padding:1rem;margin:.9rem 0}
.card h3{font-size:1rem}
.mono-editor{width:100%;min-height:180px;font-family:ui-monospace,monospace;
 font-size:.82rem;line-height:1.5;padding:.8rem;border-radius:6px;
 border:1px solid #cfcfcf;resize:vertical;white-space:pre-wrap}
.pill{font-size:.75rem;padding:.15rem .55rem;border-radius:99px;font-weight:600}
.pill.ok{background:#e6f4ea;color:#1b7f3b}
.pill.dim{background:#eee;color:#666}
textarea:focus{outline:2px solid #1b7f3b33}
""")
