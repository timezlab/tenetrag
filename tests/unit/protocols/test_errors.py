"""WriterBusyError (contracts/protocols.md §1, ADR 0024).

Behaviours:
1. It is a StorageError that keeps the holder and the lease's end time.
2. Its text names the holder and the end time in UTC ISO form, and says
   to wait for the end time or release the other writer.
3. A naive end time is a caller bug and raises ValueError.
4. Both arguments are keyword-only.
"""

from datetime import UTC, datetime, timedelta, timezone

import pytest

from tenetrag.protocols import StorageError, WriterBusyError

# 09:30 at UTC+7 is 02:30 UTC; the microseconds are dropped from the text.
END = datetime(2026, 10, 21, 9, 30, 15, 250000, tzinfo=timezone(timedelta(hours=7)))


def test_writer_busy_error():
    exc = WriterBusyError(owner="indexer:host-a", expires_at=END)

    assert isinstance(exc, StorageError)
    assert exc.owner == "indexer:host-a"
    assert exc.expires_at == END
    text = str(exc)
    assert "'indexer:host-a'" in text
    assert "2026-10-21T02:30:15+00:00" in text
    assert "wait" in text
    assert "release" in text


def test_writer_busy_error_needs_an_aware_end_time():
    with pytest.raises(ValueError, match="expires_at"):
        WriterBusyError(owner="indexer:host-a", expires_at=datetime(2026, 10, 21, 9, 30))


def test_writer_busy_error_takes_keywords_only():
    with pytest.raises(TypeError):
        WriterBusyError("indexer:host-a", datetime(2026, 10, 21, tzinfo=UTC))  # type: ignore[misc]  # the positional call is the test
