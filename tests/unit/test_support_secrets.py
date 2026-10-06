"""The planted-secret helpers must catch what they claim to, or SC-006 proves nothing."""

import logging

import pytest

from tests.support.secrets import (
    PLANTED,
    assert_exception_clean,
    assert_logs_clean,
    assert_no_secret,
)


def test_planted_values_are_distinct_and_marked():
    assert len(PLANTED) >= 3
    assert len(set(PLANTED)) == len(PLANTED)
    assert all("planted" in value for value in PLANTED)


def test_no_secret_accepts_clean_text():
    assert_no_secret("connection refused", "Secret('***')")


@pytest.mark.parametrize("secret", PLANTED)
def test_no_secret_catches_each_planted_value(secret):
    with pytest.raises(AssertionError):
        assert_no_secret("clean", f"Authorization: Bearer {secret}")


def _chained(inner_message: str, *, explicit: bool) -> BaseException:
    try:
        try:
            raise ValueError(inner_message)
        except ValueError as inner:
            if explicit:
                raise RuntimeError("wrapped, nothing secret here") from inner
            raise RuntimeError("wrapped, nothing secret here")  # noqa: B904 - tests __context__
    except RuntimeError as outer:
        return outer
    raise AssertionError("unreachable")


def test_exception_clean_accepts_clean_chain():
    assert_exception_clean(_chained("connection refused", explicit=True))


def test_exception_clean_catches_secret_in_cause():
    with pytest.raises(AssertionError):
        assert_exception_clean(_chained(f"bad key {PLANTED[0]}", explicit=True))


def test_exception_clean_catches_secret_in_context():
    with pytest.raises(AssertionError):
        assert_exception_clean(_chained(f"bad key {PLANTED[0]}", explicit=False))


def test_exception_clean_catches_secret_only_in_repr():
    class LeakyError(Exception):
        def __str__(self) -> str:
            return "clean message"

        def __repr__(self) -> str:
            return f"LeakyError(password={PLANTED[1]!r})"

    with pytest.raises(AssertionError):
        assert_exception_clean(LeakyError())


def test_exception_clean_catches_secret_in_notes():
    exc = RuntimeError("clean")
    exc.add_note(f"token was {PLANTED[2]}")
    with pytest.raises(AssertionError):
        assert_exception_clean(exc)


def test_exception_clean_stops_on_cycles():
    first, second = RuntimeError("first"), RuntimeError("second")
    first.__context__, second.__context__ = second, first
    assert_exception_clean(first)


def test_logs_clean_accepts_clean_records(caplog):
    with caplog.at_level(logging.DEBUG):
        logging.getLogger("tenetrag.test").debug("connected to %s", "localhost")
    assert_logs_clean(caplog)


def test_logs_clean_catches_secret_in_message_args(caplog):
    with caplog.at_level(logging.DEBUG):
        logging.getLogger("tenetrag.test").debug("header %s", PLANTED[1])
    with pytest.raises(AssertionError):
        assert_logs_clean(caplog)


def test_logs_clean_catches_secret_in_logged_exception(caplog):
    with caplog.at_level(logging.DEBUG):
        try:
            raise ValueError(PLANTED[2])
        except ValueError:
            logging.getLogger("tenetrag.test").exception("call failed")
    with pytest.raises(AssertionError):
        assert_logs_clean(caplog)
