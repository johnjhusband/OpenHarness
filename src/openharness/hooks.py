"""Hook registry for OpenHarness.

Hermes and OpenClaw both expose hooks: before_prompt_build, before_tool_call,
after_tool_call. Plugins use these to log, modify, or reject calls.

OpenHarness uses a small registry. Modules call `dispatch(event, payload)`
to fire all registered handlers. Handlers can mutate the payload in-place.
Returning False from a `before_*` handler aborts the call.
"""
from __future__ import annotations
from typing import Callable
from openharness import state


_HOOKS: dict[str, list[Callable]] = {}


def register(event: str, handler: Callable) -> None:
    """Register a handler for a named event.

    Standard events:
      before_prompt_build(payload) — payload has system_prompt, user_prompt
      after_prompt_build(payload)
      before_tool_call(payload)    — payload has tool_name, args; return False to block
      after_tool_call(payload)     — payload has tool_name, args, result, duration_s
      before_state_append(payload) — payload has sender, kind, content
      after_employee_tick(payload) — payload has employee, tick_result
    """
    _HOOKS.setdefault(event, []).append(handler)


def unregister(event: str, handler: Callable) -> None:
    if event in _HOOKS and handler in _HOOKS[event]:
        _HOOKS[event].remove(handler)


def dispatch(event: str, payload: dict) -> bool:
    """Fire all handlers for `event`. Returns False if any `before_*` handler returns False."""
    for h in _HOOKS.get(event, []):
        try:
            result = h(payload)
            if event.startswith("before_") and result is False:
                state.append(
                    sender="cos", kind="event",
                    content=f"hook blocked {event}: handler={h.__name__}",
                )
                return False
        except Exception as e:
            state.append(
                sender="cos", kind="event",
                content=f"hook handler raised on {event}: {h.__name__}: {e}",
            )
    return True


def registered(event: str | None = None) -> dict[str, list[str]]:
    """List registered handler names per event."""
    if event:
        return {event: [h.__name__ for h in _HOOKS.get(event, [])]}
    return {evt: [h.__name__ for h in handlers] for evt, handlers in _HOOKS.items()}
