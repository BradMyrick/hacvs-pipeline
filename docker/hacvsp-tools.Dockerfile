# HACVSP tools image — every version digest/sha256-pinned via docker/pins.env.
# syntax=docker/dockerfile:1.7
# Build: docker compose --env-file docker/pins.env -f docker/compose.yaml build tools

ARG TOOLS_BASE=python:3.11-bookworm@sha256:815dd89cd46d15d8677cb9ab1101450d5af2a103c2735577ade547b1735416ab
FROM ${TOOLS_BASE}

ARG SOLC_VERSION=0.8.38
ARG SOLC_COMMIT=commit.1835d247
ARG SOLC_SHA256=UNPINNED
ARG FOUNDRY_VERSION=v1.9.0
ARG FOUNDRYUP_SHA256=UNPINNED
ARG SLITHER_VERSION=0.11.6
ARG ADERYN_VERSION=0.6.8
ARG ADERYN_SHA256=UNPINNED
ARG ECHIDNA_VERSION=2.4.0
ARG ECHIDNA_SHA256=UNPINNED
ARG MEDUSA_VERSION=1.5.1
ARG MEDUSA_SHA256=UNPINNED
ARG MYTHRIL_VERSION=0.24.8
ARG HEVM_VERSION=0.58.0
ARG HEVM_SHA256=UNPINNED
ARG SCRIBBLE_VERSION=0.7.10
ARG GAMBIT_VERSION=1.0.6
ARG GAMBIT_SHA256=UNPINNED
ARG COSIGN_VERSION=3.1.4
ARG COSIGN_SHA256=UNPINNED
ARG SYFT_VERSION=1.57.0
ARG SYFT_SHA256=UNPINNED
ARG TRIVY_VERSION=0.76.2
ARG TRIVY_SHA256=UNPINNED

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
      git curl xz-utils jq ca-certificates gnupg build-essential \
      libssl-dev pkg-config nodejs npm; \
    rm -rf /var/lib/apt/lists/*

# Container git must accept host-owned engagement checkouts (uid mismatch)
RUN git config --global --add safe.directory '*'

# --- solc (static binary, sha256-pinned from binaries.soliditylang.org) ------
RUN set -eux; \
    curl -fsSL \
      "https://binaries.soliditylang.org/linux-amd64/solc-linux-amd64-v${SOLC_VERSION}+${SOLC_COMMIT}" \
      -o /usr/local/bin/solc; \
    if [ "${SOLC_SHA256}" != "UNPINNED" ]; then \
      echo "${SOLC_SHA256}  /usr/local/bin/solc" | sha256sum -c -; \
    else echo "!! WARN: solc artifact UNPINNED — run make pin"; fi; \
    chmod +x /usr/local/bin/solc; \
    solc --version

# --- Foundry (foundryup bootstrap + pinned stable release) --------------------
# NOTE: foundry.paradigm.xyz is now the foundryup *bootstrap*: it installs only
# the foundryup tool. The pinned toolchain comes from `foundryup --install`.
RUN set -eux; \
    curl -fsSL https://foundry.paradigm.xyz -o /tmp/foundryup.sh; \
    if [ "${FOUNDRYUP_SHA256}" != "UNPINNED" ]; then \
      echo "${FOUNDRYUP_SHA256}  /tmp/foundryup.sh" | sha256sum -c -; \
    else echo "!! WARN: foundryup UNPINNED — run make pin"; fi; \
    bash /tmp/foundryup.sh; \
    export PATH="/root/.foundry/bin:${PATH}"; \
    foundryup --install "${FOUNDRY_VERSION}"; \
    test -x /root/.foundry/bin/forge; \
    test -x /root/.foundry/bin/cast; \
    test -x /root/.foundry/bin/anvil; \
    ln -s /root/.foundry/bin/forge /usr/local/bin/forge; \
    ln -s /root/.foundry/bin/cast  /usr/local/bin/cast; \
    ln -s /root/.foundry/bin/anvil /usr/local/bin/anvil; \
    forge --version

# --- Python tooling (isolated venvs: mythril's pinned legacy deps conflict
#     with slither's modern dependency tree — each analyzer gets its own env) --
RUN set -eux; \
    python3 -m venv /opt/venv-slither; \
    /opt/venv-slither/bin/pip install --no-cache-dir "slither-analyzer==${SLITHER_VERSION}"; \
    python3 -m venv /opt/venv-mythril; \
    /opt/venv-mythril/bin/pip install --no-cache-dir "mythril==${MYTHRIL_VERSION}"; \
    ln -s /opt/venv-slither/bin/slither /usr/local/bin/slither; \
    for extra in /opt/venv-slither/bin/slither-*; do ln -s "$extra" /usr/local/bin/; done; \
    ln -s /opt/venv-mythril/bin/myth /usr/local/bin/myth; \
    ln -s /opt/venv-mythril/bin/mythril /usr/local/bin/mythril || true; \
    slither --version; myth version || true

# --- Node tooling (npm, version-pinned) ---------------------------------------
RUN set -eux; \
    npm install -g "eth-scribble@${SCRIBBLE_VERSION}"; \
    scribble --version

# --- Prebuilt release binaries (sha256-pinned when frozen) ---------------------

# Aderyn (prebuilt x86_64-linux tarball — no Rust toolchain in the supply chain)
RUN set -eux; \
    curl -fsSL \
      "https://github.com/Cyfrin/aderyn/releases/download/aderyn-v${ADERYN_VERSION}/aderyn-x86_64-unknown-linux-gnu.tar.xz" \
      -o /tmp/aderyn.tar.xz; \
    if [ "${ADERYN_SHA256}" != "UNPINNED" ]; then \
      echo "${ADERYN_SHA256}  /tmp/aderyn.tar.xz" | sha256sum -c -; \
    else echo "!! WARN: aderyn UNPINNED — run make pin"; fi; \
    tar -xJf /tmp/aderyn.tar.xz -C /tmp; \
    install -m 0755 /tmp/aderyn-x86_64-unknown-linux-gnu/aderyn /usr/local/bin/aderyn; \
    aderyn --version

# Gambit (prebuilt linux binary)
RUN set -eux; \
    curl -fsSL \
      "https://github.com/Certora/gambit/releases/download/v${GAMBIT_VERSION}/gambit-linux-v${GAMBIT_VERSION}" \
      -o /usr/local/bin/gambit; \
    if [ "${GAMBIT_SHA256}" != "UNPINNED" ]; then \
      echo "${GAMBIT_SHA256}  /usr/local/bin/gambit" | sha256sum -c -; \
    else echo "!! WARN: gambit UNPINNED — run make pin"; fi; \
    chmod +x /usr/local/bin/gambit; \
    gambit --version || true

# hevm (symbolic execution of forge tests; argotorg fork — halmos successor)
RUN set -eux; \
    curl -fsSL \
      "https://github.com/argotorg/hevm/releases/download/release/${HEVM_VERSION}/hevm-x86_64-linux" \
      -o /usr/local/bin/hevm; \
    if [ "${HEVM_SHA256}" != "UNPINNED" ]; then \
      echo "${HEVM_SHA256}  /usr/local/bin/hevm" | sha256sum -c -; \
    else echo "!! WARN: hevm UNPINNED — run make pin"; fi; \
    chmod +x /usr/local/bin/hevm; \
    hevm --version

# Echidna
RUN set -eux; \
    curl -fsSL \
      "https://github.com/crytic/echidna/releases/download/v${ECHIDNA_VERSION}/echidna-${ECHIDNA_VERSION}-x86_64-linux.tar.gz" \
      -o /tmp/echidna.tar.gz; \
    if [ "${ECHIDNA_SHA256}" != "UNPINNED" ]; then \
      echo "${ECHIDNA_SHA256}  /tmp/echidna.tar.gz" | sha256sum -c -; \
    else echo "!! WARN: echidna UNPINNED — run make pin"; fi; \
    tar -xzf /tmp/echidna.tar.gz -C /tmp; \
    install -m 0755 /tmp/echidna /usr/local/bin/echidna; \
    echidna --version

# Medusa
RUN set -eux; \
    curl -fsSL \
      "https://github.com/crytic/medusa/releases/download/v${MEDUSA_VERSION}/medusa-linux-x64.tar.gz" \
      -o /tmp/medusa.tar.gz; \
    if [ "${MEDUSA_SHA256}" != "UNPINNED" ]; then \
      echo "${MEDUSA_SHA256}  /tmp/medusa.tar.gz" | sha256sum -c -; \
    else echo "!! WARN: medusa UNPINNED — run make pin"; fi; \
    tar -xzf /tmp/medusa.tar.gz -C /tmp; \
    install -m 0755 /tmp/medusa /usr/local/bin/medusa; \
    medusa --help > /dev/null

# Cosign
RUN set -eux; \
    curl -fsSL \
      "https://github.com/sigstore/cosign/releases/download/v${COSIGN_VERSION}/cosign-linux-amd64" \
      -o /usr/local/bin/cosign; \
    if [ "${COSIGN_SHA256}" != "UNPINNED" ]; then \
      echo "${COSIGN_SHA256}  /usr/local/bin/cosign" | sha256sum -c -; \
    else echo "!! WARN: cosign UNPINNED — run make pin"; fi; \
    chmod +x /usr/local/bin/cosign; \
    cosign version

# Syft
RUN set -eux; \
    curl -fsSL \
      "https://github.com/anchore/syft/releases/download/v${SYFT_VERSION}/syft_${SYFT_VERSION}_linux_amd64.tar.gz" \
      -o /tmp/syft.tar.gz; \
    if [ "${SYFT_SHA256}" != "UNPINNED" ]; then \
      echo "${SYFT_SHA256}  /tmp/syft.tar.gz" | sha256sum -c -; \
    else echo "!! WARN: syft UNPINNED — run make pin"; fi; \
    tar -xzf /tmp/syft.tar.gz -C /tmp; \
    install -m 0755 /tmp/syft /usr/local/bin/syft; \
    syft version

# Trivy
RUN set -eux; \
    curl -fsSL \
      "https://github.com/aquasecurity/trivy/releases/download/v${TRIVY_VERSION}/trivy_${TRIVY_VERSION}_Linux-64bit.tar.gz" \
      -o /tmp/trivy.tar.gz; \
    if [ "${TRIVY_SHA256}" != "UNPINNED" ]; then \
      echo "${TRIVY_SHA256}  /tmp/trivy.tar.gz" | sha256sum -c -; \
    else echo "!! WARN: trivy UNPINNED — run make pin"; fi; \
    tar -xzf /tmp/trivy.tar.gz -C /tmp; \
    install -m 0755 /tmp/trivy /usr/local/bin/trivy; \
    trivy --version

ENV PATH="/root/.foundry/bin:${PATH}"
WORKDIR /engagement
ENTRYPOINT ["/bin/bash"]
