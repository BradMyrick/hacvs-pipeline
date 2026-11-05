# Stage 4 Runbook — Event Completeness & Indexing Verification

**Cadence:** PR tier · **Gate:** GO/NO-GO
**Spec criteria:** _Zero missing events on state-modifying functions; all primary entity identifiers correctly indexed._

## Objective
Verify that all critical state mutations emit strongly typed events with appropriate indexed topics for monitoring, subgraphs, and incident triage.

## Tools
- **Event Audit Engine** (`tools/event-audit`, stdlib Python over foundry build-info ASTs) — extracts the state-mutation graph and verifies a matching event emission for every critical mutation.
- **AiWrangler MCP** (0.1.5, MCP server — not a CLI) — the pipeline agent drives it over MCP to triage the AST state diffs and mutation graph, and to record human-review acknowledgements for any human-severity findings (stored in `review/aiwrangler-acks.json`, ratified at Stage 13).
- Slither — cross-check with its event detectors (recorded to `artifacts/slither-events.json`).

## Spec rules encoded
1. Every mutation of a **critical-category** state variable (ownership, roles/access, fees, pause, balances, core protocol parameters) inside a public/external function must emit at least one event in that function.
2. Events touching critical categories must have at least one `indexed` parameter of an actor/target identity type (address/bytes32/uint id).
3. Mutations performed directly via `emit` ordering (checks-effects-events before external interaction) are reviewed by Slither's reentrancy detectors in Stage 3; this stage verifies *presence*, Stage 3 verifies *ordering*.

## Critical-category heuristics
Name/type-based, overridable per engagement in `engagement.json → event_audit.categories`:
`owner|admin|role|authority` → ownership; `fee|rate|bps` → fees; `paused|guard` → pause; `balance|deposit|share|debt|collateral` → balances; `price|oracle|limit|cap` → parameters.

## Suppressions
`{tool: "event-audit", finding_id: "missing-event"|"unindexed-event", file, line_range, ...}` in `.security-suppressions.json` (same governance as Stage 3).

## Gate evaluation
`gate.py` requires: zero missing-event failures, zero un-suppressed indexing warnings.
