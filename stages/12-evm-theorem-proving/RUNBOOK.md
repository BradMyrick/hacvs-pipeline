# Stage 12 Runbook — EVM-Level Theorem Proving (Kontrol / KEVM)

**Cadence:** RELEASE tier · **Gate:** GO/NO-GO · **Long-running: `hacvsp stage 12 --engagement <slug> --detach`** (first `kontrol build` alone can take 30–60m; the KEVM cache volume persists it)

**Spec criteria:** _Zero failed Kontrol proofs and at least one proof ran. `review/KONTROL_VACUITY.md` exists, names every recorded proof, and states that coverage is tool-unavailable. No coverage threshold is applied. The gate does not check a signature on that file._

## What this stage runs
`kontrol build`, then `kontrol prove --match-test` for each pattern in `kontrol_match` (default `Proof*`). Pinned Kontrol 1.0.255 has no `view-coverage` command and no proof-coverage metric. The runner stores `coverage_pct` as null and saves `kontrol list` as an inventory only.

## Controls (engagement.json → applicability)
- `kontrol_match` — patterns passed to `kontrol prove --match-test` (default `Proof*`). Write the proofs as Foundry tests under `test/proofs/`.
- `kontrol_coverage_min_pct` — copied onto the proof summary (default 90). It is not applied. This Kontrol version never writes a coverage percentage, so the gate's numeric floor branch does not run.

## Non-vacuity
There is no coverage check. Non-vacuity is a written rationale in `review/KONTROL_VACUITY.md`:

- The file must exist.
- It must contain the text `coverage: tool-unavailable`.
- It must contain every name in `kontrol-proofs.json` (`passed` and `failed`). Those names are the `--match-test` patterns the runner used, not a parsed list of individual test functions.
- The gate does not verify a signature on this file.

Stage 13 signs `review/MANUAL_REVIEW_SIGNOFF.md`, not the vacuity file. The spec-audit draft asks the reviewer to read the rationale. Stage 11 runs `hevm test --prefix test_Proof` on `test/proofs/`. Stage 12 does not re-check that hevm result.

This stage does not pull in Scribble instrumentation, and it does not read an applicability key for that.

## Gate evaluation
`gate.py` requires the proof artifacts, at least one proof, and zero failures. With `coverage_pct` null it requires the vacuity doc as above. It does not check a signature. If a run wrote a numeric `coverage_pct` below `coverage_min_pct`, that branch would fail; the pinned runner always writes null.
