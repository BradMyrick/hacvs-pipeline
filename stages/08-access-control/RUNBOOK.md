# Stage 8 Runbook — Access Control & Privilege Matrix Validation

**Cadence:** RELEASE tier · **Gate:** GO/NO-GO
**Spec criteria:** _Zero unauthorized callers can execute privileged state-modifying functions; 100% concordance between declared matrix and executable tests._

## Objective
Generate and enforce an exhaustive Access Control Matrix mapping roles to external/public state transitions.

## What the runner does
1. **Extract** (`tools/access-matrix`) every public/external function from the canonical ASTs with modifiers, require-based auth sniffs, pausable detection, and role classification → `artifacts/ACCESS_CONTROL_MATRIX.{json,md}` (spec schema: contract, function_signature, allowed_roles, is_pausable, timelock_delay_seconds).
2. **Generate** the assertion harness `test/access-control/GeneratedAccessMatrix.t.sol`: for every non-PUBLIC state-changing row, a test that `vm.prank(UNPRIV)` + `vm.expectRevert()`; PUBLIC rows get informational probes. Rows with exotic arg types (arrays/structs) are listed as MANUAL rows.
3. **Enforce** by running `forge test --match-path 'test/access-control/*'` (declared + generated + manual suites).
4. **Concordance check**: every state-changing matrix row must have an executable test (`matrix_<Contract>_<fn>` in generated, or `manual_<Contract>_<fn>` in `ManualAccessMatrix.t.sol`) → `artifacts/access-concordance.json`.

## Role heuristics (expert-ratified at Stage 13)
`onlyOwner/onlyAdmin → OWNER` · `onlyRole(X)/hasRole(X) → ROLE(X)` · `onlyTimelock → TIMELOCK` · `onlyGuardian → GUARDIAN` · no auth modifier on a state-changing function → `PUBLIC` (**must be intentional**).

## Operator wiring
The generated harness contains `TODO_TARGET_CONTRACT` markers — wire the import + `setUp()` deployment, implement MANUAL rows in `ManualAccessMatrix.t.sol`, commit, and re-run the stage. Note in review: `timelock_delay_seconds` requires config introspection (expert fills from protocol config review at Stage 13).

## Known limitations (documented, mitigated)
Zero-arg probes reach modifier-based auth checks before body logic; require-based auth after input validation may need MANUAL rows with realistic args — the concordance check forces coverage either way.
