"""Restart protocol — produce the Chief of Staff briefing."""
from __future__ import annotations
import subprocess
from pathlib import Path

from openharness import config, inboxes, state


def _safe_read(path: Path) -> str:
    if not path.exists():
        return f"(missing: {path})"
    try:
        return path.read_text()
    except Exception as e:
        return f"(unreadable: {e})"


def _truncate(text: str, max_chars: int = 800) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n... [truncated, {len(text) - max_chars} chars omitted]"


def _git_log_recent(repo: Path, n: int = 10) -> str:
    if not (repo / ".git").exists():
        return ""
    try:
        out = subprocess.check_output(
            ["git", "-C", str(repo), "log", "--oneline", f"-{n}"],
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
        return out.decode().strip()
    except Exception:
        return ""


def briefing() -> str:
    """Build the Chief of Staff session-start briefing as Markdown."""
    cfg = config.load()
    root = Path(cfg["_root"])
    cos = cfg["chief_of_staff"]

    lines = []
    lines.append("# Chief of Staff briefing\n")

    # 0. Active objective + automated criteria status — read FIRST
    try:
        from openharness import goal as goal_mod
        obj_text = goal_mod.read_objective()
        lines.append("## Active objective\n")
        lines.append(obj_text.strip())
        lines.append("")
        results = goal_mod.verify()
        if results:
            green = sum(1 for r in results if r.status == "green")
            lines.append(f"**Criteria status: {green}/{len(results)} green**\n")
            for r in results:
                mark = "✓" if r.status == "green" else "✗"
                lines.append(f"- {mark} `{r.id}`: {r.description}")
                if r.status == "red":
                    lines.append(f"  - expected: {r.expected}")
                    lines.append(f"  - actual: {r.actual}")
            lines.append("")
            if green < len(results):
                first_red = next((r for r in results if r.status == "red"), None)
                lines.append(f"**Next action:** make `{first_red.id}` green.\n")
        else:
            lines.append("_(no objective criteria configured — set with `harness goal set`)_\n")
    except Exception as e:
        lines.append(f"_(goal status unavailable: {e})_\n")

    # 1. Recent escalations
    esc = _safe_read(root / cos["escalations_path"])
    if "_No active escalations._" in esc or esc.strip().endswith("_No active escalations._"):
        lines.append("## Escalations\n\n_None pending._\n")
    else:
        lines.append("## Escalations\n")
        lines.append(_truncate(esc, 1500))
        lines.append("")

    # 2. Inboxes
    inbox_list = inboxes.list_inboxes()
    if inbox_list:
        lines.append("## Inboxes\n")
        for name, info in inbox_list.items():
            lines.append(f"- **{name}** — {info['size_bytes']} bytes, modified {info['last_modified']:.0f}")
        lines.append("")
    else:
        lines.append("## Inboxes\n\n_No inboxes configured._\n")

    # 3. HEARTBEAT
    hb = _safe_read(root / cos["heartbeat_path"])
    lines.append("## HEARTBEAT (current schedule)\n")
    lines.append(_truncate(hb, 600))
    lines.append("")

    # 4. Recent MEMORY
    mem = _safe_read(root / cos["memory_path"])
    lines.append("## MEMORY (recent entries)\n")
    # Take last ~30 lines
    tail_mem = "\n".join(mem.splitlines()[-30:])
    lines.append(tail_mem)
    lines.append("")

    # 5. Recent chat.db rows
    recent = state.tail(limit=10)
    if recent:
        lines.append("## Recent chat.db entries (last 10)\n")
        for r in recent:
            lines.append(f"- #{r['id']} `{r['kind']}` {r['sender']}→{r['recipient'] or '*'}: "
                         f"{r['content'][:80]}{'...' if len(r['content']) > 80 else ''}")
        lines.append("")

    # 6. Employee registry
    employees = config.load_employees()
    if employees:
        lines.append("## Employees registered\n")
        for e in employees:
            lines.append(f"- **{e['name']}** — {e.get('path', '?')} (installed {e.get('installed_at', '?')})")
        lines.append("")
    else:
        lines.append("## Employees registered\n\n_None._\n")

    # 7. Active-repo git status
    candidate_repos = [
        Path("/home/john/repos/OpenHarness"),
        Path("/home/john/repos/Bookie"),
        Path("/home/john/repos/CTO-artifacts"),
    ]
    repo_lines = []
    for repo in candidate_repos:
        if not repo.exists():
            continue
        gl = _git_log_recent(repo, 3)
        if gl:
            repo_lines.append(f"### {repo.name}\n```\n{gl}\n```")
    if repo_lines:
        lines.append("## Active repos — recent commits\n")
        lines.extend(repo_lines)
        lines.append("")

    lines.append("---\n_Briefing complete. Read SOUL.md and AGENTS.md for the full identity + procedural manual._")
    return "\n".join(lines)


def run() -> str:
    """Run the restart protocol and return the briefing as text."""
    out = briefing()
    state.append(
        sender="cos",
        content="Restart protocol executed.",
        kind="event",
    )
    return out
