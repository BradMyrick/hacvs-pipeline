import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
import threading
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib"))

import hacvsp.insights as insights          # noqa: E402
import hacvsp.spec as spec                  # noqa: E402
from hacvsp.ui import actions               # noqa: E402


def make_engagement(root: pathlib.Path, slug="t-eng"):
    edir = root / "engagements" / slug
    (edir / "artifacts").mkdir(parents=True)
    (edir / "review").mkdir(parents=True)
    (edir / "target").mkdir(parents=True)
    (edir / "engagement.json").write_text(json.dumps(
        {"name": slug, "target": {"repo": "x", "commit": "a" * 40, "subdir": None}}))
    (edir / "GATE_LEDGER.json").write_text(json.dumps(
        {"overall": {"pr_commit_tier": "GO", "release_gate_tier": "NO_GO"},
         "verdicts": [{"stage": 1, "decision": "GO"}]}))
    (edir / "artifacts" / "static-analysis-summary.json").write_text(json.dumps(
        {"unsuppressed_findings": [
            {"engine": "slither", "check": "reentrancy-no-eth", "severity": "medium",
             "file": "src/V.sol", "lines": "10-20", "description": "x"}],
         "suppression_canonical_digests": ["deadbeef" * 8]}))
    (edir / "artifacts" / "mutation-report.json").write_text(json.dumps(
        {"survivors": [{"id": "5", "op": "X", "file": "src/V.sol", "loc": "1:1",
                        "from": "a", "to": "b", "contract_guess": "V"}]}))
    return edir


class TestInsights(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        self.edir = make_engagement(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_findings_includes_untriaged(self):
        items = insights.findings_data("t-eng", self.root)
        ids = [i["id"] for i in items]
        self.assertIn("static-0", ids)
        self.assertIn("mut-5", ids)

    def test_findings_excludes_triaged_survivors(self):
        (self.edir / "target" / "MUTATION_EXCEPTIONS.md").write_text(
            "| #5 | X | src/V.sol | equivalent |\n")
        items = insights.findings_data("t-eng", self.root)
        self.assertFalse(any(i["id"] == "mut-5" for i in items))

    def test_pending_unratified_digests(self):
        p = insights.pending_data("t-eng", self.root)
        self.assertEqual(p["unratified_suppression_digests"], ["deadbeefdead"])
        (self.edir / "review" / "MANUAL_REVIEW_SIGNOFF.md").write_text(
            "ratified deadbeefdead ok")
        p = insights.pending_data("t-eng", self.root)
        self.assertEqual(p["unratified_suppression_digests"], [])


class TestActions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        self.edir = make_engagement(self.root)
        # temp signing key
        self.key = pathlib.Path(self.tmp.name) / "k"
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "",
                        "-f", str(self.key)], check=True)
        self.old_env = os.environ.get("HACVSP_SIGN_KEY")
        os.environ["HACVSP_SIGN_KEY"] = str(self.key)
        # point the package at the fixture root
        self._patch(spec, "REPO_ROOT", self.root)

    def _patch(self, mod, name, value):
        old = getattr(mod, name)
        setattr(mod, name, value)
        self.addCleanup(setattr, mod, name, old)

    def tearDown(self):
        if self.old_env is None:
            os.environ.pop("HACVSP_SIGN_KEY", None)
        else:
            os.environ["HACVSP_SIGN_KEY"] = self.old_env
        self.tmp.cleanup()

    def test_add_suppression_signs_and_appends(self):
        entry = actions.add_suppression(
            "t-eng",
            {"tool": "slither", "finding_id": "reentrancy-no-eth",
             "file": "src/V.sol", "line_range": "10-20"},
            "test justification", "tester")
        self.assertGreater(len(entry["reviewer_signature"]), 16)
        entries = json.loads((self.edir / "target" / ".security-suppressions.json").read_text())
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["finding_id"], "reentrancy-no-eth")
        self.assertTrue((self.edir / "activity.log").exists())

    def test_save_review_doc_warns_missing_sections(self):
        missing = actions.save_review_doc(
            "t-eng", "THREAT_MODEL.md", "# Threat Model\n\nno sections")
        self.assertTrue(any("Actor Matrix" in m for m in missing))
        missing2 = actions.save_review_doc(
            "t-eng", "THREAT_MODEL.md",
            "# TM\n## Actor Matrix\n## Trust Boundaries\n## Economic Vectors\n## MEV Exposure\n")
        self.assertEqual(missing2, [])

    def test_signoff_blocked_on_missing_sections(self):
        with self.assertRaises((ValueError, FileNotFoundError)):
            actions.do_signoff("t-eng", "tester")


class TestServer(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        make_engagement(self.root)
        import hacvsp.spec as spec_mod
        self._old = spec_mod.REPO_ROOT
        spec_mod.REPO_ROOT = self.root
        from hacvsp.ui.server import UiHandler
        from http.server import ThreadingHTTPServer
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), UiHandler)
        self.port = self.httpd.server_address[1]
        self.t = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.t.start()

    def tearDown(self):
        import hacvsp.spec as spec_mod
        spec_mod.REPO_ROOT = self._old
        self.httpd.shutdown()
        self.tmp.cleanup()

    def _get(self, path):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}{path}", timeout=5) as r:
            return r.status, r.read().decode()

    def test_fleet_200(self):
        code, body = self._get("/")
        self.assertEqual(code, 200)
        self.assertIn("t-eng", body)

    def test_engagement_and_findings(self):
        code, body = self._get("/e/t-eng")
        self.assertEqual(code, 200)
        self.assertIn("Gate ledger", body)
        code, body = self._get("/e/t-eng/findings")
        self.assertEqual(code, 200)
        self.assertIn("reentrancy-no-eth", body)


if __name__ == "__main__":
    import unittest
    unittest.main()
