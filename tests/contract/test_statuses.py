"""Statuses and versions: graph.json flags and status changes in the unit (data-model §10).

Cases `supersession-flags` and `status-changes-in-unit`. Vectors play no
part here, so the writes go to the graph store without them.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterable
from datetime import date

import pytest

from tenetrag.protocols import DocumentDelete, DocumentWrite, ItemRecord, QueryError, StatusChange
from tests.support.contract.backends import ContractStores
from tests.support.contract.writes import (
    DELETE_RUN_ID,
    State,
    corpus_delete,
    corpus_table,
    corpus_writes,
    expected_statuses,
    store_id,
)

UNKNOWN_ITEM = "no-such-item"


def _statuses(stores: ContractStores, item_ids: Iterable[str]) -> dict[str, State]:
    items = stores.graph.get_items(sorted(item_ids))
    return {item.item_id: (item.status or "", item.closed_at) for item in items}


def _unknown_change() -> StatusChange:
    return StatusChange(item_id=UNKNOWN_ITEM, status="superseded", closed_at=date(2026, 1, 15))


def test_statuses_match_graph_json(stores: ContractStores) -> None:
    stores.graph.write_documents(corpus_writes(with_vectors=False))

    expected = expected_statuses()
    assert _statuses(stores, expected) == expected


def test_statuses_after_d2_deleted(stores: ContractStores) -> None:
    writes = corpus_writes(with_vectors=False)
    stores.graph.write_documents(writes)

    stores.graph.delete_documents([corpus_delete("D2")])

    rest = [document.id for document in corpus_table().documents if document.id != "D2"]
    expected = expected_statuses(rest)
    assert _statuses(stores, expected) == expected
    [d2] = [write for write in writes if write.document.doc_id == "D2"]
    assert _statuses(stores, [row.fact_id for row in d2.facts]) == {}


def test_unknown_item_fails_unit(stores: ContractStores) -> None:
    d1, d2, d5 = corpus_writes(["D1", "D2", "D5"], with_vectors=False)
    failing = dataclasses.replace(d2, status_changes=(*d2.status_changes, _unknown_change()))

    with pytest.raises(QueryError, match=UNKNOWN_ITEM):
        stores.graph.write_documents([d1, failing, d5])

    # D1 stays written, D2's unit rolled back with its own status change, D5 not tried.
    assert sorted(stores.graph.document_states()) == ["D1"]
    assert stores.graph.get_chunks([chunk.chunk_id for chunk in d2.chunks]) == []
    assert _statuses(stores, [store_id("D1.6")]) == {store_id("D1.6"): ("current", None)}

    stores.graph.write_documents([d2, d5])
    failing_delete = DocumentDelete(
        doc_id="D2", status_changes=(_unknown_change(),), run_id=DELETE_RUN_ID
    )
    with pytest.raises(QueryError, match=UNKNOWN_ITEM):
        stores.graph.delete_documents([failing_delete])
    assert sorted(stores.graph.document_states()) == ["D1", "D2", "D5"]


def _version_order(item: ItemRecord) -> tuple[str, bool, date, str]:
    """Version key, then valid_from with a missing one first, then item id."""
    return (
        item.version_key or "",
        item.valid_from is not None,
        item.valid_from or date.min,
        item.item_id,
    )


def _version_keys(write: DocumentWrite) -> set[str]:
    keys = {row.version_key for row in write.relations} | {row.version_key for row in write.facts}
    return {key for key in keys if key is not None}


def test_version_reads(stores: ContractStores) -> None:
    writes = corpus_writes(with_vectors=False)
    stores.graph.write_documents(writes)
    keys = sorted(set().union(*(_version_keys(write) for write in writes)))
    grouped = sorted(
        {row.relation_id for write in writes for row in write.relations if row.version_key}
        | {row.fact_id for write in writes for row in write.facts if row.version_key}
    )

    items = stores.graph.get_version_groups([*reversed(keys), keys[0]])
    assert items == sorted(items, key=_version_order)
    assert sorted(item.item_id for item in items) == grouped
    assert stores.graph.get_version_groups([]) == []
    assert stores.graph.get_version_groups(["no-such-key"]) == []

    by_document = {write.document.doc_id: sorted(_version_keys(write)) for write in writes}
    assert by_document["D1"]
    assert by_document["D3"] == []
    assert stores.graph.get_document_version_keys(["D3", "D1", "D404"]) == {
        "D1": by_document["D1"],
        "D3": [],
    }
    assert stores.graph.get_document_version_keys(list(by_document)) == by_document
