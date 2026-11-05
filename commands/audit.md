---
description: Audit a smart-contract repo end-to-end with the HACVSP pipeline (Kodr.pro)
---

# /audit — HACVSP engagement for $ARGUMENTS

Load the `hacvsp` and `kodr-audit` skills, then execute the engagement
methodology against the target repo: **$ARGUMENTS**

## Procedure

1. **Resolve the target.** If $ARGUMENTS is a local path, use it; if a URL,
   plan to clone. Confirm the commit to audit with the user (default: HEAD).
   Layout rules: the target must be a Foundry root (`foundry.toml` + `src/` +
   `test/`). For monorepos with the Foundry project in a subdirectory, pass
   `--subdir <path>` (e.g. `contracts/`). Bare .sol folders need a
   `/hacvsp-init` scaffold first. cwd is irrelevant — commands resolve via
   the workstation root.
2. **Intake — ask the user now** (record answers verbatim in
   `engagements/<slug>/intake.md`, mirror into `engagement.json`):
   proxy architecture(s), applicable ERCs, core contracts, external
   integrations, fork-RPC availability, baseline commit, whitepaper URL.
   Empty applicability lists fail-closed — get real answers.
3. **Bootstrap:** `hacvsp audit <repo> --commit <sha> --name <slug>` from the
   workstation root (`/home/kodr/Audits/hacvsp` unless HACVSP_ROOT is set).
4. **Doctor:** `hacvsp doctor` — if pins are unfrozen run `make pin`; if
   images missing run `make build`. Never bypass fail-closed checks.
5. **PR tier:** run stages 1→7 (`hacvsp stage N --engagement <slug>`).
   On NO_GO: triage from `hacvsp status`, propose the fix or a signed
   suppression, get user consent, re-run `hacvsp gate N`.
6. **Checkpoint:** present suppressions + coverage exceptions for the user's
   ratification. Do not proceed without it.
7. **Release tier:** stages 8→12. Stages 9/10/12 are long-runners — propose
   `--detach` (especially on the server) and continue monitoring with
   `hacvsp logs N` / `hacvsp status`.
8. **Stage 13:** draft THREAT_MODEL.md / SPEC_AUDIT.md / the diff triage,
   present to the user for adversarial review, then drive `/hacvsp-signoff`.
9. **Stage 14:** `hacvsp stage 14 --engagement <slug>` (requires COSIGN_KEY in
   the engagement .env), then show the published bundle and
   `hacvsp report` summary.

Fail-closed discipline throughout: never mark a stage GO the ledger doesn't
say is GO. If the user asks to skip a stage, record `--force` and say why in
the final report.
