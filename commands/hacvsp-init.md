---
description: Scaffold a pipeline-compliant Foundry project (HACVSP workstation)
---

# /hacvsp-init — new contract project for $ARGUMENTS

Load the `hacvsp` skill. Then:

1. Run `hacvsp init $ARGUMENTS` (creates the scaffold from
   `templates/workstation/` — spec-locked foundry.toml, test-suite layout,
   invariant handler architecture, suppression/exception files, CI tiers).
2. `cd` into the new project; summarize the layout→stage mapping from its
   README.
3. Guide next steps: pin dependencies as submodules (`forge install …
   --no-commit`, then commit the pins), add contracts under `src/`, wire
   `test/compliance/` canonical suites for the applicable ERCs, replace the
   Handler TODOs in `test/invariant/Handler.sol`.
4. Remind: the first `hacvsp audit <this-repo>` once committed is the
   pipeline's first PR-tier pass.
