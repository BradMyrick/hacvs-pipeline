# Stage 10 Runbook — Property-Based Testing & Stateful Fuzzing

**Cadence:** RELEASE tier · **Gate:** GO/NO-GO · **Long-running: `hacvsp stage 10 --engagement <slug> --detach`**

**Spec criteria:** _Zero invariant violations after target runs and depth across all active fuzzing engines._

## Engines (declared via `applicability.fuzz_engines`, default all three)
| Engine | Config | Spec targets |
|---|---|---|
| forge invariants | `--fuzz-runs 100000 --depth 500` | handler-based stateful invariants |
| Echidna 2.4.0 | `fuzz/echidna.yaml`, `--format json` | property functions |
| Medusa 1.5.1 | `fuzz/medusa.json` | parallel stateful fuzzing, optimization |

`HACVSP_INV_RUNS` / `HACVSP_INV_DEPTH` override via engagement `.env` (e.g. `256/50` for smoke runs — the gate still fails on any violation; reduced depth is recorded in the ledger for Stage 13 scrutiny).

## Handler architecture (spec-mandated, gate-checked)
`test/invariant/Handler.sol` must exist, providing:
- **ghost variable state trackers** (mirrored totals for conservation checks),
- **ghost actors** — `Admin` + at least two non-privileged users,
- **cross-contract reentrancy-set handlers** — malicious `ERC777`-style sender + `IERC721Receiver`/uniswap-V3-style receiver hooks re-entering the target mid-flight.

The scaffold (`templates/workstation/test/invariant/`) ships this architecture.

## Invariant domains (spec)
Conservation of capital (`totalAssets == liabilities + equity`), solvency under extreme multi-call sequences, strict access-control invariants.

## Gate evaluation
`gate.py` requires: fuzzing summary present, zero violations, every declared engine produced results, handler architecture present.
