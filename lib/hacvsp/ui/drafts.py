"""Stage-13 review doc drafts — generated from real engagement evidence.

An auditor should never face a blank page: the draft pre-populates every
mandatory section with what the pipeline already knows (actors from the
access matrix, invariants from the proof corpus, suppressions awaiting
ratification), leaving structured room for expert judgment.
"""
from __future__ import annotations

import json
from pathlib import Path

from .. import spec


def _art(slug: str, name: str):
    p = spec.REPO_ROOT / "engagements" / slug / "artifacts" / name
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:  # noqa: BLE001
            return {}
    return {}


def _suppressions(slug: str) -> list[dict]:
    p = spec.REPO_ROOT / "engagements" / slug / "target" / ".security-suppressions.json"
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:  # noqa: BLE001
            return []
    return []


def _untriaged_statics(slug: str) -> list[dict]:
    return (_art(slug, "static-analysis-summary.json")
            .get("unsuppressed_findings", []) or [])


def threat_model_draft(slug: str) -> str:
    am = _art(slug, "ACCESS_CONTROL_MATRIX.json")
    rows = am.get("rows", [])
    pub = [r for r in rows if r.get("state_changing") and "PUBLIC" in r.get("allowed_roles", [])]
    priv = [r for r in rows if r.get("state_changing") and "PUBLIC" not in r.get("allowed_roles", [])]

    actor_rows = "\n".join(
        f"| {r['contract']}.{r['function']} | {', '.join(r['allowed_roles'])} | <fill: trust level> | <fill: capability> | <fill: motivation> |"
        for r in priv + pub) or "| _(none extracted)_ | | | | |"

    pub_list = "\n".join(
        f"- [ ] `{r['contract']}.{r['function']}` — PUBLIC by design? annotate expected caller and abuse case"
        for r in pub) or "- _(no PUBLIC state-changing functions — confirm at review)_"

    untriaged = "\n".join(
        f"- [ ] `{f.get('engine')}/{f.get('check')}` @ {f.get('file')}:{f.get('lines')} — assess exploitability"
        for f in _untriaged_statics(slug)) or "- _(inbox empty)_"

    return f"""# THREAT_MODEL.md — {slug}

## Actor Matrix

_Checklist: every privileged entry point from the access matrix is rowed and
assessed; every PUBLIC state-changing function is explicitly confirmed._

- [ ] All privileged ({len(priv)}) entry points reviewed
- [ ] All PUBLIC ({len(pub)}) state-changing functions confirmed intentional
- [ ] Untriaged static findings assessed for exploitability

| Entry point | Roles | Trust | Capability | Motivation |
|---|---|---|---|---|
{actor_rows}

### PUBLIC-function scrutiny (must be intentional)

{pub_list}

### Untriaged static findings

{untriaged}

## Trust Boundaries

_Checklist: enumerate every boundary where control crosses a trust line._

- [ ] Native-asset custody boundary (escrow/prepayment custody mapped)
- [ ] External-call boundaries (every `.call`/interface target listed)
- [ ] Admin/privilege boundary (owner powers enumerated, timelock status)
- [ ] Upgrade/deployment boundary (proxy status confirmed, key custody)

<fill: boundary 1 — who holds what, what crosses, what enforces safety>

<fill: boundary 2 — ...>

## Economic Vectors

_Checklist: each value-flow is gamed on paper — describe the attack and the
control that blocks it._

- [ ] Custody drain vectors (escrow withdrawal paths reviewed)
- [ ] Gas/ griefing vectors (costless spam, unbounded work per call)
- [ ] Tip/reward extraction abuse (keeper economics)
- [ ] Rounding/dust accumulation reviewed
- [ ] Upgrade/deployment boundary reviewed

<fill: vector — attack description, precondition, control>

## MEV Exposure

_Checklist: ordering, backrunning, sandwich surfaces._

- [ ] Executor races (first-mover advantage for tips — priority/censorship risk)
- [ ] Backrunning opportunities (profitable follow-on transactions)
- [ ] Oracle/state-dependence ordering risks
- [ ] Cross-domain sequencing (if multi-chain)

<fill: exposure — who can reorder what, and what it costs them>
"""


def spec_audit_draft(slug: str) -> str:
    import re
    proofs_dir = spec.REPO_ROOT / "engagements" / slug / "target" / "test" / "proofs"
    proof_names = []
    if proofs_dir.exists():
        for f in proofs_dir.glob("*.t.sol"):
            proof_names += re.findall(r"function (test_Proof_\w+)", f.read_text())
    mutation = _art(slug, "mutation-report.json")
    survivors = mutation.get("survivors", []) or []
    surv = "\n".join(
        f"- [ ] Mutant #{s.get('id')} ({s.get('op')}) — equivalence confirmed or test to add"
        for s in survivors) or "- _(no surviving mutants)_"

    return f"""# SPEC_AUDIT.md — {slug}

## Invariant Completeness

_Checklist: every stated invariant is mapped to the machine evidence that
enforces it; every gap is a finding, not an omission._

- [ ] Every business invariant from the whitepaper/product docs is listed below
- [ ] Each invariant maps to at least one of: proof corpus, invariant fuzzing,
      unit/differential tests, or a documented residual-risk note
- [ ] Proof corpus non-vacuity confirmed (see review/KONTROL_VACUITY.md)

| Invariant | Enforced by | Confidence | Gap? |
|---|---|---|---|
| Escrow exact accounting (deposit/withdraw/register) | hevm proofs + mutation kills | <fill> | |
| Coverage fail-closed + terms-extend-only | Kontrol + hevm proofs | <fill> | |
| Access-control matrix enforced | stage-8 wired harness (17 tests) | <fill> | |
| Reentrancy safety (executeJob/withdraw) | suppression w/ nonReentrant + F-1 defense | <fill> | |
| Consecutive-revert circuit breaker semantics | test_Kill237 + fuzz | <fill> | |
| <fill: invariant from whitepaper> | <fill> | | |

### Formal proof corpus ({len(proof_names)} properties)

{chr(10).join(f"- [x] {n}" for n in proof_names) or "- _(no proof corpus)_"}

## Whitepaper Concordance

_Checklist: the written intent is the spec; the code is checked against it._

- [ ] Product whitepaper/docs read in full; invariants extracted (list above)
- [ ] Each documented flow traced through actual code paths
- [ ] Undocumented behaviors found in code are flagged as findings
- [ ] Suppression justifications re-checked against stated intent

<fill: concordance note — where code and docs agree>

<fill: divergence — where they don't, with severity>

### Mutation survivors re-confirmed

{surv}
"""


def signoff_draft(slug: str) -> str:
    from .sign import canonical_entry_digest
    supps = _suppressions(slug)
    rat_lines = []
    for e in supps:
        d = canonical_entry_digest(e)
        rat_lines.append(f"- [ ] `{d[:12]}` — {e.get('tool')}/{e.get('finding_id')} "
                         f"@ {e.get('file')}:{e.get('line_range')} — ratified")
    rat_block = "\n".join(rat_lines) or "- _(no suppressions)_"

    return f"""# MANUAL_REVIEW_SIGNOFF.md — {slug}

## High-Risk Assembly

- [ ] Assembly blocks reviewed (or confirmed absent) in all core contracts
- [ ] Any assembly usage justified, bounds-checked, and unit-tested

<fill: findings or 'none present'>

## Internal Accounting

- [ ] Escrow/prepayment math reviewed line-by-line (worst-case cost, rounding)
- [ ] Value-conservation checked across every payout path
- [ ] Mutation survivors in accounting paths killed or proven equivalent

<fill: findings or 'clean'>

## Suppression Audit

_Every suppression digest below must be checked (ratified) before sign-off._
_The stage-13 gate verifies each 12-hex prefix appears in this file._

{rat_block}

## Signature

- [ ] THREAT_MODEL.md reviewed and complete
- [ ] SPEC_AUDIT.md reviewed and complete
- [ ] All checklist items above either checked or annotated with reason

Reviewer: <fill>
Date: <fill>
Statement: I certify that I have reviewed the threat model, verified invariant
completeness against stated business intent, and ratify every suppression
listed above.
"""


DRAFTS = {
    "THREAT_MODEL.md": threat_model_draft,
    "SPEC_AUDIT.md": spec_audit_draft,
    "MANUAL_REVIEW_SIGNOFF.md": signoff_draft,
}
