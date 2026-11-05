# HACVSP Kontrol image — EVM-level theorem proving (Stage 12).
# Base is Runtime Verification's official Kontrol image, tag+digest pinned via
# docker/pins.env (BASE_KONTROL_TAG + BASE_KONTROL_DIGEST, Docker Hub API).
# syntax=docker/dockerfile:1.7
ARG KONTROL_BASE=runtimeverificationinc/kontrol:ubuntu-jammy-1.0.255@sha256:858f004144d61b005997f56bb8b7cd15673850286c96e0e5ec0502d9c9a9e204
FROM ${KONTROL_BASE}

USER root
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends git curl jq ca-certificates; \
    rm -rf /var/lib/apt/lists/*

# foundry/kontrol binaries are preinstalled in the base image and on PATH.
# NOTE: kontrol is a pip --user install under /home/user and ONLY works as the
# base image's `user` account (uid 1010); as root the vendored typing.py
# shadows the stdlib and every invocation tracebacks.
ENV HOME=/home/user
USER user
RUN kontrol version || true

WORKDIR /engagement
ENTRYPOINT ["/bin/bash"]
