# test/differential — reference-implementation diffs (Stage 7)

Side-by-side comparison of the target's math/state against known-good
references (Solady/OZ or canonical Python/Rust models via FFI-free Solidity
ports):

- bounded input spaces (`vm.assume`/`bound`) across the full domain,
- assert exact state divergence == 0 after mirrored call sequences,
- include boundary values: 0, 1, type(uint).max, type(int).min, rounding
  boundaries (x/2 vs (x+1)/2).

```solidity
// example shape
// function test_diff_convertToShares(uint256 assets) public {
//     assets = bound(assets, 0, 1e30);
//     assertEq(Vault.convertToShares(assets), ReferenceVault.convertToShares(assets));
// }
```
