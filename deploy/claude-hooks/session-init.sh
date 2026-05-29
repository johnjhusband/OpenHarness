#!/usr/bin/env bash
# session-init.sh — Claude Code SessionStart hook.
# Injects OpenHarness state (goal status, inboxes, escalations, due cron)
# as additional context for the first turn of every session.
set -u

HARNESS="/home/john/repos/OpenHarness/bin/harness"
if [ ! -x "$HARNESS" ]; then
  exit 0
fi

PREAMBLE=$("$HARNESS" preamble 2>&1 || echo "[OpenHarness preamble failed]")
# Truncate to keep context budget tight
PREAMBLE=$(printf '%s' "$PREAMBLE" | head -c 4000)

# Escape for JSON
PREAMBLE_JSON=$(printf '%s' "$PREAMBLE" | python3 -c 'import sys,json;print(json.dumps(sys.stdin.read()))')

cat <<EOF
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": $PREAMBLE_JSON
  }
}
EOF
exit 0
