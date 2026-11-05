# test/compliance — ERC conformance (Stage 6)

Pin canonical suites as submodules (Stage 1 enforces commit pinning) and wire
harnesses here:

```bash
forge install OpenZeppelin/openzeppelin-contracts --no-commit
forge install a16z/erc4626-property-tests --no-commit
```

- **ERC-20**: transfer/approve/transferFrom return values, safe-transfer edge
  cases, allowance races.
- **ERC-721 / ERC-1155**: mint/burn events, approvals, `supportsInterface`.
- **ERC-4626** (a16z property tests): share math rounding direction —
  round **down** shares on deposit/mint, round **up** assets on withdraw/redeem;
  inflation-attack immunity under first-depositor framing.

Files must match `test/compliance/*` — Stage 6's gate maps every declared
standard in `engagement.json → applicability.erc_standards` to at least one
passing suite here.
