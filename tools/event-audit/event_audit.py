#!/usr/bin/env python3
"""HACVSP Event Audit Engine — AST mutation graph -> event emission verification.

Parses foundry build-info ASTs (solc legacy AST), extracts the state-mutation
graph for public/external functions, and verifies every critical-category
mutation (ownership, access, fees, pause, balances, core parameters) emits a
dedicated event with properly indexed identity topics.

Output: EVENT_EMISSION_AUDIT.json with:
  summary, missing_events[], indexing_warnings[], mutation_graph{}, suppressed[]
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


CATEGORIES = {
    "ownership": re.compile(r"owner|admin|role|authority|guardian|operator|signer|auth|access", re.I),
    "fees": re.compile(r"fee|rate|bps|premium|spread|reward", re.I),
    "pause": re.compile(r"pause|frozen|halt|circuit|locked", re.I),
    "balances": re.compile(r"balance|deposit|withdraw|share|debt|credit|collateral|escrow|principal|supply|stake", re.I),
    "parameters": re.compile(r"price|oracle|limit|cap|max\b|min\b|threshold|weight|ratio|quota|param|config|duration|deadline", re.I),
}


def classify(name: str) -> list[str]:
    return [cat for cat, rx in CATEGORIES.items() if rx.search(name)]


def iter_nodes(node: dict):
    """Yield node and all descendants."""
    stack = [node]
    while stack:
        n = stack.pop()
        if isinstance(n, dict):
            yield n
            stack.extend(v for v in n.values() if isinstance(v, (dict, list)))
        elif isinstance(n, list):
            stack.extend(n)


def base_identifier(node: dict) -> dict | None:
    """Unwrap Assignment/UnaryOp/IndexAccess/MemberAccess targets to the base Identifier."""
    while node:
        t = node.get("nodeType")
        if t == "Identifier":
            return node
        if t in ("IndexAccess",):
            node = node.get("baseExpression", {}) or {}
        elif t in ("MemberAccess",):
            node = node.get("expression", {}) or {}
        elif t in ("TupleExpression",):
            comps = node.get("components") or []
            node = comps[0] if comps else {}
        else:
            return None
    return None


class Audit:
    def __init__(self, build_info_dir: Path, categories_override: dict | None = None):
        self.state_vars: dict[int, dict] = {}       # varDecl id -> info
        self.state_vars_by_name: dict[str, dict] = {}
        self.events: dict[str, list[dict]] = {}     # event name -> definitions
        self.contracts: list[dict] = []
        self.functions: list[dict] = []
        self.sources: dict[str, dict] = {}
        if categories_override:
            for cat, pat in categories_override.items():
                CATEGORIES[cat] = re.compile(pat, re.I)
        self._load(build_info_dir)

    def _load(self, bdir: Path) -> None:
        for f in sorted(bdir.glob("*.json")):
            try:
                data = json.loads(f.read_text())
            except Exception:
                continue
            for src, payload in (data.get("output", {}).get("sources") or {}).items():
                self.sources[src] = payload.get("ast", {}) or {}

        for src, ast in self.sources.items():
            for node in ast.get("nodes", []):
                if node.get("nodeType") == "ContractDefinition":
                    self._load_contract(src, node)

    def _load_contract(self, src: str, cdef: dict) -> None:
        contract = {
            "source": src, "name": cdef.get("name", "?"),
            "kind": cdef.get("kind", "contract"), "functions": [], "modifiers": {},
        }
        if contract["kind"] != "contract":
            return
        for node in cdef.get("nodes", []):
            t = node.get("nodeType")
            if t == "VariableDeclaration" and not node.get("isParameter"):
                info = {
                    "name": node.get("name", ""),
                    "type": type_str(node.get("typeName")),
                    "categories": classify(node.get("name", "")),
                    "constant": node.get("constant", False),
                }
                if info["name"] and not info["constant"]:
                    self.state_vars[node.get("id")] = info
                    self.state_vars_by_name.setdefault(info["name"], info)
            elif t == "EventDefinition":
                params = [
                    {"name": p.get("name", ""), "type": type_str(p.get("typeName")),
                     "indexed": bool(p.get("indexed"))}
                    for p in node.get("parameters", {}).get("parameters", [])
                ]
                self.events.setdefault(node.get("name", ""), []).append(params)
            elif t == "FunctionDefinition":
                contract["functions"].append(node)
            elif t == "ModifierDefinition":
                contract["modifiers"][node.get("name", "")] = node
        self.contracts.append(contract)

    def _resolve_state_var(self, ident: dict) -> dict | None:
        info = self.state_vars.get(ident.get("referencedDeclaration"))
        if info:
            return info
        return self.state_vars_by_name.get(ident.get("name", ""))

    def _function_writes(self, fn: dict, contract: dict) -> tuple[set[str], set[str]]:
        """Return (critical vars written, all vars written) in a function incl. its modifiers."""
        writes: set[str] = set()
        critical: set[str] = set()

        def scan_block(block: dict) -> None:
            if not block:
                return
            for node in iter_nodes(block):
                t = node.get("nodeType")
                if t == "Assignment":
                    ident = base_identifier(node.get("leftHandSide", {}) or {})
                    if ident:
                        info = self._resolve_state_var(ident)
                        if info:
                            writes.add(info["name"])
                            if info["categories"]:
                                critical.add(info["name"])
                elif t == "UnaryOperation" and node.get("operator") in ("++", "--", "+=", "-=", "!=", "delete"):
                    ident = base_identifier(node.get("subExpression", {}) or {})
                    if ident:
                        info = self._resolve_state_var(ident)
                        if info:
                            writes.add(info["name"])
                            if info["categories"]:
                                critical.add(info["name"])

        scan_block(fn.get("body", {}) or {})
        for mod in fn.get("modifiers", []) or []:
            mname = ((mod.get("modifierName", {}) or {}).get("name")) or mod.get("modifierName", {}).get("namePath", {}).get("name") if isinstance(mod.get("modifierName"), dict) else None
            mdef = contract["modifiers"].get(mname) if mname else None
            if mdef:
                scan_block(mdef.get("body", {}) or {})

        return critical, writes

    def _function_emits(self, fn: dict) -> list[str]:
        return [
            ((n.get("eventCall", {}) or {}).get("expression", {}) or {}).get("name", "")
            for n in iter_nodes(fn.get("body", {}) or {})
            if n.get("nodeType") == "EmitStatement"
        ]

    @staticmethod
    def _event_has_indexed_identity(params: list[dict]) -> bool:
        return any(
            p["indexed"] and (
                p["type"].startswith("address") or p["type"].startswith("bytes32")
                or p["type"].startswith("uint") or p["type"].startswith("int")
                or p["type"] == "bytes20"
            ) for p in params
        )

    def audit(self) -> dict:
        missing, warnings, graph, suppressed = [], [], {}, []
        fn_count = crit_count = 0

        for contract in self.contracts:
            cgraph = {}
            for fn in contract["functions"]:
                if fn.get("visibility") not in ("public", "external"):
                    continue
                mut = fn.get("stateMutability", "nonpayable")
                if mut in ("view", "pure"):
                    continue
                fn_count += 1
                critical, writes = self._function_writes(fn, contract)
                emits = self._function_emits(fn)
                crit_count += len(critical)
                entry = {"writes": sorted(writes), "critical_writes": sorted(critical),
                         "emits": [e for e in emits if e]}
                if not writes:
                    continue
                cgraph[fn.get("name", "?")] = entry
                # Spec scope: ON-CHAIN contracts (src/**). Scripts/tests are
                # compiled into the same build-info but never ship — report
                # informationally only.
                on_chain = contract["source"].startswith("src/") or "/src/" in contract["source"]
                if critical and not emits and on_chain:
                    missing.append({
                        "contract": contract["name"], "source": contract["source"],
                        "function": fn.get("name") or "constructor",
                        "writes": sorted(critical),
                        "categories": sorted({c for v in critical
                                              for c in (self.state_vars_by_name.get(v, {}).get("categories") or [])}),
                    })
                elif critical and not on_chain and emits == []:
                    pass  # off-chain fixture gap — recorded in mutation_graph only
                elif critical:
                    for ev in emits:
                        ev = (ev or "").strip()
                        for params in self.events.get(ev, []):
                            if not self._event_has_indexed_identity(params) and on_chain:
                                warnings.append({
                                    "contract": contract["name"], "function": fn.get("name") or "constructor",
                                    "event": ev,
                                    "issue": "no indexed identity topic (actor/target address, id)",
                                })
            if cgraph:
                graph[f"{contract['source']}::{contract['name']}"] = cgraph

        return {
            "summary": {
                "contracts": len(self.contracts),
                "functions_audited": fn_count,
                "critical_writes": crit_count,
                "missing_event_failures": len(missing),
                "indexing_warnings": len(warnings),
                "suppressed": 0,
            },
            "missing_events": missing,
            "indexing_warnings": warnings,
            "mutation_graph": graph,
            "suppressed": suppressed,
        }


def apply_suppressions(audit: dict, supp_path: Path | None) -> dict:
    if not supp_path or not supp_path.exists():
        return audit
    try:
        entries = json.loads(supp_path.read_text())
    except Exception:
        return audit
    kept_missing, kept_warn = [], []
    for m in audit["missing_events"]:
        hit = any(
            e.get("tool") == "event-audit" and e.get("finding_id") == "missing-event"
            and (m.get("source", "") or "").endswith(e.get("file", "\0"))
            for e in entries if isinstance(e, dict)
        )
        (audit["suppressed"].append(m) if hit else kept_missing.append(m))
    for w in audit["indexing_warnings"]:
        hit = any(
            e.get("tool") == "event-audit" and e.get("finding_id") == "unindexed-event"
            and w.get("contract", "") in str(e.get("file", "\0"))
            for e in entries if isinstance(e, dict)
        )
        (audit["suppressed"].append(w) if hit else kept_warn.append(w))
    audit["missing_events"] = kept_missing
    audit["indexing_warnings"] = kept_warn
    audit["summary"]["missing_event_failures"] = len(kept_missing)
    audit["summary"]["indexing_warnings"] = len(kept_warn)
    audit["summary"]["suppressed"] = len(audit["suppressed"])
    return audit


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--build-info", type=Path, required=True)
    ap.add_argument("--suppressions", type=Path, default=None)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)

    if not args.build_info.exists() or not list(args.build_info.glob("*.json")):
        print(f"[event-audit] no build-info JSON under {args.build_info}", file=sys.stderr)
        return 1

    audit = Audit(args.build_info).audit()
    audit = apply_suppressions(audit, args.suppressions)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(audit, indent=2) + "\n")
    s = audit["summary"]
    print(f"[event-audit] contracts={s['contracts']} functions={s['functions_audited']} "
          f"critical_writes={s['critical_writes']} missing={s['missing_event_failures']} "
          f"index_warnings={s['indexing_warnings']} suppressed={s['suppressed']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
