#!/usr/bin/env bash
# HACVSP pin freezer — records digests/sha256s of base images, release
# artifacts, and built images into docker/pins.env.
#
# This script only ADDS/updates pin values. It never deletes files
# (deletion policy: kodr AGENTS.local.md). Use --force to overwrite an
# existing frozen pin; default skips already-frozen entries.
set -euo pipefail
cd "$(dirname "$0")/.."

PINS=docker/pins.env
FORCE="${1:-}"

update_pin() {  # update_pin KEY VALUE
  local key="$1" value="$2" cur
  cur="$(grep -E "^${key}=" "$PINS" | cut -d= -f2- || true)"
  if [[ "$cur" == "$value" ]]; then return 0; fi
  if [[ "$cur" != "UNPINNED" && "$cur" != "" && "$FORCE" != "--force" ]]; then
    echo "skip ${key}: already pinned (${cur}); use --force to change" >&2
    return 0
  fi
  echo "pin  ${key}=${value}"
  sed -i "s|^${key}=.*|${key}=${value}|" "$PINS"
}

fetch_sha() {  # fetch_sha URL
  curl -fsSL "$1" | sha256sum | cut -d' ' -f1
}

echo "==> freezing base-image digests"
update_pin BASE_TOOLS_DIGEST \
  "sha256:$(docker manifest inspect python:3.11-bookworm 2>/dev/null | jq -r '.manifests[0].digest // .config.digest' | sed 's/sha256://')"
# BASE_KONTROL_DIGEST is intentionally NOT auto-updated: `docker manifest
# inspect` returns the per-arch manifest digest, which the registry refuses to
# serve by reference. Bump it manually from the Docker Hub API on version
# changes: https://hub.docker.com/v2/repositories/runtimeverificationinc/kontrol/tags

echo "==> freezing release-artifact sha256s (downloads each artifact once)"
V_ECHIDNA="$(grep -E '^ECHIDNA_VERSION=' "$PINS" | cut -d= -f2-)"
V_MEDUSA="$(grep -E '^MEDUSA_VERSION=' "$PINS" | cut -d= -f2-)"
V_COSIGN="$(grep -E '^COSIGN_VERSION=' "$PINS" | cut -d= -f2-)"
V_SYFT="$(grep -E '^SYFT_VERSION=' "$PINS" | cut -d= -f2-)"
V_TRIVY="$(grep -E '^TRIVY_VERSION=' "$PINS" | cut -d= -f2-)"
V_GAMBIT="$(grep -E '^GAMBIT_VERSION=' "$PINS" | cut -d= -f2-)"

update_pin FOUNDRYUP_SHA256 "$(fetch_sha https://foundry.paradigm.xyz)"
update_pin ECHIDNA_SHA256 "$(fetch_sha "https://github.com/crytic/echidna/releases/download/v${V_ECHIDNA}/echidna-${V_ECHIDNA}-x86_64-linux.tar.gz")"
update_pin MEDUSA_SHA256 "$(fetch_sha "https://github.com/crytic/medusa/releases/download/v${V_MEDUSA}/medusa-linux-x64.tar.gz")"
update_pin COSIGN_SHA256 "$(fetch_sha "https://github.com/sigstore/cosign/releases/download/v${V_COSIGN}/cosign-linux-amd64")"
update_pin SYFT_SHA256 "$(fetch_sha "https://github.com/anchore/syft/releases/download/v${V_SYFT}/syft_${V_SYFT}_linux_amd64.tar.gz")"
update_pin TRIVY_SHA256 "$(fetch_sha "https://github.com/aquasecurity/trivy/releases/download/v${V_TRIVY}/trivy_${V_TRIVY}_Linux-64bit.tar.gz")"
update_pin GAMBIT_SHA256 "$(fetch_sha "https://github.com/Certora/gambit/releases/download/v${V_GAMBIT}/gambit-linux-v${V_GAMBIT}")"

echo "==> freezing built-image digests (run 'make build' first)"
TOOLS_IMAGE="$(grep -E '^TOOLS_IMAGE=' "$PINS" | cut -d= -f2-)"
KONTROL_IMAGE="$(grep -E '^KONTROL_IMAGE=' "$PINS" | cut -d= -f2-)"
if docker image inspect "$TOOLS_IMAGE" >/dev/null 2>&1; then
  update_pin TOOLS_IMAGE_DIGEST "sha256:$(docker image inspect "$TOOLS_IMAGE" --format '{{.Id}}' | sed 's/sha256://')"
fi
if docker image inspect "$KONTROL_IMAGE" >/dev/null 2>&1; then
  update_pin KONTROL_IMAGE_DIGEST "sha256:$(docker image inspect "$KONTROL_IMAGE" --format '{{.Id}}' | sed 's/sha256://')"
fi

echo "==> done. Remaining UNPINNED entries:"
grep '=UNPINNED' "$PINS" || echo "(none — toolchain fully frozen)"
