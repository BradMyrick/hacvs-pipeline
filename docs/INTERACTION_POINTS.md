# Expert Interaction Points

Where the pipeline stops and the human decides. Everything else is automated.

| # | Point | Who | What |
|---|---|---|---|
| 1 | **Intake** (before stage 1) | Expert + client | architecture, ERCs, core contracts, fork scope, baseline commit, whitepaper — drives all applicability |
| 2 | **Stage-3 triage** (on NO_GO) | Expert | classify static findings: fix code vs signed suppression |
| 3 | **PR-tier checkpoint** (after stage 7) | Expert | ratify suppressions + COVERAGE_EXCEPTIONS entries |
| 4 | **Stage-8 ratification** | Expert | every PUBLIC state-changing row must be intentional; timelock delays confirmed from config |
| 5 | **Stage-9 triage** | Expert | surviving mutants: new assertion vs MUTATION_EXCEPTIONS equivalence |
| 6 | **Stage-13 review** (the lane itself) | Expert | THREAT_MODEL / SPEC_AUDIT adversarial review + cryptographic sign-off; every suppression digest ratified |
| 7 | **Stage-14 publication** | Expert | verify bundle signature, choose publication venue |

**Agent-side (frontier-model triage, never signing):** diff analysis between
commits, semantic checklist vs whitepaper, proof-corpus completeness review,
AiWrangler MCP acknowledgement records (`review/aiwrangler-acks.json`).

**Dry-run escapes (recorded, never for real audits):**
`HACVSP_ALLOW_STRUCTURAL_SIGNOFF=1`, `HACVSP_ALLOW_UNSIGNED=1`.
