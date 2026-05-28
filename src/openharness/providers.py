"""LLM provider abstraction + circuit breaker. PRD §20.

v1 ships one provider: ClaudeCodeHeadlessProvider, which shells out to
`claude -p` using a long-lived OAuth token. Uses John's Claude subscription
with no API key required.

Adding a new provider is one subclass of Provider.
"""
from __future__ import annotations
import json
import os
import subprocess
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from openharness import config, state


class ProviderError(Exception):
    """Raised when a provider call fails."""


class CircuitOpen(ProviderError):
    """Raised when the circuit breaker is open and the call was not attempted."""


@dataclass
class ProviderResponse:
    text: str
    raw: dict | None = None
    cost_usd: float = 0.0
    duration_seconds: float = 0.0


class Provider(ABC):
    """LLM provider interface. One subclass per backend."""

    name: str = "abstract"

    @abstractmethod
    def call(self, system_prompt: str, user_prompt: str, *, timeout: int = 300) -> ProviderResponse:
        """Make one LLM call. Returns response text; raises ProviderError on failure."""


class ClaudeCodeHeadlessProvider(Provider):
    """Calls `claude -p` (Claude Code non-interactive mode).

    Uses a long-lived OAuth token (CLAUDE_CODE_OAUTH_TOKEN env var) so it works
    headlessly without a browser. Token is generated once via `claude setup-token`.
    """

    name = "claude_code_headless"

    def __init__(self, *, oauth_token_env: str = "CLAUDE_CODE_OAUTH_TOKEN",
                 binary: str = "claude", timeout_seconds: int = 300):
        self.oauth_token_env = oauth_token_env
        self.binary = binary
        self.default_timeout = timeout_seconds

    def call(self, system_prompt: str, user_prompt: str, *, timeout: int = 300) -> ProviderResponse:
        token = os.environ.get(self.oauth_token_env)
        env = os.environ.copy()
        if token:
            env[self.oauth_token_env] = token
        # Compose the prompt; claude -p accepts the user prompt as argument and stdin alike.
        # Pass the system prompt via --append-system-prompt for proper handling.
        cmd = [self.binary, "-p", user_prompt]
        if system_prompt:
            cmd.extend(["--append-system-prompt", system_prompt])
        cmd.extend(["--output-format", "json"])
        start = time.monotonic()
        try:
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout or self.default_timeout,
            )
        except subprocess.TimeoutExpired as e:
            raise ProviderError(f"claude -p timed out after {timeout}s") from e
        except FileNotFoundError as e:
            raise ProviderError(f"binary not found: {self.binary} ({e})") from e
        duration = time.monotonic() - start
        if result.returncode != 0:
            raise ProviderError(
                f"claude -p exited {result.returncode}. stderr: {result.stderr.strip()[:500]}"
            )
        # Try to parse JSON output; fall back to raw stdout
        raw = None
        text = result.stdout
        cost = 0.0
        try:
            raw = json.loads(result.stdout)
            if isinstance(raw, dict):
                text = raw.get("result", raw.get("text", result.stdout))
                cost = float(raw.get("total_cost_usd", 0.0) or 0.0)
        except (json.JSONDecodeError, ValueError):
            pass
        return ProviderResponse(text=text, raw=raw, cost_usd=cost, duration_seconds=duration)


@dataclass
class CircuitBreakerState:
    failure_count: int = 0
    last_failure_ts: float = 0.0
    opened_at: float = 0.0
    open_count: int = 0       # how many times the breaker has opened (for backoff)
    half_open: bool = False


class CircuitBreaker:
    """Wraps a Provider with throttle + rate + cooldown.

    Pattern: throttle ≥2s between failures; ≥5 failures in 60s opens the breaker;
    cooldown 5min initial, exponential (5/10/20/30) up to 30min cap; half-open
    after cooldown; one success closes the breaker.
    """

    THROTTLE_SECONDS = 2.0
    FAILURE_WINDOW = 60.0
    FAILURE_THRESHOLD = 5
    COOLDOWN_LADDER = [300, 600, 1200, 1800]  # 5m, 10m, 20m, 30m

    def __init__(self, provider: Provider):
        self.provider = provider
        self.s = CircuitBreakerState()

    def _cooldown_seconds(self) -> float:
        idx = min(self.s.open_count - 1, len(self.COOLDOWN_LADDER) - 1) if self.s.open_count else 0
        return self.COOLDOWN_LADDER[max(idx, 0)]

    def _is_open(self) -> bool:
        if self.s.opened_at == 0:
            return False
        if time.time() - self.s.opened_at >= self._cooldown_seconds():
            self.s.half_open = True
            return False
        return True

    def _record_failure(self) -> None:
        now = time.time()
        if now - self.s.last_failure_ts > self.FAILURE_WINDOW:
            self.s.failure_count = 0
        self.s.failure_count += 1
        self.s.last_failure_ts = now
        if self.s.failure_count >= self.FAILURE_THRESHOLD:
            self.s.opened_at = now
            self.s.open_count += 1
            self.s.half_open = False
            state.append(
                sender="cos",
                kind="event",
                content=f"Circuit breaker OPENED for provider={self.provider.name} "
                        f"after {self.s.failure_count} failures; cooldown {self._cooldown_seconds()}s",
            )

    def _record_success(self) -> None:
        self.s.failure_count = 0
        if self.s.half_open or self.s.opened_at > 0:
            state.append(
                sender="cos",
                kind="event",
                content=f"Circuit breaker CLOSED for provider={self.provider.name}",
            )
        self.s.opened_at = 0
        self.s.half_open = False

    def call(self, system_prompt: str, user_prompt: str, *, timeout: int = 300) -> ProviderResponse:
        if self._is_open():
            cooldown_remaining = self._cooldown_seconds() - (time.time() - self.s.opened_at)
            raise CircuitOpen(
                f"Circuit breaker is OPEN for provider={self.provider.name}; "
                f"cooldown remaining ~{cooldown_remaining:.0f}s"
            )
        # Throttle between failures
        if self.s.last_failure_ts > 0 and time.time() - self.s.last_failure_ts < self.THROTTLE_SECONDS:
            time.sleep(self.THROTTLE_SECONDS - (time.time() - self.s.last_failure_ts))
        try:
            resp = self.provider.call(system_prompt, user_prompt, timeout=timeout)
            self._record_success()
            return resp
        except ProviderError:
            self._record_failure()
            raise


def load_default_provider() -> CircuitBreaker:
    """Read config/auth-profiles.json and instantiate the default provider."""
    cfg_root = Path(config.load()["_root"])
    auth_path = cfg_root / "config" / "auth-profiles.json"
    with auth_path.open() as f:
        data = json.load(f)
    default_name = data.get("default_profile")
    if not default_name:
        raise ProviderError("config/auth-profiles.json has no default_profile set")
    profile = data.get("profiles", {}).get(default_name)
    if not profile:
        raise ProviderError(f"profile not found: {default_name}")
    return _instantiate(profile)


def _instantiate(profile: dict) -> CircuitBreaker:
    ptype = profile.get("type")
    if ptype == "claude_code_headless":
        prov = ClaudeCodeHeadlessProvider(
            oauth_token_env=profile.get("oauth_token_env", "CLAUDE_CODE_OAUTH_TOKEN"),
            binary=profile.get("binary", "claude"),
            timeout_seconds=int(profile.get("timeout_seconds", 300)),
        )
    else:
        raise ProviderError(f"unknown provider type: {ptype!r}. Supported in v1: claude_code_headless")
    return CircuitBreaker(prov)
