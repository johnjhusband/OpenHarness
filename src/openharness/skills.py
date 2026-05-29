"""Skill dispatch.

OpenHarness discovers SKILL.md files via the extensions mechanism. This module
makes them executable: parses YAML frontmatter, finds the entry function
specified in `metadata.<runtime>.entry`, and calls it with provided arguments.

A SKILL.md entry can look like:
    metadata:
      bookie:
        entry: "bookie.categorizer.categorize"
        requires:
          modules: ["bookie.categorizer"]

`skills.run("categorize-transaction", tx=...)` would import bookie.categorizer,
look up `categorize`, and call it.
"""
from __future__ import annotations
import importlib
import re
import sys
from pathlib import Path
from typing import Any

from openharness import extensions, state


class SkillError(Exception):
    pass


def _parse_frontmatter(skill_md: Path) -> dict:
    """Parse YAML frontmatter from a SKILL.md file. Minimal parser, no PyYAML required."""
    content = skill_md.read_text()
    m = re.match(r"^---\n(.*?)\n---\n", content, re.DOTALL)
    if not m:
        return {}
    fm_text = m.group(1)
    # Minimal YAML: handle key: value and nested two-space indent
    result: dict = {}
    stack = [(0, result)]
    for line in fm_text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        # Strip list markers (skip — we don't need them for entries)
        indent = len(line) - len(line.lstrip())
        # Pop stack only if our indent is shallower than the current frame
        while stack and stack[-1][0] > indent and len(stack) > 1:
            stack.pop()
        stripped = line.strip()
        if ":" in stripped:
            key, _, value = stripped.partition(":")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if value:
                stack[-1][1][key] = value
            else:
                new_dict: dict = {}
                stack[-1][1][key] = new_dict
                stack.append((indent + 2, new_dict))
    return result


def list_skills() -> list[dict]:
    """List all discovered skills with parsed frontmatter."""
    discovered = extensions.discover_skills()
    out = []
    for s in discovered:
        try:
            fm = _parse_frontmatter(Path(s["path"]))
        except Exception as e:
            fm = {"_parse_error": str(e)}
        out.append({**s, "frontmatter": fm})
    return out


def get_skill(name: str) -> dict | None:
    """Look up a skill by name. Returns the same dict shape as list_skills entries."""
    for s in list_skills():
        if s["name"] == name:
            return s
    return None


def _resolve_entry(entry: str):
    """Import `entry` like 'module.submodule.fn' and return the callable."""
    parts = entry.rsplit(".", 1)
    if len(parts) != 2:
        raise SkillError(f"entry must be module.fn, got {entry!r}")
    mod_name, fn_name = parts
    # Try to ensure the module's source dir is on sys.path via the employee registry
    from openharness import config
    for e in config.load_employees():
        pm = e.get("python_module")
        if pm and pm not in sys.path:
            sys.path.insert(0, pm)
    mod = importlib.import_module(mod_name)
    fn = getattr(mod, fn_name, None)
    if fn is None:
        raise SkillError(f"function {fn_name!r} not in {mod_name!r}")
    return fn


def run(name: str, *, runtime_key: str = "bookie", **kwargs) -> Any:
    """Execute a skill by name. kwargs are passed to the entry function."""
    skill = get_skill(name)
    if skill is None:
        raise SkillError(f"unknown skill: {name!r}")
    fm = skill.get("frontmatter") or {}
    meta = fm.get("metadata") or {}
    rt = meta.get(runtime_key) or {}
    entry = rt.get("entry")
    if not entry:
        raise SkillError(f"skill {name!r} has no metadata.{runtime_key}.entry")
    fn = _resolve_entry(entry)
    state.append(
        sender=runtime_key, kind="event",
        content=f"skill run: {name} entry={entry}",
    )
    return fn(**kwargs)
