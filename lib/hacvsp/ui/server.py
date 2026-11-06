"""hacvsp ui — HTTP server (stdlib ThreadingHTTPServer, localhost-only)."""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from .. import engagement as eng_mod
from .. import insights, ledger as ledger_mod, spec
from . import actions, render

STATIC_DIR = Path(__file__).parent / "static"
ALLOWED_HOSTS_PREFIXES = ("127.0.0.1", "localhost", "[::1]")


class UiHandler(BaseHTTPRequestHandler):
    server_version = "hacvsp-ui/0.1"

    # ---------- helpers ----------
    def log_message(self, fmt, *args):  # quiet, activity.log is the record
        pass

    def _host_ok(self) -> bool:
        host = (self.headers.get("Host") or "").split(":")[0]
        return any(host.startswith(p) for p in ALLOWED_HOSTS_PREFIXES)

    def _flash(self) -> str:
        qs = parse_qs(urlparse(self.path).query)
        return unquote(qs.get("flash", [""])[0])

    def _ok(self, body: bytes, ctype="text/html; charset=utf-8"):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _redirect(self, path: str, flash: str = ""):
        import urllib.parse as up
        loc = path + (f"?flash={up.quote(flash)}" if flash else "")
        self.send_response(303)
        self.send_header("Location", loc)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _err(self, code: int, msg: str):
        self._ok(render.base("error", f"<h1>⛔ {code}</h1><p>{msg}</p>"))

    def _form(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length).decode() if length else ""
        return {k: v[0] for k, v in parse_qs(raw).items()}

    def _slug_ok(self, slug: str) -> bool:
        return (spec.REPO_ROOT / "engagements" / slug / "engagement.json").is_file()

    # ---------- GET ----------
    def do_GET(self):
        if not self._host_ok():
            return self._err(403, "hacvsp ui is localhost-only (see docs/DASHBOARD.md)")
        path = urlparse(self.path).path

        if path == "/" or path == "":
            return self._ok(render.fleet_page(insights.fleet_data(), self._flash()))

        if path.startswith("/static/"):
            f = STATIC_DIR / Path(path).name
            if f.exists():
                return self._ok(f.read_bytes(), "text/css")
            return self._err(404, "static asset missing (vendor pico.min.css)")

        parts = [p for p in path.split("/") if p]
        if len(parts) >= 2 and parts[0] == "e":
            slug = parts[1]
            if not self._slug_ok(slug):
                return self._err(404, f"no engagement {slug}")
            if len(parts) == 2:
                return self._ok(render.engagement_page(slug, self._flash()))
            if parts[2] == "stage" and len(parts) == 4:
                return self._ok(render.stage_page(slug, int(parts[3])))
            if parts[2] == "findings":
                return self._ok(render.findings_page(
                    slug, insights.findings_data(slug), self._flash()))
            if parts[2] == "ratify":
                return self._ok(render.ratify_page(
                    slug, insights.pending_data(slug), self._flash()))
            if parts[2] == "bundle":
                return self._ok(render.bundle_page(slug))
            if parts[2] == "review" and len(parts) == 4:
                doc = unquote(parts[3])
                if doc not in actions.REVIEW_REQUIRED_SECTIONS:
                    return self._err(404, "unknown review doc")
                p = spec.REPO_ROOT / "engagements" / slug / "review" / doc
                if not p.exists() or len(p.read_text().strip()) < 60:
                    try:
                        actions.regen_draft(slug, doc)  # evidence-drafted on first open
                    except Exception:
                        pass
                content = p.read_text() if p.exists() else f"# {doc}\n"
                qs = parse_qs(urlparse(self.path).query)
                return self._ok(render.review_edit_page(
                    slug, doc, content, qs.get("warn", [""])[0]))
        return self._err(404, f"no route for {path}")

    # ---------- POST ----------
    def do_POST(self):
        if not self._host_ok():
            return self._err(403, "localhost-only")
        parts = [p for p in urlparse(self.path).path.split("/") if p]
        if len(parts) < 3 or parts[0] != "e":
            return self._err(404, "no such action")
        slug = parts[1]
        if not self._slug_ok(slug):
            return self._err(404, f"no engagement {slug}")
        f = self._form()
        base = f"/e/{slug}"

        try:
            if parts[2] == "sign-suppression":
                if f.get("confirm") != slug:
                    return self._redirect(base + "/findings",
                                          f"sign blocked: confirmation must be the slug '{slug}'")
                entry = actions.add_suppression(
                    slug, f, f.get("justification", ""), f.get("reviewer", "?"))
                return self._redirect(base + "/findings",
                                      f"SIGNED: {entry['tool']}/{entry['finding_id']} appended")

            if parts[2] == "reject":
                actions.reject_finding(slug, f.get("id", "?"), f.get("title", "?"),
                                       f.get("note", ""))
                return self._redirect(base + "/findings", f"rejected → review/FIXTASKS.md")

            if parts[2] == "regen-draft" and len(parts) == 4:
                doc = unquote(parts[3])
                if f.get("confirm", [""])[0] != slug:
                    return self._redirect(base + f"/review/{doc}",
                                          f"regenerate blocked: type the slug to confirm")
                actions.regen_draft(slug, doc)
                return self._redirect(base + f"/review/{doc}",
                                      "draft regenerated from engagement evidence")

            if parts[2] == "save-workspace" and len(parts) == 4:
                doc = unquote(parts[3])
                sections = [f[k] for k in sorted(
                    (k for k in f if k.startswith("section")),
                    key=lambda k: int(k[7:]))]
                missing = actions.save_workspace(slug, doc, sections)
                warn = ", ".join(missing)
                return self._redirect(base + f"/review/{doc}",
                                      f"saved. ⚠ missing sections: {warn}" if warn else "saved ✓")

            if parts[2] == "signoff-ui":
                if f.get("confirm", [""])[0] != slug:
                    return self._redirect(base + "/ratify",
                                          f"sign-off blocked: type the slug to confirm")
                try:
                    actions.do_signoff_ui(slug, f.get("reviewer", "?"))
                    return self._redirect(base + "/ratify", "STAGE-13 SIGNED via dashboard")
                except Exception as exc:
                    return self._redirect(base + "/ratify", f"sign-off failed: {exc}")

            if parts[2] == "signoff":
                if f.get("confirm") != slug:
                    return self._redirect(base + "/ratify",
                                          f"sign-off blocked: type the slug to confirm")
                actions.do_signoff(slug, f.get("reviewer", "?"))
                return self._redirect(base + "/ratify", "STAGE-13 SIGN-OFF RECORDED ✓")

            if parts[2] == "stage" and len(parts) == 5 and parts[4] == "run":
                n = int(parts[3])
                actions.run_stage(slug, n, detach=f.get("detach") == "1")
                return self._redirect(base, f"stage {n} launched (detached={f.get('detach') == '1'})")

        except Exception as exc:  # noqa: BLE001 — fail closed, show why
            return self._redirect(base, f"action failed: {exc}")
        return self._err(404, "no such action")


def serve(port: int = 8787, bind: str = "127.0.0.1") -> None:
    httpd = ThreadingHTTPServer((bind, port), UiHandler)
    print(f"==> hacvsp ui on http://{bind}:{port}  (Ctrl-C to stop)")
    print("    fleet · ledger · findings triage · ratification · stage-13 forms")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")
