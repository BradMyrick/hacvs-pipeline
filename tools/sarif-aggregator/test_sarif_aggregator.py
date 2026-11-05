import json
import tempfile
import unittest
from pathlib import Path

import sarif_aggregator as sa


def slither_report():
    return {
        "results": {"detectors": [
            {"check": "reentrancy-eth", "impact": "High", "confidence": "High",
             "description": "Reentrancy in Vault.withdraw(Vault.sol:120-134)",
             "elements": [{"source_mapping": {"filename_relative": "src/Vault.sol",
                                               "lines": [120, 121, 134]}}]},
            {"check": "solc-version", "impact": "Informational", "confidence": "High",
             "description": "Version pragma",
             "elements": [{"source_mapping": {"filename_relative": "src/Vault.sol",
                                               "lines": [2]}}]},
        ]}
    }


def sarif_report():
    return {"version": "2.1.0", "runs": [{"tool": {"driver": {"name": "Aderyn", "rules": []}},
            "results": [
                {"ruleId": "centralization-risk", "level": "warning",
                 "message": {"text": "owner can rug"},
                 "locations": [{"physicalLocation": {
                     "artifactLocation": {"uri": "src/Ownable.sol"},
                     "region": {"startLine": 10, "endLine": 12}}}]}]}]}


SUPPRESSIONS = [
    {"tool": "aderyn", "finding_id": "centralization-risk", "file": "src/Ownable.sol",
     "line_range": "10-12", "git_commit_hash": "a" * 40,
     "justification": "timelock added", "reviewer": "pse",
     "reviewer_signature": "MEUCIQD" + "x" * 40},
]


class TestAggregator(unittest.TestCase):
    def test_severity_mapping(self):
        self.assertEqual(sa.SLITHER_IMPACT["Multi"], "high")
        self.assertEqual(sa.SARIF_LEVEL["error"], "high")

    def test_full_flow(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            sj = td / "slither.json"; sj.write_text(json.dumps(slither_report()))
            sr = td / "aderyn-report.sarif"; sr.write_text(json.dumps(sarif_report()))
            sp = td / ".security-suppressions.json"; sp.write_text(json.dumps(SUPPRESSIONS))
            out = td / "summary.json"
            rc = sa.main(["--slither-json", str(sj), "--sarif", str(sr),
                          "--suppressions", str(sp), "--out", str(out)])
            self.assertEqual(rc, 0)
            data = json.loads(out.read_text())
            self.assertEqual(data["totals"]["unsuppressed"]["high"], 1)  # reentrancy
            self.assertEqual(data["totals"]["suppressed"], 1)            # aderyn finding
            self.assertEqual(data["totals"]["unsuppressed"]["info"], 1)  # solc-version

    def test_invalid_suppression_fails_closed(self):
        bad = [dict(SUPPRESSIONS[0], reviewer_signature="short")]
        valid, invalid = sa.validate_suppressions(bad)
        self.assertEqual(valid, [])
        self.assertTrue(any("reviewer_signature" in i for i in invalid))

    def test_line_overlap(self):
        self.assertTrue(sa.lines_overlap("120-134", "125-130"))
        self.assertFalse(sa.lines_overlap("1-10", "11-20"))
        self.assertTrue(sa.lines_overlap("", "5-6"))


if __name__ == "__main__":
    unittest.main()
