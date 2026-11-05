# Stage 9 Runbook — Mutation Testing

**Cadence:** RELEASE tier · **Gate:** GO/NO-GO · **Long-running: `hacvsp stage 9 --engagement <slug> --detach`**

**Spec criteria:** _Mutation kill rate meets or exceeds 90%; zero unaddressed live mutants in core accounting logic._

## What the runner does
1. Generates a semantic mutant corpus with Gambit (boolean swaps, comparison swaps, if-interception, `==`↔`>=`, literal mutations, modifier removal, argument swaps…).
2. Sanity baseline: the unmutated harness **must pass** (fail-closed — a red suite makes mutation results meaningless).
3. For each mutant: copy the mutated source over the original (originals backed up byte-for-byte in the pipeline-owned workspace; the target git tree is never used for restore), run the fast test suite (`test/*` minus invariant/fork), record killed/survived, restore.
4. Resumable: `artifacts/mutation-progress.json` survives interruption; re-running continues where it left off.
5. Emits `artifacts/mutation-report.json` (total, killed, survived, kill_rate_pct, core_survivors).

## Operator controls
- `HACVSP_MUTATION_LIMIT` (engagement `.env`): cap mutants for smoke runs — **the gate still demands ≥90% over what ran**.
- `applicability.core_contracts` in `engagement.json`: survivor triage focuses here.

## Triage (spec-mandated)
Every survivor → either (a) a new test assertion that kills it, or (b) documented equivalence in target `MUTATION_EXCEPTIONS.md` (must contain the mutant id; ratified at Stage 13).

## Gate evaluation
`gate.py` requires: kill_rate_pct ≥ 90.0, zero untriaged survivors in core contracts, non-core survivors counted and reported.
