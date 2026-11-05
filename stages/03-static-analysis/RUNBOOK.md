# Stage 3 Runbook — Spec Linting & Static Analysis

**Cadence:** PR tier · **Gate:** GO/NO-GO
**Spec criteria:** _Zero unsuppressed static warnings; 100% of suppression entries cryptographically signed and structurally valid._

## Objective
Execute static analysis, detect unbounded loops/gas griefing, parse specification annotations, and enforce suppression governance.

## Tools (pinned)
- Scribble 0.7.10 — parse/validate inline spec annotations (`/// #if_succ`, `/// #invariant`, …). Instrumented output is also consumed by fuzzing (Stage 10) and proving (Stage 12) corpora.
- Slither 0.11.6 — `--json`, `--sarif`, `--checklist` (the checklist seeds expert triage).
- Aderyn 0.6.8 — SARIF output.
- SARIF Aggregator (`tools/sarif-aggregator`) — normalizes both engines and enforces suppression governance.

## What the runner does
1. Parses scribble annotations (missing annotations are recorded, not failed — the corpus may legitimately be zero on non-annotated repos, flagged at Stage 13 spec audit).
2. Runs Slither (JSON + SARIF + checklist) and Aderyn (SARIF).
3. Aggregates findings across engines; applies `.security-suppressions.json`.

## Suppression governance (spec-mandated schema)
Every suppression entry **must** carry:
```json
{
  "tool": "slither|aderyn|trivy|event-audit|mythril|...",
  "finding_id": "reentrancy-eth",
  "file": "src/Vault.sol",
  "line_range": "120-134",
  "git_commit_hash": "<40-char sha>",
  "justification": "...",
  "reviewer": "principal-security-engineer",
  "reviewer_signature": "<cosign sign-blob sig over the canonical entry digest>"
}
```
The aggregator canonicalizes each entry (sorted-key JSON of tool/finding_id/file/line_range/commit), hashes it, and treats `reviewer_signature` as a detached cosign/GPG signature over that digest. Structural validity is enforced here; cryptographic verification runs when `COSIGN_KEY`/`KODR_PUBKEY` is present, and every entry is re-ratified by the expert at Stage 13.

## Gate evaluation
`gate.py` requires: both engine reports present, unsuppressed critical/high/medium `== 0`, zero invalid/unsigned suppression entries.

## Operator notes
- Suppress low/informational freely; anything medium+ needs a signed justification.
- Slither triage: `artifacts/slither-checklist.md` is the markdown triage doc — annotate it during review and archive it in the bundle at Stage 14.
