# HACVSP — Kodr.pro High-Assurance Contract Verification & Security Pipeline

**v0.1.0 · EVM · fail-closed, dual-cadence, expert-in-the-loop**

A fail-closed gated verification system for EVM smart contracts: hermetic
digest-pinned Docker toolchain, binary GO/NO-GO gates, dual cadences (PR tier
1–7, release gate 8–14), signed suppression governance, and cryptographic
attestation of the entire evidence bundle. Certora-free formal layer: **hevm**
(source-level bounded model checking) + **Kontrol/KEVM** (EVM-level theorem
proving). Pinned Kontrol 1.0.255 has no proof-coverage metric. Non-vacuity is
a written rationale in `review/KONTROL_VACUITY.md`: the stage 12 gate fails if
that file is missing or does not name every recorded proof. It does not check
a signature on the file. Stage 11 hevm proves the Foundry proof tests
separately. The stage 13 signature is on `MANUAL_REVIEW_SIGNOFF.md`, not on
the vacuity file. AiWrangler participates as an **MCP server** (0.1.5), not a
CLI.

```
SPEC.json ──gates──> hacvsp CLI ──docker(compose)──> stages/01..14
    │                     │                              (run.sh + gate.py)
    └── verify ◄──────────┴── GATE_LEDGER.json ◄──────── binary verdicts
```

## Quick start

```bash
make build && make pin && make doctor && make verify   # hermetic setup
make ui                                            # operator dashboard :8787
hacvsp audit <repo> --commit <sha> --name <slug>        # engagement
hacvsp stage 1 --engagement <slug>                      # ... through 14
# or conversationally:  /audit <repo>   /hacvsp-init   /hacvsp-signoff
```

## Layout

| Path | Purpose |
|---|---|
| `SPEC.json` | Ground truth (v0.1.0) — the spec audits the pipeline (`make verify`) |
| `gates.json` | Derived machine-checkable gate matrix (`make gates`) |
| `bin/hacvsp` + `lib/hacvsp/` | CLI engine (thin host launcher; docker does the work) |
| `docker/` | Pin authority (`pins.env`), Dockerfiles, per-stage compose matrix |
| `stages/01..14/` | RUNBOOK + runner + gate evaluator per stage |
| `tools/` | sarif-aggregator · event-audit · access-matrix · layout-diff · attest (stdlib Python, unit-tested) |
| `templates/workstation/` | Pipeline-compliant Foundry scaffold (`hacvsp init`) |
| `engagements/` | Per-audit workspaces (ledger, artifacts, review, bundle) |
| `skills/` + `commands/` + `install/` | OpenCode integration (`/audit`, `/hacvsp-*`) |
| `docs/` | OPERATIONS · INTERACTION_POINTS · SECRETS |

## Stage map

**PR tier** 1 supply-chain/SBOM · 2 deterministic build + EIP-170/3860 ·
3 static analysis + signed suppressions · 4 event emission/indexing (AST) ·
5 storage/upgrade safety (Diamond/ERC-7201) · 6 ERC conformance ·
7 unit/differential/fork + ≥95% coverage.

**Release gate** 8 access-control matrix (exhaustive + concordant) ·
9 mutation ≥90% kill · 10 stateful fuzzing (forge+echidna+medusa, ghost actors
+ reentrancy sets) · 11 symbolic/BMC (SMTChecker bmc/chc + hevm + Mythril) ·
12 Kontrol KEVM theorem proving · 13 **expert** threat model + sign-off ·
14 cosign attestation + SLSA provenance + Sourcify mapping.

## Governing invariants

Fail-closed everywhere: missing = NO_GO, ordering enforced, pins frozen,
suppressions signed and ratified, the human signs the human lane. Assurance is
bounded by specification completeness and expert review quality — the bundle
says exactly what was proven, how, and by whom.
