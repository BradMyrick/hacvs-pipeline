#!/usr/bin/env bash
# Stage 14 — cryptographic attestation & proof packaging (RELEASE tier)
# Gate: all signed attestations, verifiable hashes, suppression tables, and
#       execution logs committed to the public repository root (engagement root).
set -uo pipefail
umask 0000  # container-created evidence stays host-manageable (runners execute as root)
ENG="${ENGAGEMENT_DIR:-/engagement}"
TARGET="$ENG/target"; ART="$ENG/artifacts"
mkdir -p "$ART" "$ENG/signatures"
stage_fail=0
note() { echo "[stage-14] $*"; }
fail() { echo "[stage-14] FAIL: $*" | tee "$ART/stage-14-failures.txt" >&2; exit 1; }

command -v cosign >/dev/null 2>&1 || { fail "cosign not available in image"; exit 1; }

note "assembling bundle (SECURITY_ASSURANCE.md, manifest, provenance)"
python3 /pipeline/tools/attest/attest.py assemble --engagement "$ENG" \
  || fail "bundle assembly failed"

MISSING="$(python3 -c "import json;print(' '.join(json.load(open('$ART/bundle-manifest.json'))['missing']))")"
if [ -n "$MISSING" ]; then
  fail "bundle incomplete — missing: $MISSING (upstream stages must produce these)"
fi

note "signing bundle manifest"
if [ -n "${COSIGN_KEY:-}" ]; then
  cosign sign-blob --key "$COSIGN_KEY" \
    --output-file "$ENG/signatures/bundle-attestation.sig" \
    "$ART/bundle-manifest.json" \
    || fail "cosign sign-blob failed"
  note "signature written: signatures/bundle-attestation.sig"
else
  if [ "${HACVSP_ALLOW_UNSIGNED:-0}" = "1" ]; then
    note "HACVSP_ALLOW_UNSIGNED=1 — unsigned bundle recorded (DRY-RUN ONLY)"
  else
    fail "COSIGN_KEY unset — cannot sign bundle (fail-closed; set COSIGN_KEY in engagement .env)"
  fi
fi

note "verifying bundle integrity"
python3 /pipeline/tools/attest/attest.py verify --engagement "$ENG" \
  || fail "bundle verification failed (digest drift after assembly?)"

# Optional on-chain verification mapping (Sourcify/explorer), when deployments declared
python3 - "$ENG" <<'PY'
import json, pathlib, sys
eng = pathlib.Path(sys.argv[1])
meta = json.loads((eng / "engagement.json").read_text())
deploys = (meta.get("deployment") or {}).get("addresses") or {}
if deploys:
    print("[stage-14] deployment addresses declared — run Sourcify verification per "
          "SECURITY_ASSURANCE.md mapping (cast verify-check / sourcify --check)")
PY

exit $stage_fail
