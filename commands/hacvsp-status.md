---
description: Show HACVSP gate ledger + cadence rollup for an engagement
---

# /hacvsp-status

Load the `hacvsp` skill.

1. Run `hacvsp status` (all engagements) or `hacvsp status --engagement <slug>`
   if an argument names one.
2. Present the verdict table + PR/release rollups, then interpret:
   - which stages are PENDING / NO_GO and their failure summaries,
   - what the ordering rules require next (earliest NO_GO stage first),
   - long-running stages still detached (check `logs/` mtimes).
3. If everything is GO through stage 12, remind the user that stage 13
   (expert review + sign-off) is the next human action — see `/hacvsp-signoff`.
