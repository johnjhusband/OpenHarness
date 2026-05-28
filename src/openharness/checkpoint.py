"""Checkpointing primitive. PRD §19 (Phase 1.5 promoted to v1 because Bookie's
month-end close is multi-step and crashable).

Tasks save state at named steps; restart can resume from the last successful
step. Storage: state/checkpoints/<task_id>/<step_name>.json.
"""
from __future__ import annotations
import json
import time
from pathlib import Path

from openharness import config


def _checkpoints_root() -> Path:
    root = Path(config.load()["_root"])
    p = root / "state" / "checkpoints"
    p.mkdir(parents=True, exist_ok=True)
    return p


def save(task_id: str, step_name: str, state_dict: dict) -> Path:
    """Save a checkpoint for a task at a named step."""
    if not task_id or "/" in task_id or ".." in task_id:
        raise ValueError(f"Invalid task_id: {task_id!r}")
    if not step_name or "/" in step_name:
        raise ValueError(f"Invalid step_name: {step_name!r}")
    task_dir = _checkpoints_root() / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    path = task_dir / f"{step_name}.json"
    payload = {
        "task_id": task_id,
        "step_name": step_name,
        "saved_at": time.time(),
        "state": state_dict,
    }
    path.write_text(json.dumps(payload, indent=2))
    return path


def resume(task_id: str) -> tuple[str, dict] | None:
    """Return (last_step_name, state_dict) for the most recent checkpoint, or None."""
    task_dir = _checkpoints_root() / task_id
    if not task_dir.is_dir():
        return None
    candidates = sorted(task_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)
    if not candidates:
        return None
    latest = candidates[-1]
    payload = json.loads(latest.read_text())
    return payload["step_name"], payload["state"]


def complete(task_id: str) -> None:
    """Mark a task complete. Marker file used by cleanup to defer deletion 30 days."""
    task_dir = _checkpoints_root() / task_id
    if not task_dir.is_dir():
        return
    (task_dir / ".completed").write_text(str(time.time()))


def list_in_flight(max_age_hours: int = 24) -> list[dict]:
    """List tasks with checkpoints younger than max_age_hours and not marked complete."""
    cutoff = time.time() - max_age_hours * 3600
    out = []
    root = _checkpoints_root()
    for task_dir in root.iterdir():
        if not task_dir.is_dir():
            continue
        if (task_dir / ".completed").exists():
            continue
        candidates = sorted(task_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)
        if not candidates:
            continue
        latest = candidates[-1]
        if latest.stat().st_mtime >= cutoff:
            out.append({
                "task_id": task_dir.name,
                "last_step": latest.stem,
                "saved_at": latest.stat().st_mtime,
            })
    return out
