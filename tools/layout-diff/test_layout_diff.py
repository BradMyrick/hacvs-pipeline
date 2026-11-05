import json
import tempfile
import unittest
from pathlib import Path

import layout_diff as ld


def write(obj) -> Path:
    p = Path(tempfile.mkdtemp()) / "layout.json"
    p.write_text(json.dumps(obj))
    return p


BASE = {"storage": [
    {"contract": "Vault", "label": "owner", "type": "t_address", "offset": 0, "slot": "0"},
    {"contract": "Vault", "label": "totalShares", "type": "t_uint256", "offset": 0, "slot": "1"},
    {"contract": "Vault", "label": "__gap", "type": "t_array[t_uint256]_storage", "offset": 0, "slot": "2"},
]}


class TestLayoutDiff(unittest.TestCase):
    def test_safe_append(self):
        cur = {"storage": BASE["storage"] + [
            {"contract": "Vault", "label": "newVar", "type": "t_uint256", "offset": 0, "slot": "52"}]}
        out = Path(tempfile.mkdtemp()) / "r.json"
        rc = ld.main(["--baseline", str(write(BASE)), "--current", str(write(cur)),
                      "--contract", "Vault", "--out", str(out)])
        self.assertEqual(rc, 0)

    def test_slot_move_detected(self):
        cur = {"storage": [
            {"contract": "Vault", "label": "totalShares", "type": "t_uint256", "offset": 0, "slot": "0"},
            {"contract": "Vault", "label": "owner", "type": "t_address", "offset": 0, "slot": "1"},
            {"contract": "Vault", "label": "__gap", "type": "t_array[t_uint256]_storage", "offset": 0, "slot": "2"}]}
        out = Path(tempfile.mkdtemp()) / "r.json"
        rc = ld.main(["--baseline", str(write(BASE)), "--current", str(write(cur)),
                      "--contract", "Vault", "--out", str(out)])
        self.assertEqual(rc, 2)
        rep = json.loads(out.read_text())
        self.assertTrue(any("slot moved" in c["issue"] for c in rep["collisions"]))

    def test_insertion_before_existing_detected(self):
        cur = {"storage": [
            {"contract": "Vault", "label": "inserted", "type": "t_uint256", "offset": 0, "slot": "0"},
            *BASE["storage"]]}
        out = Path(tempfile.mkdtemp()) / "r.json"
        rc = ld.main(["--baseline", str(write(BASE)), "--current", str(write(cur)),
                      "--contract", "Vault", "--out", str(out)])
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
