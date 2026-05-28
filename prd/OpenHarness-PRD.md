# OpenHarness — Product Requirements Document

**Version:** 0.1 (pre-build)
**Author:** Claude Code (Chief of Staff), 2026-05-27
**Status:** Draft, ready for build

---

## 1. What OpenHarness is

OpenHarness is an **AI agent harness** — the runtime infrastructure that turns Claude Code into a persistent Chief of Staff and gives that Chief of Staff the substrate to run other AI employees (Bookie, future agents).

In 2026 industry vocabulary: a **harness is what you configure and run**, distinct from a **framework you code with** (LangChain/LangGraph/CrewAI). OpenHarness is the harness; Claude Code is the inference loop inside it.

The architectural bet, taken from both OpenClaw and Hermes Agent: **the workspace IS the agent.** Identity, memory, schedule, skills, decisions all live as version-controlled Markdown files. There is no database of record; SQLite indexes the Markdown for fast recall, but the Markdown is the truth.

## 2. Problem statement

CTO (the prior agent project) failed at three architectural layers:

1. **The outbound channel never worked.** Foreground-only PWA on iOS Safari + A2A2H approval packets that nobody saw = AI agents constantly needed John but had no way to reach him.
2. **No durable identity.** Each session re-derived who the agent was from CLAUDE.md, recent commits, and chat history. Drift was constant.
3. **Routine-tick treadmill.** The work-pump ran the same safe-gate check 22 times in 2 hours because no rule said "a tick that ships nothing is a failed tick."

OpenHarness exists to solve these by giving Claude Code (and every AI employee it runs):

- A persistent, file-based identity (`SOUL.md`) loaded at every session start.
- A boring, durable inbox model (`inbox/<name>.md`) — no PWA, no push, no A2A2H.
- A natural-language schedule (`HEARTBEAT.md`) the LLM reasons about.
- A boundary table (`boundaries.md`) the agent enforces without asking.
- A restart protocol that recovers full operational continuity from files alone.

## 3. Goals

- **G1.** Make Claude Code restartable. After any context reset, reading the workspace fully recovers operational state.
- **G2.** Make AI employees fully buffered from John. No employee ever contacts John directly. Chief of Staff is the only channel.
- **G3.** Encode identity, memory, and boundaries as files John can read, edit, version, and copy.
- **G4.** Make adding a new AI employee a workspace clone, not a code change.
- **G5.** Keep the runtime small, debuggable, and operable from a single Python entry point.

## 4. Non-goals

- **NG1.** Not a framework to "write agents in code." This is a harness, not LangChain. Employees are folders + Markdown, not Python subclasses.
- **NG2.** Not a multi-LLM-vendor abstraction in v1. Claude is the model. Provider swapping is a v2 concern.
- **NG3.** Not a multi-user system. John is the only CEO. Multi-tenant is out of scope.
- **NG4.** Not a hosted SaaS. OpenHarness runs on the laptop (v1) and optionally a Hetzner VPS (v2). Other deployment targets are not in scope.
- **NG5.** Not a notification system. Nothing in OpenHarness pushes to John's phone, email, or any external channel. Ever.

## 5. Reporting structure

```
        John (CEO)
            ↑
   Chief of Staff (Claude Code in OpenHarness)
            ↑     ↑     ↑
         Bookie  ...   (future AI employees)
```

- John gives strategic direction to Chief of Staff only.
- AI employees report to Chief of Staff via their inbox file. They never contact John.
- Chief of Staff aggregates and surfaces only what truly requires CEO-level input.

## 6. Workspace layout

The OpenHarness workspace is a directory (default `~/.openharness/`, configurable). The layout:

```
workspace/
  SOUL.md              # Chief of Staff identity (slot #1 of system prompt at session start)
  USER.md              # About John (CEO context)
  MEMORY.md            # Chief of Staff's durable knowledge (agent-written, append-only)
  AGENTS.md            # Chief of Staff's procedural manual
  HEARTBEAT.md         # Natural-language schedule, polled every 30 min
  STYLE.md             # Voice / tone reference
  TOOLS.md             # Tool registry
  boundaries.md        # Auto-approve vs. escalate table
  escalations.md       # Items queued for John's read-on-open
inbox/
  bookie.md            # Bookie → Chief of Staff
  <employee>.md
outbox/
  bookie.md            # Chief of Staff → Bookie
  <employee>.md
employees/
  bookie/
    SOUL.md            # Bookie's identity
    USER.md            # About the user Bookie serves (John, via CoS)
    MEMORY.md          # Bookie's accumulated knowledge
    AGENTS.md          # Bookie's procedural manual
    HEARTBEAT.md       # Bookie's schedule
    STYLE.md
    TOOLS.md
    messages-to-cos.md # symlink/alias to ../../inbox/bookie.md
    workspace/         # Bookie's working state (drafts, in-progress reports)
state/
  chat.db              # SQLite + FTS5 message bus (every inbox/outbox write logged)
  sessions/            # bounded session IDs, rotated daily
config/
  openharness.json     # runtime config (workspace path, cadence, log level)
  auth-profiles.json   # secrets, separate from config (OpenClaw pattern)
  employees.json       # registry of installed AI employees
```

## 7. The seven file types

Each file has a single owner-writer and clear semantics:

| File | Owner | Read when | Purpose |
|------|-------|-----------|---------|
| `SOUL.md` | Human | Every session start (slot #1 of system prompt) | Identity, mission, tone, hard rules |
| `USER.md` | Human (+ agent appends) | Session start | Stable context about the user |
| `MEMORY.md` | **Agent writes** | Session start | Append-only durable knowledge; daily rollover to `memory/YYYY-MM-DD.md` |
| `AGENTS.md` | Human | Session start | Procedural manual — startup ritual, workflows |
| `HEARTBEAT.md` | Human | Polled every 30 min | Natural-language cron |
| `STYLE.md` | Human | Session start | Voice/tone patterns |
| `TOOLS.md` | Human + agent | On-demand | Tool registry |
| `boundaries.md` | Human | Session start + before any action | Auto-approve vs. escalate |
| `escalations.md` | Agent writes | John reads when he opens Claude Code | Queued items for CEO attention |

Markdown is the universal format. No YAML except in skill frontmatter (Phase 2).

## 8. CLI surface (Phase 1)

OpenHarness ships a single Python CLI: `harness`.

```
harness restart           # Run the restart protocol; print Chief of Staff briefing
harness tick              # Run one heartbeat tick (check inboxes, handle, write outbox/escalations)
harness inbox             # List all inboxes with unread counts
harness inbox <employee>  # Show one employee's inbox
harness send <employee>   # Send a message to an employee (writes to outbox/<employee>.md)
harness employee list     # Show installed employees
harness employee install <name>   # Scaffold a new employee from template
harness memory append "fact"      # Append to Chief of Staff MEMORY.md (also callable from inside Claude Code)
harness state               # Show recent chat.db rows (last 50)
harness state search "query"  # FTS5 search across chat.db
harness verify              # Workspace integrity check (every file expected, no orphan inboxes, etc.)
```

In Phase 1 the CLI is invoked manually by Claude Code at session start. Phase 2 adds a `harness daemon` mode that runs the tick on a 30-min schedule.

## 9. Restart protocol

`harness restart` does:

1. Read `SOUL.md` and load it as the Chief of Staff identity preamble.
2. Read `MEMORY.md` and the most recent rollover under `memory/`.
3. Read every file under `inbox/` and report unread counts.
4. Read `HEARTBEAT.md` and identify overdue/due items.
5. Read `AGENTS.md` for the procedural manual.
6. Read `boundaries.md` for current auto-approve / escalate table.
7. Read `escalations.md` to see what's pending for John.
8. Run `git status` and `git log --oneline -10` for active repos.
9. Read `TaskList` from the harness's own task store.
10. Print a single briefing summary: "Here's where we are. Here's what's overdue. Here's what's blocked."

The output is what Chief of Staff reads first thing on every new session.

## 10. Heartbeat tick

`harness tick` does:

1. Scan every inbox file for new content since last tick (`state/last-tick-cursor.json`).
2. For each new message, classify: routine vs. asks-for-decision.
3. Handle routine items (acknowledge in outbox, write any state changes).
4. For asks-for-decision: consult `boundaries.md`. If auto-approvable → handle. If escalate → write to `escalations.md`.
5. Update `MEMORY.md` if anything durable was learned.
6. Log every action to `state/chat.db`.
7. Advance cursor.

Tick is idempotent — re-running it should be a no-op if no new content arrived.

## 11. State model

`state/chat.db` is a SQLite database (Hermes pattern, with the `tail()` bug we fixed in CTO). Schema:

```sql
CREATE TABLE messages (
  id          INTEGER PRIMARY KEY,
  ts          REAL NOT NULL,
  sender      TEXT NOT NULL,   -- 'john' | 'cos' | 'bookie' | 'system'
  recipient   TEXT,
  kind        TEXT NOT NULL,   -- 'chat' | 'inbox' | 'outbox' | 'escalation' | 'tick' | 'event'
  correlation TEXT,
  content     TEXT NOT NULL
);
CREATE VIRTUAL TABLE messages_fts USING fts5(content, content=messages, content_rowid=id);
```

Every inbox write, outbox write, escalation, and tick result is logged here. Markdown files remain the source of truth; chat.db is the indexed view for fast recall and audit.

## 12. Employee model

An AI employee is a folder under `employees/<name>/` containing the same seven file types as the workspace (SOUL, USER, MEMORY, AGENTS, HEARTBEAT, STYLE, TOOLS). Plus:

- `messages-to-cos.md` — the employee's outbound channel to Chief of Staff. Alias of `../../inbox/<name>.md`.
- `workspace/` — the employee's working state.

Installing an employee is `harness employee install <name>` which scaffolds the folder from a template and registers it in `config/employees.json`.

Employees in v1 are not separate processes. They are folders Chief of Staff acts as. When Chief of Staff is "running Bookie," it loads Bookie's SOUL/AGENTS/MEMORY and acts within that identity. This is the simplest possible multi-agent model and is sufficient for v1.

V2 may run employees as separate processes with their own LLM calls; that's deferred.

## 13. Boundaries enforcement

`boundaries.md` is read by Chief of Staff before any agent action. Auto-approvable actions execute without further question. Escalating actions go to John via `escalations.md`. Boundaries are tuned daily per `HEARTBEAT.md`.

The default posture is **auto-approve and act**. John's time is the scarcest resource; the boundary table protects it.

## 14. Banned patterns (binding)

OpenHarness must not implement:

- **A2A2H** (Agent-to-Agent-to-Human) protocol. Failed in CTO.
- **PWA** as outbound/notification channel. Failed in CTO.
- **Push notifications to John's phone.** Hard ban from the chief-of-staff role.
- **Foreground-only delivery** of escalations. Escalations queue to a file John reads when he chooses.
- **ReAct/Reflexion** unbounded retry loops. Use bounded plan→tool→verify per the Bookie research.

## 15. Provider model

V1: Claude Code is the model. The harness does not abstract the provider.

V2 (deferred): `config/auth-profiles.json` follows the OpenClaw pattern — profiles like `anthropic:default` and `openrouter:default`, with rotation and failover. Circuit breaker pattern (throttle ≥2s + rate ≥5/60s) from Hermes.

## 16. Run-as-service model (deferred)

V1: OpenHarness runs as a Python CLI on the laptop. Chief of Staff is alive only when Claude Code is open.

V2: `harness daemon` runs on a Hetzner VPS, polls the tick every 30 min, keeps Chief of Staff "alive" between Claude Code sessions. AI employees can post to the inbox at any time; Chief of Staff handles when the daemon ticks; truly urgent items still wait until John opens Claude Code (no push, ever).

V3 (further deferred): Web UI for John to browse workspace state read-only. **NOT** a PWA, **NOT** a notification surface — purely a read-only file browser with FTS search. If this can be served by `gh` / `git` / a static HTML viewer, we use that instead of building anything.

## 17. Phasing

**Phase 1 (this build):**
- Workspace scaffold for Chief of Staff (SOUL, MEMORY, HEARTBEAT, AGENTS, boundaries — done)
- Employee template (under `employees/_template/`)
- Python CLI: `harness restart`, `harness tick`, `harness inbox`, `harness employee install`, `harness verify`
- SQLite state store with FTS5 indexing
- Bookie scaffolded as the first employee (in the Bookie repo, registered here)

**Phase 2:**
- Daemon mode for the tick (laptop or VPS)
- Provider abstraction
- Skill discovery (`skills/` folders) — only if needed
- Auth profile rotation

**Phase 3:**
- Read-only viewer (not a PWA)
- Multi-employee process isolation if any employee genuinely needs it

## 18. Success criteria

- **S1.** Chief of Staff can restart from a fresh Claude Code session, run `harness restart`, and resume operational continuity. Verified by: a session-A interaction is followed by a session-B `harness restart` that picks up correctly.
- **S2.** Bookie is installed as an employee and Chief of Staff can route messages to/from it.
- **S3.** Workspace integrity check passes (`harness verify` returns clean).
- **S4.** Every inbox/outbox/escalation/tick is logged to `state/chat.db` and searchable via FTS5.
- **S5.** No push notification is ever sent. No A2A2H or PWA code exists. Verified by grep.

## 19. Open questions

- **Workspace path.** `~/.openharness/` (per-user) vs. `~/repos/OpenHarness/workspace/` (in the repo). V1 is in-repo for visibility; if it gets noisy, move it out.
- **Memory rollover.** Daily? Weekly? Triggered by size? Start with daily; revisit.
- **Employee process model.** Whether v2 spawns separate processes per employee or stays in-process. Defer.
- **Skill system.** Whether to bring over OpenClaw's `skills/` + YAML frontmatter. Defer to Phase 2; v1 doesn't need it.

## 20. References

- CTO postmortem: `/home/john/repos/CTO-artifacts/lessons/CTO-postmortem-for-Bookie.md`
- Hermes Agent: `github.com/NousResearch/hermes-agent`
- OpenClaw: `github.com/openclaw/openclaw`
- SOUL.md spec (community): `github.com/aaronjmars/soul.md`
- AI harness term-of-art: HuggingFace agent glossary, MongoDB May 2026 post.
