"""Iterative goal verification.

Every active objective in OpenHarness has a checklist of automated criteria.
After every commit, Chief of Staff runs `harness goal verify`. If anything is
red, the immediate next task is to fix it. Loop until all green.

This module exists because memory rules alone weren't enough to make me
finish work without prompting. The structural fix is an automated check
that runs and tells me unambiguously: you are not done.

Layout:
  workspace/ACTIVE_OBJECTIVE.md     — human-readable description of the goal
  config/objective-criteria.json    — machine-checkable criteria
  workspace/objective-history/      — completed objectives archived here
"""
from __future__ import annotations
import importlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openharness import config


@dataclass
class CriterionResult:
    id: str
    description: str
    status: str  # "green" | "red"
    expected: str
    actual: str
    error: str = ""


def _objective_path() -> Path:
    return Path(config.load()["_root"]) / "workspace" / "ACTIVE_OBJECTIVE.md"


def _criteria_path() -> Path:
    return Path(config.load()["_root"]) / "config" / "objective-criteria.json"


def _history_dir() -> Path:
    d = Path(config.load()["_root"]) / "workspace" / "objective-history"
    d.mkdir(parents=True, exist_ok=True)
    return d


def read_objective() -> str:
    p = _objective_path()
    if not p.exists():
        return "(no active objective)"
    return p.read_text()


def write_objective(text: str) -> None:
    p = _objective_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def read_criteria() -> list[dict]:
    p = _criteria_path()
    if not p.exists():
        return []
    return json.loads(p.read_text()).get("criteria", [])


def write_criteria(criteria: list[dict]) -> None:
    p = _criteria_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"criteria": criteria}, indent=2))


# ---- criterion checkers -----------------------------------------------------


def _expand_path(raw: str) -> Path:
    """Resolve ${OPENHARNESS_ROOT} / ${BOOKIE_ROOT} / env vars / ~ in a path."""
    import os
    if "OPENHARNESS_ROOT" not in os.environ:
        os.environ["OPENHARNESS_ROOT"] = config.workspace_root().as_posix()
    if "BOOKIE_ROOT" not in os.environ:
        # Best-effort: prefer the employee's registered python_module's parent
        for e in config.load_employees():
            if e.get("name") == "bookie" and e.get("python_module"):
                os.environ["BOOKIE_ROOT"] = str(Path(e["python_module"]).parent)
                break
    return Path(os.path.expandvars(os.path.expanduser(raw)))


def _check_file_exists(spec: dict) -> tuple[bool, str, str]:
    path = _expand_path(spec["path"])
    return path.exists(), "file exists", "exists" if path.exists() else "missing"


def _check_not_file_exists(spec: dict) -> tuple[bool, str, str]:
    path = _expand_path(spec["path"])
    return not path.exists(), "file absent", "absent" if not path.exists() else "still exists"


def _check_grep_in_file(spec: dict) -> tuple[bool, str, str]:
    path = _expand_path(spec["path"])
    needle = spec["needle"]
    if not path.exists():
        return False, f"file contains {needle!r}", "file missing"
    found = needle in path.read_text()
    return found, f"file contains {needle!r}", "found" if found else "not found"


def _check_not_grep_in_file(spec: dict) -> tuple[bool, str, str]:
    path = _expand_path(spec["path"])
    needle = spec["needle"]
    if not path.exists():
        return True, f"file does not contain {needle!r}", "file missing (OK)"
    found = needle in path.read_text()
    return (not found), f"file does not contain {needle!r}", "not found" if not found else "still present"


def _check_command_succeeds(spec: dict) -> tuple[bool, str, str]:
    import os
    _expand_path("dummy")  # ensure env vars are populated
    cmd = os.path.expandvars(spec["command"])
    cwd = spec.get("cwd")
    if cwd:
        cwd = str(_expand_path(cwd))
    timeout = int(spec.get("timeout_seconds", 60))
    try:
        result = subprocess.run(
            cmd, shell=True, cwd=cwd,
            capture_output=True, text=True, timeout=timeout,
        )
        ok = result.returncode == 0
        tail = (result.stdout or result.stderr or "")[-200:].strip()
        return ok, f"`{cmd}` exits 0", f"rc={result.returncode}; {tail[:120]}"
    except subprocess.TimeoutExpired:
        return False, f"`{cmd}` exits 0", f"timed out after {timeout}s"
    except Exception as e:
        return False, f"`{cmd}` exits 0", f"error: {e}"


def _check_python_predicate(spec: dict) -> tuple[bool, str, str]:
    """spec['callable'] is 'module.path:function_name'; called with no args, must return True/False."""
    target = spec["callable"]
    if ":" not in target:
        return False, target, "callable spec must be 'module.path:fn'"
    mod_name, fn_name = target.split(":", 1)
    extra_paths = spec.get("sys_path", [])
    for p in extra_paths:
        p = str(_expand_path(p))
        if p not in sys.path:
            sys.path.insert(0, p)
    try:
        mod = importlib.import_module(mod_name)
        fn = getattr(mod, fn_name, None)
        if fn is None:
            return False, target, f"{fn_name} not in {mod_name}"
        result = fn()
        return bool(result), target + " returns truthy", repr(result)[:120]
    except Exception as e:
        return False, target, f"error: {e}"


CHECKERS = {
    "file_exists": _check_file_exists,
    "not_file_exists": _check_not_file_exists,
    "grep_in_file": _check_grep_in_file,
    "not_grep_in_file": _check_not_grep_in_file,
    "command_succeeds": _check_command_succeeds,
    "python_predicate": _check_python_predicate,
}


def verify() -> list[CriterionResult]:
    """Run every criterion. Returns list of CriterionResult."""
    out = []
    for c in read_criteria():
        cid = c.get("id", "?")
        desc = c.get("description", "")
        check_type = c.get("type")
        checker = CHECKERS.get(check_type)
        if checker is None:
            out.append(CriterionResult(
                id=cid, description=desc, status="red",
                expected=f"check type {check_type!r}",
                actual=f"unknown checker type {check_type!r}",
            ))
            continue
        try:
            ok, expected, actual = checker(c)
            out.append(CriterionResult(
                id=cid, description=desc,
                status="green" if ok else "red",
                expected=expected, actual=actual,
            ))
        except Exception as e:
            out.append(CriterionResult(
                id=cid, description=desc, status="red",
                expected="checker did not raise", actual=f"raised: {e}",
            ))
    return out


def next_red(results: list[CriterionResult] | None = None) -> CriterionResult | None:
    """Return the first red criterion, or None if all green."""
    results = results or verify()
    for r in results:
        if r.status == "red":
            return r
    return None


def is_all_green(results: list[CriterionResult] | None = None) -> bool:
    return next_red(results) is None


def archive_objective() -> Path | None:
    """Archive the current ACTIVE_OBJECTIVE.md + criteria into objective-history/.
    Called when John says we're done with the current objective.
    """
    import time
    obj_path = _objective_path()
    crit_path = _criteria_path()
    if not obj_path.exists():
        return None
    stamp = time.strftime("%Y%m%d-%H%M%S")
    archive = _history_dir() / f"{stamp}.md"
    text = obj_path.read_text()
    archive.write_text(text + "\n\n---\n## Criteria at archive time\n\n```json\n"
                       + (crit_path.read_text() if crit_path.exists() else "{}")
                       + "\n```\n")
    obj_path.write_text("# (no active objective)\n\nSet a new objective with "
                        "`harness goal set <description>`.\n")
    write_criteria([])
    return archive
