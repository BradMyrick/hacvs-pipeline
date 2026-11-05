# HACVSP Operations Guide

**Kodr.pro High-Assurance Contract Verification & Security Pipeline v0.1.0**
Workstation: `/home/kodr/Audits/hacvsp` (override with `HACVSP_ROOT`).

## 1. First-time setup (per machine)

```bash
cd $HACVSP_ROOT
make build          # build pinned toolchain images (tools + kontrol)
make pin            # freeze digests/sha256s into docker/pins.env
make doctor         # expect: DOCTOR: GO
make verify         # pipeline <-> SPEC.json concordance: GO
make test           # custom-tool unit tests
```

Note: `make pin` requires network to record artifact sha256s; Kontrol's base
digest ships pre-frozen. Until `make pin` runs, remaining `UNPINNED` entries
put `doctor` in bootstrap mode — stages refuse to run.

## 2. Developing a new contract (workstation flow)

```bash
hacvsp init MyProtocol --dir ~/dev/MyProtocol     # or /hacvsp-init MyProtocol
cd ~/dev/MyProtocol
# pin deps, write contracts, wire test suites (see its README)
git add -A && git commit -m "feat: initial"
hacvsp audit ~/dev/MyProtocol --name myprotocol   # local path is fine
```

## 3. Auditing a repo (engagement flow)

```bash
hacvsp audit https://github.com/client/protocol --commit <sha> --name <slug>
$EDITOR engagements/<slug>/intake.md              # answer with the client
$EDITOR engagements/<slug>/engagement.json        # mirror applicability
hacvsp stage 1 --engagement <slug>                # ... through stage 7
hacvsp status --engagement <slug>
# checkpoint: ratify suppressions + coverage exceptions
hacvsp stage 8 --engagement <slug>
hacvsp stage 9 --engagement <slug> --detach       # overnight runner
hacvsp stage 10 --engagement <slug> --detach
hacvsp stage 11 --engagement <slug>
hacvsp stage 12 --engagement <slug> --detach
# stage 13: /hacvsp-signoff (expert lane)
hacvsp stage 14 --engagement <slug>               # bundle + cosign
```

The `/audit` command automates this conversationally.

## 4. Laptop ↔ server (overnight tier)

Engagements are plain files; git is the transport:

```bash
# laptop
git -C $HACVSP_ROOT push origin main
# server
git -C $path/to/hacvsp pull && make build doctor
hacvsp stage 10 --engagement <slug> --detach
hacvsp logs 10 --engagement <slug>        # tail progress anytime
hacvsp gate 10 --engagement <slug>        # after completion
git add engagements/<slug> && git commit -m "engagement(<slug>): stage 10 evidence"
# laptop
git pull && hacvsp status --engagement <slug>
```

Requirements on the server: docker, git, python3. Nothing else.

## 5. Re-running and history

- Verdicts are append-only; the latest per stage is authoritative.
- `hacvsp gate N` re-evaluates without re-running tools (after fixes).
- `hacvsp stage N --force` bypasses ordering and is recorded in the verdict.

## 6. Publishing the audit

The engagement directory minus `target/` and `.env` is the public audit repo:
`SECURITY_ASSURANCE.md`, `artifacts/`, `signatures/`, `review/`, ledger,
logs. Push it; the bundle signature (`cosign verify-blob --key <pub>` over
`artifacts/bundle-manifest.json`) lets anyone verify integrity.

## 7. Maintenance

- Tool version bumps = spec changes: edit SPEC.json + pins.env together;
  `make gates` regenerates gates.json; `make verify` must stay GO.
- Custom tools are stdlib-Python with unit tests: `make test`.
