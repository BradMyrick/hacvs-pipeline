# Stage 5 Runbook — Storage Layout & Upgradeability Verification

**Cadence:** PR tier · **Gate:** GO/NO-GO
**Spec criteria:** _Zero storage collision warnings; formal confirmation of initializer protection and facet selector uniqueness._

## Objective
Verify storage slot preservation, proxy initialization safety, storage gaps, and Diamond (ERC-2535) facet/selector integrity.

## Applicability (from engagement intake)
`engagement.json → applicability.proxy_architectures` ∈ {UUPS, TransparentUpgradeableProxy, BeaconProxy, Diamond/ERC-2535, non-upgradeable}. For non-upgradeable first audits, current layouts become the recorded baseline for future upgrades.

## What the runner does
1. Extracts `forge inspect <C> storage-layout --json` for every `src/` contract → `artifacts/storage-layouts-current/`.
2. If `engagement.json → baseline_commit` is set: creates a **git worktree** at the baseline (never mutates the working tree), builds it, extracts baseline layouts, and runs `tools/layout-diff` per contract → `artifacts/storage-layout-diff-<C>.json` checking slot/type/offset preservation, insertion-after-baseline ordering, `__gap` shrinkage arithmetic, and ERC-7201 namespace immutability.
3. Checks Initializable logic contracts call `_disableInitializers()` (or equivalent) in constructors → `artifacts/initializer-check.json`.
4. Detects signature ambiguity across contracts (Diamond selector collision sniff) → `artifacts/diamond-selector-check.json`.

## Gate evaluation
`gate.py` requires: layouts extracted, zero collisions/gap/namespace issues in every diff report, zero initializer issues, zero duplicate signatures.

## Operator notes
- For full 4-byte selector collision coverage on Diamonds, the engagement should also run `diamond Loupe` introspection on a fork deployment at Stage 7; this stage covers static ambiguity.
- Baseline worktree `.baseline/` is gitignored inside the target and left in place (deletion policy).
