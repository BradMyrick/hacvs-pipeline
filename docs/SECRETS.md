# Secrets Policy (HACVSP)

Aligned with the Kodr personal hard rules. Non-negotiable.

## Storage
- Engagement secrets live in `engagements/<slug>/.env` — created 0600 from
  `.env.example`, **gitignored** (root `.gitignore` enforces).
- Secret names only in logs and ledgers. A rendered value is a rotation event.

## Known secrets
| Name | Used by | Notes |
|---|---|---|
| `HACVSP_FORK_RPC` | Stage 7 fork tests | archive-node RPC URL; treat as credential (embedded API keys) |
| `COSIGN_KEY` / `COSIGN_PASSWORD` | Stages 13–14 signing | key file path / passphrase; pass via env, never argv |
| `KODR_PUBKEY` | Stage 13 verification | public key path — not secret, but pin its path |

## Rules
1. Raw values enter via `.env` files or hidden prompts — never as
   command-line arguments (process lists are public).
2. When key material rotates, enumerate every copy (`.env` files across
   engagements, backups) and rotate in one pass; verify the pair before done.
3. Sweep-then-destroy: never delete key material in the same command that
   recovers values; verify recovery first.
4. The pipeline never commits `.env`; `git status` before any commit of
   engagement evidence is mandatory.
5. CI equivalents: GitHub Actions secrets only; the workflows reference
   `secrets.*` names, never values.
