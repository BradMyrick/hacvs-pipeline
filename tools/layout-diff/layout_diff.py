#!/usr/bin/env python3
"""HACVSP Layout Diff Engine — storage layout preservation & upgrade safety.

Compares two `forge inspect <Contract> storage-layout --json` dumps and:
  * flags any slot/type/offset alteration of pre-existing variables
  * flags insertions before existing variables
  * verifies __gap integrity (gap shrinkage must equal variables added before it)
  * verifies Diamond/ERC-7201 namespace structure is unchanged across versions

Output JSON: {collisions: [...], gap_issues: [...], namespace_issues: [...],
              ok: bool, summary: {...}}
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def load_layout(path: Path) -> dict:
    return json.loads(path.read_text())


def layout_rows(layout: dict) -> list[dict]:
    """forge storage-layout json: {'storage': [{contract, label, type, offset, slot}]}"""
    rows = layout.get("storage", layout if isinstance(layout, list) else [])
    return rows


def diff_layouts(base: dict, cur: dict, contract: str) -> dict:
    base_rows = [r for r in layout_rows(base)]
    cur_rows = [r for r in layout_rows(cur)]
    base_names = {r["label"]: r for r in base_rows}
    cur_names = {r["label"]: r for r in cur_rows}

    collisions, gap_issues = [], []

    # 1) pre-existing vars must keep slot+type+offset
    max_base_slot = max((int(r["slot"]) for r in base_rows), default=-1)
    for name, brow in base_names.items():
        crow = cur_names.get(name)
        if crow is None:
            collisions.append({"contract": contract, "var": name,
                               "issue": "variable removed from layout"})
            continue
        if brow["slot"] != crow["slot"]:
            collisions.append({"contract": contract, "var": name,
                               "issue": f"slot moved {brow['slot']} -> {crow['slot']}"})
        if brow["type"] != crow["type"]:
            collisions.append({"contract": contract, "var": name,
                               "issue": f"type changed {brow['type']} -> {crow['type']}"})
        if str(brow.get("offset")) != str(crow.get("offset")):
            collisions.append({"contract": contract, "var": name,
                               "issue": f"offset changed {brow.get('offset')} -> {crow.get('offset')}"})

    # 2) new variables must appear AFTER all pre-existing slots
    for name, crow in cur_names.items():
        if name in base_names:
            continue
        if int(crow["slot"]) <= max_base_slot:
            collisions.append({"contract": contract, "var": name,
                               "issue": f"new variable inserted at slot {crow['slot']} "
                                        f"<= baseline max slot {max_base_slot}"})

    # 3) __gap integrity: shrinkage must equal count of new vars placed before the gap
    base_gap = base_names.get("__gap")
    cur_gap = cur_names.get("__gap")
    if base_gap and cur_gap:
        base_len = _array_length(base, base_gap)
        cur_len = _array_length(cur, cur_gap)
        if base_len is not None and cur_len is not None:
            added_before_gap = sum(
                1 for n, c in cur_names.items()
                if n not in base_names and n != "__gap"
                and int(c["slot"]) < int(cur_gap["slot"])
            )
            expected = base_len - added_before_gap
            if cur_len != expected:
                gap_issues.append({
                    "contract": contract,
                    "issue": f"__gap size {cur_len} != expected {expected} "
                             f"(baseline {base_len} - {added_before_gap} added vars)",
                })
    elif base_gap and not cur_gap:
        gap_issues.append({"contract": contract,
                           "issue": "__gap removed in current layout"})

    return {"contract": contract, "collisions": collisions, "gap_issues": gap_issues}


def _array_length(layout: dict, row: dict) -> int | None:
    t = row.get("type", "")
    m = None
    import re
    m = re.match(r"t_array\[(\d+)\]", t) or re.match(r".*\[(\d+)\]$", t)
    if m:
        return int(m.group(1))
    return None


def namespace_check(base_src: Path | None, cur_src: Path | None) -> list[dict]:
    """ERC-7201 namespaces must be identical strings across versions."""
    import re
    issues = []
    pat = re.compile(r"keccak256\(abi\.encode\([^)]*\)\)[^;]*?/\x20*([a-z0-9_.\-]+\.erc7201[a-z0-9_.\-]*)\x20*/", re.I)
    def extract(p):
        if not p or not p.exists():
            return set()
        found = set()
        for f in p.rglob("*.sol"):
            try:
                text = f.read_text()
            except Exception:
                continue
            for m in re.finditer(r"([\w.\-]+\.erc7201[\w.\-]*)", text):
                found.add(m.group(1))
        return found
    b, c = extract(base_src), extract(cur_src)
    if b and b != c:
        for ns in sorted(c - b):
            issues.append({"issue": f"new ERC-7201 namespace introduced: {ns}"})
        for ns in sorted(b - c):
            issues.append({"issue": f"ERC-7201 namespace removed: {ns}"})
    return issues


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--baseline", type=Path, required=True)
    ap.add_argument("--current", type=Path, required=True)
    ap.add_argument("--contract", default="?")
    ap.add_argument("--baseline-src", type=Path, default=None)
    ap.add_argument("--current-src", type=Path, default=None)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)

    base, cur = load_layout(args.baseline), load_layout(args.current)
    report = diff_layouts(base, cur, args.contract)
    report["namespace_issues"] = namespace_check(args.baseline_src, args.current_src)
    report["ok"] = not (report["collisions"] or report["gap_issues"] or report["namespace_issues"])
    report["summary"] = {
        "collisions": len(report["collisions"]),
        "gap_issues": len(report["gap_issues"]),
        "namespace_issues": len(report["namespace_issues"]),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(f"[layout-diff] {args.contract}: collisions={report['summary']['collisions']} "
          f"gap_issues={report['summary']['gap_issues']} "
          f"ns_issues={report['summary']['namespace_issues']}")
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    sys.exit(main())
