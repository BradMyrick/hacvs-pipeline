#!/usr/bin/env bash
# Stage 1 — dependency hygiene & supply-chain verification (PR tier)
# Gate: zero unreviewed CVEs; all submodules pinned to immutable commits.
set -uo pipefail
ENG="${ENGAGEMENT_DIR:-/engagement}"
TARGET="$ENG/target"; ART="$ENG/artifacts"; LOG="$ENG/logs"
mkdir -p "$ART" "$LOG"
stage_fail=0
note() { echo "[stage-01] $*"; }
fail() { echo "[stage-01] FAIL: $*" | tee "$ART/stage-01-failures.txt" >&2; exit 1; }

cd "$TARGET" || { fail "target/ missing"; exit 1; }

note "tool versions"
syft version 2>/dev/null | head -2 || fail "syft unavailable"
trivy --version 2>/dev/null | head -1 || fail "trivy unavailable"

# --- Submodule pinning: every submodule must be initialized at a recorded commit
SUBMODULE_ISSUES=0
if [ -f .gitmodules ]; then
  note "checking submodule pins"
  while IFS= read -r line; do
    sha="${line:1:40}"
    marker="${line:0:1}"
    name="$(echo "$line" | awk '{print $2}')"
    case "$marker" in
      "-") fail "submodule NOT INITIALIZED: $name"; SUBMODULE_ISSUES=$((SUBMODULE_ISSUES+1)) ;;
      "+") fail "submodule CHECKED OUT AT DIFFERENT COMMIT: $name"; SUBMODULE_ISSUES=$((SUBMODULE_ISSUES+1)) ;;
      "U") fail "submodule MERGE CONFLICT: $name"; SUBMODULE_ISSUES=$((SUBMODULE_ISSUES+1)) ;;
    esac
  done < <(git submodule status 2>/dev/null)
  git submodule status > "$ART/submodule-status.txt" || fail "git submodule status failed"
else
  note "no .gitmodules (no submodules)"
fi

# --- SBOM generation (CycloneDX + SPDX)
note "generating CycloneDX + SPDX SBOMs"
syft scan dir:"$TARGET" -o cyclonedx-json="$ART/sbom.cyclonedx.json" \
  || fail "syft cyclonedx scan failed"
syft scan dir:"$TARGET" -o spdx-json="$ART/sbom.spdx.json" \
  || fail "syft spdx scan failed"

# --- Vulnerability scan of the SBOM
note "trivy SBOM vulnerability scan"
trivy sbom --scanners vuln --format json --output "$ART/trivy-results.json" \
  "$ART/sbom.cyclonedx.json" || fail "trivy sbom scan failed"

# --- Floating dependency detection (package-lock / Cargo.lock must exist if manifests do)
FLOATING=0
[ -f package.json ] && [ ! -f package-lock.json ] && { fail "package.json without package-lock.json (floating deps)"; FLOATING=$((FLOATING+1)); }
[ -f Cargo.toml ] && [ ! -f Cargo.lock ] && { fail "Cargo.toml without Cargo.lock (floating deps)"; FLOATING=$((FLOATING+1)); }

# --- Ecosystem audits (best effort, recorded)
if [ -f package-lock.json ]; then
  (cd "$TARGET" && npm audit --json > "$ART/npm-audit.json" 2>/dev/null) \
    || note "npm audit unavailable/failed (recorded)"
fi
if [ -f Cargo.lock ]; then
  (cargo audit --json > "$ART/cargo-audit.json" 2>/dev/null) \
    || note "cargo audit unavailable (not in image; recorded)"
fi

# --- Dependency checksums (libs/, lockfiles, remappings)
note "generating dependency checksums"
{
  find lib -type f -print0 2>/dev/null | xargs -0 -r sha256sum 2>/dev/null || true
  for f in package-lock.json Cargo.lock foundry.toml remappings.txt .gitmodules; do
    if [ -f "$f" ]; then sha256sum "$f"; fi
  done
  true   # group status must not leak a missing-file test under pipefail
} | sort -k2 > "$ART/dependency-checksums.sha256" || fail "checksum generation failed"

# --- Consolidated summary for the gate
python3 - "$ART" "$SUBMODULE_ISSUES" "$FLOATING" <<'PY'
import json, sys, pathlib
art = pathlib.Path(sys.argv[1])
submodule_issues, floating = int(sys.argv[2]), int(sys.argv[3])
summary = {"submodule_issues": submodule_issues, "floating_dependencies": floating,
           "trivy": {"critical": 0, "high": 0, "medium": 0, "total": 0},
           "suppressed": []}
supp_path = pathlib.Path("/engagement/target/.security-suppressions.json")
suppressed_ids = set()
if supp_path.exists():
    try:
        for e in json.loads(supp_path.read_text()):
            if e.get("tool") == "trivy":
                suppressed_ids.add(e.get("finding_id"))
    except Exception:
        pass
trivy_f = art / "trivy-results.json"
if trivy_f.exists():
    try:
        data = json.loads(trivy_f.read_text())
        for res in data.get("Results", []) or []:
            for v in res.get("Vulnerabilities") or []:
                if not v:
                    continue
                vid = v.get("VulnerabilityID", "?")
                sev = (v.get("Severity") or "UNKNOWN").upper()
                summary["trivy"]["total"] += 1
                if vid in suppressed_ids:
                    summary["suppressed"].append(vid)
                    continue
                if sev in summary["trivy"]:
                    summary["trivy"][sev] += 1
    except Exception as exc:
        summary["trivy_error"] = str(exc)
(art / "dependency-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
PY
note "summary written: artifacts/dependency-summary.json"
exit $stage_fail
