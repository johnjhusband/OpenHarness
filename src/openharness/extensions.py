"""External-source discovery. PRD §13.

Reads config/external-sources.json and globs each declared path for
skills, MCP definitions, and SOUL templates. Returns a unified index.

OpenHarness does NOT execute external skills or run external MCPs.
It documents what's available so AI employees and Chief of Staff can
reference them. Execution requires implementing matching dispatch
(deferred to Phase 2).
"""
from __future__ import annotations
from pathlib import Path

import os
from openharness import config


def _expand(path: str) -> str:
    """Resolve ${OPENHARNESS_ROOT} and env vars in a configured path string."""
    # Set OPENHARNESS_ROOT to the workspace root for substitution if not in env
    if "OPENHARNESS_ROOT" not in os.environ:
        os.environ["OPENHARNESS_ROOT"] = config.workspace_root().as_posix()
    return os.path.expandvars(os.path.expanduser(path))


def discover_skills() -> list[dict]:
    """Find <dir>/<skill>/SKILL.md files (two levels deep)."""
    out = []
    sources = config.load_external_sources().get("skills", [])
    for src in sources:
        root = Path(_expand(src))
        if not root.is_dir():
            continue
        for skill_md in root.glob("*/SKILL.md"):
            out.append({
                "name": skill_md.parent.name,
                "source": str(root),
                "path": str(skill_md),
            })
    return out


def discover_mcp_definitions() -> list[dict]:
    """Find *.mcp.json and mcp-servers/*.json files."""
    out = []
    sources = config.load_external_sources().get("mcp_definitions", [])
    for src in sources:
        root = Path(_expand(src))
        if not root.is_dir():
            continue
        for f in list(root.glob("*.mcp.json")) + list(root.glob("mcp-servers/*.json")):
            out.append({
                "name": f.stem,
                "source": str(root),
                "path": str(f),
            })
    return out


def discover_soul_templates() -> list[dict]:
    """Find <dir>/<name>/SOUL.md template files."""
    out = []
    sources = config.load_external_sources().get("soul_templates", [])
    for src in sources:
        root = Path(_expand(src))
        if not root.is_dir():
            continue
        for soul_md in root.glob("*/SOUL.md"):
            out.append({
                "name": soul_md.parent.name,
                "source": str(root),
                "path": str(soul_md),
            })
    return out


def list_vendored() -> list[dict]:
    """Return the declared vendored-code manifest."""
    return config.load_external_sources().get("vendored_code", [])


def verify() -> dict:
    """Check that every configured path exists and is readable.

    Returns {"ok": bool, "missing": [path, ...], "skills": int, "mcps": int, "templates": int}
    """
    es = config.load_external_sources()
    missing = []
    for category in ("skills", "mcp_definitions", "soul_templates"):
        for src in es.get(category, []):
            if not Path(_expand(src)).is_dir():
                missing.append(src)
    return {
        "ok": not missing,
        "missing": missing,
        "skills": len(discover_skills()),
        "mcps": len(discover_mcp_definitions()),
        "templates": len(discover_soul_templates()),
        "vendored": len(list_vendored()),
    }
