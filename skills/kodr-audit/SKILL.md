---
name: kodr-audit
description: End-to-end audit engagement methodology for Kodr.pro — intake, tiered execution, triage, expert checkpoints, threat modeling, spec audit, sign-off, and bundle publication using HACVSP. Use when the user asks to AUDIT a contract repo or produce a Kodr.pro audit deliverable. Load hacvsp first for the operator mechanics. For contract-safety domain knowledge during review, also load blockchain-contract-safety, blockchain-gas-mev, blockchain-bridges-security as applicable.
version: 0.1.0
---

# Skill: Kodr.pro Audit Engagement

## System Reference: Expert-in-the-Loop Assurance (RFC-Style Methodology)

### 1. Core Model

An audit is an **engagement** (`hacvsp audit <repo>`), not a command run. The
agent automates evidence; the Principal Security Engineer (the user) is the
authority at defined checkpoints. Automation never replaces judgment on:
business-logic correctness, economic design, threat-model completeness.

Residual risk statement (quote in every deliverable): assurance is bounded by
specification completeness and expert-review quality — not a guarantee against
novel economic attacks.

### 2. Engagement Flow (execute in order)

**Step 1 — Intake (ask the user; write answers into `engagements/<slug>/intake.md` + `engagement.json`):**
1. Architecture: proxy pattern(s)? Diamond facets? upgradeable?
2. Standards: which ERCs apply (or NONE)?
3. Core contracts for mutation triage?
4. External integrations: oracles, DEXs, lenders → fork-test scope?
5. Mainnet-fork RPC available (name only; value → engagement `.env`)?
6. Baseline commit for upgrade diffs (or first audit)?
7. Client whitepaper/docs URL for the spec audit?
Then: `hacvsp audit <repo> --commit <sha> --name <slug>`; fill applicability.

**Step 2 — PR tier:** run stages 1→7 sequentially. On NO_GO:
triage the failure list from the ledger (`hacvsp status`), fix target repo
issues (with user consent), or draft a signed suppression, then `hacvsp gate N`.

**Step 3 — Checkpoint (user):** ratify suppressions + coverage exceptions.
Present: findings table, proposed suppressions with justifications, coverage
gaps with exception drafts. The user signs or rejects.

**Step 4 — Release tier:** stages 8→12 (9/10/12 usually `--detach` overnight).
**Step 5 — Stage 13 (the user's lane; agent prepares drafts):**
- Draft `review/THREAT_MODEL.md` — sections: Actor Matrix, Trust Boundaries,
  Economic Vectors, MEV Exposure. Mine evidence: ACCESS_CONTROL_MATRIX.json
  PUBLIC rows, event audit gaps, mythril delegatecall/selfdestruct hits,
  fork-test oracle behavior.
- Draft `review/SPEC_AUDIT.md` — sections: Invariant Completeness, Whitepaper
  Concordance. Map every stated invariant to its enforcing test/proof.
- As agent (frontier-model triage): adversarial diff analysis (commit range),
  semantic checklist vs whitepaper, corpus-completeness review of proofs.
- User reviews, edits, and signs (`/hacvsp-signoff` drives cosign flow).
**Step 6 — Stage 14:** `hacvsp stage 14` assembles + signs the bundle
(SECURITY_ASSURANCE.md + artifacts + signatures). Publish the engagement dir.

### 3. Operational Rules

* **Rule 1 (Never skip intake).** Empty applicability lists fail-closed for a
  reason — an undeclared Diamond is an unaudited Diamond.
* **Rule 2 (Triage before suppression).** A suppression is a finding the
  expert accepts with a written, signed justification — not a mute button.
* **Rule 3 (Evidence-first reporting).** Every claim in a deliverable cites a
  ledger verdict, an artifact file, or a signed suppression. No vibes.
* **Rule 4 (Frontier-model boundaries).** The agent drafts and cross-checks;
  it never signs. Structural signoff mode is dry-run only.
* **Rule 5 (AiWrangler MCP).** Use wrangler tools over MCP for AST-diff triage
  and record human-severity acknowledgements (`review/aiwrangler-acks.json`).
* **Rule 6 (Deployment verification).** If addresses are declared, map each to
  Sourcify/explorer exact-match evidence in the assurance doc.

### 4. NO_GO Triage Playbook

| Gate failure | First response |
|---|---|
| Stage 1 CVEs | check advisory relevance to Solidity libs; suppress with justification or bump pin |
| Stage 2 non-reproducible | find nondeterminism (metadata, paths, timestamps) |
| Stage 3 static findings | classify true/false-positive; fix code or sign suppression |
| Stage 4 missing events | add events (correct fix); suppression only for view-adjacent edge |
| Stage 5 collisions | STOP — layout rework or explicit migration plan; never suppress |
| Stage 7 coverage | add tests; exceptions only for unreachable compiler artifacts |
| Stage 8 access | STOP if PUBLIC row surprises the expert — potential critical |
| Stage 9 survivors | write the missing assertion; equivalence only with proof |
| Stage 10 violations | STOP — reproduce, minimize, treat as critical until dismissed |
| Stage 11 counterexamples | STOP — concrete attack path; treat as finding |
| Stage 12 failed proofs | STOP — bytecode-level counterexample; treat as critical |
| Stage 13 unsigned | the expert must actually sign; no automation shortcut |

### 5. Deliverable Quality Bar

- SECURITY_ASSURANCE.md renders all five mandatory sections with the ledger table.
- Suppression inventory complete: tool, rule id, file/line, justification,
  reviewer, commit SHA — every row signed.
- Threat model names every actor with capability + motivation; every trust
  boundary has a compensating control mapped to a stage or suppression.
