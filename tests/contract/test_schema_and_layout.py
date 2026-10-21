"""ensure_schema, ensure_collections and the layout check (data-model §9, FR-024).

Cases `schema-idempotent`, `schema-additive` and `layout-version`.
"""

from __future__ import annotations

import dataclasses

import pytest

from tenetrag.protocols import ConfigError, StorageError, StoreSchema
from tests.support.contract.backends import ContractStores
from tests.support.contract.generated import two_source_writes
from tests.support.contract.writes import (
    SCHEMA,
    VECTOR_SPEC,
    corpus_writes,
    snapshot,
    write_all,
)

NEW_RELATION = "REVIEWS"


def test_schema_idempotent(stores: ContractStores) -> None:
    writes = corpus_writes(["D1"])
    write_all(stores, writes)
    counts, rows = stores.row_counts(), snapshot(stores, writes)

    stores.graph.ensure_schema(SCHEMA)
    stores.vectors.ensure_collections(VECTOR_SPEC)
    stores.open_graph().ensure_schema(SCHEMA)
    stores.open_vectors().ensure_collections(VECTOR_SPEC)

    assert stores.row_counts() == counts
    assert snapshot(stores, writes) == rows


def test_schema_additive(stores: ContractStores) -> None:
    d901 = two_source_writes(with_vectors=False)[0]
    [relation] = d901.relations
    reviews = dataclasses.replace(
        d901, relations=(dataclasses.replace(relation, type=NEW_RELATION),)
    )
    with pytest.raises(ConfigError, match=NEW_RELATION):
        stores.graph.write_documents([reviews])
    writes = corpus_writes(["D1"])
    write_all(stores, writes)
    rows = snapshot(stores, writes)

    stores.graph.ensure_schema(SCHEMA.merged(StoreSchema(relation_types=(NEW_RELATION,))))

    stores.graph.write_documents([reviews])
    [item] = stores.graph.get_items([relation.relation_id])
    assert item.type == NEW_RELATION
    assert snapshot(stores, writes) == rows
    # A schema that names only the new type adds to the recorded one, never replaces it.
    stores.graph.ensure_schema(StoreSchema(relation_types=(NEW_RELATION,)))
    write_all(stores, writes)
    assert snapshot(stores, writes) == rows


def test_layout_version_mismatch(stores: ContractStores, monkeypatch: pytest.MonkeyPatch) -> None:
    recorded = stores.layout_module.LAYOUT_VERSION
    monkeypatch.setattr(stores.layout_module, "LAYOUT_VERSION", recorded + 1)
    later = stores.open_graph()

    for call in (lambda: later.get_documents(["D1"]), lambda: later.ensure_schema(SCHEMA)):
        with pytest.raises(ConfigError) as refused:
            call()
        message = str(refused.value)
        assert f"version {recorded}" in message
        assert f"version {recorded + 1}" in message
        assert "new index id" in message

    # The store checked the layout when it opened the index, and keeps working.
    assert stores.graph.get_documents(["D1"]) == []


def test_calls_before_ensure_schema(stores: ContractStores) -> None:
    fresh = stores.open_graph(index_id=f"{stores.index_id}_fresh")

    for call in (
        lambda: fresh.get_documents(["D1"]),
        lambda: fresh.acquire_writer("other", ttl_s=60),
    ):
        with pytest.raises(StorageError, match="has no schema; call ensure_schema"):
            call()

    fresh.ensure_schema(SCHEMA)
    assert fresh.get_documents(["D1"]) == []
