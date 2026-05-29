"""Daemon scheduler. PRD §22.

`harness daemon` runs an indefinite loop. Every minute it walks the employee
registry, decides what's due based on HEARTBEAT.md, and dispatches:

1. Run the employee's Python `tick(context)` function (deterministic work)
2. If the tick returns narrative output, invoke agent_loop to compose text
3. Write any messages, MEMORY updates, escalations to files
4. Log every action to state/chat.db
5. git commit + push (sync to laptop and any other peer)

Employee tick functions are imported from `python_module` / `python_package`
declared in config/employees.json.
"""
from __future__ import annotations
import importlib
import importlib.util
import json
import signal
import subprocess
import sys
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from openharness import config, inboxes, state
from openharness.providers import CircuitBreaker, CircuitOpen, ProviderError, load_default_provider
from openharness import agent_loop


@dataclass
class TickResult:
    """Returned by an employee's tick(context) function."""
    messages_to_cos: list[str]      # plain text lines to append to inbox/<name>.md
    memory_appends: list[str]       # entries to append to employee's MEMORY.md
    escalations: list[dict]         # [{summary, body, recommendation}]
    llm_prompts: list[str]          # tasks needing LLM narrative; daemon invokes agent_loop
    status: str = "ok"


def _load_employee_module(emp: dict):
    """Add employee's python_module to sys.path and import its python_package."""
    py_mod = emp.get("python_module")
    py_pkg = emp.get("python_package")
    if not py_mod or not py_pkg:
        return None
    py_mod_path = Path(py_mod).resolve()
    if str(py_mod_path) not in sys.path:
        sys.path.insert(0, str(py_mod_path))
    return importlib.import_module(py_pkg)


def _build_employee_context(emp: dict) -> dict:
    """Build the dict passed to employee.tick()."""
    root = Path(config.load()["_root"])
    emp_path = Path(emp["path"])
    return {
        "name": emp["name"],
        "path": str(emp_path),
        "openharness_root": str(root),
        "inbox_path": str(root / "inbox" / f"{emp['name']}.md"),
        "outbox_path": str(root / "outbox" / f"{emp['name']}.md"),
        "memory_path": str(emp_path / "MEMORY.md"),
        "heartbeat_path": str(emp_path / "HEARTBEAT.md"),
        "now_ts": time.time(),
    }


def _handle_tick_result(emp: dict, result, provider: CircuitBreaker) -> None:
    """Apply a TickResult: write messages, append MEMORY, escalate, invoke LLM for narrative work."""
    root = Path(config.load()["_root"])
    emp_name = emp["name"]
    emp_path = Path(emp["path"])

    # Coerce dict / dataclass uniformly
    if isinstance(result, dict):
        messages = result.get("messages_to_cos", [])
        memory = result.get("memory_appends", [])
        escalations = result.get("escalations", [])
        llm_prompts = result.get("llm_prompts", [])
        status = result.get("status", "ok")
    else:
        messages = getattr(result, "messages_to_cos", [])
        memory = getattr(result, "memory_appends", [])
        escalations = getattr(result, "escalations", [])
        llm_prompts = getattr(result, "llm_prompts", [])
        status = getattr(result, "status", "ok")

    # 1. Append inbox messages
    inbox_path = root / "inbox" / f"{emp_name}.md"
    for m in messages:
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with inbox_path.open("a") as f:
            f.write(f"\n## {stamp}\n{m.rstrip()}\n")
        state.append(sender=emp_name, recipient="cos", kind="inbox", content=m)

    # 2. Append MEMORY entries
    memory_path = emp_path / "MEMORY.md"
    for entry in memory:
        stamp = time.strftime("%Y-%m-%d")
        with memory_path.open("a") as f:
            f.write(f"\n## {stamp}\n\n{entry.rstrip()}\n")

    # 3. Escalations
    for esc in escalations:
        inboxes.append_escalation(
            summary=esc.get("summary", "(no summary)"),
            body=esc.get("body", ""),
            recommendation=esc.get("recommendation", ""),
        )
        state.append(sender=emp_name, recipient="john", kind="escalation",
                     content=json.dumps(esc))

    # 4. LLM-driven narrative work
    for prompt in llm_prompts:
        try:
            resp = agent_loop.invoke(provider, emp_path, emp_name, prompt)
            stamp = time.strftime("%Y-%m-%d %H:%M:%S")
            with inbox_path.open("a") as f:
                f.write(f"\n## {stamp}\n{resp.text.rstrip()}\n")
            state.append(sender=emp_name, recipient="cos", kind="inbox",
                         content=resp.text)
        except CircuitOpen as e:
            state.append(sender=emp_name, kind="event",
                         content=f"agent_loop skipped (circuit open): {e}")
        except ProviderError as e:
            state.append(sender=emp_name, kind="event",
                         content=f"agent_loop failed: {e}")

    state.append(sender=emp_name, kind="tick", content=f"tick complete, status={status}")


def tick_employee(emp: dict, provider: CircuitBreaker) -> str:
    """Run one tick for one employee. Returns a one-line status."""
    try:
        module = _load_employee_module(emp)
        if module is None:
            return f"{emp['name']}: no python_module configured; skip"
        if not hasattr(module, "tick"):
            return f"{emp['name']}: module has no tick() function; skip"
        ctx = _build_employee_context(emp)
        result = module.tick(ctx)
        if result is None:
            return f"{emp['name']}: tick returned None; nothing to do"
        _handle_tick_result(emp, result, provider)
        return f"{emp['name']}: tick OK"
    except Exception as e:
        tb = traceback.format_exc(limit=3)
        state.append(sender=emp["name"], kind="event",
                     content=f"tick FAILED: {e}\n{tb}")
        return f"{emp['name']}: tick FAILED: {e}"


def git_sync(repo_root: Path) -> None:
    """Commit any state changes and push. Best-effort; failures don't crash the daemon."""
    try:
        subprocess.run(["git", "-C", str(repo_root), "add", "-A"],
                       capture_output=True, timeout=30)
        # Check if there's anything to commit
        result = subprocess.run(
            ["git", "-C", str(repo_root), "diff", "--cached", "--quiet"],
            capture_output=True, timeout=10,
        )
        if result.returncode == 0:
            return  # nothing to commit
        subprocess.run(
            ["git", "-C", str(repo_root), "commit", "-q", "-m", "daemon: tick state update"],
            capture_output=True, timeout=30,
        )
        subprocess.run(["git", "-C", str(repo_root), "push", "-q"],
                       capture_output=True, timeout=60)
    except Exception as e:
        state.append(sender="cos", kind="event",
                     content=f"git_sync failed (non-fatal): {e}")


_running = True


def _handle_signal(signum, frame):
    global _running
    _running = False


def run(*, interval_seconds: int = 60, git_sync_enabled: bool = True,
        once: bool = False) -> None:
    """Main daemon entrypoint.

    Args:
        interval_seconds: sleep between scheduler ticks. Default 60s.
        git_sync_enabled: commit + push after each cycle. Default True.
        once: run a single cycle and exit (for tests / CLI smoke).
    """
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)
    state.append(sender="cos", kind="event", content="daemon: started")
    try:
        provider = load_default_provider()
    except ProviderError as e:
        state.append(sender="cos", kind="event",
                     content=f"daemon: cannot load provider: {e}")
        print(f"FATAL: {e}", file=sys.stderr)
        sys.exit(1)
    repo_root = Path(config.load()["_root"])

    while _running:
        # 1. Fire any due cron jobs first (reflection etc.)
        try:
            from openharness import cron as cron_mod
            due = cron_mod.due_now()
            for job in due:
                state.append(sender="cos", kind="event",
                             content=f"cron firing job {job['id']} target={job['target']}")
                result = cron_mod.run_job(job)
                cron_mod.mark_ran(job["id"])
                state.append(sender="cos", kind="event",
                             content=f"cron job {job['id']} result={result.get('ok')}: "
                                     f"{(result.get('error') or '')[:200]}")
        except Exception as e:
            state.append(sender="cos", kind="event",
                         content=f"cron loop failed (non-fatal): {e}")

        # 2. Run each employee's tick()
        for emp in config.load_employees():
            status = tick_employee(emp, provider)
            print(status)
        if git_sync_enabled:
            git_sync(repo_root)
        if once:
            break
        # Sleep responsively to SIGINT
        slept = 0
        while _running and slept < interval_seconds:
            time.sleep(min(1, interval_seconds - slept))
            slept += 1

    state.append(sender="cos", kind="event", content="daemon: stopped")
