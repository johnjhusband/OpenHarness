"""Memory tool API. Programmatic reads and writes of an employee's MEMORY.md.

Per gap analysis: agents need a callable API to write durable knowledge into
MEMORY.md mid-task without manually opening the file. Includes capacity gate
(Hermes pattern: ~2,200 chars max, consolidate-on-overflow signal).

Memory layers per OpenHarness PRD §8 typology:
- episodic — what happened
- semantic — accumulated facts
- procedural — reusable workflows
- working — active task state (lives in workspace/, not MEMORY.md)
"""
from __future__ import annotations
import time
from pathlib import Path
from typing import Literal

from openharness import config, state


MEMORY_CAPACITY_CHARS = 8000  # higher than Hermes's 2200; ours rolls over daily
ROLLOVER_THRESHOLD_CHARS = 6500


Layer = Literal["episodic", "semantic", "procedural"]


def _memory_path(employee: str) -> Path:
    if employee == "cos":
        cfg = config.load()
        return Path(cfg["_root"]) / cfg["chief_of_staff"]["memory_path"]
    for e in config.load_employees():
        if e["name"] == employee:
            return Path(e["path"]) / "MEMORY.md"
    raise ValueError(f"unknown employee: {employee}")


def _ensure_rollover(memory_path: Path) -> None:
    """If MEMORY.md exceeds threshold, archive to memory/YYYY-MM-DD.md and reset."""
    if not memory_path.exists():
        return
    content = memory_path.read_text()
    if len(content) < ROLLOVER_THRESHOLD_CHARS:
        return
    archive_dir = memory_path.parent / "memory"
    archive_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%d")
    archive_path = archive_dir / f"{stamp}.md"
    if archive_path.exists():
        # already rolled today; append a separator
        with archive_path.open("a") as f:
            f.write(f"\n\n---\n# Continued from {memory_path.name}\n\n")
            f.write(content)
    else:
        archive_path.write_text(
            f"# Memory archive — {stamp}\n\nRolled over from {memory_path.name}.\n\n" + content
        )
    # Reset memory file with header only
    header = content.split("\n\n", 1)[0]   # keep the title section
    memory_path.write_text(header + "\n\n_Recent entries; older archived to memory/_\n")


def add(employee: str, content: str, *, layer: Layer = "episodic",
        tag: str | None = None) -> int:
    """Append a tagged entry to the employee's MEMORY.md. Returns chat.db row id."""
    path = _memory_path(employee)
    path.parent.mkdir(parents=True, exist_ok=True)
    _ensure_rollover(path)
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    label = f"[{layer}]"
    if tag:
        label += f" [{tag}]"
    body = f"\n## {stamp}\n\n{label} {content.strip()}\n"
    with path.open("a") as f:
        f.write(body)
    return state.append(
        sender=employee,
        kind="memory",
        content=f"{label} {content[:200]}",
    )


def tail(employee: str, *, n: int = 30) -> str:
    """Return the last n lines of the employee's MEMORY.md."""
    path = _memory_path(employee)
    if not path.exists():
        return ""
    lines = path.read_text().splitlines()
    return "\n".join(lines[-n:])


def search(employee: str | None, query: str, *, limit: int = 20) -> list[dict]:
    """Search across chat.db `kind='memory'` rows and (FTS5) MEMORY content.

    If `employee` is provided, restrict to that employee's writes.
    Returns rows with id, ts, sender, content.
    """
    rows = state.search(query, limit=limit * 2)
    out = []
    for r in rows:
        if employee and r.get("sender") != employee:
            continue
        out.append(r)
        if len(out) >= limit:
            break
    return out


def capacity(employee: str) -> dict:
    """Return current size + threshold + rollover state for the employee."""
    path = _memory_path(employee)
    size = path.stat().st_size if path.exists() else 0
    return {
        "employee": employee,
        "path": str(path),
        "size_chars": size,
        "rollover_threshold": ROLLOVER_THRESHOLD_CHARS,
        "hard_cap": MEMORY_CAPACITY_CHARS,
        "needs_rollover": size >= ROLLOVER_THRESHOLD_CHARS,
    }
