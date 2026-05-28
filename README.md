# OpenHarness

An AI agent harness — the runtime that turns Claude Code into a persistent Chief of Staff and gives that Chief of Staff the substrate to run other AI employees.

**Status:** Pre-build. PRD complete, MVP build in progress, 2026-05-27.

## What's a harness?

In 2026 vocabulary:

- **Harness / runtime** = infrastructure that wraps an LLM with memory, tools, schedulers, channels, identity, and persistence (OpenClaw, Hermes, Claude Code itself).
- **Framework / library** = building blocks you code with (LangChain, LangGraph, CrewAI).

OpenHarness is the harness. Claude Code is the inference loop inside it.

## Architectural bet

**The workspace IS the agent.** Identity, memory, schedule, skills, decisions all live as version-controlled Markdown files. SQLite indexes them for fast recall; Markdown is the truth. Pattern shared by OpenClaw and Hermes; adopted here.

## Reporting structure

```
        John (CEO)
            ↑
   Chief of Staff (Claude Code in OpenHarness)
            ↑     ↑     ↑
         Bookie  ...   (future AI employees)
```

AI employees never contact John directly. They write to Chief of Staff's inbox; Chief of Staff aggregates and surfaces only what truly requires CEO-level input.

## How to read this repo

1. **`prd/OpenHarness-PRD.md`** — full product requirements.
2. **`workspace/SOUL.md`** — Chief of Staff identity (the most load-bearing file).
3. **`workspace/HEARTBEAT.md`** — schedule.
4. **`workspace/boundaries.md`** — auto-approve vs. escalate table.
5. **`bin/harness`** — the Python CLI (Phase 1 build).
6. **`employees/_template/`** — template for new AI employees.

## Sibling projects

- **Bookie** (github.com/johnjhusband/Bookie) — the first AI employee, an autonomous bookkeeper.
- **CTO** (github.com/johnjhusband/CTO) — sunset prior agent project; source of lessons.
- **CTO-artifacts** (private) — captured artifacts from CTO.

## Banned patterns

- No A2A2H protocol.
- No PWA as outbound or notification channel.
- No push notifications to John's phone.
- No unbounded ReAct/Reflexion retry loops.

See `prd/OpenHarness-PRD.md` §14 for the full list.
