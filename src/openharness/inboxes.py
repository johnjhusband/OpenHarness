"""Inbox / outbox / escalations file operations."""
from __future__ import annotations
from pathlib import Path

from openharness import config


def inbox_dir() -> Path:
    return Path(config.load()["_root"]) / "inbox"


def outbox_dir() -> Path:
    return Path(config.load()["_root"]) / "outbox"


def escalations_path() -> Path:
    cfg = config.load()
    return Path(cfg["_root"]) / cfg["chief_of_staff"]["escalations_path"]


def list_inboxes() -> dict:
    """Return {employee_name: {path, size_bytes, last_modified}}."""
    d = inbox_dir()
    d.mkdir(parents=True, exist_ok=True)
    out = {}
    for f in d.glob("*.md"):
        name = f.stem
        stat = f.stat()
        out[name] = {
            "path": str(f),
            "size_bytes": stat.st_size,
            "last_modified": stat.st_mtime,
        }
    return out


def read_inbox(employee: str) -> str:
    p = inbox_dir() / f"{employee}.md"
    if not p.exists():
        return ""
    return p.read_text()


def write_to_outbox(employee: str, content: str) -> None:
    """Append a message to the outbox for an employee."""
    d = outbox_dir()
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{employee}.md"
    import time
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    header = f"\n## {stamp}\n"
    if not p.exists():
        p.write_text(f"# outbox — {employee}\n\nMessages from Chief of Staff to {employee}.\n")
    with p.open("a") as f:
        f.write(header)
        f.write(content.rstrip() + "\n")


def append_escalation(summary: str, body: str = "", recommendation: str = "") -> None:
    """Append an escalation to escalations.md."""
    p = escalations_path()
    import time
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    entry = f"\n## {stamp} — {summary}\n\n"
    if body:
        entry += body.rstrip() + "\n\n"
    if recommendation:
        entry += f"**Recommendation:** {recommendation}\n\n"
    entry += "---\n"
    with p.open("a") as f:
        f.write(entry)
