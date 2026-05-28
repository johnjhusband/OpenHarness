"""Employee management. Install / list / sync from template."""
from __future__ import annotations
import shutil
import time
from pathlib import Path

from openharness import config


def template_dir() -> Path:
    return Path(config.load()["_root"]) / "employees" / "_template"


def employee_dir(name: str) -> Path:
    return Path(config.load()["_root"]) / "employees" / name


def list_employees() -> list:
    return config.load_employees()


def install(name: str, *, from_template: Path | None = None) -> Path:
    """Scaffold a new employee from the default template (or a custom source).

    Creates employees/<name>/ with all template files, replaces [NAME] placeholders,
    creates inbox/<name>.md and outbox/<name>.md, registers in employees.json.
    """
    target = employee_dir(name)
    if target.exists():
        raise FileExistsError(f"Employee already exists: {target}")
    src = from_template if from_template else template_dir()
    shutil.copytree(src, target)
    # Replace [NAME] placeholders in template files (best-effort, only in .md)
    for md in target.rglob("*.md"):
        content = md.read_text()
        content = content.replace("[NAME]", name)
        md.write_text(content)
    # Create inbox/outbox files
    root = Path(config.load()["_root"])
    (root / "inbox").mkdir(parents=True, exist_ok=True)
    (root / "outbox").mkdir(parents=True, exist_ok=True)
    inbox_path = root / "inbox" / f"{name}.md"
    outbox_path = root / "outbox" / f"{name}.md"
    if not inbox_path.exists():
        inbox_path.write_text(f"# inbox — {name}\n\nMessages from {name} to Chief of Staff.\n")
    if not outbox_path.exists():
        outbox_path.write_text(f"# outbox — {name}\n\nMessages from Chief of Staff to {name}.\n")
    # Symlink messages-to-cos.md → ../../inbox/<name>.md (best-effort; falls back to file copy)
    mtc = target / "messages-to-cos.md"
    if mtc.exists():
        mtc.unlink()
    try:
        rel = Path("..") / ".." / "inbox" / f"{name}.md"
        mtc.symlink_to(rel)
    except OSError:
        mtc.write_text(f"# messages-to-cos — {name}\n\nAlias for ../../inbox/{name}.md (symlink unavailable).\n")
    # Register
    employees = config.load_employees()
    if not any(e.get("name") == name for e in employees):
        employees.append({
            "name": name,
            "path": str(target),
            "installed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        })
        config.save_employees(employees)
    return target
