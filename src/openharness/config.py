"""Config loading. Single source of truth for paths and runtime knobs."""
from __future__ import annotations
import json
import os
from pathlib import Path


def workspace_root() -> Path:
    env = os.environ.get("OPENHARNESS_ROOT")
    if env:
        return Path(env).resolve()
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "config" / "openharness.json").exists():
            return parent
    raise FileNotFoundError(
        "Cannot locate OpenHarness workspace root. Set OPENHARNESS_ROOT or run from inside the repo."
    )


def load() -> dict:
    root = workspace_root()
    cfg_path = root / "config" / "openharness.json"
    with cfg_path.open() as f:
        cfg = json.load(f)
    cfg["_root"] = str(root)
    return cfg


def employees_registry_path() -> Path:
    return workspace_root() / "config" / "employees.json"


def external_sources_path() -> Path:
    return workspace_root() / "config" / "external-sources.json"


def load_employees() -> list:
    path = employees_registry_path()
    with path.open() as f:
        return json.load(f).get("employees", [])


def save_employees(employees: list) -> None:
    path = employees_registry_path()
    with path.open() as f:
        data = json.load(f)
    data["employees"] = employees
    with path.open("w") as f:
        json.dump(data, f, indent=2)


def load_external_sources() -> dict:
    with external_sources_path().open() as f:
        return json.load(f)
