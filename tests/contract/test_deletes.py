"""Deletes: end state, orphans, sources and `text_in` links (data-model §10).

Cases `end-state-after-delete`, `orphan-cleanup`,
`sources-deleted-with-document` and `text-in-added-and-removed`. The corpus
has no identity blocks, no `same_as` links and no link written from the
entity side, so these tests add them to corpus writes.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterable
from datetime import date

from tenetrag.engine.text import norm
from tenetrag.protocols import (
    AttributeSource,
    ChunkRecord,
    DocumentDelete,
    DocumentWrite,
    IdentityBlock,
    SameAsLink,
    StatusChange,
    TextInLink,
)
from tests.support.contract.backends import ContractStores
from tests.support.contract.writes import (
    COUNTED_TABLES,
    DELETE_RUN_ID,
    LANGUAGES,
    RUN_ID,
    corpus_delete,
    corpus_writes,
    count_rows,
    delete_all,
    edited_write,
    entity_id,
    expected_counts,
    expected_statuses,
    question_id,
    store_id,
    write_all,
)

EDIT_RUN_ID = "run-2"
HEADING = "QUY CHẾ CÔNG TÁC PHÍ"


def _alias_count(writes: Iterable[DocumentWrite], alive: set[str]) -> int:
    """Alias rows go only with their entity, so every alias of a living entity stays."""
    return len(
        {
            (row.entity_id, row.alias, row.origin)
            for write in writes
            for row in write.aliases
            if row.entity_id in alive
        }
    )


def _links(writes: Iterable[DocumentWrite]) -> set[tuple[str, str, str]]:
    return {(row.entity_id, row.doc_id, row.attribute) for write in writes for row in write.text_in}


def _same_as(first: str, second: str) -> SameAsLink:
    entity_a, entity_b = sorted([first, second])
    return SameAsLink(
        entity_a=entity_a,
        entity_b=entity_b,
        score=0.9,
        origin="embedding",
        status="candidate",
        run_id=RUN_ID,
    )


def _source(
    entity: str,
    attribute: str,
    value: str,
    *,
    chunk: ChunkRecord,
    quote: str,
    observed_at: date | None,
) -> AttributeSource:
    start = chunk.text.index(quote)
    return AttributeSource(
        entity_id=entity,
        attribute=attribute,
        value=value,
        value_norm=norm(value, languages=LANGUAGES),
        doc_id=chunk.doc_id,
        chunk_id=chunk.chunk_id,
        quote=quote,
        quote_start=start,
        quote_end=start + len(quote),
        observed_at=observed_at,
        run_id=RUN_ID,
    )


def _block(entity: str, candidate: str, chunk: ChunkRecord) -> IdentityBlock:
    return IdentityBlock(
        entity_id=entity,
        candidate_id=candidate,
        attribute="version_label",
        value="1",
        candidate_value="2",
        quote=chunk.text,
        candidate_quote=chunk.text,
        doc_id=chunk.doc_id,
        chunk_id=chunk.chunk_id,
        run_id=RUN_ID,
    )


def test_delete_all_leaves_nothing(stores: ContractStores) -> None:
    writes = corpus_writes(["D1", "D2", "D5"])
    write_all(stores, writes)

    delete_all(
        stores,
        [
            corpus_delete("D5", written=["D1", "D2", "D5"]),
            corpus_delete("D2", written=["D1", "D2"]),
            corpus_delete("D1", written=["D1"]),
        ],
    )

    assert stores.row_counts() == dict.fromkeys(COUNTED_TABLES, 0)
    assert stores.graph.document_states() == {}
    for collection in ("chunks", "entities", "chunk_questions"):
        ids = sorted({record.id for write in writes for record in write.vectors[collection]})
        assert stores.vectors.get_vectors(collection, ids) == {}


def test_delete_d2_end_state(stores: ContractStores) -> None:
    writes = d1, d2, d5 = corpus_writes(["D1", "D2", "D5"])
    write_all(stores, writes)

    delete_all(stores, [corpus_delete("D2", written=["D1", "D2", "D5"])])

    graph = stores.graph
    statuses = expected_statuses(["D1", "D5"])
    assert statuses[store_id("D1.6")] == ("current", None)
    assert {
        item.item_id: (item.status, item.closed_at) for item in graph.get_items(sorted(statuses))
    } == statuses
    assert graph.get_documents(["D2"]) == []
    assert graph.get_chunks([chunk.chunk_id for chunk in d2.chunks]) == []
    d2_items = [row.relation_id for row in d2.relations] + [row.fact_id for row in d2.facts]
    assert graph.get_items(d2_items) == []
    alive = {row.entity_id for write in (d1, d5) for row in write.entities}
    only_d2 = sorted({row.entity_id for row in d2.entities} - alive)
    assert only_d2 == [entity_id("alpha.ctp.v2")]
    assert graph.get_entities(only_d2) == []
    assert graph.entities_in_chunks([chunk.chunk_id for chunk in d1.chunks]) == sorted(
        d1.mentions, key=lambda row: (row.chunk_id, row.start, row.entity_id)
    )
    assert stores.row_counts() == {
        **expected_counts(["D1", "D5"]),
        "aliases": _alias_count(writes, alive),
    }


def test_orphans_after_edit(stores: ContractStores) -> None:
    [d1] = corpus_writes(["D1"])
    [metric] = [row for row in d1.entities if row.type == "Metric"]
    [office] = [row for row in d1.entities if row.name == "Phòng Tài chính"]
    with_identity = dataclasses.replace(metric, identity={"code": ("met.luu-tru",)})
    augmented = dataclasses.replace(
        d1,
        entities=tuple(with_identity if row is metric else row for row in d1.entities),
        same_as=(_same_as(metric.entity_id, office.entity_id),),
    )
    write_all(stores, [augmented])
    assert stores.row_counts()["same_as"] == 1

    edited = edited_write(augmented, run_id=EDIT_RUN_ID)
    alive = {row.entity_id for row in edited.entities}
    assert metric.entity_id not in alive, "the edit no longer orphans the Metric"
    write_all(stores, [edited])

    assert stores.graph.get_entities([metric.entity_id]) == []
    assert stores.row_counts() == {
        **count_rows([edited]),
        "aliases": _alias_count([augmented], alive),
    }
    dropped = d1.chunks[-1].chunk_id
    assert stores.vectors.get_vectors("chunks", [dropped]) == {}
    assert stores.vectors.get_vectors("chunk_questions", [question_id(dropped)]) == {}
    assert stores.vectors.get_vectors("entities", [metric.entity_id]) == {}


def test_orphans_after_delete(stores: ContractStores) -> None:
    d1, d2 = corpus_writes(["D1", "D2"])
    v1, v2 = entity_id("alpha.ctp.v1"), entity_id("alpha.ctp.v2")
    heading = d1.chunks[0]
    # D1 again, with rows hanging on ctp.v2 that D2's step 1 does not remove.
    hanging = dataclasses.replace(
        d1,
        attribute_sources=(
            *d1.attribute_sources,
            _source(
                v2,
                "title",
                "Quy chế công tác phí",
                chunk=heading,
                quote=HEADING,
                observed_at=d1.document.doc_date,
            ),
        ),
        identity_blocks=(_block(v1, v2, heading),),
        text_in=(
            *d1.text_in,
            TextInLink(entity_id=v2, doc_id="D1", attribute="title", run_id=RUN_ID),
        ),
        same_as=(_same_as(v1, v2),),
    )
    write_all(stores, [d1, d2, hanging])
    counts = stores.row_counts()
    assert (counts["same_as"], counts["identity_blocks"]) == (1, 1)

    delete_all(stores, [corpus_delete("D2", written=["D1", "D2"])])

    assert stores.graph.get_entities([v2]) == []
    alive = {row.entity_id for row in d1.entities}
    assert stores.row_counts() == {**count_rows([d1]), "aliases": _alias_count([d1, d2], alive)}
    assert stores.text_in_links() == _links([d1])
    assert stores.vectors.get_vectors("entities", [v2]) == {}


def test_sources_deleted_with_document(stores: ContractStores) -> None:
    d1, d2 = corpus_writes(["D1", "D2"])
    v1, v2 = entity_id("alpha.ctp.v1"), entity_id("alpha.ctp.v2")
    assert not [row for row in d2.attribute_sources if row.entity_id == v1]
    heading, *_, last = d2.chunks
    newer, same_day = date(2026, 1, 5), date(2025, 1, 10)
    by_chunk = [
        _source(v1, "code", value, chunk=chunk, quote=chunk.text[:7], observed_at=newer)
        for value, chunk in (("from-heading", heading), ("from-last", last))
    ]
    extra = (
        # Newer than D1's sources: wins.
        _source(v1, "title", HEADING, chunk=heading, quote=HEADING, observed_at=newer),
        # No date: loses to D1's dated source.
        _source(v1, "version_label", "9", chunk=heading, quote=HEADING, observed_at=None),
        # The same day as D1's: D1 wins on doc_id.
        _source(v1, "issued_on", "2099-01-01", chunk=heading, quote=HEADING, observed_at=same_day),
        # The same day and document: the smaller chunk_id wins, then the smaller quote_start.
        *by_chunk,
        _source(v1, "note", "second", chunk=last, quote="phiên bản", observed_at=newer),
        _source(v1, "note", "first", chunk=last, quote="Quy chế", observed_at=newer),
    )
    augmented = dataclasses.replace(
        d2,
        attribute_sources=d2.attribute_sources + extra,
        identity_blocks=(_block(v1, v2, last),),
    )
    write_all(stores, [d1, augmented])

    [entity] = stores.graph.get_entities([v1])
    assert entity.attributes == {
        "title": HEADING,
        "version_label": "1",
        "issued_on": "2025-01-10",
        "effective_from": "2025-02-01",
        "code": min(by_chunk, key=lambda row: row.chunk_id).value,
        "note": "first",
    }
    assert stores.row_counts()["identity_blocks"] == 1

    delete_all(stores, [corpus_delete("D2", written=["D1", "D2"])])

    [entity] = stores.graph.get_entities([v1])
    assert entity.attributes == {
        row.attribute: row.value for row in d1.attribute_sources if row.entity_id == v1
    }
    counts = stores.row_counts()
    assert (counts["attribute_sources"], counts["identity_blocks"]) == (
        len(d1.attribute_sources),
        0,
    )


def test_text_in_added_and_removed(stores: ContractStores) -> None:
    written = ["D1", "D2", "D5"]
    writes = d1, d2, d5 = corpus_writes(written)
    v2 = entity_id("alpha.ctp.v2")
    link = TextInLink(entity_id=v2, doc_id="D5", attribute="title", run_id=RUN_ID)
    write_all(stores, writes)

    # From the entity side: D2 names ctp.v2, and the link names D5. D5 goes, ctp.v2 stays.
    write_all(stores, [dataclasses.replace(d2, text_in=(*d2.text_in, link))])
    assert stores.text_in_links() == _links(writes) | {(v2, "D5", "title")}
    delete_all(stores, [corpus_delete("D5", written=written)])
    assert stores.text_in_links() == _links([d1, d2])
    assert [row.entity_id for row in stores.graph.get_entities([v2])] == [v2]

    # From the document side: D5 holds ctp.v2's text. ctp.v2 goes with D2, D5 stays.
    write_all(stores, [dataclasses.replace(d5, text_in=(*d5.text_in, link))])
    assert stores.text_in_links() == _links(writes) | {(v2, "D5", "title")}
    delete_all(stores, [corpus_delete("D2", written=written)])
    assert stores.graph.get_entities([v2]) == []
    assert stores.text_in_links() == _links([d1, d5])
    assert sorted(stores.graph.document_states()) == ["D1", "D5"]


def test_unknown_delete(stores: ContractStores) -> None:
    write_all(stores, corpus_writes(["D1", "D2"]))
    counts, states = stores.row_counts(), stores.graph.document_states()

    delete_all(stores, [DocumentDelete(doc_id="D404", run_id=DELETE_RUN_ID)])
    assert (stores.row_counts(), stores.graph.document_states()) == (counts, states)

    r1 = store_id("D1.6")
    change = StatusChange(item_id=r1, status="current", closed_at=None)
    delete_all(
        stores, [DocumentDelete(doc_id="D404", status_changes=(change,), run_id=DELETE_RUN_ID)]
    )
    [item] = stores.graph.get_items([r1])
    assert (item.status, item.closed_at) == ("current", None)
    assert (stores.row_counts(), stores.graph.document_states()) == (counts, states)
