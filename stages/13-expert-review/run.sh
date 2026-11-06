#!/usr/bin/env bash
# Stage 13 — expert threat model & frontier review (RELEASE tier)
# THE HUMAN LANE: the Principal Security Engineer (Kodr.pro) is the gate.
# The runner validates deliverables + signature; the agent drafts, the expert rules.
set -uo pipefail
umask 0000  # container-created evidence stays host-manageable (runners execute as root)
ENG="${ENGAGEMENT_DIR:-/engagement}"
TARGET="$ENG/target"; ART="$ENG/artifacts"
mkdir -p "$ART" "$ENG/review"
stage_fail=0
note() { echo "[stage-13] $*"; }
fail() { echo "[stage-13] FAIL: $*" | tee "$ART/stage-13-failures.txt" >&2; exit 1; }

cd "$TARGET" || { fail "target/ missing"; exit 1; }

# --- Deliverable presence + mandatory section checks
check_sections() { # check_sections FILE header1 header2...
  local f="$1"; shift
  [ -f "$f" ] || { fail "missing deliverable: $f"; return 1; }
  local missing=0
  for h in "$@"; do
    grep -qiE "^#+ .*$h" "$f" || { fail "$f missing section: $h"; missing=1; }
  done
  return $missing
}

check_sections "$ENG/review/THREAT_MODEL.md" "Actor Matrix" "Trust Boundaries" "Economic Vectors" "MEV Exposure" || true
check_sections "$ENG/review/SPEC_AUDIT.md" "Invariant Completeness" "Whitepaper Concordance" || true
check_sections "$ENG/review/MANUAL_REVIEW_SIGNOFF.md" "High-Risk Assembly" "Internal Accounting" "Suppression Audit" "Signature" || true

# --- Suppression ratification: every canonical digest must appear in the signoff
python3 - "$ENG" "$ART" <<'PY' || fail "suppression ratification incomplete"
import json, pathlib, sys
eng, art = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
summ_f = eng / "artifacts" / "static-analysis-summary.json"
digests = []
if summ_f.exists():
    try:
        digests = json.loads(summ_f.read_text()).get("suppression_canonical_digests", [])
    except Exception:
        pass
signoff_f = eng / "review" / "MANUAL_REVIEW_SIGNOFF.md"
text = signoff_f.read_text() if signoff_f.exists() else ""
unratified = [d[:12] for d in digests if d[:12] not in text]
out = {"suppression_digests": len(digests), "unratified_prefixes": unratified}
(art / "suppression-ratification.json").write_text(json.dumps(out, indent=2) + "\n")
print(json.dumps(out))
sys.exit(1 if unratified else 0)
PY

# --- Signature verification: expert must have signed the signoff payload
# Supports two signing methods:
#   1. cosign (if KODR_PUBKEY is set and cosign is available)
#   2. ssh-keygen (if signatures/manual-signoff.pub exists alongside the .sig)
SIGNOFF="$ENG/review/MANUAL_REVIEW_SIGNOFF.md"
SIG="$ENG/signatures/manual-signoff.sig"
SIGPUB="$ENG/signatures/manual-signoff.pub"
VERIFIED="false"

if [ -f "$SIGNOFF" ] && [ -f "$SIG" ]; then
  if [ -n "${KODR_PUBKEY:-}" ] && [ -f "${KODR_PUBKEY}" ] && command -v cosign >/dev/null 2>&1; then
    # cosign path
    if cosign verify-blob --key "$KODR_PUBKEY" --signature "$SIG" "$SIGNOFF" \
        > "$ART/signoff-verify.txt" 2>&1; then
      VERIFIED="true"; note "cosign signature VERIFIED"
    else
      fail "cosign signature verification FAILED — see artifacts/signoff-verify.txt"
    fi
  elif [ -f "$SIGPUB" ]; then
    # ssh-keygen path: verify using allowed-signers format
    DIGEST=$(sha256sum "$SIGNOFF" | cut -d' ' -f1)
    ALLOWED=$(mktemp)
    echo "reviewer $(cat "$SIGPUB")" > "$ALLOWED"
    if echo "$DIGEST" | ssh-keygen -Y verify -f "$ALLOWED" -I reviewer \
        -n hacvsp -s "$SIG" 2>/dev/null; then
      VERIFIED="true"; note "ssh-keygen signature VERIFIED"
    else
      fail "ssh-keygen signature verification FAILED — signature/key mismatch"
    fi
    rm -f "$ALLOWED"
  elif [ "${HACVSP_ALLOW_STRUCTURAL_SIGNOFF:-0}" = "1" ]; then
    note "structural signoff mode (HACVSP_ALLOW_STRUCTURAL_SIGNOFF=1) — recorded, NOT cryptographic"
  else
    fail "no verification method available: set KODR_PUBKEY for cosign, or use the dashboard's Sign button (which stores the pubkey alongside the signature)"
  fi
fi

python3 - "$ART" "$VERIFIED" <<'PY'
import json, pathlib, sys
art, verified = pathlib.Path(sys.argv[1]), sys.argv[2]
summary = {"deliverables": {
    "THREAT_MODEL.md": (pathlib.Path("/engagement/review/THREAT_MODEL.md")).exists(),
    "SPEC_AUDIT.md": (pathlib.Path("/engagement/review/SPEC_AUDIT.md")).exists(),
    "MANUAL_REVIEW_SIGNOFF.md": (pathlib.Path("/engagement/review/MANUAL_REVIEW_SIGNOFF.md")).exists(),
}, "signature_verified": verified == "true"}
(art / "expert-review-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
PY

note "AiWrangler MCP: human-review acknowledgements (wrangler_ack) recorded in"
note "review/aiwrangler-acks.json complete this lane's audit trail."

exit $stage_fail
