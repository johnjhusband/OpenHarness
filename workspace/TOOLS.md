# TOOLS — Chief of Staff tool registry

What tools I have available, what they're for, and where to look for more.

## Built-in (via Claude Code)

| Tool | Purpose |
|------|---------|
| `Read`, `Write`, `Edit` | File operations |
| `Bash` | Shell commands (sandboxed; needs approval for some) |
| `Agent` | Spawn sub-agents (Explore, general-purpose, claude-code-guide, Plan, etc.) for parallelizable work |
| `Task*` | Task management (TaskCreate, TaskList, TaskUpdate, etc.) |
| `WebSearch`, `WebFetch` | Live web research |
| `AskUserQuestion` | Structured questions to John (use sparingly; he prefers terse asks) |
| `ScheduleWakeup`, `CronCreate` | Self-scheduled wake-ups (dynamic and cron-based) |
| `Monitor` | Watch background processes for output |

## MCP servers loaded in Claude Code

| Server | Tools | Purpose |
|--------|-------|---------|
| `Gmail` | search, label, create draft, get thread | John's email access (OAuth, no app passwords) |
| `Google Calendar` | authenticate | Calendar (needs auth flow) |
| `Google Drive` | authenticate | Drive (needs auth flow) |
| `playwright` | navigate, click, fill_form, screenshot, console_messages | Browser automation |

## OpenHarness CLI

`harness <command>` — see `prd/OpenHarness-PRD.md` §8 for the full surface.

## OS / CLI binaries

| Binary | Path | Purpose |
|--------|------|---------|
| `hcloud` | `/home/john/.local/bin/hcloud` | Hetzner cloud CLI |
| `gh` | system | GitHub CLI (auth via stored token) |
| `git` | system | Git |
| `python3` | system | Python 3 |
| `lightpanda` | `/home/john/.local/bin/lightpanda` | Headless browser (CDP-compatible), 130MB |

## Tools NOT installed (would have to ask before)

- Stagehand (not installed; pip/npm install when adopted)
- Browserbase (paid account, not configured)
- Anthropic Computer Use / OpenAI CUA (API only, no extra install)
- QBO / Plaid SDKs (Bookie installs these when needed)

## Where to find more

- **Extensions:** `harness extensions list` — surfaces skills/MCPs/templates from external sources (PRD §13). Currently empty.
- **MCP catalog:** `mcp.so` (web) for discoverable MCP servers.
- **Reference repos** (if cloned): `~/repos/references/` — OpenClaw, Hermes, awesome-openclaw-agents, soul.md.

## Browser-automation escalation ladder

Bookie and any agent that needs browser interaction follows the 6-rung ladder in `/home/john/repos/Bookie/lessons/browser-automation-escalation-ladder.md`. Start cheapest (static fetch), escalate only on failure, hard-stop on 5min / 50 LLM calls / $1 cost ceiling / 10 attempts per site per day.
