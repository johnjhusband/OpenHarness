"""Self-improvement: reflection loop.

Reads recent decisions from chat.db for an employee, builds a prompt asking
the LLM to identify patterns the employee should remember, writes the
synthesized learnings into MEMORY.md.

Inspired by Hermes's curator and OpenClaw's `self-improving-agent` pattern.
"""
from __future__ import annotations
import json
import time
from pathlib import Path

from openharness import config, memory, providers, state


REFLECTION_SYSTEM_PROMPT = """You are reviewing the recent decision log of an AI
employee. Read the rationales. Identify patterns the employee should remember
going forward so it makes faster, better decisions next time.

Output one of the following per finding:

[semantic] <a concrete fact the employee should know>
[procedural] <a workflow or rule the employee should apply>
[escalation-candidate] <a class of decision the employee should escalate to Chief of Staff>
[skill-candidate] <a reusable skill that would automate a recurring pattern>

Lead with the strongest 1-5 findings. Skip noise. Cite specific transaction
ids, vendors, amounts, or dates from the log to ground each finding. If
nothing is worth remembering, output exactly: NO_FINDINGS
"""


def _collect_recent_decisions(employee: str, since_ts: float) -> list[dict]:
    """Pull memory + audit + tick + escalation rows for the employee since ts."""
    with state.connection() as conn:
        rows = conn.execute(
            "SELECT id, ts, sender, recipient, kind, correlation, content "
            "FROM messages "
            "WHERE sender = ? AND ts >= ? "
            "AND kind IN ('audit','tick','inbox','memory','escalation','event') "
            "ORDER BY ts ASC",
            (employee, since_ts),
        ).fetchall()
    return [
        {"id": r[0], "ts": r[1], "kind": r[4], "content": r[6]}
        for r in rows
    ]


def _employee_workspace(employee: str) -> Path:
    for e in config.load_employees():
        if e["name"] == employee:
            return Path(e["path"])
    raise ValueError(f"unknown employee: {employee}")


def _read_decisions_files(employee: str, since_ts: float) -> list[dict]:
    """Also pull employee-written workspace/decisions/*.json since ts."""
    workspace = _employee_workspace(employee) / "workspace" / "decisions"
    if not workspace.exists():
        return []
    out = []
    for f in workspace.glob("*.json"):
        if f.stat().st_mtime < since_ts:
            continue
        try:
            data = json.loads(f.read_text())
            if isinstance(data, list):
                out.extend(data)
        except Exception:
            continue
    return out


def reflect(employee: str, *, since_hours: int = 168, dry_run: bool = False) -> dict:
    """Run one reflection pass for the employee.

    Args:
        employee: the employee name (e.g. "bookie")
        since_hours: how far back to look (default 7 days)
        dry_run: if True, do not append to MEMORY.md; return the would-be entry

    Returns dict with rows_reviewed, decisions_reviewed, findings_text,
    appended_to_memory, and prompt cost.
    """
    since_ts = time.time() - (since_hours * 3600)
    chat_rows = _collect_recent_decisions(employee, since_ts)
    decisions = _read_decisions_files(employee, since_ts)

    if not chat_rows and not decisions:
        return {
            "employee": employee,
            "since_hours": since_hours,
            "rows_reviewed": 0,
            "decisions_reviewed": 0,
            "findings_text": "NO_FINDINGS",
            "appended_to_memory": False,
            "cost_usd": 0.0,
        }

    # Build a compact log summary; cap to keep the prompt within budget
    log_lines = []
    for r in chat_rows[-100:]:
        log_lines.append(f"[{r['kind']}] #{r['id']} {r['content'][:200]}")
    decision_lines = []
    for d in decisions[-100:]:
        decision_lines.append(
            f"{d.get('tx_id', '?')} {d.get('vendor', '')[:30]} ${d.get('amount', 0):>9.2f} "
            f"→ {d.get('gl_account', '?')} step={d.get('step', '?')} "
            f"conf={d.get('confidence', '?')} :: {d.get('rationale', '')[:120]}"
        )

    user_prompt = (
        f"Employee: {employee}\n"
        f"Window: last {since_hours} hours ({len(chat_rows)} chat rows, "
        f"{len(decisions)} decision records)\n\n"
        f"=== Recent decisions ===\n" + "\n".join(decision_lines[-80:]) + "\n\n"
        f"=== Recent chat.db rows ===\n" + "\n".join(log_lines[-80:]) + "\n\n"
        "Identify the strongest findings now."
    )

    # Invoke the provider
    prov = providers.load_default_provider()
    resp = prov.call(REFLECTION_SYSTEM_PROMPT, user_prompt, timeout=180)
    findings = resp.text.strip()

    appended = False
    if not dry_run and findings and findings != "NO_FINDINGS":
        memory.add(
            employee=employee,
            content=f"Reflection pass over last {since_hours}h "
                    f"({len(chat_rows)} chat rows, {len(decisions)} decisions):\n\n{findings}",
            layer="procedural",
            tag="reflection",
        )
        appended = True

    state.append(
        sender=employee, kind="event",
        content=f"reflection: window={since_hours}h findings_chars={len(findings)} "
                f"appended={appended} cost=${resp.cost_usd:.4f}"
    )

    return {
        "employee": employee,
        "since_hours": since_hours,
        "rows_reviewed": len(chat_rows),
        "decisions_reviewed": len(decisions),
        "findings_text": findings,
        "appended_to_memory": appended,
        "cost_usd": resp.cost_usd,
        "duration_seconds": resp.duration_seconds,
    }
