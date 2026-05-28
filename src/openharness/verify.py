"""Workspace integrity check."""
from __future__ import annotations
from pathlib import Path

from openharness import config, extensions


REQUIRED_WORKSPACE_FILES = [
    "soul_path", "user_path", "memory_path", "agents_path",
    "heartbeat_path", "style_path", "tools_path",
    "boundaries_path", "escalations_path",
]


def run() -> dict:
    """Run integrity checks. Returns a dict with ok/issues."""
    cfg = config.load()
    root = Path(cfg["_root"])
    cos = cfg["chief_of_staff"]

    issues = []

    # 1. Chief of Staff workspace files all exist
    for key in REQUIRED_WORKSPACE_FILES:
        rel = cos.get(key)
        if not rel:
            issues.append(f"Config missing chief_of_staff.{key}")
            continue
        p = root / rel
        if not p.exists():
            issues.append(f"Missing workspace file: {rel}")
        elif p.stat().st_size == 0:
            issues.append(f"Empty workspace file: {rel}")

    # 2. inbox/outbox dirs exist
    for d in ("inbox", "outbox"):
        if not (root / d).is_dir():
            issues.append(f"Missing directory: {d}/")

    # 3. config files exist
    for f in ("config/openharness.json", "config/employees.json",
              "config/auth-profiles.json", "config/external-sources.json"):
        if not (root / f).exists():
            issues.append(f"Missing config file: {f}")

    # 4. Employee template exists
    template = root / "employees" / "_template"
    if not template.is_dir():
        issues.append("Missing employee template: employees/_template/")

    # 5. Each registered employee has its folder
    for e in config.load_employees():
        ep = Path(e.get("path", ""))
        if not ep.exists():
            issues.append(f"Registered employee missing on disk: {e['name']} (expected {ep})")

    # 6. Each inbox file has a matching outbox file (orphan detection)
    inbox_dir = root / "inbox"
    outbox_dir = root / "outbox"
    if inbox_dir.is_dir() and outbox_dir.is_dir():
        inbox_names = {p.stem for p in inbox_dir.glob("*.md")}
        outbox_names = {p.stem for p in outbox_dir.glob("*.md")}
        orphan_inboxes = inbox_names - outbox_names
        for o in orphan_inboxes:
            issues.append(f"Orphan inbox (no matching outbox): inbox/{o}.md")

    # 7. Extensions verify
    ext = extensions.verify()
    if not ext["ok"]:
        for m in ext["missing"]:
            issues.append(f"Configured external source missing on disk: {m}")

    return {
        "ok": not issues,
        "issues": issues,
        "checked_workspace_files": REQUIRED_WORKSPACE_FILES,
        "employees_registered": len(config.load_employees()),
        "extensions": ext,
    }
