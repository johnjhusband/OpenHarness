#!/usr/bin/env bash
# stop-check.sh — Claude Code Stop hook.
# When Claude is about to stop, verify the goal. If anything is red, force
# another turn so Claude has to acknowledge and address the red criterion
# instead of quietly finishing.
set -u

HARNESS="/home/john/repos/OpenHarness/bin/harness"
if [ ! -x "$HARNESS" ]; then
  exit 0
fi

VERIFY_OUTPUT=$("$HARNESS" goal verify 2>&1)
REDS=$(printf '%s' "$VERIFY_OUTPUT" | grep -E '^FAIL' | head -10)

if [ -z "$REDS" ]; then
  # all green — let stop proceed
  exit 0
fi

REASON="OpenHarness goal verify is RED. The following criteria failed:

$REDS

Per the iterative-goal-verification rule: the immediate next action is to make the reddest criterion green. Do not stop until all green."

REASON_JSON=$(printf '%s' "$REASON" | python3 -c 'import sys,json;print(json.dumps(sys.stdin.read()))')
cat <<EOF
{
  "decision": "block",
  "reason": $REASON_JSON
}
EOF
exit 0
