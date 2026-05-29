# OpenHarness gap analysis vs Hermes Agent + OpenClaw

**Date:** 2026-05-28
**Purpose:** Honest accounting of what Hermes and OpenClaw have that OpenHarness doesn't, with a decision for each: build it, skip it, or defer it.

I told John earlier that OpenHarness was a superset of Hermes and OpenClaw. That was wrong. This document corrects the record by enumerating every capability gap and committing to a build plan for the ones that matter.

---

## What OpenHarness has today

These are the existing capabilities, so we're clear about the starting point.

The workspace files SOUL.md, USER.md, MEMORY.md, AGENTS.md, HEARTBEAT.md, STYLE.md, TOOLS.md, boundaries.md, and escalations.md are all present and Markdown-based. Each AI employee gets its own copy of these under `employees/<name>/`. An inbox file and an outbox file pair sits in `inbox/` and `outbox/` for each employee.

The state store is a SQLite database at `state/chat.db` with FTS5 full-text indexing. Every state-changing action gets logged there with `kind`, `sender`, `recipient`, `correlation`, `content`.

The agent loop is a single-turn Python function: `agent_loop.invoke(provider, employee, prompt)`. It builds a system prompt from the employee's workspace files and calls the provider once.

The provider abstraction supports one provider today — Claude Code headless via `claude -p`. A circuit breaker wraps the call with throttling, rate gating, and exponential cooldown.

The scheduler is a daemon loop (`harness daemon`) that walks the employee registry every 60 seconds and calls each employee's Python `tick(context)` function.

The policy engine reads `boundaries.md` and gates state-changing actions before they run. Three autonomy modes (manual, tiered, autonomous) tune the gate.

Skills are discoverable: external-sources.json points at directories containing `SKILL.md` files. The discovery works. The dispatch (actually calling a skill) does not — skills are documentation, not executable.

A checkpoint primitive saves named steps for resumable long tasks.

Restart protocol reads SOUL, MEMORY, AGENTS, HEARTBEAT, inbox, escalations, and git status on session start.

That's the substrate. Now the gaps.

---

## The headline gap: OpenHarness does not self-improve

This is the gap John flagged first. Hermes has a feature where the agent, after completing a complex task (5 or more tool calls), automatically writes a reusable skill capturing what worked. There's also a separate Hermes self-evolution repository using genetic prompt evolution on execution traces. OpenClaw doesn't have this in core but has a community skill called `self-improving-agent` that does roughly the same thing — capturing learnings, corrections, and successful patterns into a local `.learnings/` directory.

OpenHarness has neither. Bookie's `decisions/` folder records every categorization with its rationale, but nothing reads those decisions back to learn from them. The chat.db audit log is searchable but no agent searches it. MEMORY.md exists but agents don't write to it autonomously.

**Decision: BUILD.** This is the most important gap to close. John asked for it explicitly.

---

## Significant gaps to build

### Gap 1: Reflection loop

Hermes has a "curator" subsystem that analyzes successful task trajectories and turns them into skills. OpenClaw's community pattern does similar work via the `self-improving-agent` skill.

OpenHarness has nothing equivalent. The piece needed is a function that reads an employee's recent decisions from chat.db, asks the LLM "what patterns should this employee remember going forward," and writes the answer into MEMORY.md. Trigger: weekly cron, or manually via `harness reflect <employee>`.

**Decision: BUILD.**

### Gap 2: Memory tool (programmatic memory writes)

In Hermes the agent has a `memory` tool with `add`, `replace`, and `remove` actions. The agent can write to its own memory mid-task without leaving the agent loop. Capacity gate at 2,200 characters per memory file. OpenClaw has memory tools too: `memory_search`, `memory_get`.

OpenHarness has neither. Agents technically can write to MEMORY.md but there's no Python API exposed and no capacity check. Adding a memory write today requires Bookie's tick function to manually open the file and append.

**Decision: BUILD.** Needed for the reflection loop and for general agent self-management.

### Gap 3: Searchable session history exposed as a tool

Both Hermes and OpenClaw expose past conversations as something the agent can search at runtime. Hermes calls it `session_search`. OpenClaw's `memory_search` covers it. The underlying storage in both is SQLite with FTS5.

OpenHarness has chat.db with FTS5 indexing built in. The data is there. There's no `session_search` tool exposed to agents. Bookie can't ask "have I categorized this vendor before."

**Decision: BUILD.** Minimal — the index already exists.

### Gap 4: Cron jobs as first-class entities

Both Hermes and OpenClaw treat scheduled jobs as first-class objects with their own CLI (`hermes cron`, `openclaw cron`). Jobs are persisted, listable, runnable, removable. They run independently of the main agent loop.

OpenHarness has a daemon loop that fires every 60 seconds and calls `tick()`, but there's no concept of named jobs with their own schedules. If Bookie needs a weekly reflection pass, today the only way is to add it inside `tick()` with manual date math. That's brittle.

**Decision: BUILD.** Needed for the reflection loop to run weekly without modifying employee Python code.

### Gap 5: Hooks (pre/post tool call, pre prompt build)

OpenClaw and Hermes both expose hooks: `before_prompt_build`, `before_tool_call`, `after_tool_call`. These let plugins intercept and modify or reject calls.

OpenHarness has the policy engine (which is a `before_tool_call` hook in everything but name) but no general hook system. Adding a hook today means modifying the daemon or agent_loop code directly.

**Decision: BUILD, minimal.** A small registry + dispatch. Lets us add things like "log the duration of every LLM call" without touching core code.

### Gap 6: Skills as executable, not just documentation

OpenHarness discovers `SKILL.md` files but cannot invoke them. Hermes invokes skills as slash commands. OpenClaw's skills can bypass the model entirely via `command-dispatch: tool` and route directly to a tool. Both interpret SKILL.md as a contract — frontmatter says what the skill does, the agent calls it by name.

OpenHarness today: Bookie has five SKILL.md files (categorize-transaction, etc.) but the daemon imports `bookie.categorizer` directly. The SKILL.md files are documentation for me to read, not executable artifacts.

**Decision: BUILD, basic.** A `harness skill run <name>` command that loads the SKILL.md frontmatter and calls the entry function. Enough to make the abstraction real.

---

## Gaps I'm deferring (real gaps, but not blocking)

### Hub / marketplace for skills

Hermes has nine skill hub sources including ClawHub, skills.sh, and direct GitHub. OpenClaw has ClawHub built in with trust verification.

OpenHarness has `external-sources.json` for discovering skills from local clones. That's lighter. A hub/publish flow could come later if you ever want to share skills publicly.

**Decision: DEFER.** Not blocking. External-sources covers the single-user case.

### Many provider plugins

Hermes supports 18+ providers including Anthropic, OpenAI, OpenRouter, Codex OAuth, Claude Pro, ChatGPT Pro, SuperGrok, Copilot, Gemini, DeepSeek, xAI, Hugging Face, and custom endpoints. OpenClaw has 40+.

OpenHarness has one: Claude Code headless. That's sufficient because you're using your Claude subscription and don't want new API keys. Adding more providers is a half-day each when needed.

**Decision: DEFER until needed.**

### Multiple terminal backends

Hermes supports local, docker, ssh, modal, daytona, and singularity backends. Lets the agent run code in isolated environments.

OpenHarness runs Python locally inside the daemon process. For Bookie's purposes (calling QBO API, driving a browser), this is fine. Docker isolation would help if we ever ran untrusted code.

**Decision: DEFER.**

### Provider proxy (subscription-to-OpenAI-API)

Hermes's `proxy` feature exposes Claude/ChatGPT subscriptions as OpenAI-compatible local endpoints so tools like Aider, Cline, Codex can consume them.

OpenHarness uses Claude Code headless directly. We don't need a proxy because we're not bridging to other tools.

**Decision: DEFER.**

### Per-turn file mutation verifier

Hermes v0.14 added a footer that confirms claimed file writes actually landed. Catches LLM hallucinations about "I wrote the file."

OpenHarness uses deterministic Python for file writes (employees call `Path.write_text()`), not LLM-claimed writes. No mutation verifier needed today.

**Decision: DEFER.** Would matter only when we add a `write_file` tool the LLM calls directly.

### Path-scoped concurrent file ops

Hermes can run parallel `read_file`/`write_file` calls when paths don't overlap. Clever optimization.

OpenHarness ticks are serial. Bookie's workload is low-volume. Not needed.

**Decision: DEFER.**

### Kanban multi-agent coordination

Hermes has a Kanban board where multiple workers pick up tasks, hand off, and close them. Zombie detection and retry budgets.

OpenHarness has one employee (Bookie) today. When you commission a second employee, we'll likely use the inbox/outbox pattern between them via Chief of Staff, not Kanban. The Chief of Staff role is incompatible with peer-to-peer agent handoff.

**Decision: DEFER.** May never be needed given the structural Chief-of-Staff buffer.

---

## Gaps I'm skipping (intentional, not building)

### Channel plugins for messaging (Telegram, WhatsApp, Slack, etc.)

Hermes has 22 messaging platform adapters. OpenClaw has 26+. Both let agents send messages to humans via those platforms.

OpenHarness will never have these. They're banned per `feedback_no_a2a2h_no_pwa` and `feedback_chief_of_staff_role`. Nothing in OpenHarness pushes to John's phone or any external channel. Ever.

**Decision: SKIP, by policy.**

### Control UI web dashboard

OpenClaw serves a PWA dashboard at `http://localhost:18789/` for chat, channels, sessions, cron, skills, nodes, activity, and logs. Hermes has `hermes dashboard`.

OpenHarness has banned PWAs as a UI surface. The closest equivalent would be a read-only file viewer in Phase 3 of the OpenHarness PRD, not a control UI.

**Decision: SKIP, by policy.**

### Browser tools as native runtime feature

Hermes ships `browser_navigate`, `browser_snapshot`, `browser_vision` as built-in tools, with 180× speedup via persistent CDP in v0.14.

OpenHarness has browser automation in Bookie specifically (`bookie.browser` using Stagehand against QBO). It's per-employee, not a core OpenHarness feature. Adding it to core is overkill for our single-employee scope.

**Decision: SKIP.** Bookie owns its own browser code.

### Cross-instance A2A protocol

Both projects have or are experimenting with agent-to-agent protocols across instances.

OpenHarness has the Chief of Staff structural role explicitly to prevent peer agent handoff. All agent communication routes through me. That's a deliberate design decision, not a missing feature.

**Decision: SKIP, by policy.**

---

## Summary of what gets built

Six things, in priority order:

1. Reflection loop (`harness reflect <employee>`) that reads chat.db decisions and writes learnings to MEMORY.md
2. Memory tool API (`memory.add`, `memory.search`, capacity gate)
3. session_search FTS5 helper exposed as a Python API and CLI
4. Cron jobs as first-class entities (`harness cron add/list/run/remove`)
5. Hooks system (before/after tool call, before prompt build)
6. Skills as executable (`harness skill run <name>` dispatches via SKILL.md frontmatter)

Plus: Bookie gets an opinion about what to reflect on (categorization patterns that should become Bank Rules) so the self-improvement is concrete for the one employee we have.

Estimate: roughly a day of focused work for the six pieces plus Bookie's specific reflection logic.

After this build, OpenHarness genuinely is a superset of the core self-improvement and learning capabilities of Hermes and OpenClaw, minus the things we've banned by policy (push channels, web UIs, peer agent handoff).
