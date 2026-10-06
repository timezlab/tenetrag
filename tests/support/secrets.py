"""Planted fake secrets and the checks that prove none of them leaks (SC-006).

The values are distinctive so a hit can only come from the test's own input.
The hyphens keep them from matching real-key patterns in secret scanners.
"""

from __future__ import annotations

import pytest

PLANTED: tuple[str, ...] = (
    "sk-planted-a1b2-c3d4-e5f6",
    "pw-planted-g7h8-i9j0",
    "tok-planted-k1l2-m3n4",
    "dapi-planted-o5p6-q7r8",
    "cs-planted-s9t0-u1v2",
)


def assert_no_secret(*texts: str) -> None:
    for index, text in enumerate(texts):
        for secret in PLANTED:
            assert secret not in text, f"planted secret {secret!r} found in text #{index}"


def assert_exception_clean(exc: BaseException) -> None:
    """Check str, repr and notes of the exception and of its whole cause/context chain."""
    seen: set[int] = set()
    pending: list[BaseException] = [exc]
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        notes = getattr(current, "__notes__", [])
        assert_no_secret(str(current), repr(current), *notes)
        pending.extend(e for e in (current.__cause__, current.__context__) if e is not None)


def assert_logs_clean(caplog: pytest.LogCaptureFixture) -> None:
    """Check formatted log output, including logged tracebacks, and each record's message."""
    assert_no_secret(caplog.text, *(record.getMessage() for record in caplog.records))
