"""Single-turn agent loop. PRD §21.

The system prompt is built from the employee's SOUL + AGENTS + recent
MEMORY + relevant inbox/outbox. The user prompt is the specific task.

Multi-turn tool use and MCP integration are v2; v1 keeps the loop simple
because most employee work is deterministic Python the daemon runs *before*
the LLM is invoked.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path

from openharness import config, state
from openharness.providers import CircuitBreaker, ProviderResponse


@dataclass
class EmployeeContext:
    name: str
    soul: str
    agents: str
    heartbeat: str
    memory_tail: str    # last ~30 lines of MEMORY.md
    inbox_tail: str     # last ~50 lines of inbox/<name>.md
    outbox_tail: str    # last ~50 lines of outbox/<name>.md


def _safe_tail(path: Path, n_lines: int = 50) -> str:
    if not path.exists():
        return ""
    try:
        lines = path.read_text().splitlines()
    except Exception:
        return ""
    return "\n".join(lines[-n_lines:])


def load_employee_context(employee_path: Path, employee_name: str) -> EmployeeContext:
    root = Path(config.load()["_root"])
    return EmployeeContext(
        name=employee_name,
        soul=(employee_path / "SOUL.md").read_text() if (employee_path / "SOUL.md").exists() else "",
        agents=(employee_path / "AGENTS.md").read_text() if (employee_path / "AGENTS.md").exists() else "",
        heartbeat=(employee_path / "HEARTBEAT.md").read_text() if (employee_path / "HEARTBEAT.md").exists() else "",
        memory_tail=_safe_tail(employee_path / "MEMORY.md", 30),
        inbox_tail=_safe_tail(root / "inbox" / f"{employee_name}.md", 50),
        outbox_tail=_safe_tail(root / "outbox" / f"{employee_name}.md", 50),
    )


def build_system_prompt(ctx: EmployeeContext) -> str:
    return (
        f"You are {ctx.name}, operating headlessly inside OpenHarness.\n\n"
        f"# Your identity (SOUL.md)\n\n{ctx.soul}\n\n"
        f"# Procedural manual (AGENTS.md)\n\n{ctx.agents}\n\n"
        f"# Schedule (HEARTBEAT.md)\n\n{ctx.heartbeat}\n\n"
        f"# Recent MEMORY entries\n\n{ctx.memory_tail}\n\n"
        f"# Recent inbox (your messages to Chief of Staff)\n\n{ctx.inbox_tail}\n\n"
        f"# Recent outbox (Chief of Staff to you)\n\n{ctx.outbox_tail}\n\n"
        f"You will be given one task. Respond in plain text only. "
        f"Do not invent tool calls; the harness will execute any deterministic work for you."
    )


def invoke(
    provider: CircuitBreaker,
    employee_path: Path,
    employee_name: str,
    user_prompt: str,
    *,
    timeout: int = 300,
) -> ProviderResponse:
    """Run one LLM call for an employee. Logs to chat.db, returns the response.

    Caller decides what to do with the response (write to inbox, MEMORY, etc.).
    """
    ctx = load_employee_context(employee_path, employee_name)
    system = build_system_prompt(ctx)
    state.append(
        sender=employee_name,
        kind="event",
        content=f"agent_loop.invoke: prompt={user_prompt[:140]!r}",
    )
    resp = provider.call(system, user_prompt, timeout=timeout)
    state.append(
        sender=employee_name,
        kind="event",
        content=f"agent_loop.response: cost=${resp.cost_usd:.4f} dur={resp.duration_seconds:.2f}s "
                f"text={resp.text[:140]!r}",
    )
    return resp
