"""The shared retry policy (data-model §6, research R10).

Behaviours:
1. The first success returns at once, with no sleep.
2. A transient failure is retried, and the later result is returned.
3. Attempts stop at max_attempts with RetryExhaustedError, chained to the last failure.
4. Time spent inside calls counts toward max_total_seconds.
5. A delay that would pass the budget ends the retries instead of sleeping.
6. Full-jitter backoff: delay n is rand() * min(max_backoff, initial * 2**(n-1)).
7. A Retry-After hint replaces the computed delay when it fits the remaining budget,
   and is ignored when it does not.
8. parse_retry_after reads retry-after-ms first, then Retry-After seconds, ignoring junk.
9. reauth calls on_reauth once and retries at once, without using an attempt.
10. A second reauth fails with the original error.
11. reauth without an on_reauth hook fails with the original error.
12. fail re-raises the original error at once.
13. A BaseException that is not an Exception passes through unclassified.
"""

import random

import pytest

from tenetrag._retry import (
    RetryExhaustedError,
    RetryPolicy,
    Verdict,
    parse_retry_after,
    run_with_retry,
)

POLICY = RetryPolicy(
    max_attempts=5,
    max_total_seconds=60.0,
    initial_backoff_seconds=0.5,
    max_backoff_seconds=8.0,
)
NEAR_ONE = 0.999


class TransientError(Exception):
    def __init__(self, retry_after: float | None = None) -> None:
        super().__init__("transient")
        self.retry_after = retry_after


class RejectedError(Exception):
    pass


class FatalError(Exception):
    pass


def classify(exc: Exception) -> Verdict:
    if isinstance(exc, TransientError):
        return Verdict.retry(exc.retry_after)
    if isinstance(exc, RejectedError):
        return Verdict.reauth()
    return Verdict.fail()


class FakeTime:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


class Script:
    """Raises or returns the outcomes in order; each call can take fake time."""

    def __init__(self, *outcomes, fake_time=None, call_seconds=0.0) -> None:
        self.outcomes = list(outcomes)
        self.fake_time = fake_time
        self.call_seconds = call_seconds
        self.calls = 0

    def __call__(self):
        self.calls += 1
        if self.fake_time is not None:
            self.fake_time.now += self.call_seconds
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class Counter:
    def __init__(self) -> None:
        self.count = 0

    def __call__(self) -> None:
        self.count += 1


@pytest.fixture
def fake_time() -> FakeTime:
    return FakeTime()


def run(fn, fake_time, *, policy=POLICY, on_reauth=None, rand=lambda: NEAR_ONE, classify=classify):
    return run_with_retry(
        fn,
        classify,
        policy=policy,
        on_reauth=on_reauth,
        clock=fake_time.clock,
        sleep=fake_time.sleep,
        rand=rand,
    )


def test_first_success_returns_without_sleeping(fake_time):
    script = Script("ok")
    assert run(script, fake_time) == "ok"
    assert script.calls == 1
    assert fake_time.sleeps == []


def test_transient_failure_is_retried(fake_time):
    script = Script(TransientError(), TransientError(), "ok")
    assert run(script, fake_time) == "ok"
    assert script.calls == 3
    assert len(fake_time.sleeps) == 2


def test_attempts_stop_at_max_attempts(fake_time):
    failures = [TransientError() for _ in range(6)]
    script = Script(*failures)
    with pytest.raises(RetryExhaustedError) as caught:
        run(script, fake_time)
    assert script.calls == 5
    assert caught.value.attempts == 5
    assert caught.value.__cause__ is failures[4]
    assert "5 attempts" in str(caught.value)
    assert len(fake_time.sleeps) == 4


def test_time_spent_in_calls_counts_toward_budget(fake_time):
    script = Script(*[TransientError() for _ in range(5)], fake_time=fake_time, call_seconds=25.0)
    with pytest.raises(RetryExhaustedError) as caught:
        run(script, fake_time)
    assert script.calls == 3
    assert caught.value.elapsed_seconds == pytest.approx(75.0 + 0.5 * NEAR_ONE + 1.0 * NEAR_ONE)


def test_delay_past_budget_ends_retries(fake_time):
    policy = RetryPolicy(
        max_attempts=5, max_total_seconds=1.0, initial_backoff_seconds=0.5, max_backoff_seconds=8.0
    )
    script = Script(*[TransientError() for _ in range(5)])
    with pytest.raises(RetryExhaustedError):
        run(script, fake_time, policy=policy)
    assert script.calls == 2
    assert fake_time.sleeps == [pytest.approx(0.5 * NEAR_ONE)]


JITTER_POLICY = RetryPolicy(
    max_attempts=7, max_total_seconds=1000.0, initial_backoff_seconds=0.5, max_backoff_seconds=4.0
)
JITTER_CAPS = [0.5, 1.0, 2.0, 4.0, 4.0, 4.0]


def test_full_jitter_upper_bound_doubles_to_the_cap(fake_time):
    with pytest.raises(RetryExhaustedError):
        run(Script(*[TransientError() for _ in range(7)]), fake_time, policy=JITTER_POLICY)
    assert fake_time.sleeps == pytest.approx([cap * NEAR_ONE for cap in JITTER_CAPS])


def test_full_jitter_lower_bound_is_zero(fake_time):
    with pytest.raises(RetryExhaustedError):
        run(
            Script(*[TransientError() for _ in range(7)]),
            fake_time,
            policy=JITTER_POLICY,
            rand=lambda: 0.0,
        )
    assert fake_time.sleeps == [0.0] * 6


def test_full_jitter_stays_within_bounds_with_real_randomness(fake_time):
    with pytest.raises(RetryExhaustedError):
        run(
            Script(*[TransientError() for _ in range(7)]),
            fake_time,
            policy=JITTER_POLICY,
            rand=random.Random(7).random,  # noqa: S311 - seeded jitter source, not a secret
        )
    assert len(fake_time.sleeps) == len(JITTER_CAPS)
    for delay, cap in zip(fake_time.sleeps, JITTER_CAPS, strict=True):
        assert 0.0 <= delay <= cap


def test_retry_after_hint_replaces_computed_delay(fake_time):
    assert run(Script(TransientError(retry_after=3.0), "ok"), fake_time) == "ok"
    assert fake_time.sleeps == [3.0]


def test_retry_after_hint_past_budget_is_ignored(fake_time):
    policy = RetryPolicy(
        max_attempts=5, max_total_seconds=10.0, initial_backoff_seconds=0.5, max_backoff_seconds=8.0
    )
    assert run(Script(TransientError(retry_after=30.0), "ok"), fake_time, policy=policy) == "ok"
    assert fake_time.sleeps == [pytest.approx(0.5 * NEAR_ONE)]


@pytest.mark.parametrize(
    ("headers", "expected"),
    [
        ({"retry-after-ms": "1500"}, 1.5),
        ({"Retry-After-Ms": "1500"}, 1.5),
        ({"Retry-After": "2"}, 2.0),
        ({"retry-after": "0.25"}, 0.25),
        ({"retry-after-ms": "500", "retry-after": "9"}, 0.5),
        ({"retry-after-ms": "soon", "retry-after": "2"}, 2.0),
        ({}, None),
        ({"retry-after": "Wed, 21 Oct 2026 07:28:00 GMT"}, None),
        ({"retry-after": "-1"}, None),
        ({"retry-after": "nan"}, None),
        ({"retry-after": "inf"}, None),
        ({"retry-after-ms": "soon"}, None),
    ],
)
def test_parse_retry_after(headers, expected):
    assert parse_retry_after(headers) == expected


def test_reauth_invalidates_once_and_retries_at_once(fake_time):
    on_reauth = Counter()
    script = Script(RejectedError(), "ok")
    assert run(script, fake_time, on_reauth=on_reauth) == "ok"
    assert on_reauth.count == 1
    assert script.calls == 2
    assert fake_time.sleeps == []


def test_reauth_does_not_use_an_attempt(fake_time):
    policy = RetryPolicy(
        max_attempts=2, max_total_seconds=60.0, initial_backoff_seconds=0.5, max_backoff_seconds=8.0
    )
    script = Script(RejectedError(), TransientError(), TransientError())
    with pytest.raises(RetryExhaustedError) as caught:
        run(script, fake_time, policy=policy, on_reauth=Counter())
    assert script.calls == 3
    assert caught.value.attempts == 2


def test_second_reauth_fails_with_the_original_error(fake_time):
    on_reauth = Counter()
    second = RejectedError()
    script = Script(RejectedError(), second)
    with pytest.raises(RejectedError) as caught:
        run(script, fake_time, on_reauth=on_reauth)
    assert caught.value is second
    assert on_reauth.count == 1
    assert script.calls == 2


def test_reauth_without_a_hook_fails_with_the_original_error(fake_time):
    rejected = RejectedError()
    script = Script(rejected)
    with pytest.raises(RejectedError) as caught:
        run(script, fake_time, on_reauth=None)
    assert caught.value is rejected
    assert script.calls == 1


def test_fail_reraises_at_once(fake_time):
    fatal = FatalError()
    script = Script(fatal)
    with pytest.raises(FatalError) as caught:
        run(script, fake_time)
    assert caught.value is fatal
    assert script.calls == 1
    assert fake_time.sleeps == []


def test_base_exception_passes_through_unclassified(fake_time):
    classified: list[BaseException] = []

    def spy(exc: Exception) -> Verdict:
        classified.append(exc)
        return Verdict.fail()

    with pytest.raises(KeyboardInterrupt):
        run(Script(KeyboardInterrupt()), fake_time, classify=spy)
    assert classified == []
