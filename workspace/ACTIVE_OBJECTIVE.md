# Active objective

**Bookie operates fully on OpenHarness's latest capabilities, producing clean books for Husband.LLC that John's CPA can use for taxes.**

## What this means concretely

Bookie runs on OpenHarness (not Hermes, not OpenClaw). Whenever I add new OpenHarness capabilities, Bookie uses them. Whenever I change Bookie's requirements, the criteria below reflect that change. The goal is not "Bookie built once" — it's "Bookie current with the latest design, running on the latest OpenHarness, delivering monthly reports to John's CPA."

Traceable to John (2026-05-28): *"I want it to do my bookkeeping so that I can give the reports to the accountant who will prepare my taxes."* Plus: *"Open Harness was supposed to do everything OpenClaw and Hermes can do. The supper set of each."*

## Done state

This objective is met when:
- All criteria in `config/objective-criteria.json` are green.
- Bookie has run for at least 30 days against your real QBO without escalations John couldn't resolve in under 5 minutes.
- John's CPA has accepted at least one monthly report or year-end package from Bookie's output without rejecting the format or substance.

## What "still working on it" looks like

Any time a criterion turns red, the immediate next action is to make it green. No new work, no other tasks, no "let me also build X." Make the red green. Verify. Then continue.

## Update rules

This file changes when John changes the objective. The criteria file changes whenever a capability is added or removed and there's a new automatable check that represents "Bookie uses this capability" or "Bookie does not regress on this."
