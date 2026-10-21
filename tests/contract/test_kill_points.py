"""Killed units (stores.md §3.4), case `killed-run-atomicity`.

T032 seeds this file with the last step only, because a swap made before
that step's hook survived every other test. T037 adds the remaining steps
and the split crash.
"""

from __future__ import annotations

import pytest

from tenetrag.protocols import StepHook, WriteStep
from tests.support.contract.backends import ContractStores, writer_owner
from tests.support.contract.writes import corpus_writes, snapshot

TTL_S = 60


class _KilledError(Exception):
    """Raised by the step hook, as a crash inside the unit would be."""


def _fail_at(step: WriteStep) -> StepHook:
    def hook(at: WriteStep, doc_id: str) -> None:
        if at is step:
            raise _KilledError(f"{doc_id} killed at {at}")

    return hook


def test_failure_in_last_step_writes_nothing(stores: ContractStores) -> None:
    d1, d2 = corpus_writes(["D1", "D2"], with_vectors=False)
    stores.graph.write_documents([d1])
    counts, rows = stores.row_counts(), snapshot(stores, [d1, d2])
    hooked = stores.open_graph(step_hook=_fail_at(WriteStep.DOCUMENT_ROW))
    hooked.acquire_writer(writer_owner(stores.backend), ttl_s=TTL_S)

    with pytest.raises(_KilledError):
        hooked.write_documents([d2])

    assert stores.row_counts() == counts
    assert snapshot(stores, [d1, d2]) == rows
