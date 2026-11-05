# test/proofs — formal property corpus (Stages 11 & 12)

Tests named `Proof*` run symbolically under:

- **Halmos** (Stage 11, source-level bounded model checking): symbolically
  bound inputs, no concrete `vm.assume` over-constraining.
- **Kontrol** (Stage 12, KEVM bytecode-level theorem proving): the same Foundry
  tests, proven for all input states at the EVM level. Coverage floor and
  non-vacuity rationale in `review/KONTROL_VACUITY.md` are gate-enforced.

```solidity
contract Proofs is Test {
    function proof_conservation(uint256 amount, address who) public {
        amount = bound(amount, 0, 1e30);
        // symbolic execution + theorem proving of the conservation property
    }
}
```

Guidelines:
- one property per `Proof*` test, named after the invariant it proves,
- avoid `vm.prank`-dependent control flow when the property is universal,
- document non-vacuity: which variables are symbolic and why inputs remain
  unconstrained.
