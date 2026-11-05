# Stage 1 Runbook — Dependency Hygiene & Supply-Chain Verification

**Cadence:** PR tier · **Gate:** GO/NO-GO, binary, fail-closed
**Spec criteria:** _Zero unreviewed CVEs in third-party libraries; all submodules pinned to immutable commit hashes._

## Objective
Audit external dependencies, generate CycloneDX/SPDX SBOM, enforce cryptographic tag verification, and freeze immutable git submodules.

## Tools (pinned)
- Syft 1.57.0 — SBOM generation (CycloneDX + SPDX)
- Trivy 0.76.2 — SBOM vulnerability scanning
- git / npm audit — submodule pin enforcement, lockfile discipline

## What the runner does
1. Verifies every git submodule is initialized at the recorded commit (`git submodule status` — `+`/`-`/`U` markers fail).
2. Generates `artifacts/sbom.cyclonedx.json` + `artifacts/sbom.spdx.json`.
3. Scans the SBOM with Trivy → `artifacts/trivy-results.json`.
4. Rejects floating dependencies (`package.json` without lockfile, `Cargo.toml` without `Cargo.lock`).
5. Records ecosystem audits (npm/cargo, best-effort).
6. Emits `artifacts/dependency-checksums.sha256` over `lib/`, lockfiles, `foundry.toml`, `remappings.txt`.
7. Consolidates `artifacts/dependency-summary.json` for the gate.

## Suppressions
Unreviewed CVEs fail the gate unless a signed entry `{tool: "trivy", finding_id: "<CVE-ID>", ...}` exists in the target's `.security-suppressions.json` (see Stage 3 governance; signatures verified there, honored here).

## Gate evaluation
`gate.py` requires: summary exists & parseable, `submodule_issues == 0`, `floating_dependencies == 0`, unreviewed critical/high/medium CVEs `== 0`.

## Operator notes
- If the target has no `lib/` and no lockfiles, checksums will cover whatever exists — empty checksum files still fail the "untracked dependency" sniff test at review.
- Expert interaction point: ratification of any CVE suppressions happens at Stage 13.
