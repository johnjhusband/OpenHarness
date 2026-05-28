# OpenHarness — Product Requirements Document

**Version:** 0.2 (post-Chimera gap-fill)
**Author:** Claude Code (Chief of Staff), 2026-05-27
**Status:** Draft, ready for build

---

## 1. What OpenHarness is

OpenHarness is an **AI agent harness** — the runtime infrastructure that turns Claude Code into a persistent Chief of Staff and gives that Chief of Staff the substrate to run other AI employees (Bookie, future agents).

In 2026 industry vocabulary: a **harness is what you configure and run**, distinct from a **framework you code with** (LangChain/LangGraph/CrewAI). OpenHarness is the harness; Claude Code is the inference loop inside it.

The architectural bet, taken from both OpenClaw and Hermes Agent: **the workspace IS the agent.** Identity, memory, schedule, skills, decisions all live as version-controlled Markdown files. There is no database of record; SQLite indexes the Markdown for fast recall, but the Markdown is the truth.

## 2. Strategic positioning

OpenHarness positions itself narrowly in a crowded 2026 agent-platform field.

| Project | Category | What it is | Why we're not it |
|---------|----------|------------|------------------|
| **LangChain / LlamaIndex** | Framework (library) | Building blocks for coding agents | We are a harness, not a library. Employees are folders + Markdown, not Python subclasses. |
| **LangGraph** | Framework | Typed-state graph orchestration library | Useful inside an employee's logic; not our harness layer. |
| **CrewAI / AutoGen** | Framework | Multi-agent coordination library | We are hub-and-spoke through Chief of Staff, not generic crews. |
| **Hermes Agent** | Harness | Self-improving agent runtime, Markdown-files-as-primitives | Closest sibling. We borrow files-as-primitives and the circuit-breaker pattern. We differ in scope (single CEO, fewer surfaces) and the explicit Chief-of-Staff structural role. |
| **OpenClaw** | Harness | Resilient execution harness, SOUL.md + skills + channel plugins | The other closest sibling. We borrow SOUL.md, workspace-is-the-agent, and the loopback-or-die hardening. We differ in scope (no marketplace, no channel plugins targeting humans). |
| **OpenDevin** | Specialized agent | Software-engineering agent | Different problem (code-writing, not org orchestration). |
| **Chimera** | Aspirational platform | OS for persistent autonomous agents, multi-tenant, marketplace, SDKs | We are a narrower personal harness; Chimera is enterprise scope. We selectively borrow subsystem ideas (risk register, autonomy modes, checkpointing). |

**One-line positioning:** OpenHarness is the personal agent harness for John Husband's AI org. One CEO, one Chief of Staff, named employees, file-based identity and memory, no push, no PWA. Borrows from Hermes + OpenClaw; rejects the marketplace / SDK / PWA layers; adds the Chief-of-Staff structural role and the banned-patterns enforcement.

## 3. Problem statement

CTO (the prior agent project) failed at three architectural layers:

1. **The outbound channel never worked.** Foreground-only PWA on iOS Safari + A2A2H approval packets that nobody saw = AI agents constantly needed John but had no way to reach him.
2. **No durable identity.** Each session re-derived who the agent was from CLAUDE.md, recent commits, and chat history. Drift was constant.
3. **Routine-tick treadmill.** The work-pump ran the same safe-gate check 22 times in 2 hours because no rule said "a tick that ships nothing is a failed tick."

OpenHarness exists to solve these by giving Claude Code (and every AI employee it runs):

- A persistent, file-based identity (`SOUL.md`) loaded at every session start.
- A boring, durable inbox model (`inbox/<name>.md`) — no PWA, no push, no A2A2H.
- A natural-language schedule (`HEARTBEAT.md`) the LLM reasons about.
- A boundary table (`boundaries.md`) enforced by a runtime policy engine.
- A restart protocol that recovers full operational continuity from files alone.

## 4. Goals

- **G1.** Make Claude Code restartable. After any context reset, reading the workspace fully recovers operational state.
- **G2.** Make AI employees fully buffered from John. No employee ever contacts John directly. Chief of Staff is the only channel.
- **G3.** Encode identity, memory, and boundaries as files John can read, edit, version, and copy.
- **G4.** Make adding a new AI employee a workspace clone, not a code change.
- **G5.** Keep the runtime small, debuggable, and operable from a single Python entry point.

## 5. Non-goals

- **NG1.** Not a framework to "write agents in code." This is a harness, not LangChain. Employees are folders + Markdown, not Python subclasses.
- **NG2.** Not a multi-LLM-vendor abstraction in v1. Claude is the model. Provider swapping is a v2 concern.
- **NG3.** Not a multi-user system. John is the only CEO. Multi-tenant is out of scope.
- **NG4.** Not a hosted SaaS. OpenHarness runs on the laptop (v1) and optionally a Hetzner VPS (v2). Other deployment targets are not in scope.
- **NG5.** Not a notification system. Nothing in OpenHarness pushes to John's phone, email, or any external channel. Ever.
- **NG6.** Not a multi-agent swarm. AI employees do not coordinate peer-to-peer or via consensus. All coordination flows through Chief of Staff. Hub-and-spoke is intentional.
- **NG7.** Not a developer SDK in v1. Employees are folders + Markdown, not Python/TypeScript subclasses. Adding a new employee is `harness employee install <name>`, not `npm install`.
- **NG8.** Not a plugin marketplace with signed plugins. External capability discovery uses `config/external-sources.json` (PRD §14) pointing at local clones of upstream repos. Lighter, no marketplace infrastructure.
- **NG9.** Not a web dashboard. May add a read-only file viewer in Phase 3; it must not be a PWA and must not deliver notifications.

## 6. Reporting structure

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

## 7. Workspace layout

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
  boundaries.md        # Auto-approve vs. escalate table (read by policy engine)
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
  chat.db              # SQLite + FTS5 message bus (every inbox/outbox/escalation/tick logged)
  checkpoints/         # task-resumption state (Phase 1.5)
  sessions/            # bounded session IDs, rotated daily
config/
  openharness.json     # runtime config (workspace path, cadence, log level)
  auth-profiles.json   # secrets, separate from config (OpenClaw pattern)
  employees.json       # registry of installed AI employees, with autonomy_mode per employee
  external-sources.json # external skill / template / MCP discovery
```

## 8. The seven file types

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
| `boundaries.md` | Human | Session start + before every action (policy engine) | Auto-approve vs. escalate |
| `escalations.md` | Agent writes | John reads when he opens Claude Code | Queued items for CEO attention |

Markdown is the universal format. No YAML except in skill frontmatter (Phase 2).

### Memory typology inside `MEMORY.md`

Following the 2026 consensus on AI agent memory, the single `MEMORY.md` per agent holds four conceptual layers. v1 does not split them into separate files; v2 may.

- **Episodic** — what happened. "On 2026-05-15 the May Notion charge was categorized as Software-SaaS."
- **Semantic** — accumulated facts. "Notion bills monthly on the 15th around $79."
- **Procedural** — reusable workflows. "Subscription pattern → check vendor against memorized transactions, then categorize as Software-SaaS."
- **Working** — active task state. Lives in `workspace/` subdirectories rather than MEMORY.md; cleared per task.

Agents are expected to annotate MEMORY entries with `[episodic]` / `[semantic]` / `[procedural]` markers so future automated reflection (Phase 2) can index them.

## 9. CLI surface (Phase 1)

OpenHarness ships a single Python CLI: `harness`.

```
harness restart                        # Run the restart protocol; print Chief of Staff briefing
harness tick                           # Run one heartbeat tick (check inboxes, handle, write outbox/escalations)
harness inbox                          # List all inboxes with unread counts
harness inbox <employee>               # Show one employee's inbox
harness send <employee>                # Send a message to an employee (writes to outbox/<employee>.md)
harness employee list                  # Show installed employees with their autonomy modes
harness employee install <name>        # Scaffold a new employee from template
harness employee set-mode <name> <m>   # Set autonomy mode: manual | tiered | autonomous
harness memory append "fact"           # Append to Chief of Staff MEMORY.md
harness state                          # Show recent chat.db rows (last 50)
harness state search "query"           # FTS5 search across chat.db
harness state metrics                  # Show quantitative metrics (Phase 1.5)
harness verify                         # Workspace integrity check
harness extensions list                # Discovered skills/templates/MCPs from external sources
harness extensions verify              # Check external-sources paths exist
harness policy check <action>          # Dry-run the policy engine against an action description
harness audit verify                   # Phase 1.5 — verify chat.db row chain integrity
harness audit export --since DATE      # Phase 1.5 — export audit log JSONL
harness checkpoint resume <task_id>    # Phase 1.5 — resume an in-flight task
harness reflect <task_id>              # Phase 2 — run self-eval on a completed task
```

In Phase 1 the CLI is invoked manually by Claude Code at session start. Phase 2 adds a `harness daemon` mode that runs the tick on a 30-min schedule.

## 10. Restart protocol

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
10. Identify any task in `state/checkpoints/` with a checkpoint < 24h old; offer resume.
11. Print a single briefing summary: "Here's where we are. Here's what's overdue. Here's what's blocked."

The output is what Chief of Staff reads first thing on every new session.

## 11. Heartbeat tick

`harness tick` does:

1. Scan every inbox file for new content since last tick (`state/last-tick-cursor.json`).
2. For each new message, classify: routine vs. asks-for-decision.
3. Handle routine items (acknowledge in outbox, write any state changes).
4. For asks-for-decision: invoke the policy engine. If auto-approvable → handle. If escalate → write to `escalations.md`.
5. Update `MEMORY.md` if anything durable was learned.
6. Log every action to `state/chat.db`.
7. Advance cursor.

Tick is idempotent — re-running it should be a no-op if no new content arrived.

## 12. State model & audit log

`state/chat.db` is a SQLite database (Hermes pattern, with the `tail()` bug we fixed in CTO). Schema:

```sql
CREATE TABLE messages (
  id          INTEGER PRIMARY KEY,
  ts          REAL NOT NULL,
  sender      TEXT NOT NULL,   -- 'john' | 'cos' | 'bookie' | 'system'
  recipient   TEXT,
  kind        TEXT NOT NULL,   -- 'chat' | 'inbox' | 'outbox' | 'escalation' | 'tick' | 'event' | 'audit'
  correlation TEXT,
  content     TEXT NOT NULL
);
CREATE VIRTUAL TABLE messages_fts USING fts5(content, content=messages, content_rowid=id);
```

Every inbox write, outbox write, escalation, tick result, and state-changing action is logged here. Markdown files remain the source of truth; chat.db is the indexed view for fast recall and audit.

### Audit log discipline

chat.db is the canonical audit log. Rules:

- **Append-only at the application level.** No `UPDATE` or `DELETE` in normal operation. `harness audit verify` (Phase 1.5) checks the row chain for tampering.
- **Retention:** 7 years. Matches the longest applicable regulatory retention for any current or future employee.
- **Every state-changing action writes a row** with sender, action description, target system, idempotency key, and rationale.
- **Export:** `harness audit export --since YYYY-MM-DD > audit.jsonl` produces a portable record for external review.
- **Sealed snapshots:** monthly `state/audit-seal-YYYY-MM.json` captures a hash of all chat.db rows for that month. Tampering with prior months breaks the hash.

## 13. Employee model

An AI employee is a folder under `employees/<name>/` containing the same seven file types as the workspace (SOUL, USER, MEMORY, AGENTS, HEARTBEAT, STYLE, TOOLS). Plus:

- `messages-to-cos.md` — the employee's outbound channel to Chief of Staff. Alias of `../../inbox/<name>.md`.
- `workspace/` — the employee's working state.

Installing an employee is `harness employee install <name>` which scaffolds the folder from a template and registers it in `config/employees.json` with default autonomy mode = **manual** (first week).

Employees in v1 are not separate processes. They are folders Chief of Staff acts as. When Chief of Staff is "running Bookie," it loads Bookie's SOUL/AGENTS/MEMORY and acts within that identity. This is the simplest possible multi-agent model and is sufficient for v1.

V2 may run employees as separate processes with their own LLM calls; that's deferred.

## 14. Extension mechanism (v1)

OpenHarness can include skills, MCP definitions, and SOUL templates from external repos without copying, vendoring, or git-submoduling.

`config/external-sources.json` declares paths the runtime globs at load time:

```jsonc
{
  "skills": [],                // dirs containing SKILL.md folders
  "mcp_definitions": [],       // dirs containing MCP server definitions / configs
  "soul_templates": [],        // dirs containing SOUL.md template libraries
  "vendored_code": []          // pinned snippets — {upstream, path, commit, purpose}
}
```

Discovery rules:

- **Skills:** each entry is a directory; OpenHarness globs `*/SKILL.md` two levels deep, parses YAML frontmatter, registers the skill name → folder path. Precedence: workspace skills (Phase 2) → external sources in array order.
- **MCP definitions:** each entry is a directory; OpenHarness reads any `*.mcp.json` and `mcp-servers/*.json` files. These describe MCP servers John could install in his Claude Code config — OpenHarness *documents* them; it does not run them.
- **SOUL templates:** each entry is a directory of `<name>/SOUL.md` files. Used by `harness employee install <name> --from-template <slug>`.
- **Vendored code:** declarative manifest only. Each entry records upstream repo, file path, commit hash, and purpose. The actual file copy lives under `OpenHarness/vendor/` with a sibling `MANIFEST.md`.

Why this design:

- **No git submodules.** UX is painful; sparse-checkout adds another layer.
- **No fork-and-track.** External code stays in its canonical repo on disk; we glob.
- **Updates are explicit.** `cd /home/john/repos/references/openclaw && git pull` is the update path. OpenHarness picks up changes on next load.
- **Caveat documented:** skills assume their host runtime. OpenHarness can read OpenClaw/Hermes skill definitions, but executing them requires implementing matching dispatch (deferred to Phase 2). v1 discovery is "I can show you the template"; execution is later.

V1 ships with `external-sources.json` containing empty arrays. Populating happens when John says go; the runtime supports it from day one so we don't lock ourselves out.

## 15. Boundaries enforcement & policy engine

`boundaries.md` is the source of truth for what every employee can auto-approve vs. escalate. The default posture is **auto-approve and act**; John's time is the scarcest resource, and the boundary table protects it.

In v1, boundaries are not advisory — they are **enforced at runtime** by a small policy engine.

### Policy engine v1

OpenHarness ships a `policy.check(action, context) -> Decision` Python function. Every employee call site that mutates state must route through it before execution. The engine:

1. Loads `boundaries.md` and parses its tables.
2. Loads the calling employee's autonomy mode from `config/employees.json`.
3. Evaluates the action against the boundary table.
4. Returns one of: `Allow`, `Escalate` (writes to `escalations.md`), `Deny` (hard block, logs the attempt).

Decisions and rationales are logged to chat.db with `kind='audit'`.

### Enforcement seam

Every employee's tool layer wraps state-changing actions in `with policy.guard(action):`. The guard calls `policy.check`, raises if denied, logs the audit row, and proceeds only on `Allow`. The seam is at the layer that touches external systems (QBO, Plaid, file writes outside the workspace, etc.) so it is impossible to bypass by accident.

### Daily review

Per HEARTBEAT, Chief of Staff reviews `boundaries.md` daily and proposes tightening (auto-deny patterns John has rejected 3+ times) or loosening (auto-approve patterns John has accepted 3+ times). Proposals are queued in `escalations.md`.

## 16. Autonomy modes

Every AI employee operates in one of three modes, declared in `config/employees.json` and switchable via `harness employee set-mode <name> <mode>`.

| Mode | Behavior | When used |
|------|----------|-----------|
| **Manual** | Every state-changing action proposed to Chief of Staff for approval before execution | First week of any new employee; after any incident; for high-risk actions regardless of mode |
| **Tiered** (default) | Actions within `boundaries.md` auto-execute; actions outside escalate per the table | Steady-state for mature employees |
| **Autonomous** | Even ambiguous actions execute on the employee's best judgment; only invariant violations or external-system errors escalate | Mature employees with proven track record; **never** for items touching real money or third parties |

Mode is enforced by the same `policy.check` engine that enforces boundaries. The mode acts as a multiplier on what the boundary table allows.

## 17. Banned patterns (binding)

OpenHarness must not implement:

- **A2A2H** (Agent-to-Agent-to-Human) protocol. Failed in CTO.
- **PWA** as outbound/notification channel. Failed in CTO.
- **Push notifications to John's phone.** Hard ban from the Chief-of-Staff role.
- **Foreground-only delivery** of escalations. Escalations queue to a file John reads when he chooses.
- **ReAct/Reflexion** unbounded retry loops. Use bounded plan → tool → verify per the Bookie research.
- **Multi-agent peer-to-peer messaging.** Employees route through Chief of Staff only.
- **Signed plugin marketplace.** External sources are local clones, not a registry.
- **Background process daemons that bypass the policy engine.** Anything that touches external systems goes through `policy.check`.

## 18. Risk register

Explicit risks and mitigations. Reviewed quarterly.

| # | Risk | Mitigation |
|---|------|------------|
| R1 | Runaway autonomy — agent acts beyond intended scope | Hard caps in `boundaries.md`; `policy.check` enforcement; per-task cost ceiling; autonomy-mode caps |
| R2 | Hallucinated execution — invalid action triggered | Deterministic invariants outside the LLM; dry-run mode by default for new behaviors; shadow mode for new employees |
| R3 | Memory corruption — bad facts persist and propagate | MEMORY.md is agent-written and append-only; daily rollover under `memory/YYYY-MM-DD.md`; periodic Chief of Staff review |
| R4 | Tool abuse — credentials misused | Scoped credentials per employee (separate `auth-profiles.json` entries); audit log captures every tool call |
| R5 | Cost explosion — long-running loops | Per-task LLM call cap; per-day token budget; hard cost ceiling per action; no unbounded ReAct |
| R6 | Channel failure — escalation queued but never read | `escalations.md` is part of the restart-protocol read sequence; Chief of Staff always reads it on session start |
| R7 | Boundary drift — boundaries.md edited without review | File is git-tracked; every change committed; Chief of Staff reviews daily per HEARTBEAT |
| R8 | Identity drift — SOUL.md modified accidentally | SOUL.md changes require explicit John approval; git history is the trail |
| R9 | Documentation rot — workspace files stale, restart fails | Doc hygiene is a standing duty in HEARTBEAT and AGENTS; `harness verify` catches some classes of rot |
| R10 | Inbox starvation — employee writes to inbox but Chief of Staff never reads | Inbox size logged; over-threshold flagged on next restart |
| R11 | Provider degradation — model API degraded or rate-limited | v2 circuit breaker + fallback provider (Hermes pattern) |
| R12 | Workspace disappearance — laptop loss, drive failure | Git push to GitHub origin after every state change ([always-sync rule]); workspace fully recoverable from origin |
| R13 | Policy engine bypass — agent calls an external API without going through `policy.guard` | Enforcement seam at the lowest tool layer; code review on every PR adding a new mutation site |
| R14 | Checkpoint drift — task resumes with stale assumptions | Checkpoints carry a workspace-state hash; resume fails fast if workspace has diverged |

## 19. Checkpointing & reflection (Phase 1.5 / Phase 2 commitments)

### Checkpointing primitive (Phase 1.5)

Long-running tasks (anything > 1 minute or > 5 LLM calls) must persist a resumable checkpoint. API:

```python
checkpoint.save(task_id, step_name, state_dict)
checkpoint.resume(task_id) -> (last_step, state_dict) | None
checkpoint.complete(task_id)  # marks done; auto-cleanup after 30 days
```

Storage: `state/checkpoints/<task_id>/<step_name>.json`. Auto-cleanup of completed tasks after 30 days. Crash recovery: any employee's restart routine attempts to resume any in-flight task with a checkpoint < 24h old.

### Reflection hook (Phase 2)

After any completed task, the employee may run `harness reflect <task_id>`, which triggers:

1. Read the task's decision rationales from chat.db (`kind='audit'`).
2. Read the task's outcome (success / failure / partial).
3. Run a self-critique pass: what worked, what could be a reusable pattern, what was a mistake.
4. Append to MEMORY.md (semantic / procedural layer).
5. Optionally synthesize a reusable skill in `employees/<name>/skills/` (Phase 3).

This is the harness primitive that Chimera §7.3 (skill synthesis) and §7.7 (reflection) collapse into. v1 declares the API; v1.5 implements checkpointing; v2 implements reflection; v3 considers full skill synthesis.

## 20. Provider model

V1: Claude Code is the model. The harness does not abstract the provider.

V2 (deferred): `config/auth-profiles.json` follows the OpenClaw pattern — profiles like `anthropic:default` and `openrouter:default`, with rotation and failover. Circuit breaker pattern (throttle ≥2s + rate ≥5/60s) from Hermes.

## 21. Run-as-service model (deferred)

V1: OpenHarness runs as a Python CLI on the laptop. Chief of Staff is alive only when Claude Code is open.

V2: `harness daemon` runs on a Hetzner VPS, polls the tick every 30 min, keeps Chief of Staff "alive" between Claude Code sessions. AI employees can post to the inbox at any time; Chief of Staff handles when the daemon ticks; truly urgent items still wait until John opens Claude Code (no push, ever).

V3 (further deferred): Web UI for John to browse workspace state read-only. **NOT** a PWA, **NOT** a notification surface — purely a read-only file browser with FTS search. If this can be served by `gh` / `git` / a static HTML viewer, we use that instead of building anything.

## 22. Phasing

**Phase 1 (MVP — this build):**
- Workspace scaffold for Chief of Staff (SOUL, MEMORY, HEARTBEAT, AGENTS, STYLE, USER, TOOLS, boundaries, escalations)
- Employee template (under `employees/_template/`)
- Python CLI: `harness restart`, `harness tick`, `harness inbox`, `harness send`, `harness employee install/list/set-mode`, `harness verify`, `harness extensions list/verify`, `harness state`, `harness policy check`
- SQLite + FTS5 state store
- Policy engine v1 (`policy.check` reading `boundaries.md`)
- Three autonomy modes selectable per employee
- Bookie scaffolded as the first employee

**Phase 1.5:**
- Checkpointing primitive (save/resume/complete)
- Audit log formalization (`harness audit verify`, `harness audit export`, monthly hash snapshots)
- Metrics surface (`harness state metrics`)
- `harness checkpoint resume <task_id>`

**Phase 2:**
- Daemon mode for the tick (laptop or VPS)
- Provider abstraction + circuit breaker
- Reflection hook (`harness reflect <task_id>`)
- Skill discovery (`skills/` folders) — only if needed
- Auth profile rotation

**Phase 3:**
- Read-only viewer (not a PWA)
- Vector / graph memory if needed
- Multi-employee process isolation if any employee genuinely needs it
- Skill synthesis from completed tasks

## 23. Success criteria

### Qualitative (S-series)

- **S1.** Chief of Staff can restart from a fresh Claude Code session, run `harness restart`, and resume operational continuity. Verified by: a session-A interaction is followed by a session-B `harness restart` that picks up correctly.
- **S2.** Bookie is installed as an employee and Chief of Staff can route messages to/from it.
- **S3.** Workspace integrity check passes (`harness verify` returns clean).
- **S4.** Every inbox/outbox/escalation/tick/audit is logged to `state/chat.db` and searchable via FTS5.
- **S5.** No push notification is ever sent. No A2A2H or PWA code exists. Verified by grep.
- **S6.** Every state-changing action by any employee routes through `policy.check`. Verified by code review and a runtime smoke test that intentionally tries to bypass.

### Quantitative (M-series — measured continuously, surfaced via `harness state metrics`)

- **M1.** Restart briefing produces in < 5 seconds.
- **M2.** Heartbeat tick completes in < 30 seconds (idle case) / < 5 minutes (full inbox).
- **M3.** Zero push notifications sent. Verified by grep across all code: 0 calls to any push API.
- **M4.** `harness verify` returns clean on every commit (CI gate, Phase 1.5).
- **M5.** Workspace fully restorable from `git clone` + the latest commit — no laptop-only state.
- **M6.** Audit log grows monotonically with every state-changing action. Zero missing rows; verified by `harness audit verify`.
- **M7.** Median escalation latency (employee writes to inbox → Chief of Staff handles) < 1 hour while running, < 24 hours including overnight.
- **M8.** Per-employee LLM cost stays within configured per-day budget. Verified by metrics surface.
- **M9.** Zero policy-engine bypasses recorded in audit log.

## 24. Open questions

- **Workspace path.** `~/.openharness/` (per-user) vs. `~/repos/OpenHarness/workspace/` (in the repo). V1 is in-repo for visibility; if it gets noisy, move it out.
- **Memory rollover.** Daily? Weekly? Triggered by size? Start with daily; revisit.
- **Employee process model.** Whether v2 spawns separate processes per employee or stays in-process. Defer.
- **Skill system.** Whether to bring over OpenClaw's `skills/` + YAML frontmatter. Defer to Phase 2; v1 doesn't need it.
- **Policy engine grammar.** `boundaries.md` is human-readable Markdown — what's the parser? Start with section-headers + bullets matched against a small DSL; revisit if it gets brittle.
- **Checkpoint serialization format.** JSON is the default; should it be `pickle`, `msgpack`, or stay plain JSON? Start JSON, switch if needed.

## 25. References

- CTO postmortem: `/home/john/repos/CTO-artifacts/lessons/CTO-postmortem-for-Bookie.md`
- Bookie design synthesis: `/home/john/repos/Bookie/lessons/Bookie-design-research-synthesis.md`
- Hermes Agent: `github.com/NousResearch/hermes-agent`
- OpenClaw: `github.com/openclaw/openclaw`
- SOUL.md spec (community): `github.com/aaronjmars/soul.md`
- AI harness term-of-art: HuggingFace agent glossary, MongoDB May 2026 post.
- Chimera PRD (gap source for v0.2): provided by John, 2026-05-27.
