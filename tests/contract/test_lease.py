"""The writer lease (stores.md §2, ADR 0024), case `writer-lease`.

The fixture holds the lease as `writer_owner(backend)`. Expiry is waited
out on the server clock, since the Docker stores have no clock to move.
"""

from __future__ import annotations

import dataclasses
import time
from collections.abc import Callable
from datetime import UTC, datetime

import pytest

from tenetrag.protocols import (
    DocumentDelete,
    RunRecord,
    RunStatus,
    StorageError,
    Verdict,
    WriterBusyError,
    WriterLease,
)
from tests.support.contract.backends import ContractStores, writer_owner
from tests.support.contract.writes import RUN_ID, corpus_writes

TTL_S = 60
# Past the end time, for clocks that differ by a little.
EXPIRY_MARGIN_S = 0.3


def _wait_out(lease: WriterLease) -> None:
    remaining = (lease.expires_at - datetime.now(UTC)).total_seconds()
    time.sleep(max(remaining, 0) + EXPIRY_MARGIN_S)


def _run() -> RunRecord:
    return RunRecord(
        run_id=RUN_ID,
        status=RunStatus.RUNNING,
        started_at=None,
        finished_at=None,
        stage_hashes={},
        prompt_versions={},
        pack="enterprise-docs",
        pack_version="1",
        pack_hash="0" * 64,
        stats={},
    )


def test_second_writer_busy(stores: ContractStores) -> None:
    owner = writer_owner(stores.backend)
    lease = stores.graph.acquire_writer(owner, ttl_s=TTL_S)

    with pytest.raises(WriterBusyError) as busy:
        stores.open_graph().acquire_writer("other", ttl_s=TTL_S)

    assert (busy.value.owner, busy.value.expires_at) == (owner, lease.expires_at)
    assert owner in str(busy.value)


def test_same_owner_reacquires(stores: ContractStores) -> None:
    owner = writer_owner(stores.backend)
    first = stores.graph.acquire_writer(owner, ttl_s=TTL_S)

    again = stores.graph.acquire_writer(owner, ttl_s=TTL_S)

    assert (again.index_id, again.owner, again.fence) == (stores.index_id, owner, first.fence)
    assert again.expires_at >= first.expires_at


def test_renew_moves_end(stores: ContractStores) -> None:
    lease = stores.graph.acquire_writer(writer_owner(stores.backend), ttl_s=TTL_S)

    renewed = stores.graph.renew_writer(lease, ttl_s=10 * TTL_S)

    assert renewed.expires_at > lease.expires_at
    assert (renewed.owner, renewed.fence) == (lease.owner, lease.fence)
    for wrong in (
        dataclasses.replace(lease, fence=lease.fence + 1),
        dataclasses.replace(lease, owner="other"),
    ):
        with pytest.raises(WriterBusyError):
            stores.graph.renew_writer(wrong, ttl_s=TTL_S)
    for ttl_s in (0, 86_401):
        with pytest.raises(ValueError, match="ttl_s is"):
            stores.graph.acquire_writer(lease.owner, ttl_s=ttl_s)
        with pytest.raises(ValueError, match="ttl_s is"):
            stores.graph.renew_writer(renewed, ttl_s=ttl_s)


def test_release_lets_next_acquire(stores: ContractStores) -> None:
    lease = stores.graph.acquire_writer(writer_owner(stores.backend), ttl_s=TTL_S)

    stores.graph.release_writer(lease)

    taken = stores.open_graph().acquire_writer("other", ttl_s=TTL_S)
    assert taken.fence == lease.fence + 1
    # Already gone and now taken: not an error, and the new holder keeps the lease.
    stores.graph.release_writer(lease)
    with pytest.raises(WriterBusyError):
        stores.graph.acquire_writer(lease.owner, ttl_s=TTL_S)


def test_expiry_lets_next_acquire(stores: ContractStores) -> None:
    short = stores.graph.acquire_writer(writer_owner(stores.backend), ttl_s=1)

    _wait_out(short)

    assert stores.open_graph().acquire_writer("other", ttl_s=TTL_S).fence == short.fence + 1


def test_fenced_writer_fails(stores: ContractStores) -> None:
    short = stores.graph.acquire_writer(writer_owner(stores.backend), ttl_s=1)
    _wait_out(short)
    other = stores.open_graph()
    other.acquire_writer("other", ttl_s=TTL_S)

    with pytest.raises(WriterBusyError) as busy:
        stores.graph.write_documents(corpus_writes(["D1"], with_vectors=False))

    assert busy.value.owner == "other"
    assert other.document_states() == {}


def test_every_write_needs_the_lease(stores: ContractStores) -> None:
    unleased = stores.open_graph()
    verdict = Verdict(pair_key="a|b", verdict="same", method="llm", model="fake", run_id=RUN_ID)
    calls: dict[str, Callable[[], None]] = {
        "write_documents": lambda: unleased.write_documents(
            corpus_writes(["D1"], with_vectors=False)
        ),
        "delete_documents": lambda: unleased.delete_documents(
            [DocumentDelete(doc_id="D1", run_id=RUN_ID)]
        ),
        "begin_run": lambda: unleased.begin_run(_run()),
        "finish_run": lambda: unleased.finish_run(RUN_ID, RunStatus.COMPLETED, {}),
        "put_cached_extractions": lambda: unleased.put_cached_extractions({"key": b"payload"}),
        "put_resolution_decisions": lambda: unleased.put_resolution_decisions([verdict]),
    }
    for name, call in calls.items():
        with pytest.raises(StorageError, match="acquire_writer") as refused:
            call()
        assert not isinstance(refused.value, WriterBusyError), name

    assert unleased.document_states() == {}
    assert unleased.get_runs(10) == []
    assert unleased.get_cached_extractions(["key"]) == {}
    assert unleased.get_resolution_decisions(["a|b"]) == {}


def test_two_objects_one_lease(stores: ContractStores) -> None:
    owner = writer_owner(stores.backend)
    first, second = stores.graph, stores.open_graph()
    with pytest.raises(WriterBusyError) as busy:
        second.acquire_writer("other", ttl_s=TTL_S)
    assert busy.value.owner == owner

    lease = first.acquire_writer(owner, ttl_s=TTL_S)
    first.release_writer(lease)
    assert second.acquire_writer("other", ttl_s=TTL_S).fence == lease.fence + 1

    with pytest.raises(WriterBusyError) as busy:
        first.acquire_writer(owner, ttl_s=TTL_S)
    assert busy.value.owner == "other"
    second.write_documents(corpus_writes(["D1"], with_vectors=False))
    assert sorted(first.document_states()) == ["D1"]


def test_quickstart_negative_check(stores: ContractStores) -> None:
    """quickstart §1: a second store that never acquired, then acquires while held."""
    second = stores.open_graph()

    with pytest.raises(StorageError, match="acquire_writer"):
        second.write_documents(corpus_writes(["D1"]))
    with pytest.raises(WriterBusyError) as busy:
        second.acquire_writer("other", ttl_s=TTL_S)

    assert busy.value.owner == writer_owner(stores.backend)
    assert busy.value.owner in str(busy.value)
