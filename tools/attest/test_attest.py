import json
import tempfile
import unittest
from pathlib import Path

import attest


def make_engagement(td: Path) -> Path:
    eng = td / "engagements" / "demo"
    (eng / "artifacts").mkdir(parents=True)
    (eng / "signatures").mkdir()
    (eng / "target").mkdir()
    meta = {
        "name": "demo",
        "target": {"repo": "https://example.com/repo", "commit": "a" * 40},
        "spec_version": "v0.1.0",
        "applicability": {},
    }
    (eng / "engagement.json").write_text(json.dumps(meta))
    (eng / "GATE_LEDGER.json").write_text(json.dumps(
        {"overall": {"pr_commit_tier": "GO", "release_gate_tier": "GO"}, "verdicts": []}))
    for rel in ["artifacts/sbom.cyclonedx.json", "artifacts/ACCESS_CONTROL_MATRIX.json",
                "artifacts/EVENT_EMISSION_AUDIT.json", "artifacts/kontrol-proofs.json",
                "artifacts/mutation-report.json", "artifacts/mythril-results.json"]:
        (eng / rel).write_text("{}")
    return eng


class TestAttest(unittest.TestCase):
    def test_assemble_and_verify(self):
        import sys
        repo_root = Path(__file__).resolve().parents[2]
        sys.path.insert(0, str(repo_root / "lib"))
        with tempfile.TemporaryDirectory() as td:
            eng = make_engagement(Path(td))
            self.assertEqual(attest.assemble(eng), 0)
            self.assertTrue((eng / "SECURITY_ASSURANCE.md").exists())
            manifest = json.loads((eng / "artifacts" / "bundle-manifest.json").read_text())
            self.assertIn("bundle_digest", manifest)
            # provenance appended
            prov = (eng / "artifacts" / "provenance.intoto.jsonl").read_text().strip()
            self.assertIn("in-toto.io/Statement", prov)
            # verify without signature: reports missing sig
            rc = attest.verify(eng)
            self.assertEqual(rc, 1)  # signature absent


if __name__ == "__main__":
    unittest.main()
