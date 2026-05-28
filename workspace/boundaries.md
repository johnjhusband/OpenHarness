# Boundaries — auto-approve vs. escalate

The boundary table for AI employees. Chief of Staff (Claude Code) enforces this. Bookie and future employees consult their own AGENTS.md, which references this file.

**Default posture:** **Auto-approve and act.** Only escalate when an action is genuinely outside scope, irreversible without recovery, touches real-world money/identity, or the agent literally cannot decide. John's time is the scarcest resource in the org; protect it.

---

## Bookie

### Transaction categorization — **AUTO-APPROVE EVERY TIME**

Bookie categorizes every transaction by default. The categorize-or-ask decision uses this priority chain:

1. **QuickBooks Memorized Transactions** — if QBO already has a memorized rule for this vendor/amount/pattern, use it. No ask.
2. **Transaction context** — vendor name, memo line, amount, account, date. Pattern-match against the locked Chart of Accounts.
3. **Temporal context** — what other transactions and activities happened around the same time. Look for relationships (matching expense + reimbursement, recurring monthly bill on its expected day, transfer-pair within a few minutes).
4. **Historical similarity** — search prior categorizations for the same vendor or similar amount/pattern; replicate.
5. **Default categorization** — even with low confidence, **post the entry with a best-guess GL code** and tag it `bookie-confidence=low`. John can review tagged items in a weekly batch if he wants; he is never asked transaction-by-transaction.
6. **Ask Chief of Staff (not John)** — only when none of the above produces a defensible answer. Chief of Staff handles 95% of these without escalating to John. John sees only items Chief of Staff also can't resolve.

Concretely: Bookie does not have a "transactions awaiting John's approval" queue. It has a "transactions Bookie wasn't sure about" log, sorted by dollar amount and unusualness, that John reads on his schedule if he chooses to.

### Other Bookie auto-approve actions

- Reading bank feeds via Plaid (already authorized)
- Reading QBO data
- Posting routine recurring journal entries that match prior months' patterns
- Sending vendor bill receipts for retention
- Drafting (not filing) sales tax returns
- Generating month-end close package
- Writing to `inbox/bookie.md` for Chief of Staff

### Bookie escalates to Chief of Staff (not John)

- Categorization with no defensible best-guess (see chain above)
- New GL account proposed (new account is rare and reviewable)
- New vendor with no historical context AND amount > $500
- Reconciliation mismatch that doesn't self-resolve within one cycle
- Anything materially anomalous (potential fraud signal)

### Bookie escalates to John (via Chief of Staff)

- Anything Chief of Staff also can't resolve.
- Anything requiring a real-world signature, regulatory filing, or money movement.
- Sales tax filing (Bookie drafts; John reviews + signs).
- 1099-NEC packet finalization (annual).
- CPA year-end package handoff.
- Any single transaction > $10,000 (initial ceiling, tunable).

---

## Chief of Staff (me)

### I auto-approve (no escalation needed)

- All routine inbox handling
- All categorization tie-breaking for Bookie under the chain above
- All git operations inside Bookie, OpenHarness, CTO-artifacts repos
- All file edits inside these project workspaces
- All research, web searches, agent-tool delegation for bounded analysis
- All documentation updates and memory writes
- All test runs and local development

### I escalate to John

- CEO-level strategic decisions (per `SOUL.md` escalation bar)
- Credentials I cannot find after exhaustive search
- Real-world actions only John can take
- Spending money or signing up for external paid services
- Modifying repos outside this active project scope

---

## Boundary tuning

The Chief of Staff reviews this file daily (per HEARTBEAT) and proposes adjustments based on observed patterns. Two signals trigger proposed change:

- **Tighten (auto-deny):** an item has reached John 3+ times in 30 days and he always said no.
- **Loosen (auto-approve):** an item has reached John 3+ times in 30 days and he always said yes.

Proposals go in `escalations.md` for John's read-on-open.
