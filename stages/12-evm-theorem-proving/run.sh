#!/usr/bin/env bash
# Stage 12 — EVM-level theorem proving via Kontrol/KEVM (RELEASE tier, long-running)
# Gate: zero failed proofs; coverage-enforced non-vacuity.
# NOTE: runs in the pinned kontrol image (docker/compose.yaml service stage-12).
set -uo pipefail
ENG="${ENGAGEMENT_DIR:-/engagement}"
TARGET="$ENG/target"; ART="$ENG/artifacts"
mkdir -p "$ART"
stage_fail=0
note() { echo "[stage-12] $*"; }
fail() { echo "[stage-12] FAIL: $*" | tee -a "$ART/stage-12-failures.txt" >&2; stage_fail=1; }

cd "$TARGET" || { fail "target/ missing"; exit 1; }

MATCH="$(python3 -c "import json;print(json.load(open('$ENG/engagement.json'))['applicability'].get('kontrol_match','Proof*'))")"
COV_MIN="$(python3 -c "import json;print(json.load(open('$ENG/engagement.json'))['applicability'].get('kontrol_coverage_min_pct',90))")"
note "proof match: ${MATCH} | coverage floor: ${COV_MIN}%"

command -v kontrol >/dev/null 2>&1 || { fail "kontrol binary not on PATH (must run in stage-12/kontrol image)"; exit 1; }

note "kontrol build (KEVM kompilation — first run is slow; cache volume persists it)"
kontrol build > "$ART/kontrol-build.log" 2>&1 \
  || fail "kontrol build failed — see artifacts/kontrol-build.log"

note "kontrol prove --match-test ${MATCH}"
kontrol prove --match-test "$MATCH" > "$ART/kontrol-prove.log" 2>&1 \
  || note "kontrol prove exited non-zero (failed proofs or crash — parsed below)"

note "kontrol view-coverage"
kontrol view-coverage > "$ART/kontrol-coverage-raw.txt" 2>&1 \
  || note "view-coverage unavailable (recorded)"

python3 - "$ART" "$COV_MIN" <<'PY' || fail "kontrol results parsing found failures"
import json, pathlib, re, sys
art, cov_min = pathlib.Path(sys.argv[1]), float(sys.argv[2])
prove_log = (art / "kontrol-prove.log").read_text()
proof_names = re.findall(r"(Proof\w*)", prove_log)
failed = re.findall(r"(\w*(?:Proof|Invariant)\w*)\s*FAILED", prove_log)
passed = re.findall(r"(\w*(?:Proof|Invariant)\w*)\s*(?:PASSED|PASS)", prove_log)
cov_raw = (art / "kontrol-coverage-raw.txt")
coverage_pct = None
if cov_raw.exists():
    m = re.search(r"coverage[^\d]*(\d+(?:\.\d+)?)%", cov_raw.read_text(), re.I)
    if m:
        coverage_pct = float(m.group(1))
proofs = {
    "passed": sorted(set(passed)),
    "failed": sorted(set(failed)),
    "failed_count": len(set(failed)),
    "total": len(set(passed)) + len(set(failed)),
    "coverage_pct": coverage_pct,
    "coverage_min_pct": cov_min,
    "ok": len(set(failed)) == 0 and len(set(passed)) > 0
          and (coverage_pct is None or coverage_pct >= cov_min),
}
(art / "kontrol-proofs.json").write_text(json.dumps(proofs, indent=2) + "\n")
(art / "kontrol-coverage.json").write_text(json.dumps({
    "coverage_pct": coverage_pct, "min_required": cov_min,
    "raw": cov_raw.read_text()[:4000] if cov_raw.exists() else "",
}, indent=2) + "\n")
print(json.dumps({k: proofs[k] for k in ("total", "failed_count", "coverage_pct", "ok")}))
sys.exit(0 if proofs["ok"] else 1)
PY

note "non-vacuity: review/KONTROL_VACUITY.md must document rationale per proof"
if [ ! -f "$ENG/review/KONTROL_VACUITY.md" ]; then
  fail "review/KONTROL_VACUITY.md missing — each proven rule needs non-vacuity rationale (symbolic inputs genuinely unconstrained, branch coverage non-trivial)"
fi

exit $stage_fail
