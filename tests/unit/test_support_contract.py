"""The contract suite's fixture helpers must build what they claim, or the suite proves nothing.

Pins tests/support/contract/ (specs/003-stores-and-contract-suite,
contract-suite.md §2) as tests/unit/test_support_packs.py pins
tests/support/packs.py:
1. `corpus_writes` turns the committed corpus into one write per document,
   with the id recipes of engine brief §1, chunks split at blank lines,
   quotes and surfaces at their spans, and `norm()` text.
2. The statuses its writes carry, and those of `corpus_delete`, replay
   graph.json.
3. `edited_write`, `expected_counts`, `SCHEMA` and `VECTOR_SPEC`.
4. The generated data holds what its case needs, with fictional names only.
5. Both reference stores satisfy the protocols, for mypy as for `isinstance`.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import math
import re
from datetime import date

import pytest

from tenetrag.engine.text import norm
from tenetrag.packs import load_pack, store_schema
from tenetrag.protocols import (
    AttributeSource,
    CollectionSpec,
    DocumentWrite,
    EventEvidence,
    FactRow,
    GraphStore,
    RelationRow,
    StatusChange,
    VectorStore,
)
from tests.support.contract.generated import (
    pack_status_writes,
    recall_fixture,
    tone_mark_writes,
    two_source_writes,
)
from tests.support.contract.writes import (
    COUNTED_TABLES,
    SCHEMA,
    VECTOR_SPEC,
    corpus_delete,
    corpus_vectors,
    corpus_writes,
    edited_write,
    entity_id,
    expected_counts,
    expected_statuses,
    store_id,
)
from tests.support.packs import REPO_ROOT
from tests.support.reference import ReferenceDatabase, ReferenceGraphStore, ReferenceVectorStore

GENERATED = REPO_ROOT / "tests" / "fixtures" / "corpus" / "generated"
VI = ("vi",)
CORE = ["D1", "D2", "D5"]
EMAIL = re.compile(r"[\w.+-]+@([\w-]+(?:\.[\w-]+)*)")
FICTIONAL_COMPANIES = ("alpha", "beta", "gamma")


def sha(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()


def graph_json() -> dict[str, object]:
    graph: dict[str, object] = json.loads((GENERATED / "graph.json").read_text(encoding="utf-8"))
    return graph


def document_text(doc_id: str) -> str:
    return (GENERATED / "docs" / f"{doc_id}.md").read_text(encoding="utf-8")


def every_row(write: DocumentWrite) -> list[object]:
    return [
        *write.chunks,
        *write.entities,
        *write.aliases,
        *write.attribute_sources,
        *write.identity_blocks,
        *write.mentions,
        *write.relations,
        *write.events,
        *write.event_evidence,
        *write.facts,
        *write.roles,
        *write.text_in,
        *write.same_as,
        *(record for records in write.vectors.values() for record in records),
    ]


def quoted_spans(write: DocumentWrite) -> list[tuple[str, int, int, str]]:
    """(chunk id, start, end, text) for every quote and surface of the write."""
    rows: list[AttributeSource | RelationRow | FactRow | EventEvidence] = [
        *write.attribute_sources,
        *write.relations,
        *write.facts,
        *write.event_evidence,
    ]
    spans = [(row.chunk_id, row.quote_start, row.quote_end, row.quote) for row in rows]
    spans += [(row.chunk_id, row.start, row.end, row.surface) for row in write.mentions]
    return spans


# 1. Corpus writes


def test_corpus_writes_core():
    writes = corpus_writes(CORE)

    assert [write.document.doc_id for write in writes] == CORE
    for write in writes:
        assert write.run_id == "run-1"
        assert write.document.run_id == "run-1"
        assert all(getattr(row, "run_id", "run-1") == "run-1" for row in every_row(write))
        assert write.chunks
        assert write.entities
        assert write.mentions
        assert (
            write.document.content_hash
            == hashlib.sha256(
                (GENERATED / "docs" / f"{write.document.doc_id}.md").read_bytes()
            ).hexdigest()
        )


def test_ids_follow_the_recipes():
    """Engine brief §1, recomputed here, with world ids standing for resolved identities."""
    d1 = corpus_writes(["D1"])[0]
    chunk = d1.chunks[1]
    alpha = sha("Organization", "", norm("Công ty CP Alpha", languages=VI))
    finance = sha("Organization", alpha, norm("Phòng Tài chính", languages=VI))
    policy = sha("Policy", alpha, norm("Quy chế công tác phí", languages=VI), "1")
    (owner_of,) = [row for row in d1.relations if row.type == "OWNER_OF"]

    assert chunk.chunk_hash == hashlib.sha256(chunk.text.encode()).hexdigest()
    assert chunk.chunk_id == sha("D1", "1", chunk.chunk_hash)
    assert entity_id("alpha") == alpha
    assert {entity.entity_id for entity in d1.entities} >= {alpha, finance, policy}
    assert (owner_of.subject_id, owner_of.object_id) == (finance, policy)
    assert owner_of.chunk_id == chunk.chunk_id
    assert owner_of.relation_id == sha(
        chunk.chunk_id, "OWNER_OF", finance, policy, "{}", "2025-02-01", ""
    )
    assert store_id("D1.5") == owner_of.relation_id
    assert store_id("D1.2") == finance


def test_chunks_split_at_blank_lines():
    for write in corpus_writes(CORE):
        text = document_text(write.document.doc_id)

        assert [chunk.text for chunk in write.chunks] == text.rstrip("\n").split("\n\n")
        assert [chunk.ordinal for chunk in write.chunks] == list(range(len(write.chunks)))
        for chunk in write.chunks:
            assert text[chunk.start : chunk.end] == chunk.text
            assert chunk.doc_id == write.document.doc_id


def test_quotes_and_surfaces_at_their_spans():
    for write in corpus_writes():
        chunks = {chunk.chunk_id: chunk.text for chunk in write.chunks}
        for chunk_id, start, end, quoted in quoted_spans(write):
            assert chunks[chunk_id][start:end] == quoted


def test_norm_fields():
    """Every `*_norm` field is `norm()` of its source with the corpus's language (ADR 0025)."""
    for write in corpus_writes(CORE):
        document = write.document
        assert document.title is not None
        assert document.title_norm == norm(document.title, languages=VI)
        assert document.code_norm == (
            None if document.code is None else norm(document.code, languages=VI)
        )
        for chunk in write.chunks:
            assert chunk.text_norm == norm(chunk.text, languages=VI)
        for entity in write.entities:
            assert entity.name_norm == norm(entity.name, languages=VI)
        for alias in write.aliases:
            assert alias.alias_norm == norm(alias.alias, languages=VI)
        for source in write.attribute_sources:
            assert source.value_norm == norm(str(source.value), languages=VI)


def test_corpus_writes_all_in_order():
    writes = corpus_writes()

    assert [write.document.doc_id for write in writes] == [f"D{n}" for n in range(1, 42)]
    ids = [row.relation_id for write in writes for row in write.relations]
    ids += [row.fact_id for write in writes for row in write.facts]
    assert len(set(ids)) == len(ids)


# 2. Statuses


def as_status_map(members: list[dict[str, str]]) -> dict[str, tuple[str, date | None]]:
    return {
        store_id(member["item"]): (
            member["status"],
            date.fromisoformat(member["closed_at"]) if member["closed_at"] else None,
        )
        for member in members
    }


def test_expected_statuses_equal_graph_json():
    versions = graph_json()["versions"]
    assert isinstance(versions, dict)
    expected = {}
    for members in versions.values():
        expected.update(as_status_map(members))

    assert expected_statuses() == expected


def test_writes_carry_the_status_changes():
    """Applying each write's rows, then its status changes, ends at graph.json."""
    seen: dict[str, tuple[str, date | None]] = {}
    for write in corpus_writes():
        seen.update({row.relation_id: (row.status, row.closed_at) for row in write.relations})
        seen.update({row.fact_id: (row.status, row.closed_at) for row in write.facts})
        for change in write.status_changes:
            assert change.item_id in seen
            seen[change.item_id] = (change.status, change.closed_at)

    expected = expected_statuses()
    assert {item: seen[item] for item in expected} == expected
    assert {seen[item][0] for item in seen.keys() - expected.keys()} == {"current"}


@pytest.mark.parametrize("doc_id", ["D2", "D8", "D41"])
def test_corpus_delete_replays_graph_json(doc_id):
    deletions = graph_json()["deletions"]
    assert isinstance(deletions, dict)
    expected = {}
    for members in deletions[doc_id]["versions"].values():
        expected.update(as_status_map(members))

    delete = corpus_delete(doc_id)

    assert delete.doc_id == doc_id
    assert delete.run_id == "run-2"
    changes = delete.status_changes
    assert {change.item_id: (change.status, change.closed_at) for change in changes} == expected


def test_corpus_delete_over_written_documents():
    """D2 deleted after D1 and D2 only: D1's requirement is current again."""
    delete = corpus_delete("D2", written=["D1", "D2"])

    assert delete.status_changes == (
        StatusChange(item_id=store_id("D1.6"), status="current", closed_at=None),
    )


# 3. Vectors, edits, counts, schema


def test_vectors_on_the_write_or_apart():
    (with_vectors,) = corpus_writes(["D1"])
    (without,) = corpus_writes(["D1"], with_vectors=False)
    apart = corpus_vectors(["D1"])

    assert without.vectors == {}
    assert dataclasses.replace(with_vectors, vectors={}) == without
    assert set(with_vectors.vectors) == set(apart) == {"chunks", "entities", "chunk_questions"}
    for collection, records in apart.items():
        assert list(with_vectors.vectors[collection]) == records
        assert all(len(record.vector) == 8 for record in records)
    assert [record.id for record in apart["chunks"]] == [c.chunk_id for c in with_vectors.chunks]
    assert {record.id for record in apart["entities"]} == {
        entity.entity_id for entity in with_vectors.entities
    }
    for record in apart["chunks"]:
        assert math.isclose(math.fsum(x * x for x in record.vector), 1.0)
        assert record.doc_id == "D1"


def test_schema_and_vector_spec():
    spec = CollectionSpec(model_id="fake-embed", dimensions=8)

    assert store_schema(load_pack("enterprise-docs")) == SCHEMA
    assert (VECTOR_SPEC.chunks, VECTOR_SPEC.entities, VECTOR_SPEC.chunk_questions) == (
        spec,
        spec,
        spec,
    )


def test_edited_write_drops_the_last_chunk():
    (write,) = corpus_writes(["D1"])
    dropped = write.chunks[-1].chunk_id

    edited = edited_write(write, run_id="run-2")

    assert edited.chunks == tuple(
        dataclasses.replace(chunk, run_id="run-2") for chunk in write.chunks[:-1]
    )
    assert edited.document.content_hash != write.document.content_hash
    assert edited.run_id == "run-2"
    assert all(getattr(row, "run_id", "run-2") == "run-2" for row in every_row(edited))
    assert all(getattr(row, "chunk_id", None) != dropped for row in every_row(edited))
    assert dropped not in {record.id for record in edited.vectors["chunks"]}
    assert len(edited.facts) < len(write.facts)
    named = {mention.entity_id for mention in edited.mentions}
    named |= {row.target_id for row in edited.roles}
    named |= {end for row in edited.relations for end in (row.subject_id, row.object_id)}
    assert {entity.entity_id for entity in edited.entities} <= named
    assert {alias.entity_id for alias in edited.aliases} <= named


def test_expected_counts():
    writes = corpus_writes(CORE)

    counts = expected_counts(CORE)

    assert set(counts) == set(COUNTED_TABLES)
    assert counts["documents"] == 3
    assert counts["chunks"] == sum(len(write.chunks) for write in writes)
    assert counts["entities"] == len({e.entity_id for w in writes for e in w.entities})
    assert counts["aliases"] == len(
        {(a.entity_id, a.alias, a.origin) for w in writes for a in w.aliases}
    )
    assert counts["mentions"] == sum(len(write.mentions) for write in writes)
    assert counts["relations"] == sum(len(write.relations) for write in writes)
    assert counts["facts"] == sum(len(write.facts) for write in writes)
    assert counts["events"] == len({e.event_id for w in writes for e in w.events})
    assert counts["roles"] == sum(len(write.roles) for write in writes)
    assert counts["text_in"] == len(
        {(t.entity_id, t.doc_id, t.attribute) for w in writes for t in w.text_in}
    )
    assert counts["text_in"] == 3
    assert counts["same_as"] == counts["identity_blocks"] == 0


# 4. Generated data


def test_two_source_writes():
    first, second = two_source_writes()
    (one,), (other,) = first.relations, second.relations

    assert first.document.doc_id != second.document.doc_id
    assert (one.type, one.subject_id, one.object_id) == (
        other.type,
        other.subject_id,
        other.object_id,
    )
    assert one.relation_id != other.relation_id


def test_pack_status_writes():
    writes = pack_status_writes()
    facts = [fact for write in writes for fact in write.facts]
    events = [event for write in writes for event in write.events]

    assert any(
        fact.type == "ActionItem" and fact.attributes["status"] != fact.status for fact in facts
    )
    assert any(event.type == "Decision" and "status" in event.attributes for event in events)


def test_tone_mark_writes():
    writes = tone_mark_writes()
    names = {entity.name for write in writes for entity in write.entities}
    texts = " ".join(chunk.text for write in writes for chunk in write.chunks)

    for pair in (("Hoà", "Hòa"), ("Thuỷ", "Thủy")):
        assert norm(pair[0], languages=VI) == norm(pair[1], languages=VI)
        assert any(pair[0] in name or pair[1] in name for name in names)
    diacritics = ("Lãi", "Lại", "Lai")
    assert len({norm(word, languages=VI) for word in diacritics}) == 3
    for word in diacritics:
        assert any(name.endswith(word) for name in names)
    for text in ("lãi suất cho vay", "quay lại sau", "lai lịch nhân viên", "2.500.000 vnd/ngày"):
        assert text in texts
    assert "500 " not in texts.replace("2.500.000", "")


def test_recall_fixture():
    fixture = recall_fixture()

    assert len(fixture.records) == 3000
    assert len(fixture.queries) == len(fixture.top_10) == 30
    assert all(len(record.vector) == 64 for record in fixture.records)
    for query, top in list(zip(fixture.queries, fixture.top_10, strict=True))[:3]:
        scores = sorted(
            ((-math.fsum(a * b for a, b in zip(query, r.vector, strict=True)), r.id))
            for r in fixture.records
        )
        assert top == tuple(record_id for _, record_id in scores[:10])
    assert recall_fixture.__wrapped__() == fixture


def test_fictional_only():
    """As test_fictional_only checks the corpus: people and organizations sit under a
    fictional company, and every email uses the .example domain."""
    companies = {entity_id(name) for name in FICTIONAL_COMPANIES}
    writes = [*two_source_writes(), *pack_status_writes(), *tone_mark_writes()]
    for write in writes:
        for entity in write.entities:
            if entity.type in {"Organization", "Person"}:
                assert entity.entity_id in companies or companies & set(entity.scope_path), (
                    entity.name
                )
        texts = [chunk.text for chunk in write.chunks]
        domains = {match[1] for text in texts for match in EMAIL.finditer(text)}
        assert all(domain.endswith(".example") for domain in domains), domains


# 5. Reference stores


def test_reference_satisfies_protocols():
    database = ReferenceDatabase()
    vectors: VectorStore = ReferenceVectorStore(database, "t000000000000")
    graph: GraphStore = ReferenceGraphStore(database, "t000000000000")

    assert isinstance(graph, GraphStore)
    assert isinstance(vectors, VectorStore)
    assert vectors.capabilities.max_dimensions == 4096
