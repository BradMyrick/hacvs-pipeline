"""Renderers — server-rendered HTML, classless pico CSS, zero JavaScript."""
from __future__ import annotations

import html as H
from pathlib import Path

from .. import insights, ledger as ledger_mod, spec

STATIC = Path(__file__).parent / "static"
BADGE = {"GO": "✅", "NO_GO": "🔴", "PENDING": "⬜"}


def esc(s) -> str:
    return H.escape(str(s))


def base(title: str, body: str, refresh: int | None = None) -> bytes:
    meta = f'<meta http-equiv="refresh" content="{refresh}">' if refresh else ""
    return (f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
{meta}<title>{esc(title)} — hacvsp</title>
<link rel="stylesheet" href="/static/pico.min.css">
<style>
 body{{max-width:1180px;margin:1rem auto;padding:0 1rem;font-size:.92rem}}
 h1,h2,h3{{margin-bottom:.4rem}} h1{{font-size:1.5rem}} h2{{font-size:1.2rem;margin-top:1.4rem}}
 table{{font-size:.85rem}} td,th{{padding:.3rem .5rem}}
 .mono{{font-family:ui-monospace,monospace}} .dim{{opacity:.55}}
 .badge-NO_GO{{color:#b02a37;font-weight:700}} .badge-GO{{color:#1b7f3b;font-weight:700}}
 .row{{display:flex;gap:.6rem;align-items:center;flex-wrap:wrap}}
 details summary{{cursor:pointer}} pre{{padding:.6rem;font-size:.8rem}}
 .flash{{border-left:4px solid #1b7f3b;padding:.5rem .8rem;background:#f4fbf6;margin:.6rem 0}}
 .flash-warn{{border-left-color:#b8860b;background:#fdf9ef}}
</style></head><body>
<nav class="row"><strong>hacvsp</strong><span class="dim">operator cockpit</span>
<a href="/">fleet</a></nav>
{body}</body></html>""").encode()


def _badge(v: str) -> str:
    return f'<span class="badge-{v}">{BADGE.get(v, v)}</span>'


def fleet_page(data: list[dict], flash: str = "") -> bytes:
    rows = "".join(f"""
<tr><td><a href="/e/{e['slug']}"><strong>{esc(e['slug'])}</strong></a></td>
<td class="mono dim">{esc(e['commit'])}</td>
<td>{_badge(e['pr_tier'])}</td><td>{_badge(e['release_tier'])}</td>
<td class="mono">{e['stages_go']}G {e['stages_nogo']}N {e['stages_pending']}P</td>
<td class="mono">{esc(e['last_activity'])}</td>
<td>{('⚡ ' + esc(",".join(x.replace('stage-','s') for x in e['active_logs']))) if e['active_logs'] else ''}</td>
</tr>""" for e in data)
    flash_html = f'<div class="flash">{esc(flash)}</div>' if flash else ""
    return base("Fleet", f"""
{flash_html}
<h1>Engagements</h1>
<table><thead><tr><th>engagement</th><th>commit</th><th>PR tier</th>
<th>release</th><th>stages</th><th>last activity</th><th>live</th></tr></thead>
<tbody>{rows or '<tr><td colspan="7" class="dim">no engagements — hacvsp audit &lt;repo&gt;</td></tr>'}</tbody></table>
<p class="dim">⬜ pending · ⚡ = log activity in the last 3 minutes (detached runs). Auto-refresh 20s.</p>
""", refresh=20)


def engagement_page(slug: str, flash: str = "") -> bytes:
    edir = spec.REPO_ROOT / "engagements" / slug
    led = ledger_mod.load(edir)
    meta = __import__("json").loads((edir / "engagement.json").read_text())
    rows = ""
    for s in spec.stages():
        v = ledger_mod.latest(led, s["order"])
        dec = v["decision"] if v else "PENDING"
        fails = ""
        if v and v.get("failures"):
            fails = f"<details><summary class='dim'>{len(v['failures'])} failure(s)</summary><ul>" + \
                "".join(f"<li class='mono'>{esc(f[:180])}</li>" for f in v["failures"][:8]) + "</ul></details>"
        rows += f"""<tr>
<td class="mono dim">{s['order']:>2}</td>
<td><a href="/e/{slug}/stage/{s['order']}">{esc(s['stage'])}</a></td>
<td>{esc(s['cadence'].replace('_tier','').replace('pr_commit','PR').replace('release_gate','RELEASE'))}</td>
<td>{_badge(dec)}</td><td>{fails}</td>
<td>
<form method="post" action="/e/{slug}/stage/{s['order']}/run" class="row" style="margin:0">
<button>run</button>
<label style="margin:0"><input type="checkbox" name="detach" value="1"> det</label>
</form></td></tr>"""
    flash_html = f'<div class="flash">{esc(flash)}</div>' if flash else ""
    return base(slug, f"""
{flash_html}
<h1>{esc(slug)} <span class="dim mono" style="font-size:.8rem">{esc((meta.get('target') or {}).get('repo','?'))} @ {esc(((meta.get('target') or {}).get('commit') or '?')[:12])}</span></h1>
<div class="row">
<a href="/e/{slug}/findings">📥 findings inbox</a>
<a href="/e/{slug}/ratify">⚖ ratification queue</a>
<a href="/e/{slug}/review/THREAT_MODEL.md">📝 threat model</a>
<a href="/e/{slug}/review/SPEC_AUDIT.md">📝 spec audit</a>
<a href="/e/{slug}/review/MANUAL_REVIEW_SIGNOFF.md">📝 sign-off</a>
<a href="/e/{slug}/bundle">📦 bundle preview</a>
</div>
<h2>Gate ledger — PR {_badge(led['overall']['pr_commit_tier'])} · RELEASE {_badge(led['overall']['release_gate_tier'])}</h2>
<table><thead><tr><th>#</th><th>stage</th><th>tier</th><th>verdict</th><th>failures</th><th></th></tr></thead>
<tbody>{rows}</tbody></table>
<p class="dim">Auto-refresh 30s while stages run.</p>
""", refresh=30)


def stage_page(slug: str, n: int) -> bytes:
    edir = spec.REPO_ROOT / "engagements" / slug
    led = ledger_mod.load(edir)
    s = spec.stage_by_order(n)
    history = [v for v in led.get("verdicts", []) if v["stage"] == n]
    body = "".join(f"""
<h2>{esc(v['timestamp'])} — {_badge(v['decision'])}</h2>
<pre>{esc(__import__('json').dumps({k: v[k] for k in ('failures','evidence','details') if k in v}, indent=1)[:4000])}</pre>"""
                   for v in history[-4:])
    return base(f"{slug} stage {n}", f"""
<h1>Stage {n} — {esc(s['stage'])}</h1>
<p class="dim">{esc(s.get('gate',{}).get('criteria',''))}</p>
<p><a href="/e/{slug}">← {esc(slug)}</a> · <a href="/pipeline/stages">runbooks are on disk: stages/{n:02d}-*/RUNBOOK.md</a></p>
{body}""")


def findings_page(slug: str, items: list[dict], flash: str = "") -> bytes:
    rows = ""
    for f in items:
        sign_form = ""
        if f.get("suppress_fields"):
            sf = f["suppress_fields"]
            sign_form = f"""
<details><summary>sign &amp; suppress</summary>
<form method="post" action="/e/{slug}/sign-suppression">
<input type="hidden" name="tool" value="{esc(sf['tool'])}">
<input type="hidden" name="finding_id" value="{esc(sf['finding_id'])}">
<input type="hidden" name="file" value="{esc(sf.get('file',''))}">
<input type="hidden" name="line_range" value="{esc(sf.get('line_range',''))}">
<input type="text" name="justification" placeholder="justification (expert rationale)" required style="width:100%">
<div class="row"><input type="text" name="reviewer" placeholder="reviewer name" required>
<input type="text" name="confirm" placeholder="type {esc(slug)} to confirm" required></div>
<button>sign &amp; append</button></form></details>"""
        reject = f"""
<form method="post" action="/e/{slug}/reject">
<input type="hidden" name="id" value="{esc(f['id'])}">
<input type="hidden" name="title" value="{esc(f['title'])}">
<div class="row"><input type="text" name="note" placeholder="fix note" required>
<button class="outline">reject → fixtask</button></div></form>"""
        rows += f"""<tr>
<td class="mono dim">{esc(f['id'])}</td><td>{esc(f['kind'])}</td>
<td class="mono">{esc(f['severity'])}</td><td><strong>{esc(f['title'])}</strong></td>
<td class="mono dim">{esc(f['where'])}</td><td class="dim">{esc(f['detail'])[:120]}</td>
<td>{sign_form}{reject}</td></tr>"""
    flash_html = f'<div class="flash">{esc(flash)}</div>' if flash else ""
    return base(f"{slug} findings", f"""
{flash_html}
<h1>📥 Findings inbox — {esc(slug)}</h1>
<p class="dim">Unsuppressed statics, mutation survivors, mythril results, gate gaps.
Signing appends a signed entry to the target's .security-suppressions.json — the exact
governance the stage gates verify. Mutation survivors and coverage gaps are triaged via
their exception docs (see <a href="/e/{slug}/ratify">ratification queue</a>).</p>
<table><thead><tr><th>id</th><th>kind</th><th>sev</th><th>finding</th><th>where</th><th>detail</th><th>action</th></tr></thead>
<tbody>{rows or '<tr><td colspan="7">🎉 inbox empty</td></tr>'}</tbody></table>""")


def ratify_page(slug: str, p: dict, flash: str = "") -> bytes:
    docs = "".join(
        f"<li>{'✅' if ok else '⬜'} <a href='/e/{slug}/review/{d}'>{d}</a></li>"
        for d, ok in p["review_docs"].items())
    exc = "".join(
        f"<li>{'✅' if v['signed'] else '⚠️' if v['present'] else '⬜'} {k}"
        f" — {'signed' if v['signed'] else 'present, unsigned' if v['present'] else 'missing'}</li>"
        for k, v in p["exceptions"].items())
    digests = (", ".join(p["unratified_suppression_digests"])
               if p["unratified_suppression_digests"] else "<em>all ratified</em>")
    flash_html = f'<div class="flash {"flash-warn" if "warn" in flash.lower() else ""}">{esc(flash)}</div>' if flash else ""
    return base(f"{slug} ratify", f"""
{flash_html}
<h1>⚖ Ratification queue — {esc(slug)}</h1>
<h2>Stage-13 readiness</h2>
<ul>
<li>{'✅' if p['stages_1_12_go'] else '⬜'} stages 1–12 all GO</li>
<li>{'✅' if p['kontrol_vacuity_doc'] else '⬜'} KONTROL_VACUITY.md present</li>
<li>{'✅' if p['signoff_signed'] else '⬜'} manual sign-off signed</li>
</ul>
<h2>Review documents</h2><ul>{docs}</ul>
<h2>Exception documents (in target repo)</h2><ul>{exc}</ul>
<h2>Suppression digests — {p['suppression_count']} total</h2>
<p class="mono">{digests}</p>
<p class="dim">Digest prefixes must each appear in MANUAL_REVIEW_SIGNOFF.md — exactly what
stage 13's runner enforces.</p>""")


def review_edit_page(slug: str, doc: str, content: str, warning: str = "") -> bytes:
    warn = f'<div class="flash flash-warn">⚠ missing sections: {esc(warning)}</div>' if warning else ""
    return base(f"{slug} {doc}", f"""
<h1>📝 {esc(doc)} — {esc(slug)}</h1>{warn}
<form method="post" action="/e/{slug}/save/{doc}">
<textarea name="content" rows="28" style="font-family:ui-monospace,monospace;font-size:.82rem">{esc(content)}</textarea>
<button>save</button></form>
<p class="dim">Saved straight to engagements/{esc(slug)}/review/{esc(doc)} — the file the
stage-13 gate reads. Section warnings are advisory; the gate stays authoritative.</p>""")


def bundle_page(slug: str) -> bytes:
    edir = spec.REPO_ROOT / "engagements" / slug
    sa = edir / "SECURITY_ASSURANCE.md"
    body = ""
    if sa.exists():
        text = sa.read_text()
        body = f'<pre style="white-space:pre-wrap">{esc(text[:8000])}</pre>'
    else:
        body = "<p class='dim'>SECURITY_ASSURANCE.md is rendered by stage 14 — not yet present.</p>"
    spec_list = "".join(
        f"<li>{'✅' if (edir / f).exists() else '⬜'} <code>{f}</code></li>"
        for f in ["SECURITY_ASSURANCE.md", "artifacts/sbom.cyclonedx.json",
                  "artifacts/ACCESS_CONTROL_MATRIX.json", "artifacts/EVENT_EMISSION_AUDIT.json",
                  "artifacts/kontrol-proofs.json", "artifacts/mutation-report.json",
                  "artifacts/mythril-results.json", "artifacts/provenance.intoto.jsonl",
                  "signatures/bundle-attestation.sig"])
    return base(f"{slug} bundle", f"""
<h1>📦 Published bundle — {esc(slug)}</h1><h2>Spec bundle checklist</h2><ul>{spec_list}</ul>
<h2>SECURITY_ASSURANCE.md</h2>{body}""")
