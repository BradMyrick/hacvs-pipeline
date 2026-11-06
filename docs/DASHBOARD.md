# hacsvp ui — Operator Dashboard

`hacsvp ui` serves a localhost-only web cockpit over your engagements:
fleet overview, gate ledgers, findings triage (sign & suppress / reject),
the stage-13 ratification queue and form editors, stage run/gate actions,
and the bundle preview.

```bash
hacvsp ui                 # http://127.0.0.1:8787
hacvsp ui --port 9000     # different port
```

## What it writes

Every action is ONE atomic file write to the SAME files the pipeline reads
(plus a line in `engagements/<slug>/activity.log`):

- **Sign & suppress** → appends a signed entry to the target's
  `.security-suppressions.json` (canonical digest signed via `ssh-keygen -Y
  sign`, namespace `hacvsp`). Requires typing the engagement slug to confirm.
- **Reject → fixtask** → appends to `review/FIXTASKS.md`.
- **Review docs** → saves `review/{THREAT_MODEL,SPEC_AUDIT,MANUAL_REVIEW_SIGNOFF}.md`;
  warns on missing mandatory sections (the stage-13 gate stays authoritative).
- **Sign-off** → signs `MANUAL_REVIEW_SIGNOFF.md` into
  `signatures/manual-signoff.sig` — the same artifact stage 13 verifies.
- **Stage run/gate** → launches the exact `hacvsp stage` CLI (`det` checkbox
  = `--detach`), logged to `logs/ui-actions.log`.

## Signing keys

Key discovery: `HACVSP_SIGN_KEY` env var → `~/.ssh/id_ed25519` fallback.
Keys never enter the browser; the server process signs on the host.

## Security

- Binds `127.0.0.1` only. Off-localhost binds print a warning — don't.
- Audit evidence and sign actions have no auth layer; the localhost bind IS
  the boundary.
- `.env` is never read by the UI.

## Server engagements

Engagements are files. Run `hacvsp ui` on the machine where they live
(overnight mutation/fuzz/kontrol runs), then from your laptop:

```bash
ssh -L 8787:localhost:8787 <server>
```

## CLI data emitters (same layer, scriptable)

```bash
hacvsp fleet --json
hacvsp findings --engagement <slug> --json
hacvsp pending --engagement <slug> --json
```
