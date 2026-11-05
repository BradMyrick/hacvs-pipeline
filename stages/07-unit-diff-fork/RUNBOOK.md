# Stage 7 Runbook — Concrete Unit, Differential & Fork Testing

**Cadence:** PR tier · **Gate:** GO/NO-GO
**Spec criteria:** _All unit, differential, and fork tests pass; coverage meets >= 95% threshold with all gap justifications approved._

## Objective
Validate concrete state transitions, differential math against reference implementations, gas limits, and real mainnet-fork environments.

## What the runner does
1. `forge test -vvv --gas-report --summary` — full unit suite → `artifacts/unit-results.txt`.
2. Differential suite (`test/differential/*`) — absence is recorded and flagged for Stage 13 review (math-heavy cores require it).
3. Fork suite (`test/fork/*`) — runs against `HACVSP_FORK_RPC` from the engagement `.env` (0600). If `fork_tests_required=true` (default) and no RPC is provided → fail-closed.
4. `forge coverage` (lcov) → parsed by a stdlib lcov parser → `artifacts/coverage-summary.json` with line/branch percentages per file.

## Coverage thresholds (spec)
- line ≥ 95.0% · branch ≥ 95.0%
- Below threshold requires `COVERAGE_EXCEPTIONS.md` in the target root with a `Reviewer-Signature` block; entries are re-ratified at Stage 13.

## Fork scope (spec)
Oracle latency/staleness simulation, flash-loan callbacks under real pool states, liquidity depth/price-impact limits.

## Secrets
`HACVSP_FORK_RPC` lives in `engagements/<slug>/.env` (0600, gitignored, names-only logging).

## Gate evaluation
`gate.py` requires: coverage summary present, thresholds met (or signed exceptions file), no failed suites detected in results.

## Known toolchain interaction: via_ir + vm.warp (2026-11-05, PeekPeak)

solc's Yul optimizer rematerializes `block.timestamp` at use sites — valid for
real transactions (timestamp is tx-stable), invalid across `vm.warp`. A test
that captures `uint256 t0 = block.timestamp;` and reads `t0` after a warp gets
the POST-warp value under `via_ir = true`. Contracts' emitted/storage behavior
is unaffected. Rule: in tests, capture time with `vm.getBlockTimestamp()`.
