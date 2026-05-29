#!/usr/bin/env bash
# install-laptop-hooks.sh — install OpenHarness Claude Code hooks on the laptop.
#
# Drops the four hook scripts into ~/repos/.claude/hooks/ and writes
# ~/repos/.claude/settings.json. Idempotent.
#
# Run once on a fresh laptop install. The hooks are NOT installed on the VPS
# (the daemon doesn't run Claude Code interactively there).
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
TARGET_DIR="${TARGET_DIR:-$HOME/repos/.claude}"
HOOKS_DIR="$TARGET_DIR/hooks"

mkdir -p "$HOOKS_DIR"
for sh in "$HERE/claude-hooks"/*.sh; do
  base="$(basename "$sh")"
  cp "$sh" "$HOOKS_DIR/$base"
  chmod +x "$HOOKS_DIR/$base"
  echo "installed: $HOOKS_DIR/$base"
done

if [ ! -f "$TARGET_DIR/settings.json" ]; then
  cp "$HERE/claude-hooks/settings.json.template" "$TARGET_DIR/settings.json"
  echo "installed: $TARGET_DIR/settings.json"
else
  echo "skipped (already exists): $TARGET_DIR/settings.json"
  echo "  Compare with $HERE/claude-hooks/settings.json.template if you want updates."
fi

echo
echo "Done. Hooks will fire on the next new Claude Code session."
