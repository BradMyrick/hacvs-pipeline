#!/usr/bin/env python3
"""HACVSP Access Matrix Extractor — AST entry-point/guard extraction.

Extracts every public/external function per contract with its guard modifiers,
classifies allowed roles (heuristic, expert-confirmed at Stage 13), detects
pausable/timelock properties, and emits:
  * artifacts/ACCESS_CONTROL_MATRIX.json  (machine)
  * artifacts/ACCESS_CONTROL_MATRIX.md    (human/expert)
  * test/access-control/GeneratedAccessMatrix.t.sol (assertion harness)

Role heuristics (modifier name -> role):
  onlyOwner/onlyAdmin/owner           -> OWNER
  onlyRole(<ROLE>)/hasRole(<ROLE>)    -> <ROLE>
  onlyTimelock/onlyGuardian           -> TIMELOCK/GUARDIAN
  nonReentrant/validAddress/...       -> (not auth) ignored
  no auth modifier on state-changing  -> PUBLIC  (expert must ratify)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

def type_str(type_name: dict) -> str:
    """solc AST type: typeDescriptions.typeString (0.8.x) with description fallback."""
    td = (type_name or {}).get("typeDescriptions", {}) or {}
    return td.get("typeString") or (type_name or {}).get("description") or ""


AUTH_PATTERNS = [
    (re.compile(r"onlyowner|onlyadmin|_?auth(?:orize)?$", re.I), "OWNER"),
    (re.compile(r"onlyrole|hasrole|requiresrole|role\b", re.I), "ROLE"),
    (re.compile(r"onlytimelock|timelock", re.I), "TIMELOCK"),
    (re.compile(r"onlyguardian|guardian", re.I), "GUARDIAN"),
    (re.compile(r"onlypauser|onlyemergency|emergency", re.I), "EMERGENCY"),
    (re.compile(r"onlyminter|onlyburner|onlyoperator|onlystrategy|onlymanager|onlyvault|onlycontroller", re.I), "OPERATOR"),
    (re.compile(r"onlyself|onlythis|internal$", re.I), "SELF"),
]
ZERO_VALUES = {
    "address": "address(0)", "address payable": "address(0)",
    "bool": "false", "string": '""', "bytes": '""',
}


def classify_role(modifiers: list[dict], body_require_auth: bool) -> list[str]:
    roles: list[str] = []
    for mod in modifiers:
        name = (mod.get("name") or "").strip()
        for rx, role in AUTH_PATTERNS:
            if rx.search(name):
                arg = (mod.get("arg") or "").strip().strip('"')
                roles.append(f"{role}({arg})" if arg and role == "ROLE" else role)
                break
    if body_require_auth and not roles:
        roles.append("AUTH-REQUIRED")  # require-based auth the AST sniff detected
    return sorted(set(roles)) or ["PUBLIC"]


def extract(build_info_dir: Path) -> list[dict]:
    rows: list[dict] = []
    for f in sorted(build_info_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text())
        except Exception:
            continue
        for src, payload in (data.get("output", {}).get("sources") or {}).items():
            ast = payload.get("ast", {}) or {}
            for node in ast.get("nodes", []):
                # solc 0.8.38 build-info ASTs may omit ContractDefinition.kind —
                # default to "contract" (interfaces/libraries still labeled).
                if node.get("nodeType") != "ContractDefinition":
                    continue
                if (node.get("kind") or "contract") != "contract":
                    continue
                cname = node.get("name", "?")
                for fn in node.get("nodes", []):
                    if fn.get("nodeType") != "FunctionDefinition":
                        continue
                    vis = fn.get("visibility", "internal")
                    if vis not in ("public", "external"):
                        continue
                    mods = []
                    for m in fn.get("modifiers", []) or []:
                        mname_node = (m or {}).get("modifierName", {}) or {}
                        name = mname_node.get("name") or (
                            mname_node.get("namePath", {}) or {}).get("name", "")
                        args = m.get("arguments") or []
                        arg = ""
                        if args and isinstance(args[0], dict) and args[0].get("nodeType") == "Identifier":
                            arg = args[0].get("name", "")
                        elif args and isinstance(args[0], dict) and args[0].get("nodeType") == "Literal":
                            arg = (args[0].get("value") or "")
                        if name:
                            mods.append({"name": name, "arg": arg})
                    mod_names = " ".join(m["name"].lower() for m in mods)
                    params = [
                        (type_str(p.get("typeName")) or "?")
                        for p in (fn.get("parameters", {}) or {}).get("parameters", [])
                    ]
                    state_changing = fn.get("stateMutability", "nonpayable") not in ("view", "pure")
                    # require-based auth sniff: identifier named *role*/owner in a require call
                    body_text = json.dumps(fn.get("body", {}))
                    require_auth = bool(re.search(r'"\s*(not\s+)?(owner|role|admin|authorized|paused)',
                                                  body_text, re.I)) and "require(" in body_text
                    roles = classify_role(mods, require_auth and state_changing)
                    rows.append({
                        "contract": cname,
                        "source": src,
                        "function": fn.get("name", "?"),
                        "function_signature": f"{fn.get('name','?')}({','.join(params)})",
                        "param_types": params,
                        "allowed_roles": roles,
                        "state_changing": state_changing,
                        "is_pausable": bool(re.search(r"pause|whennotpaused", mod_names)),
                        "timelock_delay_seconds": None
                        if "TIMELOCK" not in " ".join(roles)
                        else "GETTER-INTROSPECT",  # expert fills from config review
                        "modifiers": [f"{m['name']}({m['arg']})".rstrip("()") for m in mods],
                    })
    return rows


def to_markdown(rows: list[dict]) -> str:
    lines = [
        "# ACCESS CONTROL MATRIX (generated — Stage 8)",
        "",
        "| Contract | Function | Signature | Allowed Roles | Pausable | Timelock | State-changing |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['contract']} | {r['function']} | `{r['function_signature']}` "
            f"| {', '.join(r['allowed_roles'])} | {r['is_pausable']} "
            f"| {r['timelock_delay_seconds'] or '-'} | {r['state_changing']} |"
        )
    lines += [
        "",
        "_PUBLIC + state_changing=true rows demand explicit expert ratification at Stage 13._",
    ]
    return "\n".join(lines) + "\n"


def zero_arg(t: str) -> str | None:
    t = t.strip()
    if t in ZERO_VALUES:
        return ZERO_VALUES[t]
    if re.match(r"^u?int\d*$", t):
        return "0"
    if re.match(r"^bytes\d+$", t):
        return '""'
    if t.endswith("]"):
        return None  # arrays: manual row
    return None  # structs/enums/contracts: manual row


def generate_harness(rows: list[dict], target_contract: str | None) -> str:
    """Foundry harness: unprivileged caller must revert on every non-PUBLIC row."""
    automated, manual = [], []
    for r in rows:
        if not r["state_changing"]:
            continue
        args = [zero_arg(t) for t in r["param_types"]]
        fn_name = f"matrix_{r['contract']}_{r['function']}".replace("[", "_").replace("]", "")
        if all(a is not None for a in args):
            automated.append((fn_name, r, args))
        else:
            manual.append((fn_name, r))
    target = target_contract or "TODO_TARGET_CONTRACT"
    out = [
        "// SPDX-License-Identifier: MIT",
        "pragma solidity >=0.8.38 <0.9.0;",
        "",
        "import {Test} from \"forge-std/Test.sol\";",
        f"import {{{target}}} from \"src/...\"; // OPERATOR: wire import + setUp target",
        "",
        "contract GeneratedAccessMatrix is Test {",
        f"    {target} target;",
        "    address constant UNPRIV = address(0xBEEF); // non-privileged actor",
        "",
        "    function setUp() public virtual {",
        "        // OPERATOR: deploy/attach target here",
        "        vm.label(UNPRIV, \"unprivileged\");",
        "    }",
        "",
    ]
    for fn_name, r, args in automated:
        expect = "PUBLIC" in " ".join(r["allowed_roles"])
        call = f"target.{r['function']}({', '.join(args)})"
        if expect:
            out += [
                f"    /// matrix: {r['contract']}.{r['function_signature']} "
                f"roles={','.join(r['allowed_roles'])} (PUBLIC — informational)",
                f"    function {fn_name}() public {{",
                f"        vm.prank(UNPRIV);",
                f"        try {call} {{}} catch (bytes memory) {{}}",
                "    }",
                "",
            ]
        else:
            out += [
                f"    /// matrix: {r['contract']}.{r['function_signature']} "
                f"roles={','.join(r['allowed_roles'])} — MUST revert for UNPRIV",
                f"    function {fn_name}() public {{",
                f"        vm.prank(UNPRIV);",
                f"        vm.expectRevert();",
                f"        {call};",
                "    }",
                "",
            ]
    if manual:
        out += [
            "    // ------------------------------------------------------------------",
            "    // MANUAL ROWS (complex arg types) — implement in ManualAccessMatrix.t.sol:",
            "    // each must assert revert for UNPRIV or document PUBLIC intent.",
        ]
        for fn_name, r in manual:
            out.append(f"    //   {fn_name}: {r['function_signature']} roles={','.join(r['allowed_roles'])}")
    out += ["}", ""]
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--build-info", type=Path, required=True)
    ap.add_argument("--out-json", type=Path, required=True)
    ap.add_argument("--out-md", type=Path, required=True)
    ap.add_argument("--harness", type=Path, default=None)
    ap.add_argument("--target-contract", default=None)
    args = ap.parse_args(argv)

    rows = extract(args.build_info)
    matrix = {
        "schema": ["contract", "function_signature", "allowed_roles",
                   "is_pausable", "timelock_delay_seconds"],
        "rows": rows,
        "summary": {
            "contracts": len({r["contract"] for r in rows}),
            "entry_points": len(rows),
            "state_changing": sum(1 for r in rows if r["state_changing"]),
            "public_state_changing": sum(
                1 for r in rows if r["state_changing"] and "PUBLIC" in r["allowed_roles"]),
        },
    }
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(matrix, indent=2) + "\n")
    args.out_md.write_text(to_markdown(rows))
    if args.harness:
        args.harness.parent.mkdir(parents=True, exist_ok=True)
        args.harness.write_text(generate_harness(rows, args.target_contract))
    print(f"[access-matrix] {len(rows)} entry points across "
          f"{matrix['summary']['contracts']} contracts; "
          f"{matrix['summary']['public_state_changing']} PUBLIC state-changing rows")
    return 0 if rows else 1


if __name__ == "__main__":
    sys.exit(main())
