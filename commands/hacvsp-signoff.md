---
description: Drive the Stage-13 expert sign-off flow (threat model, spec audit, cosign)
---

# /hacvsp-signoff — expert review + cryptographic sign-off

Load the `kodr-audit` skill. This command is the Stage 13 human-lane driver.
The user is the Principal Security Engineer; you prepare and verify, never sign.

1. **Pre-flight:** `hacvsp status --engagement <slug>` — stages 1–12 must be GO.
2. **Draft if absent** (in `engagements/<slug>/review/`):
   - `THREAT_MODEL.md` — Actor Matrix / Trust Boundaries / Economic Vectors /
     MEV Exposure; mine ACCESS_CONTROL_MATRIX.json PUBLIC rows, event-audit
     gaps, mythril hits, fork-test oracle behavior.
   - `SPEC_AUDIT.md` — Invariant Completeness / Whitepaper Concordance; map
     every invariant to its enforcing test/proof.
   - `MANUAL_REVIEW_SIGNOFF.md` skeleton with High-Risk Assembly / Internal
     Accounting / Suppression Audit sections and one line per suppression
     digest prefix from `artifacts/static-analysis-summary.json`.
3. **User review loop:** present the drafts; the user edits/approves each.
4. **Signature:** have the user sign:
   `cosign sign-blob --key "$COSIGN_KEY" review/MANUAL_REVIEW_SIGNOFF.md --output-file signatures/manual-signoff.sig`
   and ensure `KODR_PUBKEY` is set in the engagement `.env`. Never touch the
   key material yourself; give the commands.
5. **Verify:** `hacvsp stage 13 --engagement <slug>` — the gate validates
   sections, ratification digests, and the cosign signature. Report the
   verdict, then tee up stage 14.
