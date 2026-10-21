"""The reference vector store (research R19): exact cosine and the R6 full-text rule.

The write functions take an index's `Tables`, so the paired graph store
applies them to its unit's copy and the vectors commit with the unit
(stores.md §3.3).
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable, Sequence
from typing import Final

from tenetrag.protocols import (
    Collection,
    CollectionSpec,
    ConfigError,
    Hit,
    QueryError,
    StorageError,
    VectorCapabilities,
    VectorFilter,
    VectorRecord,
    VectorSpec,
)
from tenetrag.protocols.stores import LIMIT_MAX
from tests.support.reference.database import ReferenceDatabase, Tables

# The larger of the real backends' limits (Neo4j), so no fixture fits one and not the other.
MAX_DIMENSIONS: Final = 4096

# Research R6: runs of characters other than letters, digits, `.` and `,` split
# syllables, and so does a `.` or `,` not between two digits.
_SPLIT: Final = re.compile(r"(?:[^\w.,]|_)+|(?<!\d)[.,]|[.,](?!\d)")


def syllables(text_norm: str) -> set[str]:
    """The distinct syllables of R6's split, as Postgres and Neo4j index them."""
    return set(_SPLIT.sub(" ", text_norm).split())


def check_k(k: int) -> None:
    if not 1 <= k <= LIMIT_MAX:
        raise ValueError(f"k is {k}; use 1 to {LIMIT_MAX}")


def collection_spec(tables: Tables, collection: Collection, index_id: str) -> CollectionSpec:
    spec = tables.collections.get(collection)
    if spec is None:
        raise StorageError(
            f"index `{index_id}` has no vector collection '{collection}'; call ensure_collections"
        )
    return spec


def upsert_vectors(
    tables: Tables, collection: Collection, records: Sequence[VectorRecord], index_id: str
) -> None:
    """Every length is checked before any record is written."""
    spec = collection_spec(tables, collection, index_id)
    for record in records:
        if len(record.vector) != spec.dimensions:
            raise QueryError(
                f"Vector '{record.id}' has {len(record.vector)} dimensions, and collection "
                f"'{collection}' of index `{index_id}` holds {spec.dimensions}; "
                f"embed it with {spec.model_id}"
            )
    rows = tables.vectors.setdefault(collection, {})
    for record in records:
        rows[record.id] = record


def delete_vectors(tables: Tables, collection: Collection, ids: Iterable[str]) -> None:
    rows = tables.vectors.get(collection, {})
    for record_id in ids:
        rows.pop(record_id, None)


def delete_document_vectors(tables: Tables, collection: Collection, doc_ids: Iterable[str]) -> None:
    gone = set(doc_ids)
    rows = tables.vectors.get(collection, {})
    for record_id in [key for key, record in rows.items() if record.doc_id in gone]:
        del rows[record_id]


def _passes(record: VectorRecord, where: VectorFilter | None) -> bool:
    if where is None:
        return True
    return (
        (where.types is None or record.type in where.types)
        and (where.languages is None or record.language in where.languages)
        and (where.doc_ids is None or record.doc_id in where.doc_ids)
        and (where.exclude_run is None or record.run_id != where.exclude_run)
    )


def _cosine(query: Sequence[float], vector: Sequence[float]) -> float:
    norms = math.hypot(*query) * math.hypot(*vector)
    if norms == 0:
        return 0.0
    return math.fsum(a * b for a, b in zip(query, vector, strict=True)) / norms


class ReferenceVectorStore:
    capabilities: VectorCapabilities

    def __init__(self, db: ReferenceDatabase, index_id: str) -> None:
        self._db = db
        self._index_id = index_id
        self.capabilities = VectorCapabilities(
            text_search=True,
            fused_hybrid_only=False,
            eventual_sync=False,
            max_dimensions=MAX_DIMENSIONS,
        )

    def ensure_collections(self, spec: VectorSpec) -> None:
        wanted: dict[Collection, CollectionSpec] = {
            "chunks": spec.chunks,
            "entities": spec.entities,
            "chunk_questions": spec.chunk_questions,
        }
        for collection_wanted in wanted.values():
            if collection_wanted.dimensions > MAX_DIMENSIONS:
                raise ConfigError(
                    f"{collection_wanted.dimensions} dimensions exceed the {MAX_DIMENSIONS} that "
                    "the reference vector store can index; choose a smaller embedding model or "
                    "another vector connection"
                )
        with self._db.lock:
            tables = self._db.tables(self._index_id)
            for collection, collection_wanted in wanted.items():
                recorded = tables.collections.get(collection)
                if recorded is not None and recorded != collection_wanted:
                    raise ConfigError(
                        f"Vector collection '{collection}' of index `{self._index_id}` holds "
                        f"{recorded.model_id} vectors of {recorded.dimensions} dimensions, and "
                        f"the profile asks for {collection_wanted.model_id} with "
                        f"{collection_wanted.dimensions} dimensions; rebuild under a new index id"
                    )
            tables.collections.update(wanted)

    def upsert(self, collection: Collection, records: Sequence[VectorRecord]) -> None:
        with self._db.lock:
            upsert_vectors(self._db.tables(self._index_id), collection, records, self._index_id)

    def delete(self, collection: Collection, ids: Sequence[str]) -> None:
        with self._db.lock:
            delete_vectors(self._db.tables(self._index_id), collection, ids)

    def delete_documents(self, collection: Collection, doc_ids: Sequence[str]) -> None:
        with self._db.lock:
            delete_document_vectors(self._db.tables(self._index_id), collection, doc_ids)

    def search(
        self,
        collection: Collection,
        vectors: Sequence[Sequence[float]],
        k: int,
        where: VectorFilter | None,
    ) -> list[list[Hit]]:
        check_k(k)
        with self._db.lock:
            tables = self._db.tables(self._index_id)
            spec = collection_spec(tables, collection, self._index_id)
            rows = [r for r in tables.vectors.get(collection, {}).values() if _passes(r, where)]
        results = []
        for query in vectors:
            if len(query) != spec.dimensions:
                raise QueryError(
                    f"A query vector has {len(query)} dimensions, and collection '{collection}' "
                    f"of index `{self._index_id}` holds {spec.dimensions}; "
                    f"embed it with {spec.model_id}"
                )
            hits = [
                Hit(id=row.id, score=_cosine(query, row.vector), doc_id=row.doc_id) for row in rows
            ]
            results.append(sorted(hits, key=lambda hit: (-hit.score, hit.id))[:k])
        return results

    def search_text(
        self, collection: Collection, text_norm: str, k: int, where: VectorFilter | None
    ) -> list[Hit]:
        check_k(k)
        query = syllables(text_norm)
        if not query:
            return []
        with self._db.lock:
            tables = self._db.tables(self._index_id)
            collection_spec(tables, collection, self._index_id)
            rows = [
                row
                for row in tables.vectors.get(collection, {}).values()
                if row.text_norm is not None and _passes(row, where)
            ]
        # The score is the number of query syllables a row holds; the contract never compares it.
        hits = [
            Hit(
                id=row.id,
                score=float(len(query & syllables(row.text_norm or ""))),
                doc_id=row.doc_id,
            )
            for row in rows
        ]
        return sorted((hit for hit in hits if hit.score), key=lambda hit: (-hit.score, hit.id))[:k]

    def get_vectors(self, collection: Collection, ids: Sequence[str]) -> dict[str, list[float]]:
        with self._db.lock:
            rows = self._db.tables(self._index_id).vectors.get(collection, {})
            return {
                record_id: list(rows[record_id].vector) for record_id in ids if record_id in rows
            }
