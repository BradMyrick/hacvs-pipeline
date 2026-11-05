# Stage 12 Runbook — EVM-Level Theorem Proving (Kontrol / KEVM)

**Cadence:** RELEASE tier · **Gate:** GO/NO-GO · **Long-running: `hacvsp stage 12 --engagement <slug> --detach`** (first `kontrol build` alone can take 30–60m; the KEVM cache volume persists it)

**Spec criteria:** _Zero failed Kontrol proofs; coverage thresholds met on all proven rules; zero undocumented vacuous proofs._

## What Kontrol does
Compiles the Foundry test suite to KEVM (K Framework) semantics and proves each matched test for **all symbolic input states at the bytecode level** — source-level tooling quirks (AST misreads, compiler-assumption gaps) don't apply.

## Controls (engagement.json → applicability)
- `kontrol_match` — test-name glob for the proof corpus (default `Proof*`; write proofs as Foundry tests under `test/proofs/` with symbolic-bound inputs).
- `kontrol_coverage_min_pct` — node/rule coverage floor (default 90).

## Non-vacuity enforcement (spec vacuity-checking analog)
Two layers:
1. **Coverage floor** — `kontrol view-coverage` node coverage must meet the floor; trivially-true proofs cover almost no bytecode.
2. **Documented rationale** — `review/KONTROL_VACUITY.md` must exist and name **every** proven rule with a written argument that its symbolic variables are genuinely unconstrained (no accidental `vm.assume` over-constraining that makes the property untestable).

Scribble-instrumented invariants from Stage 3 should be included in the proof corpus where applicable (instrumented source can be compiled by kontrol via `src/` overlay — see engagement applicability `scribble_in_proofs`).

## Gate evaluation
`gate.py` requires: proofs ran (>0), zero failures, coverage ≥ floor, vacuity doc present + naming every proof.
