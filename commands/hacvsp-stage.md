---
description: Run a single HACVSP stage + gate (args: stage number, e.g. "3")
---

# /hacvsp-stage — run stage $ARGUMENTS

Load the `hacvsp` skill. Parse `$ARGUMENTS` as the stage number (1–14) plus
optional `--engagement <slug>` and `--detach`.

1. If no engagement given, run `hacvsp list` and use the most recent (confirm
   with the user if several).
2. Show `hacvsp status --engagement <slug>` first — earlier NO_GO stages must
   be resolved (or the user explicitly chooses `--force`, which gets recorded).
3. Run `hacvsp stage <N> --engagement <slug>` (add `--detach` for 9/10/12 or
   on request). Stream the tail of `logs/stage-NN.log` for long runs.
4. On completion, report the binary verdict and, on NO_GO, the failure list
   with the runbook's triage guidance (`stages/NN-*/RUNBOOK.md`).
5. Propose the next command (fix + `hacvsp gate N`, or the next stage).
