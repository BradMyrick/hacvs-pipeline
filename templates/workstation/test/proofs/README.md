# test/proofs — formal property corpus (Stages 11 & 12)

Foundry proof tests in this directory are run by:

- **hevm** (Stage 11): `hevm test --prefix test_Proof`. Failing proofs fail
  that gate. Stage 12 does not re-check the hevm result.
- **Kontrol** (Stage 12, KEVM bytecode-level theorem proving): `kontrol prove
  --match-test` with `kontrol_match` (default `Proof*`). Pinned Kontrol
  1.0.255 reports no coverage. The stage 12 gate requires
  `review/KONTROL_VACUITY.md` to exist, to contain
  `coverage: tool-unavailable`, and to name every recorded proof (the
  match-test patterns). It does not check a signature on that file.

```solidity
contract Proofs is Test {
    function test_Proof_conservation(uint256 amount, address who) public {
        amount = bound(amount, 0, 1e30);
        // symbolic execution + theorem proving of the conservation property
    }
}
```

Guidelines:
- one property per `Proof*` test, named after the invariant it proves,
- avoid `vm.prank`-dependent control flow when the property is universal,
- document non-vacuity in `review/KONTROL_VACUITY.md`: which variables are
  symbolic, and why the assumptions do not make the property trivial. The
  stage 12 gate checks that each recorded proof name appears in that file.
  It does not judge the rationale or sign the file.
