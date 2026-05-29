#!/usr/bin/env bash
# prompt-submit.sh — Claude Code UserPromptSubmit hook.
# Surfaces the OpenHarness goal-verify status before every turn so
# Claude sees any RED criteria immediately.
set -u

HARNESS="/home/john/repos/OpenHarness/bin/harness"
if [ ! -x "$HARNESS" ]; then
  exit 0
fi

# Light variant: just verify status + count, no full preamble (keeps prompt budget small)
VERIFY=$("$HARNESS" goal verify 2>&1 | tail -1 || echo "")
if [ -z "$VERIFY" ]; then
  exit 0
fi

# Only inject if there's a red — silent when all green
if echo "$VERIFY" | grep -q "/" && ! echo "$VERIFY" | grep -q "^[0-9]\+/[0-9]\+ criteria green$"; then
  # Mixed status — get the reds
  REDS=$("$HARNESS" goal verify 2>&1 | grep '^FAIL' | head -3)
  MSG="[OpenHarness] $VERIFY"
  if [ -n "$REDS" ]; then
    MSG="$MSG"$'\n'"$REDS"
  fi
elif echo "$VERIFY" | grep -qE "^[0-9]+/[0-9]+ criteria green$"; then
  TOTAL=$(echo "$VERIFY" | awk -F'/' '{print $2}' | awk '{print $1}')
  GREEN=$(echo "$VERIFY" | awk -F'/' '{print $1}')
  if [ "$GREEN" = "$TOTAL" ]; then
    exit 0  # all green, silent
  fi
  MSG="[OpenHarness] $VERIFY"
else
  exit 0
fi

MSG_JSON=$(printf '%s' "$MSG" | python3 -c 'import sys,json;print(json.dumps(sys.stdin.read()))')
cat <<EOF
{
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": $MSG_JSON
  }
}
EOF
exit 0
