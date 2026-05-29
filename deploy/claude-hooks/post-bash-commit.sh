#!/usr/bin/env bash
# post-bash-commit.sh — Claude Code PostToolUse hook for Bash.
# After every successful Bash call, check if the command was a git commit.
# If so, run `harness goal verify` and surface any red criteria as additional
# context for the next turn. Catches "I committed but forgot to update X"
# patterns automatically.
set -u

HARNESS="/home/john/repos/OpenHarness/bin/harness"
if [ ! -x "$HARNESS" ]; then
  exit 0
fi

INPUT=$(cat /dev/stdin)
COMMAND=$(printf '%s' "$INPUT" | python3 -c 'import json,sys;d=json.load(sys.stdin);print(d.get("tool_input",{}).get("command",""))' 2>/dev/null)

# Match git commit (allowing flags, message bodies, etc.)
if ! printf '%s' "$COMMAND" | grep -qE 'git[[:space:]]+commit'; then
  exit 0
fi

VERIFY_OUTPUT=$("$HARNESS" goal verify 2>&1)
REDS=$(printf '%s' "$VERIFY_OUTPUT" | grep -E '^FAIL' | head -10)
SUMMARY=$(printf '%s' "$VERIFY_OUTPUT" | tail -1)

if [ -z "$REDS" ]; then
  # All green — silent acknowledgment
  MSG="[OpenHarness goal verify after commit] all green: $SUMMARY"
else
  MSG="[OpenHarness goal verify after commit] RED criteria detected — fix before declaring done:
$REDS

$SUMMARY"
fi

MSG_JSON=$(printf '%s' "$MSG" | python3 -c 'import sys,json;print(json.dumps(sys.stdin.read()))')
cat <<EOF
{
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "additionalContext": $MSG_JSON
  }
}
EOF
exit 0
