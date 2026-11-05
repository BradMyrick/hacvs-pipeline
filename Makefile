# HACVSP — Kodr.pro High-Assurance Contract Verification & Security Pipeline
# Docker digest-pinned hermetic toolchain. Fail-closed.

SHELL := /bin/bash
HACVSP := ./bin/hacvsp

.PHONY: help build pin doctor verify gates test install-opencode

help:
	@echo "HACVSP targets:"
	@echo "  build            Build the pinned toolchain images (tools + kontrol)"
	@echo "  pin              Freeze base-image digests and tool artifact sha256s into docker/pins.env"
	@echo "  doctor           Fail-closed verification that every pin is present and every image matches"
	@echo "  verify           Cross-check pipeline implementation against SPEC.json (the spec audits the pipeline)"
	@echo "  gates            Regenerate gates.json (derived, machine-checkable gate matrix)"
	@echo "  test             Run custom-tool unit tests + hacvsp verify"
	@echo "  install-opencode Wire skills/commands into ~/.config/opencode (idempotent)"

build:
	$(HACVSP) doctor --allow-missing-images || true
	@echo "==> building tools image (versions pinned via docker/pins.env)"
	docker compose --project-directory . --env-file docker/pins.env -f docker/compose.yaml build tools
	@echo "==> building kontrol image"
	docker compose --project-directory . --env-file docker/pins.env -f docker/compose.yaml build kontrol || \
		echo "!! kontrol image build failed — stage 12 will fail closed until pinned (see docker/pins.env KONTROL_IMAGE)"

pin:
	./docker/pin.sh

doctor:
	$(HACVSP) doctor

verify:
	$(HACVSP) verify

gates:
	$(HACVSP) gates > gates.json && echo "gates.json regenerated"

test:
	@for d in tools/*/; do \
	  if ls "$$d"test_*.py >/dev/null 2>&1; then \
	    echo "==> unittest $${d}"; \
	    (cd "$$d" && python3 -m unittest discover -p 'test_*.py') || exit 1; \
	  fi; \
	done
	$(HACVSP) verify

install-opencode:
	./install/install-opencode.sh
