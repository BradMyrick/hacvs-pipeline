# HACVSP Contract Workstation

A pipeline-compliant Foundry scaffold for developing EVM contracts under the
**Kodr.pro High-Assurance Contract Verification & Security Pipeline v0.1.0**.

## Layout → Stage mapping

| Path | Pipeline stage |
|---|---|
| `foundry.toml` (via_ir, runs 200, ipfs, SMTChecker) | 2, 11 |
| `.security-suppressions.json` | 3 (governed suppressions; signed) |
| `test/compliance/` | 6 (ERC-20/721/1155/4626 canonical suites) |
| `test/unit/` | 7 |
| `test/differential/` | 7 (math vs reference implementations) |
| `test/fork/` | 7 (mainnet-fork: oracles, flash loans, liquidity) |
| `test/access-control/` | 8 (declared + GeneratedAccessMatrix.t.sol + Manual) |
| `test/invariant/` (Handler + Actors + ReentrancyReceiver) | 10 |
| `fuzz/echidna.yaml`, `fuzz/medusa.json` | 10 |
| `test/proofs/` | 11 (Halmos BMC) + 12 (Kontrol theorem proving) |
| `COVERAGE_EXCEPTIONS.md`, `MUTATION_EXCEPTIONS.md` | 7 / 9 triage |
| `.github/workflows/pr-tier.yml`, `release-gate.yml` | CI cadences |

## Quick start

```bash
hacvsp init MyProtocol --dir ~/dev/MyProtocol   # or: /hacvsp-init MyProtocol
cd ~/dev/MyProtocol
forge install foundry-rs/forge-std --no-commit  # pin submodules! (stage 1)
forge build && forge test
```

## Non-negotiables (fail-closed)

1. Submodules/dependencies pinned to immutable commits; lockfiles committed.
2. Compiler settings locked (via_ir, 200 runs, ipfs metadata) — Stage 2 asserts them.
3. Every critical state mutation emits an indexed event (Stage 4).
4. Suppressing any finding requires a **signed** entry in `.security-suppressions.json`.
5. Invariant handlers must keep the ghost-actor + reentrancy-set architecture.
6. Coverage <95% and surviving mutants require signed exception tables.

## Proof corpus naming

- Halmos (Stage 11) + Kontrol (Stage 12) run tests named `Proof*` under
  `test/proofs/` — write properties as Foundry tests with symbolic-bound inputs.
