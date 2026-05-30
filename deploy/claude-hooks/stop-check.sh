#!/usr/bin/env bash
# stop-check.sh — Claude Code Stop hook. THE LOOP ENFORCER.
#
# Fires when Claude tries to end a turn. It:
#   1. Always re-injects the operating-loop doctrine (so it never fades).
#   2. Asks the harness for the next concrete action.
#   3. If goal criteria are RED, or there's WORK or RESEARCH to do, it BLOCKS
#      the stop — Claude gets another turn and must keep working. No idle.
#   4. Only allows the stop on HANDOFF (nothing left to do/research/invent)
#      AND all goal criteria green.
#
# John authorized the infinite loop (2026-05-29) and steers by injecting
# prompts mid-work. So this blocks aggressively whenever there's anything to do.
set -u

HARNESS="/home/john/repos/OpenHarness/bin/harness"
if [ ! -x "$HARNESS" ]; then
  exit 0
fi

LOOP_DOCTRINE="OPERATING LOOP (run it now, do not idle):
1. What does John want to accomplish? 2. Next steps? 3. Research them live (never guess). 4. Do what I can NOW. 5. For John-only steps, research to completeness then hand off exact instructions. 6. If nothing left I can do, invent a way to do his steps. 7. Always Working / Researching / Inventing — never idle while intent is unrealized. Take work OFF his plate."

VERDICT_OUT=$("$HARNESS" loop 2>&1)
VERDICT=$(printf '%s' "$VERDICT_OUT" | grep '^VERDICT:' | cut -d' ' -f2-)
ACTION=$(printf '%s' "$VERDICT_OUT" | grep '^ACTION:' | cut -d' ' -f2-)

GOAL_OUT=$("$HARNESS" goal verify 2>&1)
REDS=$(printf '%s' "$GOAL_OUT" | grep -E '^FAIL' | head -10)

# Decide: block or allow
BLOCK=0
REASON=""

if [ -n "$REDS" ]; then
  BLOCK=1
  REASON="Goal criteria are RED — fix these before stopping:
$REDS

$LOOP_DOCTRINE"
elif [ "$VERDICT" = "WORK" ] || [ "$VERDICT" = "RESEARCH" ]; then
  BLOCK=1
  REASON="The loop says you are NOT done. Next action:
$VERDICT: $ACTION

$LOOP_DOCTRINE"
fi

if [ "$BLOCK" = "1" ]; then
  REASON_JSON=$(printf '%s' "$REASON" | python3 -c 'import sys,json;print(json.dumps(sys.stdin.read()))')
  cat <<EOF
{
  "decision": "block",
  "reason": $REASON_JSON
}
EOF
  exit 0
fi

# HANDOFF + all green: allow the stop, but still surface the doctrine for next turn.
exit 0
