"""The vector store (protocols.md §3): recall, scores, filters, collections and writes.

Cases `recall-floor` (SC-010), `vector-scores`, `collection-change` and
`exclude-run` (vectors). Scores are compared only on the three reference
vectors, within 1e-3 (contract-suite.md §3).
"""

from __future__ import annotations

import math

import pytest

from tenetrag.protocols import (
    Collection,
    CollectionSpec,
    ConfigError,
    QueryError,
    VectorFilter,
    VectorRecord,
    VectorSpec,
)
from tests.support.contract.backends import ContractStores
from tests.support.contract.generated import (
    RECALL_DIMENSIONS,
    RECALL_K,
    recall_fixture,
)
from tests.support.contract.writes import VECTOR_SPEC, corpus_writes, write_all

RECALL_FLOOR = 0.9
SCORE_TOLERANCE = 1e-3
VECTOR_TOLERANCE = 1e-6
DIMENSIONS = VECTOR_SPEC.chunks.dimensions


def _spec(model_id: str, dimensions: int) -> VectorSpec:
    collection = CollectionSpec(model_id=model_id, dimensions=dimensions)
    return VectorSpec(chunks=collection, entities=collection, chunk_questions=collection)


def _padded(*values: float) -> tuple[float, ...]:
    return values + (0.0,) * (DIMENSIONS - len(values))


def _record(
    record_id: str,
    vector: tuple[float, ...],
    *,
    doc_id: str | None = None,
    type: str | None = None,
    language: str | None = None,
    run_id: str = "run-1",
    text_norm: str | None = None,
) -> VectorRecord:
    return VectorRecord(
        id=record_id,
        vector=vector,
        doc_id=doc_id,
        type=type,
        language=language,
        run_id=run_id,
        text_norm=text_norm,
    )


def test_recall_floor(stores: ContractStores) -> None:
    fixture = recall_fixture()
    vectors = stores.open_vectors(index_id=f"{stores.index_id}_recall")
    vectors.ensure_collections(_spec("fake-embed", RECALL_DIMENSIONS))
    vectors.upsert("chunks", fixture.records)

    results = vectors.search("chunks", fixture.queries, RECALL_K, None)

    found = sum(
        len({hit.id for hit in hits} & set(top))
        for hits, top in zip(results, fixture.top_10, strict=True)
    )
    recall = found / (RECALL_K * len(fixture.queries))
    print(f"recall@{RECALL_K} on {stores.backend}: {recall:.3f}")
    assert recall >= RECALL_FLOOR


def test_scores_are_cosine(stores: ContractStores) -> None:
    v1, v2, v3 = _padded(1.0, 2.0), _padded(2.0, -1.0), _padded(-1.0, -2.0)
    stores.vectors.upsert("entities", [_record("v1", v1), _record("v2", v2), _record("v3", v3)])
    query = tuple(3 * value for value in v1)

    [hits] = stores.vectors.search("entities", [query], 3, None)

    def cosine(vector: tuple[float, ...]) -> float:
        dot = math.fsum(a * b for a, b in zip(query, vector, strict=True))
        return dot / (math.hypot(*query) * math.hypot(*vector))

    assert [hit.id for hit in hits] == ["v1", "v2", "v3"]
    for hit, vector in zip(hits, (v1, v2, v3), strict=True):
        assert hit.score == pytest.approx(cosine(vector), abs=SCORE_TOLERANCE)


def test_search_shape(stores: ContractStores) -> None:
    [write] = corpus_writes(["D1"])
    write_all(stores, [write])
    records = write.vectors["chunks"]
    k = 3

    results = stores.vectors.search("chunks", [record.vector for record in records], k, None)

    assert len(results) == len(records)
    for record, hits in zip(records, results, strict=True):
        assert [hits] == stores.vectors.search("chunks", [record.vector], k, None)
        assert 0 < len(hits) <= k
        assert record.id in {hit.id for hit in hits}
        assert [hit.score for hit in hits] == sorted((hit.score for hit in hits), reverse=True)
        assert all(-1 - SCORE_TOLERANCE <= hit.score <= 1 + SCORE_TOLERANCE for hit in hits)
        assert {hit.doc_id for hit in hits} == {"D1"}
    for bad_k in (0, 1001):
        with pytest.raises(ValueError, match="k is"):
            stores.vectors.search("chunks", [records[0].vector], bad_k, None)
        with pytest.raises(ValueError, match="k is"):
            stores.vectors.search_text("chunks", "quy chế", bad_k, None)


def test_collection_change_refused(stores: ContractStores) -> None:
    other = stores.open_vectors()
    for spec in (_spec("other-embed", DIMENSIONS), _spec("fake-embed", 2 * DIMENSIONS)):
        with pytest.raises(ConfigError) as refused:
            other.ensure_collections(spec)
        message = str(refused.value)
        for named in ("chunks", "fake-embed", spec.chunks.model_id, "new index id"):
            assert named in message
        assert f"{DIMENSIONS} " in message
        assert f"{spec.chunks.dimensions} " in message


def test_dimensions_over_maximum(stores: ContractStores) -> None:
    wide = stores.open_vectors(index_id=f"{stores.index_id}_wide")
    maximum = wide.capabilities.max_dimensions

    with pytest.raises(ConfigError) as refused:
        wide.ensure_collections(_spec("wide-embed", maximum + 1))

    message = str(refused.value)
    assert f"{maximum + 1} dimensions exceed the {maximum}" in message
    assert "choose a smaller embedding model" in message


def test_wrong_length_writes_nothing(stores: ContractStores) -> None:
    good = [_record("a", _padded(1.0)), _record("c", _padded(0.0, 1.0))]
    short = _record("b", (1.0,) * (DIMENSIONS - 1))

    with pytest.raises(QueryError, match="'b'"):
        stores.vectors.upsert("chunks", [good[0], short, good[1]])

    assert stores.vectors.get_vectors("chunks", ["a", "b", "c"]) == {}


def _filter_records() -> tuple[list[VectorRecord], list[VectorRecord]]:
    chunks = [
        _record("c1", _padded(1.0, 0.1), doc_id="A", language="vi", text_norm="alpha một"),
        _record(
            "c2",
            _padded(1.0, 0.2),
            doc_id="A",
            language="en",
            run_id="run-2",
            text_norm="alpha one",
        ),
        _record(
            "c3",
            _padded(1.0, 0.3),
            doc_id="B",
            language="vi",
            run_id="run-2",
            text_norm="alpha hai",
        ),
    ]
    entities = [
        _record("e1", _padded(1.0, 0.1), type="Person"),
        _record("e2", _padded(1.0, 0.2), type="Organization", run_id="run-2"),
    ]
    return chunks, entities


def test_filters(stores: ContractStores) -> None:
    chunks, entities = _filter_records()
    stores.vectors.upsert("chunks", chunks)
    stores.vectors.upsert("entities", entities)
    query = _padded(1.0)

    def found(collection: Collection, where: VectorFilter | None) -> set[str]:
        [hits] = stores.vectors.search(collection, [query], 10, where)
        return {hit.id for hit in hits}

    assert found("chunks", None) == {"c1", "c2", "c3"}
    assert found("chunks", VectorFilter()) == {"c1", "c2", "c3"}
    assert found("chunks", VectorFilter(doc_ids=("A",))) == {"c1", "c2"}
    assert found("chunks", VectorFilter(languages=("vi",))) == {"c1", "c3"}
    assert found("chunks", VectorFilter(doc_ids=("A",), languages=("vi",))) == {"c1"}
    assert found("chunks", VectorFilter(doc_ids=())) == set()
    assert found("chunks", VectorFilter(languages=())) == set()
    assert found("entities", VectorFilter(types=("Person",))) == {"e1"}
    assert found("entities", VectorFilter(types=())) == set()


def test_exclude_run(stores: ContractStores) -> None:
    chunks, entities = _filter_records()
    stores.vectors.upsert("chunks", chunks)
    stores.vectors.upsert("entities", entities)
    where = VectorFilter(exclude_run="run-2")

    [chunk_hits] = stores.vectors.search("chunks", [_padded(1.0)], 10, where)
    [entity_hits] = stores.vectors.search("entities", [_padded(1.0)], 10, where)
    text_hits = stores.vectors.search_text("chunks", "alpha", 10, where)

    assert {hit.id for hit in chunk_hits} == {"c1"}
    assert {hit.id for hit in entity_hits} == {"e1"}
    assert {hit.id for hit in text_hits} == {"c1"}
    all_text = stores.vectors.search_text("chunks", "alpha", 10, None)
    assert {hit.id for hit in all_text} == {"c1", "c2", "c3"}


def test_upsert_delete_and_read(stores: ContractStores) -> None:
    chunks, _ = _filter_records()
    stores.vectors.upsert("chunks", chunks)
    moved = _record("c1", _padded(0.5, -0.5, 0.25), doc_id="A", language="vi", text_norm="một")

    stores.vectors.upsert("chunks", [moved])

    read = stores.vectors.get_vectors("chunks", ["c3", "c1", "no-such-id"])
    assert sorted(read) == ["c1", "c3"]
    assert read["c1"] == pytest.approx(list(moved.vector), abs=VECTOR_TOLERANCE)
    assert read["c3"] == pytest.approx(list(chunks[2].vector), abs=VECTOR_TOLERANCE)
    assert stores.vectors.get_vectors("chunks", []) == {}
    assert {hit.id for hit in stores.vectors.search_text("chunks", "alpha", 10, None)} == {
        "c2",
        "c3",
    }

    stores.vectors.delete("chunks", ["c1", "no-such-id"])
    assert sorted(stores.vectors.get_vectors("chunks", ["c1", "c2", "c3"])) == ["c2", "c3"]
    stores.vectors.delete_documents("chunks", ["B", "no-such-doc"])
    assert sorted(stores.vectors.get_vectors("chunks", ["c1", "c2", "c3"])) == ["c2"]
