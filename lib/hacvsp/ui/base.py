"""Base HTML shell — pico classless + hacvsp affordances."""
from __future__ import annotations
import html as H
BADGE = {"GO": "\u2705", "NO_GO": "\U0001F534", "PENDING": "\u2b1c"}

def esc(s) -> str:
    return H.escape(str(s))

def base(title: str, body: str, refresh: int | None = None, extra_css: str = "") -> bytes:
    meta = f'<meta http-equiv="refresh" content="{refresh}">' if refresh else ""
    return (f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
{meta}<title>{esc(title)} \u2014 hacvsp</title>
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
{extra_css}
</style></head><body>
<nav class="row"><strong>hacvsp</strong><span class="dim">operator cockpit</span>
<a href="/">fleet</a></nav>
{body}</body></html>""").encode()
