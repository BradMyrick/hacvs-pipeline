# Stage 13 Runbook — Expert Threat Model & Frontier Review

**Cadence:** RELEASE tier · **Gate:** GO/NO-GO — **the Principal Security Engineer (you) IS the gate.**

**Spec criteria:** _Signed cryptographic approval by Principal Security Engineer certifying threat model coverage, invariant completeness, and suppression justifications._

## Division of labor
| Actor | Does |
|---|---|
| **Principal Security Engineer (Kodr.pro)** | spec-vs-whitepaper audit, privilege/governance escalation mapping against `ACCESS_CONTROL_MATRIX.json`, economic/oracle/MEV analysis, composability review, final ratification of all suppressions + coverage exceptions |
| **Frontier Model Auxiliary Triage** (separate OpenCode agent session) | adversarial commit-diff analysis, semantic business-logic checklist vs whitepaper, second pair of eyes on hevm/Kontrol corpus completeness |
| **AiWrangler MCP** (0.1.5) | AST-diff triage assistance + `wrangler_ack` human-review acknowledgements recorded in `review/aiwrangler-acks.json` |

## Deliverables (runner-validated)
`review/THREAT_MODEL.md` — sections: **Actor Matrix, Trust Boundaries, Economic Vectors, MEV Exposure**
`review/SPEC_AUDIT.md` — sections: **Invariant Completeness, Whitepaper Concordance**
`review/MANUAL_REVIEW_SIGNOFF.md` — sections: **High-Risk Assembly, Internal Accounting, Suppression Audit, Signature** + one line per ratified suppression digest prefix (the runner fails if any digest from Stage 3 is missing)

## Signing flow (fail-closed)
```bash
# 1. expert reviews + edits the three docs in engagements/<slug>/review/
# 2. signs:
cosign sign-blob --key "$COSIGN_KEY" \
  engagements/<slug>/review/MANUAL_REVIEW_SIGNOFF.md \
  --output-file engagements/<slug>/signatures/manual-signoff.sig
# 3. verification key recorded in engagement .env:
echo 'KODR_PUBKEY=/path/to/cosign.pub' >> engagements/<slug>/.env
# 4. re-run: hacvsp stage 13 --engagement <slug>
```
Without `KODR_PUBKEY` the gate fails closed. `HACVSP_ALLOW_STRUCTURAL_SIGNOFF=1` records a non-cryptographic signoff — for dry-runs only, never a real audit.

## The `/hacvsp-signoff` command drives this whole flow conversationally.
