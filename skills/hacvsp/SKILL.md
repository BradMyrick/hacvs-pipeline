---
name: hacvsp
description: Operate the Kodr.pro High-Assurance Contract Verification & Security Pipeline (HACVSP v0.1.0) — run stages and gates, manage engagements, verify the hermetic toolchain, scaffold pipeline-compliant contracts, and read gate ledgers. Use for ANY task involving hacvsp, gate verdicts, stage runners, suppressions governance, or the contract workstation. For end-to-end audit engagement methodology, load kodr-audit after this.
version: 0.1.0
---

# Skill: HACVSP Pipeline Operator

## System Reference: Fail-Closed Gated Verification (RFC-Style Engineering Spec)

### 1. Core Model

HACVSP is a **fail-closed, dual-cadence** verification system for EVM contracts.
Ground truth is `SPEC.json` in the workstation repo (default
`/home/kodr/Audits/hacvsp`). Four properties are non-negotiable:

1. **Binary gates.** Every stage ends GO or NO_GO. There is no partial credit:
   anything missing, errored, or ambiguous is NO_GO.
2. **Fail-closed defaults.** Missing artifact, unparseable report, unfrozen
   toolchain pin, absent signature → the gate fails. Overrides exist only as
   explicit, recorded env flags (`HACVSP_ALLOW_*`), never silently.
3. **The spec audits the pipeline.** `hacvsp verify` cross-checks the
   implementation against SPEC.json; drift is a build error.
4. **Expert-in-the-loop.** Stage 13 is the human lane; automation prepares,
   the Principal Security Engineer rules. Suppressions require signed
   justification and ratification.

### 2. Cadences (SPEC v0.1.0)

| Tier | Stages | Runs on |
|---|---|---|
| PR commit | 1 dependency/supply-chain · 2 deterministic build · 3 static analysis · 4 events · 5 storage/upgrade · 6 ERC conformance · 7 unit/differential/fork (≥95% cov) | every PR |
| Release gate | 8 access matrix · 9 mutation (≥90% kill) · 10 stateful fuzzing (forge+echidna+medusa) · 11 symbolic/BMC (SMTChecker+hevm+Mythril) · 12 Kontrol EVM theorem proving · 13 expert review (HUMAN) · 14 attestation & bundle | release |

Stage 11/12 note (v0.1.0): Certora is **not** used. hevm is the primary
source-level BMC engine and proves the Foundry proof tests (`test_Proof`
prefix). Kontrol (KEVM/K Framework, docker-digest-pinned 1.0.255) proves the
matched Foundry tests at the bytecode level. That Kontrol version has no
proof-coverage metric. Non-vacuity is a written rationale in
`review/KONTROL_VACUITY.md`: the stage 12 gate fails if the file is missing,
does not contain `coverage: tool-unavailable`, or does not name every recorded
proof (the `--match-test` patterns). It does not check a signature on that
file. Stage 13 signs `MANUAL_REVIEW_SIGNOFF.md`, not the vacuity file.

### 3. Operational Rules

* **Rule 1 (Doctor before stages).** `hacvsp doctor` verifies docker + frozen
  pins (`docker/pins.env`) + image digests. Never bypass; build images with
  `make build`, freeze pins with `make pin`.
* **Rule 2 (Ordering).** `hacvsp stage N` refuses to run if an earlier stage
  in the same cadence is missing or NO_GO. `--force` overrides and is
  recorded in the verdict.
* **Rule 3 (Ledger is truth).** `engagements/<slug>/GATE_LEDGER.json` holds
  append-only verdicts; latest wins; cadence rollup is GO only if every stage
  is GO. Check `hacvsp status --engagement <slug>` before making claims.
* **Rule 4 (Long-runners detach).** Stages 9, 10, 12 run overnight:
  `hacvsp stage N --engagement <slug> --detach`, then `hacvsp logs N`,
  then `hacvsp gate N` when finished.
* **Rule 5 (Suppressions are signed).** `.security-suppressions.json` entries
  need tool, finding_id, file, line_range, git_commit_hash, justification,
  reviewer, reviewer_signature (cosign/GPG over the canonical digest). Invalid
  or unsigned entries fail Stage 3.
* **Rule 6 (Secrets discipline).** RPC URLs and keys live in
  `engagements/<slug>/.env` (0600, gitignored). Log names, never values.
* **Rule 7 (Deletion policy).** The pipeline never deletes: workspaces rotate
  by rename (`mutants` → `mutants.prev`), baselines are git worktrees, builds
  go to fresh out-dirs.

### 4. CLI Reference (bin/hacvsp)

```
hacvsp init NAME [--dir DIR]              # scaffold pipeline-compliant Foundry project
hacvsp audit REPO [--commit SHA] [--name SLUG]
hacvsp stage N --engagement SLUG [--detach] [--force]
hacvsp gate N --engagement SLUG           # re-evaluate a gate after fixes
hacvsp status [--engagement SLUG]
hacvsp logs N --engagement SLUG
hacvsp doctor | verify | gates | list
hacvsp report --engagement SLUG           # SECURITY_ASSURANCE.md draft
```

### 5. Server / laptop workflow (overnight runs)

Everything is files under `engagements/<slug>/` (ledger, artifacts, logs) —
git is the transport, no daemon:

```
laptop:  git push origin <engagement-branch>
server:  git pull && hacvsp stage 10 --engagement <slug> --detach
server:  hacvsp logs 10 --engagement <slug>        # tail anytime
server:  git add engagements/<slug> && git commit  # evidence
laptop:  git pull && hacvsp status --engagement <slug>
```

### 6. Applicability (engagement.json → applicability)

`proxy_architectures` (UUPS/Transparent/Beacon/Diamond/none) drives Stage 5;
`erc_standards` (or explicit `["NONE"]`) drives Stage 6; `core_contracts`
drives Stage 9 triage; `fuzz_engines` + `echidna_contract` drive Stage 10;
`kontrol_match` selects the Stage 12 proofs (default `Proof*`).
`kontrol_coverage_min_pct` is recorded and not applied: Kontrol 1.0.255 writes
no coverage percentage. Empty lists fail-closed at intake.

### 7. Key Files

```
SPEC.json                     # ground truth (v0.1.0) — never edit ad hoc
gates.json                    # derived gate matrix (make gates)
docker/pins.env               # hermetic pin authority (make pin)
stages/NN-*/{RUNBOOK.md,run.sh,gate.py}
tools/{sarif-aggregator,event-audit,access-matrix,layout-diff,attest}
templates/workstation/        # contract scaffold (hacvsp init)
engagements/_template/        # intake.md, engagement.json, .env.example
docs/{OPERATIONS,INTERACTION_POINTS,SECRETS}.md
```
