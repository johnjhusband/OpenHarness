"""Heartbeat tick — check inboxes since last cursor, log to chat.db.

In v1, the tick records what's new. Chief of Staff (the human-in-the-loop —
i.e., Claude Code reading the briefing) decides how to handle each item.
Phase 2 will add automated handling for items inside the boundaries table.
"""
from __future__ import annotations
import hashlib
from pathlib import Path

from openharness import config, inboxes, state


def _file_signature(path: Path) -> str:
    """Quick signature: size + mtime + content-hash of first 4KB."""
    stat = path.stat()
    head = path.read_bytes()[:4096]
    h = hashlib.sha256(head).hexdigest()[:16]
    return f"{stat.st_size}:{stat.st_mtime:.0f}:{h}"


def run() -> dict:
    """One tick. Returns {employee: 'unchanged' | 'changed', 'log_id': N}."""
    cursor = state.read_cursor()
    inbox_state = cursor.get("inboxes", {})

    results = {}
    changes = []
    for name, info in inboxes.list_inboxes().items():
        path = Path(info["path"])
        sig = _file_signature(path)
        prev = inbox_state.get(name)
        if prev != sig:
            results[name] = "changed"
            changes.append(name)
            inbox_state[name] = sig
        else:
            results[name] = "unchanged"

    log_id = state.append(
        sender="cos",
        kind="tick",
        content=f"Tick result: {len(changes)} changed inbox(es): {', '.join(changes) if changes else 'none'}",
    )

    cursor["inboxes"] = inbox_state
    cursor["last_tick_log_id"] = log_id
    state.write_cursor(cursor)

    return {"results": results, "changes": changes, "log_id": log_id}
