# Stage 2 Runbook — Deterministic Build & Bytecode Size Validation

**Cadence:** PR tier · **Gate:** GO/NO-GO
**Spec criteria:** _Bytecode matches bit-for-byte in clean hermetic container; zero contracts violate EIP-170 or EIP-3860 size boundaries._

## Objective
Produce byte-for-byte reproducible build artifacts, lock compiler flags, and validate EVM runtime bytecode and initcode boundaries.

## Spec-locked compiler settings
`via_ir = true` · `optimizer_runs = 200` · `bytecode_hash = "ipfs"` — asserted from the target's `foundry.toml` before any build.

## What the runner does
1. Asserts compiler settings match SPEC (`via_ir`, optimizer runs 200, ipfs metadata hash).
2. Builds twice into separate out dirs (`out-a`, `out-b`) — nothing is ever deleted.
3. `diff -r out-a out-b` → `artifacts/reproducibility.diff` (must be empty).
4. Extracts runtime/initcode sizes for every artifact → `artifacts/bytecode-sizes.json`, flags EIP-170 (>24576B runtime) and EIP-3860 (>49152B initcode) violations.
5. Emits canonical AST (`artifacts/canonical-ast.json`, paths relativized) — consumed by Stages 4 and 8.
6. Emits `artifacts/reproducible-manifest.sha256` over all build outputs.

## Gate evaluation
`gate.py` requires: empty reproducibility diff, zero size violations, non-empty canonical AST, manifest present.

## Operator notes
- Non-reproducible builds are usually un-pinned metadata (timestamps, paths) or non-deterministic `block.timestamp`-style constants; both are findings, not noise.
- The two-out-dir approach avoids deleting any previous build outputs (deletion policy).
