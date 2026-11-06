import unittest

import access_matrix as am


def fn_node(name, visibility, params=None, modifiers=(), mutability="nonpayable", body="{}"):
    return {
        "nodeType": "FunctionDefinition", "name": name, "visibility": visibility,
        "stateMutability": mutability,
        "parameters": {"parameters": [
            {"typeName": {"description": t}} for t in (params or [])
        ]},
        "modifiers": [
            {"modifierName": {"name": m}, "arguments": []} for m in modifiers
        ],
        "body": body,
    }


def contract_node(name, fns):
    return {"nodeType": "ContractDefinition", "name": name, "kind": "contract",
            "nodes": fns}


def fake_build_info(ast):
    import json, tempfile
    from pathlib import Path
    d = Path(tempfile.mkdtemp())
    (d / "bi.json").write_text(json.dumps(
        {"output": {"sources": {"src/X.sol": {"ast": {"nodes": ast}}}}}))
    return d


class TestAccessMatrix(unittest.TestCase):
    def test_role_classification(self):
        rows = am.extract(fake_build_info([contract_node("Vault", [
            fn_node("setFee", "external", ["uint256"], ["onlyOwner"]),
            fn_node("sweep", "external", ["address", "uint256"], ["onlyRole", "nonReentrant"]),
            fn_node("deposit", "external", ["address", "uint256"]),
            fn_node("pause", "external", ["bool"], ["onlyEmergency", "whenNotPaused"]),
            fn_node("peek", "external", [], [], mutability="view"),
        ])]))
        by_fn = {r["function"]: r for r in rows}
        self.assertEqual(by_fn["setFee"]["allowed_roles"], ["OWNER"])
        self.assertEqual(by_fn["sweep"]["allowed_roles"], ["ROLE"])
        self.assertEqual(by_fn["deposit"]["allowed_roles"], ["PUBLIC"])
        self.assertTrue(by_fn["pause"]["is_pausable"])
        self.assertFalse(by_fn["peek"]["state_changing"])

    def test_harness_generation_revert_rows(self):
        rows = am.extract(fake_build_info([contract_node("Vault", [
            fn_node("setFee", "external", ["uint256"], ["onlyOwner"]),
            fn_node("deposit", "external", ["address", "uint256"]),
            fn_node("exotic", "external", ["uint256[2]"], ["onlyOwner"]),
        ])]))
        harness = am.generate_harness(rows, "Vault")
        self.assertIn("function test_matrix_Vault_setFee", harness)
        self.assertIn("vm.expectRevert();", harness)
        self.assertIn("matrix_Vault_exotic", harness)  # flagged as manual row


if __name__ == "__main__":
    unittest.main()
