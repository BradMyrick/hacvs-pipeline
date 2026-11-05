import json
import tempfile
import unittest
from pathlib import Path

import event_audit as ea


def build_info(ast_sources: dict) -> Path:
    """Fabricate a minimal foundry build-info JSON from raw AST dicts."""
    td = tempfile.mkdtemp()
    p = Path(td) / "build-info-abc.json"
    p.write_text(json.dumps({
        "input": {"sources": {}},
        "output": {"sources": {k: {"ast": v} for k, v in ast_sources.items()}, "contracts": {}},
    }))
    return p.parent


SAFE_AST = {
    "src/Vault.sol": {
        "nodeType": "SourceUnit", "id": 1, "nodes": [
            {"nodeType": "ContractDefinition", "id": 2, "name": "Vault", "kind": "contract",
             "nodes": [
                 {"nodeType": "VariableDeclaration", "id": 10, "name": "owner",
                  "isParameter": False, "constant": False,
                  "typeName": {"description": "address"}},
                 {"nodeType": "VariableDeclaration", "id": 11, "name": "totalShares",
                  "isParameter": False, "constant": False,
                  "typeName": {"description": "uint256"}},
                 {"nodeType": "EventDefinition", "id": 20, "name": "OwnershipTransferred",
                  "parameters": {"parameters": [
                      {"name": "newOwner", "indexed": True,
                       "typeName": {"description": "address"}}]}},
                 {"nodeType": "FunctionDefinition", "id": 30, "name": "setOwner",
                  "visibility": "public", "stateMutability": "nonpayable",
                  "body": {"nodeType": "Block", "statements": [
                      {"nodeType": "ExpressionStatement", "expression":
                          {"nodeType": "Assignment",
                           "leftHandSide": {"nodeType": "Identifier", "id": 40,
                                            "name": "owner", "referencedDeclaration": 10},
                           "rightHandSide": {"nodeType": "Identifier", "name": "newOwner"}}},
                      {"nodeType": "EmitStatement", "eventCall": {
                          "expression": {"name": "OwnershipTransferred"},
                          "arguments": []}}]}},
             ]},
        ],
    },
}


UNSAFE_AST = {
    "src/Bad.sol": {
        "nodeType": "SourceUnit", "nodes": [
            {"nodeType": "ContractDefinition", "name": "Bad", "kind": "contract",
             "nodes": [
                 {"nodeType": "VariableDeclaration", "id": 10, "name": "feeBps",
                  "isParameter": False, "constant": False,
                  "typeName": {"description": "uint256"}},
                 {"nodeType": "FunctionDefinition", "name": "setFee",
                  "visibility": "external", "stateMutability": "nonpayable",
                  "body": {"nodeType": "Block", "statements": [
                      {"nodeType": "ExpressionStatement", "expression":
                          {"nodeType": "Assignment",
                           "leftHandSide": {"nodeType": "Identifier",
                                            "name": "feeBps", "referencedDeclaration": 10},
                           "rightHandSide": {"nodeType": "Identifier", "name": "v"}}}]}}
             ]},
        ],
    },
}


class TestEventAudit(unittest.TestCase):
    def test_classify(self):
        self.assertIn("fees", ea.classify("feeBps"))
        self.assertIn("ownership", ea.classify("owner"))
        self.assertIn("balances", ea.classify("userBalance"))

    def test_safe_contract_passes(self):
        bdir = build_info(SAFE_AST)
        audit = ea.Audit(bdir).audit()
        self.assertEqual(audit["summary"]["missing_event_failures"], 0)
        self.assertEqual(audit["summary"]["indexing_warnings"], 0)
        self.assertTrue(audit["mutation_graph"]["src/Vault.sol::Vault"]["setOwner"]["critical_writes"])

    def test_unsafe_contract_missing_event(self):
        bdir = build_info(UNSAFE_AST)
        audit = ea.Audit(bdir).audit()
        self.assertEqual(audit["summary"]["missing_event_failures"], 1)
        self.assertEqual(audit["missing_events"][0]["function"], "setFee")


if __name__ == "__main__":
    unittest.main()
