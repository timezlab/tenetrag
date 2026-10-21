"""Writes: counts, replay, read-back, pack attributes and two sources (data-model §10).

Cases `counts-after-write-and-replay`, `pack-attributes-apart` and
`one-of-two-sources`, on every backend of the `stores` fixture.
"""

from __future__ import annotations

import dataclasses
from typing import Any

import pytest

from tenetrag.protocols import (
    ConfigError,
    DocumentDelete,
    DocumentWrite,
    EntityRecord,
    EntityWrite,
    EventEvidence,
    Evidence,
    FactRow,
    ItemRecord,
    RelationRow,
    RoleRow,
    StorageError,
)
from tests.support.contract.backends import ContractStores
from tests.support.contract.generated import pack_status_writes, two_source_writes
from tests.support.contract.writes import (
    COUNTED_TABLES,
    DELETE_RUN_ID,
    RUN_ID,
    corpus_writes,
    count_rows,
    delete_all,
    expected_counts,
    snapshot,
    write_all,
)

REPLAY_RUN_ID = "run-2"


def _evidence(row: RelationRow | FactRow | EventEvidence) -> Evidence:
    return Evidence(
        doc_id=row.doc_id,
        chunk_id=row.chunk_id,
        quote=row.quote,
        quote_start=row.quote_start,
        quote_end=row.quote_end,
        quote_match=row.quote_match,
        observed_at=row.observed_at,
    )


def _expected_items(write: DocumentWrite) -> list[ItemRecord]:
    """The items of one document as `get_items` reads them (data-model §3.2)."""
    roles = sorted(write.roles, key=lambda role: (role.role, role.target_id))

    def owned(owner_id: str) -> tuple[RoleRow, ...]:
        return tuple(role for role in roles if role.owner_id == owner_id)

    def stated(row: RelationRow | FactRow) -> dict[str, Any]:
        return {
            "attributes": row.attributes,
            "valid_from": row.valid_from,
            "valid_to": row.valid_to,
            "valid_precision": row.valid_precision,
            "valid_source": row.valid_source,
            "observed_at": row.observed_at,
            "recorded_at": row.recorded_at,
            "status": row.status,
            "closed_at": row.closed_at,
            "version_key": row.version_key,
            "evidence": (_evidence(row),),
            "confidence": row.confidence,
            "pack": row.pack,
            "pack_version": row.pack_version,
            "run_id": row.run_id,
        }

    items = [
        ItemRecord(
            item_id=row.relation_id,
            kind="relation",
            type=row.type,
            subject_id=row.subject_id,
            object_id=row.object_id,
            roles=(),
            **stated(row),
        )
        for row in write.relations
    ]
    items += [
        ItemRecord(
            item_id=row.fact_id,
            kind="fact",
            type=row.type,
            subject_id=None,
            object_id=None,
            roles=owned(row.fact_id),
            **stated(row),
        )
        for row in write.facts
    ]
    for event in write.events:
        evidence = sorted(
            (row for row in write.event_evidence if row.event_id == event.event_id),
            key=lambda row: (row.doc_id, row.chunk_id, row.quote_start),
        )
        items.append(
            ItemRecord(
                item_id=event.event_id,
                kind="event",
                type=event.type,
                subject_id=None,
                object_id=None,
                roles=owned(event.event_id),
                attributes=event.attributes,
                valid_from=event.valid_from,
                valid_to=event.valid_to,
                valid_precision=event.valid_precision,
                valid_source=None,
                observed_at=None,
                recorded_at=None,
                status=None,
                closed_at=None,
                version_key=None,
                evidence=tuple(_evidence(row) for row in evidence),
                confidence=None,
                pack=event.pack,
                pack_version=event.pack_version,
                run_id=event.run_id,
            )
        )
    return sorted(items, key=lambda item: item.item_id)


def _expected_entity(entity: EntityWrite, write: DocumentWrite) -> EntityRecord:
    """The entity as read after only `write`, which gives each attribute one source."""
    sources = [row for row in write.attribute_sources if row.entity_id == entity.entity_id]
    attributes = {row.attribute: row.value for row in sources}
    assert len(attributes) == len(sources), "the fixture gives an attribute two sources"
    aliases = sorted(
        (row for row in write.aliases if row.entity_id == entity.entity_id),
        key=lambda row: (row.alias_norm, row.origin),
    )
    return EntityRecord(
        entity_id=entity.entity_id,
        type=entity.type,
        name=entity.name,
        name_norm=entity.name_norm,
        label=entity.label,
        scope_path=entity.scope_path,
        scope_source=entity.scope_source,
        attributes=attributes,
        identity=entity.identity,
        aliases=tuple(aliases),
        degree=0,
        run_id=entity.run_id,
    )


def _item_ids(writes: list[DocumentWrite]) -> list[str]:
    return sorted(
        {row.relation_id for write in writes for row in write.relations}
        | {row.fact_id for write in writes for row in write.facts}
        | {row.event_id for write in writes for row in write.events}
    )


def test_counts_after_write(stores: ContractStores) -> None:
    write_all(stores, corpus_writes(["D1", "D2", "D5"]))
    assert stores.row_counts() == expected_counts(["D1", "D2", "D5"])

    write_all(stores, corpus_writes())
    assert stores.row_counts() == expected_counts()


def test_replay_changes_no_count(stores: ContractStores) -> None:
    writes = corpus_writes(["D1", "D2", "D5"]) + pack_status_writes()
    write_all(stores, writes)
    counts, rows = stores.row_counts(), snapshot(stores, writes)

    replay = corpus_writes(["D1", "D2", "D5"], run_id=REPLAY_RUN_ID)
    replay += pack_status_writes(run_id=REPLAY_RUN_ID)
    write_all(stores, replay)

    assert stores.row_counts() == counts
    assert snapshot(stores, replay) == rows
    entity_ids = sorted({row.entity_id for write in writes for row in write.entities})
    entities = stores.graph.get_entities(entity_ids)
    assert {entity.run_id for entity in entities} == {RUN_ID}
    assert {alias.run_id for entity in entities for alias in entity.aliases} == {RUN_ID}
    items = stores.graph.get_items(_item_ids(writes))
    assert {item.run_id for item in items if item.kind == "event"} == {RUN_ID}
    assert {item.run_id for item in items if item.kind != "event"} == {REPLAY_RUN_ID}
    doc_ids = [write.document.doc_id for write in writes]
    assert {document.run_id for document in stores.graph.get_documents(doc_ids)} == {REPLAY_RUN_ID}


def test_records_read_back_equal(stores: ContractStores) -> None:
    [write] = corpus_writes(["D1"])
    write_all(stores, [write])
    graph = stores.graph

    assert graph.get_documents(["D1"]) == [write.document]
    chunk_ids = sorted(chunk.chunk_id for chunk in write.chunks)
    assert graph.get_chunks(chunk_ids) == sorted(write.chunks, key=lambda chunk: chunk.chunk_id)
    entities = sorted(write.entities, key=lambda entity: entity.entity_id)
    assert graph.get_entities([entity.entity_id for entity in entities]) == [
        _expected_entity(entity, write) for entity in entities
    ]
    assert graph.get_items(_item_ids([write])) == _expected_items(write)
    assert graph.entities_in_chunks(chunk_ids) == sorted(
        write.mentions, key=lambda mention: (mention.chunk_id, mention.start, mention.entity_id)
    )


def test_ids_and_text_kept(stores: ContractStores) -> None:
    [write] = corpus_writes(["D1"], with_vectors=False)
    first, *others = write.entities
    # Not what norm() gives: the store keeps what it is handed and normalizes nothing.
    odd = dataclasses.replace(first, name_norm="Quy Chế  KHÔNG Chuẩn Hoá ")
    write = dataclasses.replace(write, entities=(odd, *others))
    stores.graph.write_documents([write])

    [entity] = stores.graph.get_entities([odd.entity_id])
    assert entity.name_norm == odd.name_norm
    chunk_ids = [chunk.chunk_id for chunk in write.chunks]
    assert {(chunk.text, chunk.text_norm) for chunk in stores.graph.get_chunks(chunk_ids)} == {
        (chunk.text, chunk.text_norm) for chunk in write.chunks
    }
    assert stores.row_counts() == count_rows([write])
    assert set(stores.graph.document_states()) == {"D1"}
    assert {row.entity_id for row in stores.graph.entities_in_chunks(chunk_ids)} == {
        row.entity_id for row in write.mentions
    }
    assert stores.text_in_links() == {
        (row.entity_id, row.doc_id, row.attribute) for row in write.text_in
    }


def test_unknown_type_refused(stores: ContractStores) -> None:
    [d1] = corpus_writes(["D1"], with_vectors=False)
    [d903] = pack_status_writes(with_vectors=False)
    relation, *relations = d1.relations
    entity, *entities = d1.entities
    fact, *facts = d1.facts
    event, *events = d903.events
    refused = {
        "UNKNOWN_RELATION": dataclasses.replace(
            d1, relations=(dataclasses.replace(relation, type="UNKNOWN_RELATION"), *relations)
        ),
        "UnknownEntity": dataclasses.replace(
            d1, entities=(dataclasses.replace(entity, type="UnknownEntity"), *entities)
        ),
        "UnknownFact": dataclasses.replace(
            d1, facts=(dataclasses.replace(fact, type="UnknownFact"), *facts)
        ),
        "UnknownEvent": dataclasses.replace(
            d903, events=(dataclasses.replace(event, type="UnknownEvent"), *events)
        ),
    }
    for type_name, write in refused.items():
        with pytest.raises(ConfigError, match=type_name):
            stores.graph.write_documents([write])

    assert stores.row_counts() == dict.fromkeys(COUNTED_TABLES, 0)
    assert stores.graph.document_states() == {}


def test_vectors_follow_pairing(stores: ContractStores) -> None:
    [write] = corpus_writes(["D1"])
    if not stores.graph_writes_vectors:
        with pytest.raises(StorageError, match="vectors"):
            stores.graph.write_documents([write])
        assert stores.graph.document_states() == {}
        return

    stores.graph.write_documents([write])
    for collection, records in write.vectors.items():
        ids = sorted(record.id for record in records)
        assert sorted(stores.vectors.get_vectors(collection, ids)) == ids


def test_pack_attributes_apart(stores: ContractStores) -> None:
    [write] = pack_status_writes()
    write_all(stores, [write])

    items = stores.graph.get_items(_item_ids([write]))
    assert items == _expected_items(write)
    [action] = [item for item in items if item.type == "ActionItem"]
    assert (action.attributes["status"], action.status) == ("done", "current")
    [decision] = [item for item in items if item.type == "Decision"]
    assert (decision.attributes["status"], decision.status) == ("approved", None)


def test_one_of_two_sources(stores: ContractStores) -> None:
    d901, d902 = two_source_writes()
    write_all(stores, [d901, d902])
    [kept], [gone] = d902.relations, d901.relations
    both = sorted([kept.relation_id, gone.relation_id])
    assert [item.item_id for item in stores.graph.get_items(both)] == both

    delete_all(stores, [DocumentDelete(doc_id="D901", run_id=DELETE_RUN_ID)])

    [item] = stores.graph.get_items(both)
    assert item.item_id == kept.relation_id
    assert [evidence.doc_id for evidence in item.evidence] == ["D902"]
    ends = sorted([kept.subject_id, kept.object_id])
    assert [entity.entity_id for entity in stores.graph.get_entities(ends)] == ends
