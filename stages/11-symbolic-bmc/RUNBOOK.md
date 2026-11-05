# Stage 11 Runbook — Symbolic Execution & Bounded Model Checking

**Cadence:** RELEASE tier · **Gate:** GO/NO-GO
**Spec criteria:** _All bounded paths proven safe; zero unmitigated bytecode vulnerabilities reported by Mythril/Halmos._

## Dual BMC layers (per spec v0.1.0 — Halmos promoted to primary source-level BMC)
1. **solc SMTChecker** (bmc + chc, z3/eldarica, timeout 120000ms, targets `assert,underflow,overflow,divByZero,balance`) — driven through the target's `[profile.default.model_checker]` (scaffold ships the spec-locked settings). Any `Counterexample` in the build log fails the gate.
2. **Halmos 0.3.3** — proves Foundry tests with symbolic calldata/storage (`test/proofs/*`, `--loop 3`). Failing proofs fail the gate; **zero passing proofs also fails** (a proof corpus is mandatory on the release tier).

## Bytecode layer
3. **Mythril 0.24.8** (`--execution-timeout 600 --solver-timeout 30000 --strategy bfs`) — taint/path analysis independent of the AST: delegatecall exposure, unprotected selfdestruct, arbitrary send. High/Critical issues must be suppressed via signed `{tool: "mythril"}` entries or they fail the gate. Raw JSON → `artifacts/mythril-results.json` (published in the Stage 14 bundle per spec).

## Analysis targets (spec)
Reachable `assert(false)`, arithmetic overflow/underflow in assembly/`unchecked` blocks, taint confirmation that sensitive storage slots cannot be overwritten by arbitrary call inputs.

## Gate evaluation
`gate.py` requires: zero SMT counterexamples, zero halmos failures + ≥1 proof, zero unmitigated mythril high/critical.
