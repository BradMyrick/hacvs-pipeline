# Engagement Intake — fill with the client / expert before running stages

Engagement: _
Date: _
Client: _
Protocol whitepaper / docs: _

## Target
- Repo: _
- Commit under audit: _
- Baseline commit (for upgrades; else `null`): _

## Architecture (drives stage applicability)
- Proxy architecture(s): UUPS / Transparent / Beacon / Diamond-ERC2535 / none
- Core contracts (mutation triage + selector focus): _
- External integrations (oracles, DEXs, lenders): _

## Standards (Stage 6)
- Applicable ERCs: ERC20 / ERC721 / ERC1155 / ERC4626 / NONE

## Testing scope (Stage 7)
- Mainnet-fork tests required? yes / no
- Fork RPC endpoint available? (name only, value goes in .env): HACVSP_FORK_RPC
- Differential reference implementations to mirror: _

## Fuzzing (Stage 10)
- Engines: forge / echidna / medusa (default all three)
- Echidna target contract (if echidna enabled): _
- Invariant runs/depth for smoke vs release: 256/50 vs 100000/500

## Formal layers (Stages 11-12)
- Kontrol proof corpus match (default `Proof*`): _
- Kontrol coverage floor (default 90): _

## Sign-off (Stages 13-14)
- Principal Security Engineer: _
- Reviewer public key path (KODR_PUBKEY): _
- Bundle signing key (COSIGN_KEY) available: yes / no

## Secrets checklist (0600 .env — names only here)
- [ ] HACVSP_FORK_RPC (if fork tests)
- [ ] COSIGN_KEY (+ COSIGN_PASSWORD)
- [ ] KODR_PUBKEY
