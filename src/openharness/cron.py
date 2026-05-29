"""First-class scheduled jobs.

Hermes and OpenClaw both treat cron jobs as named, persisted, listable entities.
OpenHarness stores them in config/cron-jobs.json and checks each tick of the
daemon whether any are due.

A job is: {id, schedule, target, args, last_run_ts, enabled}
where:
  schedule is a natural-language interval Bookie can also reason about:
    "every 30m", "every 1h", "daily 06:00", "weekly Sunday 18:00", "monthly day 1"
  target is "harness:<command>" or "employee:<name>:<function>"
  args is a dict passed to the target
"""
from __future__ import annotations
import json
import re
import time
import uuid
from datetime import datetime, timedelta, time as dt_time
from pathlib import Path
from typing import Optional

from openharness import config, state


def _jobs_path() -> Path:
    return Path(config.load()["_root"]) / "config" / "cron-jobs.json"


def _load() -> list[dict]:
    p = _jobs_path()
    if not p.exists():
        return []
    with p.open() as f:
        return json.load(f).get("jobs", [])


def _save(jobs: list[dict]) -> None:
    p = _jobs_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"jobs": jobs}, indent=2))


def add(*, schedule: str, target: str, args: dict | None = None,
        job_id: str | None = None) -> dict:
    """Register a new cron job. Returns the stored record."""
    jobs = _load()
    job = {
        "id": job_id or uuid.uuid4().hex[:12],
        "schedule": schedule,
        "target": target,
        "args": args or {},
        "last_run_ts": 0.0,
        "enabled": True,
        "created_at": time.time(),
    }
    jobs.append(job)
    _save(jobs)
    state.append(sender="cos", kind="event",
                 content=f"cron added: {job['id']} schedule={schedule!r} target={target!r}")
    return job


def list_jobs() -> list[dict]:
    return _load()


def remove(job_id: str) -> bool:
    jobs = _load()
    before = len(jobs)
    jobs = [j for j in jobs if j["id"] != job_id]
    if len(jobs) == before:
        return False
    _save(jobs)
    state.append(sender="cos", kind="event", content=f"cron removed: {job_id}")
    return True


def enable(job_id: str, enabled: bool = True) -> bool:
    jobs = _load()
    found = False
    for j in jobs:
        if j["id"] == job_id:
            j["enabled"] = bool(enabled)
            found = True
    if found:
        _save(jobs)
    return found


def _is_due(job: dict, now_ts: float) -> bool:
    """Cheap heuristics. Errs on the side of running."""
    if not job.get("enabled", True):
        return False
    last = job.get("last_run_ts", 0.0)
    elapsed = now_ts - last
    sched = job.get("schedule", "").lower().strip()

    # every <N><unit>
    m = re.match(r"every\s+(\d+)\s*([smhd])", sched)
    if m:
        n = int(m.group(1))
        unit = m.group(2)
        seconds = {"s": n, "m": n * 60, "h": n * 3600, "d": n * 86400}[unit]
        return elapsed >= seconds

    now = datetime.fromtimestamp(now_ts)
    # daily HH:MM
    m = re.match(r"daily\s+(\d{1,2}):(\d{2})", sched)
    if m:
        target = dt_time(int(m.group(1)), int(m.group(2)))
        last_dt = datetime.fromtimestamp(last) if last else None
        if now.time() >= target and (last_dt is None or last_dt.date() < now.date()):
            return True
        return False

    # weekly <weekday> HH:MM
    m = re.match(r"weekly\s+(\w+)\s+(\d{1,2}):(\d{2})", sched)
    if m:
        weekdays = ["monday", "tuesday", "wednesday", "thursday",
                    "friday", "saturday", "sunday"]
        day_name = m.group(1).lower()
        if day_name not in weekdays:
            return False
        target_wday = weekdays.index(day_name)
        target_time = dt_time(int(m.group(2)), int(m.group(3)))
        last_dt = datetime.fromtimestamp(last) if last else None
        if now.weekday() == target_wday and now.time() >= target_time and (
                last_dt is None or (now - last_dt) >= timedelta(days=6)):
            return True
        return False

    # monthly day N
    m = re.match(r"monthly\s+day\s+(\d{1,2})", sched)
    if m:
        target_day = int(m.group(1))
        last_dt = datetime.fromtimestamp(last) if last else None
        if now.day == target_day and (last_dt is None or last_dt.month != now.month
                                       or last_dt.year != now.year):
            return True
        return False

    return False


def due_now() -> list[dict]:
    """Return jobs whose schedule says they should run now."""
    now_ts = time.time()
    return [j for j in _load() if _is_due(j, now_ts)]


def mark_ran(job_id: str) -> None:
    jobs = _load()
    for j in jobs:
        if j["id"] == job_id:
            j["last_run_ts"] = time.time()
    _save(jobs)


def run_job(job: dict) -> dict:
    """Execute a job. Returns {ok, output, error}."""
    target = job.get("target", "")
    args = job.get("args", {}) or {}
    try:
        if target.startswith("harness:reflect"):
            # target format: "harness:reflect:<employee>"
            parts = target.split(":")
            employee = args.get("employee") or (parts[2] if len(parts) > 2 else None)
            if not employee:
                return {"ok": False, "error": "reflect job missing employee"}
            from openharness import reflection
            since_hours = int(args.get("since_hours", 168))
            result = reflection.reflect(employee, since_hours=since_hours)
            return {"ok": True, "output": result}
        if target.startswith("employee:"):
            # target format: "employee:<name>:<function_name>"
            parts = target.split(":")
            if len(parts) < 3:
                return {"ok": False, "error": f"malformed employee target: {target!r}"}
            emp_name, fn_name = parts[1], parts[2]
            import importlib
            for e in config.load_employees():
                if e["name"] == emp_name:
                    pm = e.get("python_module")
                    if pm:
                        import sys
                        if pm not in sys.path:
                            sys.path.insert(0, pm)
                    mod = importlib.import_module(e["python_package"])
                    fn = getattr(mod, fn_name, None)
                    if fn is None:
                        return {"ok": False, "error": f"function {fn_name} not in {emp_name}"}
                    out = fn(**args)
                    return {"ok": True, "output": out}
            return {"ok": False, "error": f"unknown employee: {emp_name}"}
        return {"ok": False, "error": f"unknown target: {target}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}
