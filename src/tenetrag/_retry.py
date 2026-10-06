"""The retry policy shared by model calls and Postgres units of work.

Standard library only (data-model §6, research R10). Callers classify each
failure as retry, reauth or fail; this module owns attempts, the time budget,
full-jitter backoff and the single reauth retry. Libraries such as tenacity
were considered and rejected in research R10.
"""

from __future__ import annotations

import enum
import math
import random
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Values from the profile's `RetrySettings`, which also holds the defaults."""

    max_attempts: int
    max_total_seconds: float
    initial_backoff_seconds: float
    max_backoff_seconds: float


class Action(enum.Enum):
    RETRY = "retry"
    REAUTH = "reauth"
    FAIL = "fail"


@dataclass(frozen=True, slots=True)
class Verdict:
    """How the caller classified one failure."""

    action: Action
    retry_after_seconds: float | None = None

    @classmethod
    def retry(cls, after_seconds: float | None = None) -> Verdict:
        """Transient failure; `after_seconds` is the server's hint, if it sent one."""
        return cls(Action.RETRY, after_seconds)

    @classmethod
    def reauth(cls) -> Verdict:
        """The server rejected a token of a refreshable credential."""
        return cls(Action.REAUTH)

    @classmethod
    def fail(cls) -> Verdict:
        return cls(Action.FAIL)


class RetryExhaustedError(Exception):
    """Retries ran out. Private: callers map it to their public unavailable error.

    The last failure is the `__cause__`.
    """

    def __init__(self, attempts: int, elapsed_seconds: float) -> None:
        super().__init__(f"gave up after {attempts} attempts in {elapsed_seconds:.1f} s")
        self.attempts = attempts
        self.elapsed_seconds = elapsed_seconds


def parse_retry_after(headers: Mapping[str, str]) -> float | None:
    """Read `retry-after-ms`, then `Retry-After` in seconds. HTTP dates and junk give None."""
    lowered = {name.lower(): value for name, value in headers.items()}
    for name, scale in (("retry-after-ms", 0.001), ("retry-after", 1.0)):
        try:
            seconds = float(lowered[name]) * scale
        except (KeyError, ValueError):
            continue
        if math.isfinite(seconds) and seconds >= 0:
            return seconds
    return None


def run_with_retry(
    fn: Callable[[], T],
    classify: Callable[[Exception], Verdict],
    *,
    policy: RetryPolicy,
    on_reauth: Callable[[], None] | None = None,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    rand: Callable[[], float] = random.random,  # jitter, not a secret
) -> T:
    """Call `fn` until it succeeds, a failure is final, or the policy runs out.

    - fail: the original error is re-raised at once.
    - reauth: `on_reauth` invalidates the token once and `fn` runs again at once,
      without using an attempt. A second reauth, or no hook, counts as fail.
    - retry: sleep, then try again, while attempts and time remain; otherwise
      raise `RetryExhaustedError` from the last failure.
    """
    start = clock()
    attempt = 1
    reauth_used = False
    while True:
        try:
            return fn()
        except Exception as exc:
            verdict = classify(exc)
            if verdict.action is Action.REAUTH and on_reauth is not None and not reauth_used:
                reauth_used = True
                on_reauth()
                continue
            if verdict.action is not Action.RETRY:
                raise
            elapsed = clock() - start
            delay = _next_delay(policy, attempt, verdict.retry_after_seconds, elapsed, rand)
            if attempt >= policy.max_attempts or delay is None:
                raise RetryExhaustedError(attempt, elapsed) from exc
        sleep(delay)
        attempt += 1


def _next_delay(
    policy: RetryPolicy,
    attempt: int,
    hint_seconds: float | None,
    elapsed_seconds: float,
    rand: Callable[[], float],
) -> float | None:
    """The delay before the next attempt, or None when it would pass the time budget."""
    remaining = policy.max_total_seconds - elapsed_seconds
    if hint_seconds is not None and hint_seconds <= remaining:
        return hint_seconds
    cap = min(policy.max_backoff_seconds, policy.initial_backoff_seconds * 2 ** (attempt - 1))
    delay = rand() * cap
    return delay if delay <= remaining else None
