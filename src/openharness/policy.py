"""Policy engine v1. PRD §15.

Reads boundaries.md and the calling employee's autonomy mode. Returns a Decision
for any state-changing action. Every employee tool layer must route mutations
through `policy.guard(action)` so the check is impossible to bypass at the
layer that matters.

v1 grammar: boundaries.md sections per employee with `### auto-approve` and
`### escalate` subsections. Each line under those is a pattern.
"""
from __future__ import annotations
import re
import json
import time
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

from openharness import config, state


@dataclass
class Action:
    employee: str
    kind: str           # "categorize" | "post_journal_entry" | "send_message" | "write_file" | etc.
    target: str         # what's being acted on (transaction id, vendor, file path, etc.)
    amount: float = 0.0
    description: str = ""
    metadata: dict | None = None


@dataclass
class Decision:
    result: str         # "allow" | "escalate" | "deny"
    rule: str           # matched rule from boundaries.md
    rationale: str
    autonomy_mode: str

    def is_allow(self) -> bool:
        return self.result == "allow"


class PolicyBypass(Exception):
    """Raised when an action is denied or escalated and the caller did not handle it."""


def _load_boundaries_text() -> str:
    cfg = config.load()
    path = Path(cfg["_root"]) / cfg["chief_of_staff"]["boundaries_path"]
    if not path.exists():
        return ""
    return path.read_text()


def _employee_mode(employee: str) -> str:
    for e in config.load_employees():
        if e.get("name") == employee:
            return e.get("autonomy_mode", "tiered")
    return "tiered"


def _amount_exceeds_ceiling(action: Action, text: str) -> Optional[str]:
    """Look for '> $X' or 'over $X' rules in boundaries.md and check the action amount."""
    if action.amount <= 0:
        return None
    for m in re.finditer(r"(?:>|over|exceed[s]?|above)\s*\$([\d,]+(?:\.\d+)?)", text, re.IGNORECASE):
        try:
            ceiling = float(m.group(1).replace(",", ""))
            if action.amount > ceiling:
                return f"amount ${action.amount:.2f} exceeds boundary ceiling ${ceiling:.2f}"
        except ValueError:
            continue
    return None


def check(action: Action) -> Decision:
    """Evaluate an action against boundaries.md + employee autonomy mode.

    v1 heuristic: look for explicit ceilings, default to allow under tiered mode
    unless the action kind matches a known escalation pattern.
    """
    text = _load_boundaries_text()
    mode = _employee_mode(action.employee)

    # Manual mode: every state-changing action escalates
    if mode == "manual":
        return Decision(
            result="escalate",
            rule="autonomy_mode=manual",
            rationale="Employee is in manual mode; every action requires Chief of Staff approval.",
            autonomy_mode=mode,
        )

    # Check explicit dollar ceilings
    ceiling_breach = _amount_exceeds_ceiling(action, text)
    if ceiling_breach:
        return Decision(
            result="escalate",
            rule="dollar_ceiling",
            rationale=ceiling_breach,
            autonomy_mode=mode,
        )

    # Known always-escalate kinds (parsed loosely from boundaries.md text)
    always_escalate_kinds = []
    for kind in ("new GL account", "tax filing", "money movement", "new vendor"):
        if kind.lower() in text.lower():
            always_escalate_kinds.append(kind.lower())
    if any(k in action.kind.lower() or k in action.description.lower() for k in always_escalate_kinds):
        if mode != "autonomous":
            return Decision(
                result="escalate",
                rule="known_escalation_kind",
                rationale=f"Action kind matches an always-escalate pattern: {action.kind}",
                autonomy_mode=mode,
            )

    # Default under tiered mode: allow
    return Decision(
        result="allow",
        rule="default_tiered",
        rationale="No ceiling breach; no known escalation kind; tiered mode default-allows.",
        autonomy_mode=mode,
    )


def _log(action: Action, decision: Decision) -> int:
    payload = {
        "action": asdict(action),
        "decision": asdict(decision),
        "ts": time.time(),
    }
    return state.append(
        sender=action.employee,
        kind="audit",
        content=json.dumps(payload),
        correlation=f"policy:{action.kind}:{action.target}",
    )


@contextmanager
def guard(action: Action):
    """Context manager every state-changing employee action must wrap with.

    Raises PolicyBypass if the action is escalated or denied. The caller can
    catch and write to escalations.md, or let it propagate to fail the action.
    """
    decision = check(action)
    _log(action, decision)
    if not decision.is_allow():
        raise PolicyBypass(f"{decision.result}: {decision.rationale}")
    yield decision
