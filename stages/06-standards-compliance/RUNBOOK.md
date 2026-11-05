# Stage 6 Runbook — Standards Compliance & Conformance Suite

**Cadence:** PR tier · **Gate:** GO/NO-GO
**Spec criteria:** _100% pass across all applicable reference standard compliance suites._

## Objective
Verify strict conformance to standard interface specifications and mathematical boundary constraints.

## Applicability
`engagement.json → applicability.erc_standards` — e.g. `["ERC20", "ERC4626"]`, or explicitly `["NONE"]` for non-standard contracts (recorded, never silently skipped).

## What the runner does
1. Refuses to run with an empty applicability list (fail-closed: intake must decide).
2. Runs `forge test --match-path 'test/compliance/*' --json`.
3. Maps results per declared standard; any declared standard with **no matching suite** is a failure (the scaffold ships canonical suites: OZ ERC-20/721/1155 + a16z ERC-4626 property tests as pinned submodules).
4. Emits `artifacts/compliance-summary.json`.

## ERC-4626 rounding direction
The reference suite proves: assets = mint/deposit round **down** on shares, withdraw/redeem round **up** on assets (protects pool solvency) and inflation-attack immunity under first-depositor adversarial framing.

## Gate evaluation
`gate.py` requires: `passed_all == true` (zero failed tests, ≥1 total, every declared standard covered).

## Operator notes
- If the target repo lacks `test/compliance/`, copy the canonical suites from `templates/workstation/test/compliance/` and adapt the harness import — suites themselves are pinned dependencies, so adaptation is a reviewable diff.
