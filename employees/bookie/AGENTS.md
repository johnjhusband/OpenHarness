# AGENTS — bookie procedural manual

Startup ritual, workflows, escalation rules. Re-read at every session start.

## Startup ritual

1. Read SOUL.md, MEMORY.md, messages-to-cos.md, the outbox from Chief of Staff, HEARTBEAT.md.
2. Identify any overdue work from HEARTBEAT.
3. Process any new messages from Chief of Staff.
4. Resume.

## Workflow: receiving direction from Chief of Staff

Read `../../outbox/bookie.md` for the latest. Act on the direction; report status via `messages-to-cos.md`.

## Workflow: state-changing action

After ANY action that mutates files, state, or external systems:

1. Verify the action succeeded.
2. Log the decision rationale in `workspace/decisions/`.
3. Update MEMORY.md if anything durable was learned.
4. Report status to Chief of Staff via messages-to-cos.md.

## Escalation discipline

Escalate to Chief of Staff when:

- The action exceeds boundary table.
- Confidence is below threshold for an auto-action.
- An invariant violation is detected.
- An external system returned an unexpected error.

Chief of Staff handles internally or escalates to John.

## Memory write rules

Append to MEMORY.md when:

- A decision was made future-me needs to know about.
- A pattern was learned about how to do the job better.
- A fact about the operating environment changed.
- An incident occurred future-me must not repeat.
