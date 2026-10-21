"""Provenance and reads by id (data-model §10, contracts/protocols.md §2).

Case `provenance-reachability`. D1, D2 and D5 hold no event, so D903 joins
them to cover event evidence.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from tests.support.contract.backends import ContractStores
from tests.support.contract.generated import pack_status_writes
from tests.support.contract.writes import corpus_writes


def test_every_item_reaches_its_chunks_and_documents(stores: ContractStores) -> None:
    writes = corpus_writes(["D1", "D2", "D5"], with_vectors=False)
    writes += pack_status_writes(with_vectors=False)
    stores.graph.write_documents(writes)
    item_ids = sorted(
        {row.relation_id for write in writes for row in write.relations}
        | {row.fact_id for write in writes for row in write.facts}
        | {row.event_id for write in writes for row in write.events}
    )

    items = stores.graph.get_items(item_ids)

    assert [item.item_id for item in items] == item_ids
    chunk_ids = sorted(
        {evidence.chunk_id for item in items for evidence in item.evidence}
        | {role.chunk_id for item in items for role in item.roles}
    )
    chunks = {chunk.chunk_id: chunk for chunk in stores.graph.get_chunks(chunk_ids)}
    assert sorted(chunks) == chunk_ids
    doc_ids = sorted({chunk.doc_id for chunk in chunks.values()})
    assert [document.doc_id for document in stores.graph.get_documents(doc_ids)] == doc_ids
    for item in items:
        assert item.evidence, f"{item.kind} {item.item_id} has no evidence"
        for evidence in item.evidence:
            chunk = chunks[evidence.chunk_id]
            assert chunk.doc_id == evidence.doc_id
            assert chunk.text[evidence.quote_start : evidence.quote_end] == evidence.quote
        for role in item.roles:
            assert chunks[role.chunk_id].doc_id == role.doc_id


def test_entities_in_chunks_order(stores: ContractStores) -> None:
    writes = corpus_writes(["D1", "D2", "D5"], with_vectors=False)
    stores.graph.write_documents(writes)
    chunk_ids = [chunk.chunk_id for write in writes for chunk in write.chunks]

    mentions = stores.graph.entities_in_chunks([*reversed(chunk_ids), "no-such-chunk"])

    assert mentions == sorted(
        (row for write in writes for row in write.mentions),
        key=lambda row: (row.chunk_id, row.start, row.entity_id),
    )
    assert stores.graph.entities_in_chunks([]) == []


def test_reads_by_id(stores: ContractStores) -> None:
    writes = corpus_writes(["D1", "D2"], with_vectors=False)
    stores.graph.write_documents(writes)
    graph = stores.graph
    reads: list[tuple[Callable[[Sequence[str]], Sequence[object]], str, list[str]]] = [
        (graph.get_documents, "doc_id", [write.document.doc_id for write in writes]),
        (graph.get_chunks, "chunk_id", [row.chunk_id for write in writes for row in write.chunks]),
        (
            graph.get_entities,
            "entity_id",
            [row.entity_id for write in writes for row in write.entities],
        ),
        (
            graph.get_items,
            "item_id",
            [row.relation_id for write in writes for row in write.relations]
            + [row.fact_id for write in writes for row in write.facts],
        ),
    ]
    for read, key, ids in reads:
        wanted = sorted(set(ids))
        records = read([*reversed(wanted), "no-such-id", wanted[0]])
        assert [getattr(record, key) for record in records] == wanted, read.__name__
        assert read([]) == [], read.__name__
