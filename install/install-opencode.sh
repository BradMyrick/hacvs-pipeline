#!/usr/bin/env bash
# Wire HACVSP skills + commands into the global OpenCode config.
# Idempotent: safe to re-run. Only adds files and a marked router block —
# never deletes or rewrites user content (deletion policy).
set -euo pipefail

HACVSP_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OC="$HOME/.config/opencode"
SKILLS="$OC/skills"
COMMANDS="$OC/command"
ROUTER="$SKILLS/AGENTS.md"

echo "==> installing skills"
mkdir -p "$SKILLS" "$COMMANDS"
for skill in hacvsp kodr-audit; do
  src="$HACVSP_ROOT/skills/$skill"
  dst="$SKILLS/$skill"
  mkdir -p "$dst"
  cp "$src/SKILL.md" "$dst/SKILL.md"
  echo "    $dst/SKILL.md"
done

echo "==> installing commands"
for cmd in audit hacvsp-init hacvsp-stage hacvsp-status hacvsp-signoff; do
  cp "$HACVSP_ROOT/commands/$cmd.md" "$COMMANDS/$cmd.md"
  echo "    $COMMANDS/$cmd.md"
done

echo "==> patching router ($ROUTER)"
if [ -f "$ROUTER" ] && grep -q "BEGIN HACVSP ROUTER BLOCK" "$ROUTER"; then
  echo "    router block already present (idempotent)"
else
  cat >> "$ROUTER" <<'EOF'

<!-- BEGIN HACVSP ROUTER BLOCK -->
### Kodr.pro Audit Pipeline (HACVSP v0.1.0)
- operating any HACVSP stage/gate, engagement mechanics, toolchain pins, contract workstation scaffold → `hacvsp`
- auditing a smart-contract repo end-to-end, engagement intake, expert checkpoints, threat model/sign-off, audit deliverables → `kodr-audit` (load `hacvsp` first; `blockchain-contract-safety` for domain review)
<!-- END HACVSP ROUTER BLOCK -->
EOF
  echo "    router block appended"
fi

echo "==> done. /audit <repo>, /hacvsp-init, /hacvsp-stage N, /hacvsp-status, /hacvsp-signoff are live."
