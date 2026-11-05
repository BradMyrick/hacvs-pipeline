# Stage 14 Runbook — Cryptographic Attestation & Proof Packaging

**Cadence:** RELEASE tier · **Gate:** GO/NO-GO
**Spec criteria:** _All signed attestations, verifiable build hashes, active suppression tables, and execution logs committed to public repository root._

## What the runner does
1. **Assemble** (`tools/attest assemble`): renders final `SECURITY_ASSURANCE.md` at the engagement root with all five mandatory sections; hashes every bundle file into `artifacts/bundle-manifest.json` (with `bundle_digest`); appends a SLSA in-toto predicate to `artifacts/provenance.intoto.jsonl` (CI runs using `actions/attest-build-provenance` contribute the GitHub-native statement instead).
2. **Sign**: `cosign sign-blob --key $COSIGN_KEY` over the manifest → `signatures/bundle-attestation.sig`. Fail-closed without `COSIGN_KEY` (`HACVSP_ALLOW_UNSIGNED=1` marks a dry-run only).
3. **Verify**: recompute digests (`tools/attest verify`) — any drift after assembly is a NO_GO.
4. If `engagement.json → deployment.addresses` is declared, the Sourcify/explorer exact-match mapping is emitted into the assurance doc.

## Published bundle (spec)
`SECURITY_ASSURANCE.md` · `artifacts/sbom.cyclonedx.json` · `artifacts/ACCESS_CONTROL_MATRIX.json` · `artifacts/EVENT_EMISSION_AUDIT.json` · `artifacts/kontrol-proofs.json` · `artifacts/mutation-report.json` · `artifacts/mythril-results.json` · `artifacts/provenance.intoto.jsonl` · `signatures/bundle-attestation.sig`

## Secrets
`COSIGN_KEY` (and `COSIGN_PASSWORD` if keyed) live in `engagements/<slug>/.env` — 0600, gitignored, names-only in logs.

## Publishing
The engagement directory (minus `target/` and `.env`) is the public audit repo: push it as-is. `hacvsp report --engagement <slug>` can regenerate drafts any time.
