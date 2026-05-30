"""Task-ownership ledger + deliverable-freshness tracking.

Two structural fixes for failures the harness wasn't catching:

1. OWNERSHIP: setup steps are encoded as data with an owner (claude/john/
   deferred), status, and blocked_on. The harness can compute "claude-owned,
   unblocked, incomplete" steps — and a goal criterion turns RED when any
   exist. That structurally stops me from leaving my own work assigned to
   John: once his prerequisite step completes, my steps unblock, the goal
   goes red, and the Stop hook refuses to let me finish until I do them.

2. FRESHNESS: derived artifacts (SETUP.md, the emailed checklist) are tracked
   against their source. When the source changes but the delivery wasn't
   refreshed, a criterion turns RED. That stops stale copies lingering.

The plan file is per-employee: employees/<name>/setup-plan.json, OR for Bookie
specifically it lives in the Bookie repo at ${BOOKIE_ROOT}/setup-plan.json.
"""
from __future__ import annotations
import hashlib
import json
import os
import time
from pathlib import Path

from openharness import config


def _bookie_root() -> Path | None:
    for e in config.load_employees():
        if e.get("name") == "bookie" and e.get("python_module"):
            return Path(e["python_module"]).parent
    return None


def plan_path() -> Path:
    """Locate the Bookie setup plan."""
    override = os.environ.get("BOOKIE_SETUP_PLAN")
    if override:
        return Path(override)
    root = _bookie_root()
    if root:
        return root / "setup-plan.json"
    return Path("/home/john/repos/Bookie/setup-plan.json")


def load_plan() -> dict:
    p = plan_path()
    if not p.exists():
        return {"steps": []}
    return json.loads(p.read_text())


def _by_id(steps: list[dict]) -> dict[str, dict]:
    return {s["id"]: s for s in steps}


def _is_done(step: dict) -> bool:
    return step.get("status") in ("done", "deferred")


def _is_blocked(step: dict, index: dict[str, dict]) -> bool:
    for dep in step.get("blocked_on", []):
        dep_step = index.get(dep)
        if dep_step is None:
            continue
        if not _is_done(dep_step):
            return True
    return False


def claude_actionable() -> list[dict]:
    """Claude-owned steps that are incomplete and unblocked — these are MINE to do now."""
    steps = load_plan().get("steps", [])
    index = _by_id(steps)
    out = []
    for s in steps:
        if s.get("owner") != "claude":
            continue
        if _is_done(s):
            continue
        if _is_blocked(s, index):
            continue
        out.append(s)
    return out


def john_actionable() -> list[dict]:
    """John-owned steps that are incomplete and unblocked — his real to-do list."""
    steps = load_plan().get("steps", [])
    index = _by_id(steps)
    out = []
    for s in steps:
        if s.get("owner") != "john":
            continue
        if _is_done(s):
            continue
        if _is_blocked(s, index):
            continue
        out.append(s)
    return out


def blocked_steps() -> list[dict]:
    steps = load_plan().get("steps", [])
    index = _by_id(steps)
    return [s for s in steps if not _is_done(s) and _is_blocked(s, index)]


def set_status(step_id: str, status: str) -> bool:
    plan = load_plan()
    found = False
    for s in plan.get("steps", []):
        if s["id"] == step_id:
            s["status"] = status
            found = True
    if found:
        plan_path().write_text(json.dumps(plan, indent=2))
    return found


# ---------------- predicates for goal criteria ----------------

def no_claude_work_left_undone() -> bool:
    """True if there are NO claude-owned, unblocked, incomplete steps.

    Goal criterion uses this: when it returns False (I have actionable work),
    the criterion is RED and the Stop hook won't let me finish.
    """
    return len(claude_actionable()) == 0


# ---------------- deliverable freshness ----------------

def _deliveries_path() -> Path:
    return Path(config.load()["_root"]) / "state" / "deliveries.json"


def _load_deliveries() -> dict:
    p = _deliveries_path()
    if not p.exists():
        return {}
    return json.loads(p.read_text())


def _save_deliveries(d: dict) -> None:
    p = _deliveries_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, indent=2))


def _sha256_file(path: Path) -> str:
    if not path.exists():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def record_delivery(artifact_id: str, source_path: str) -> None:
    """Record that `artifact_id` was delivered reflecting the current source content."""
    d = _load_deliveries()
    d[artifact_id] = {
        "source_path": source_path,
        "source_sha": _sha256_file(Path(source_path)),
        "delivered_at": time.time(),
    }
    _save_deliveries(d)


def delivery_is_current(artifact_id: str, source_path: str) -> bool:
    """True if the artifact was delivered reflecting the CURRENT source content."""
    d = _load_deliveries()
    rec = d.get(artifact_id)
    if rec is None:
        return False
    return rec.get("source_sha") == _sha256_file(Path(source_path))


def setup_doc_delivery_current() -> bool:
    """Predicate for goal criterion: the emailed SETUP checklist reflects current SETUP.md."""
    root = _bookie_root()
    if root is None:
        return True  # can't locate; don't block
    setup_md = root / "SETUP.md"
    if not setup_md.exists():
        return True
    return delivery_is_current("bookie-setup-email", str(setup_md))


# ---------------- doc rendering ----------------

def render_setup_markdown() -> str:
    """Render SETUP.md from the plan so the doc can't drift from the ledger."""
    plan = load_plan()
    steps = plan.get("steps", [])
    index = _by_id(steps)
    lines = []
    lines.append(f"# {plan.get('title', 'Bookie setup')}\n")
    lines.append("> This file is generated from `setup-plan.json` by `harness plan sync-doc`. "
                 "Edit the plan, not this file.\n")
    if plan.get("critical_path_note"):
        lines.append(f"**Critical path:** {plan['critical_path_note']}\n")

    # Ownership summary up top
    mine = [s for s in steps if s.get("owner") == "claude" and not _is_done(s)]
    johns = john_actionable()
    deferred = [s for s in steps if s.get("status") == "deferred"]
    lines.append("## Who does what\n")
    lines.append(f"- **You (John) — actionable now:** "
                 + (", ".join(f"Step {s['id']}" for s in johns) if johns else "none") + "")
    lines.append(f"- **Claude — does these (some blocked until you finish your steps):** "
                 + (", ".join(f"Step {s['id']}" for s in mine) if mine else "none") + "")
    lines.append(f"- **Deferred (not needed for first light):** "
                 + (", ".join(f"Step {s['id']}" for s in deferred) if deferred else "none") + "\n")

    lines.append("## Steps\n")
    for s in steps:
        owner = s.get("owner", "?")
        owner_label = {"claude": "CLAUDE DOES THIS", "john": "JOHN DOES THIS",
                       "deferred": "DEFERRED"}.get(owner, owner.upper())
        status = s.get("status", "todo")
        status_mark = {"done": "✓ DONE", "deferred": "— deferred",
                       "todo": "TODO"}.get(status, status)
        blocked = _is_blocked(s, index)
        block_note = ""
        if blocked:
            deps = ", ".join(s.get("blocked_on", []))
            block_note = f" _(blocked until Step {deps} done)_"
        lines.append(f"### Step {s['id']} — {s['title']}  [{owner_label}] {status_mark}{block_note}\n")
        if s.get("detail"):
            lines.append(s["detail"] + "\n")
        if s.get("claude_assist"):
            lines.append(f"*Claude can assist:* {s['claude_assist']}\n")
        if s.get("why_owner") and owner == "john":
            lines.append(f"*Why this is yours and not automatable:* {s['why_owner']}\n")
    return "\n".join(lines)


def sync_doc() -> Path:
    """Write the rendered markdown to SETUP.md in the Bookie repo."""
    root = _bookie_root()
    if root is None:
        raise RuntimeError("cannot locate Bookie root to write SETUP.md")
    out = root / "SETUP.md"
    out.write_text(render_setup_markdown())
    return out


# ---------------- THE LOOP: next-action engine ----------------
# Powers the Stop hook. Computes the single next concrete action, or HANDOFF
# when there's genuinely nothing left for me to do/research/invent. The hook
# can ONLY block me from stopping if this names a concrete action — so it can
# never trap me in an infinite block.

def john_pending_unresearched() -> list[dict]:
    """John-owned, unblocked, incomplete steps that I have NOT yet researched
    to completeness this cycle. Researching them is MY work (shrinks his risk
    of bouncing back). A step is 'researched' when it has researched_at set
    AND that timestamp is newer than the step's last content change — we
    approximate by just requiring the researched flag to be present and true.
    """
    out = []
    for s in john_actionable():
        if not s.get("researched"):
            out.append(s)
    return out


def next_action() -> dict:
    """Return the single next concrete action under the operating loop.

    verdict is one of:
      WORK     — a claude-owned step is actionable now; do it
      RESEARCH — a john-owned pending step is unresearched; research it so his
                 handoff is bulletproof
      HANDOFF  — nothing left for me; the remainder is genuinely John's and is
                 researched. Allowed to yield.
    Returns {"verdict", "action", "detail"}.
    """
    mine = claude_actionable()
    if mine:
        s = mine[0]
        return {
            "verdict": "WORK",
            "action": f"Do Step {s['id']}: {s['title']}",
            "detail": s.get("detail", ""),
        }
    unresearched = john_pending_unresearched()
    if unresearched:
        s = unresearched[0]
        return {
            "verdict": "RESEARCH",
            "action": f"Research Step {s['id']} ({s['title']}) against current docs "
                      f"so John's instructions are exact and complete",
            "detail": s.get("detail", ""),
        }
    return {
        "verdict": "HANDOFF",
        "action": "Nothing actionable for me. Remaining work is John's and is researched.",
        "detail": "",
    }


def mark_researched(step_id: str) -> bool:
    """Mark a john-owned step as researched-to-completeness this cycle."""
    p = load_plan()
    found = False
    for s in p.get("steps", []):
        if s["id"] == step_id:
            s["researched"] = True
            s["researched_at"] = time.time()
            found = True
    if found:
        plan_path().write_text(json.dumps(p, indent=2))
    return found
