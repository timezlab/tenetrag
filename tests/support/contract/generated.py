"""Data the corpus lacks, built by the recipes of writes.py (contract-suite.md §2).

Every name is fictional. Generated documents use ids from D901 on, so they
never meet a corpus id, and add their entities after the corpus world, so a
corpus entity keeps its id here. `hub_writes` comes with the hop cases (T034).
"""

from __future__ import annotations

import functools
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from operator import mul
from typing import Any, Final

from tenetrag.llm.fake import FakeEmbeddingModel
from tenetrag.protocols import DocumentWrite, VectorRecord
from tests.support.contract.writes import RUN_ID, Corpus, corpus_table
from tests.support.corpus.facts import Document, FactTable, Golden, Graph, World, WorldEntity
from tests.support.corpus.render import render

RECALL_RECORDS: Final = 3000
RECALL_QUERIES: Final = 30
RECALL_DIMENSIONS: Final = 64
RECALL_K: Final = 10

_TOPICS: Final = (
    "công tác phí",
    "bảo mật thông tin",
    "quản lý dự án",
    "chăm sóc khách hàng",
    "đào tạo nhân viên",
    "mua sắm thiết bị",
)


def _corpus(extras: Mapping[str, dict[str, Any]], documents: Sequence[dict[str, Any]]) -> Corpus:
    """The corpus world plus `extras`, with these documents only."""
    corpus = corpus_table()
    world = {
        **corpus.world.entities,
        **{world_id: WorldEntity.model_validate(entity) for world_id, entity in extras.items()},
    }
    table = FactTable(
        world=World(entities=world),
        documents=tuple(Document.model_validate(document) for document in documents),
        graph=Graph(),
        golden=Golden(),
    )
    return Corpus(table, {document.id: render(document) for document in table.documents})


def _entity(item_id: str, entity_type: str, world_id: str, surface: str) -> dict[str, Any]:
    return {
        "id": item_id,
        "kind": "entity",
        "type": entity_type,
        "world": world_id,
        "surface": surface,
        "is_name": True,
    }


@functools.cache
def _two_sources() -> Corpus:
    def document(doc_id: str, issued_on: str, title: str, text: str, quote: str) -> dict[str, Any]:
        return {
            "id": doc_id,
            "language": "vi",
            "issuer": "alpha",
            "title": title,
            "format": "md",
            "dates": {"issued_on": issued_on},
            "blocks": [{"heading": title.upper()}, {"paragraph": text}],
            "items": [
                _entity(f"{doc_id}.1", "Organization", "alpha.kt", "Phòng Kế toán"),
                _entity(f"{doc_id}.2", "Organization", "alpha", "Công ty CP Alpha"),
                {
                    "id": f"{doc_id}.3",
                    "kind": "relation",
                    "type": "PART_OF",
                    "from": f"{doc_id}.1",
                    "to": f"{doc_id}.2",
                    "quote": quote,
                },
            ],
        }

    return _corpus(
        {},
        [
            document(
                "D901",
                "2025-03-01",
                "Sơ đồ tổ chức",
                "Phòng Kế toán trực thuộc Công ty CP Alpha.",
                "Phòng Kế toán trực thuộc Công ty CP Alpha",
            ),
            document(
                "D902",
                "2025-06-01",
                "Giới thiệu công ty",
                "Công ty CP Alpha gồm Phòng Kế toán và các phòng chức năng khác.",
                "Công ty CP Alpha gồm Phòng Kế toán",
            ),
        ],
    )


@functools.cache
def _pack_status() -> Corpus:
    return _corpus(
        {},
        [
            {
                "id": "D903",
                "language": "vi",
                "issuer": "alpha",
                "title": "Biên bản họp giao ban",
                "format": "docx",
                "dates": {"held_on": "2025-05-05"},
                "blocks": [
                    {"heading": "BIÊN BẢN HỌP GIAO BAN"},
                    {"paragraph": "Chủ trì: Nguyễn Văn An."},
                    {"paragraph": "Cuộc họp phê duyệt nâng cấp hệ thống quản lý chi phí."},
                    {"paragraph": "Nâng cấp hệ thống quản lý chi phí đã xong, hạn 2025-06-30."},
                ],
                "items": [
                    _entity("D903.1", "Person", "alpha.an", "Nguyễn Văn An"),
                    _entity("D903.2", "System", "alpha.htcp", "hệ thống quản lý chi phí"),
                    {
                        "id": "D903.3",
                        "kind": "event",
                        "type": "Meeting",
                        "roles": {"chair": "D903.1"},
                        "attributes": {"title": {"value": "họp giao ban", "quote": "HỌP GIAO BAN"}},
                        "quote": "BIÊN BẢN HỌP GIAO BAN",
                        "valid_from": "2025-05-05",
                    },
                    {
                        "id": "D903.4",
                        "kind": "event",
                        "type": "Decision",
                        "roles": {"about": "D903.2", "decided_by": "D903.1", "made_in": "D903.3"},
                        "attributes": {"status": {"value": "approved", "quote": "phê duyệt"}},
                        "quote": "Cuộc họp phê duyệt nâng cấp hệ thống quản lý chi phí",
                    },
                    {
                        "id": "D903.5",
                        "kind": "fact",
                        "type": "ActionItem",
                        "roles": {"owner": "D903.1", "about": "D903.2", "assigned_in": "D903.3"},
                        "attributes": {
                            "status": {"value": "done", "quote": "đã xong"},
                            "due_date": {"value": "2025-06-30", "quote": "2025-06-30"},
                        },
                        "quote": "Nâng cấp hệ thống quản lý chi phí đã xong",
                    },
                ],
            }
        ],
    )


@functools.cache
def _tone_marks() -> Corpus:
    # Names that differ only in tone-mark placement (Hoà/Hòa, Thuỷ/Thủy) must
    # match; names that differ in diacritics (Lãi/Lại/Lai) must not. The other
    # chunks hold the full-text cases of research R6.
    places = {
        "place.xom-lai-nga": "Xóm Lãi",
        "place.xom-lai-nang": "Xóm Lại",
        "place.xom-lai": "Xóm Lai",
    }
    extras: dict[str, dict[str, Any]] = {
        world_id: {"type": "Place", "name": name} for world_id, name in places.items()
    }
    extras["alpha.hoa"] = {"type": "Person", "name": "Lê Thị Hoà", "scope": "alpha"}
    extras["beta.thuy"] = {"type": "Person", "name": "Phạm Văn Thuỷ", "scope": "beta"}
    paragraphs = [
        "Xóm Lãi: lãi suất cho vay.",
        "Xóm Lại: quay lại sau.",
        "Xóm Lai: lai lịch nhân viên.",
        "Phụ cấp 2.500.000 vnd/ngày cho phòng-ban và đơn vị.",
        "Người liên hệ: Lê Thị Hoà.",
        "Người phụ trách: Phạm Văn Thuỷ.",
        "Mục a, b, c và d của phụ lục.",
    ]
    items = [
        _entity(f"D904.{n}", "Place", world_id, name)
        for n, (world_id, name) in enumerate(places.items(), start=1)
    ]
    items += [
        _entity("D904.4", "Person", "alpha.hoa", "Lê Thị Hoà"),
        _entity("D904.5", "Person", "beta.thuy", "Phạm Văn Thuỷ"),
    ]
    return _corpus(
        extras,
        [
            {
                "id": "D904",
                "language": "vi",
                "issuer": "alpha",
                "title": "Danh bạ địa bàn",
                "format": "md",
                "dates": {"issued_on": "2025-07-01"},
                "blocks": [
                    {"heading": "DANH BẠ ĐỊA BÀN"},
                    *({"paragraph": text} for text in paragraphs),
                ],
                "items": items,
            }
        ],
    )


def two_source_writes(*, run_id: str = RUN_ID, with_vectors: bool = True) -> list[DocumentWrite]:
    """D901 and D902 both state that Phòng Kế toán is part of Công ty CP Alpha."""
    return _two_sources().writes(None, run_id=run_id, with_vectors=with_vectors)


def pack_status_writes(*, run_id: str = RUN_ID, with_vectors: bool = True) -> list[DocumentWrite]:
    """D903: a Decision with a pack `status`, and an ActionItem whose pack `status` is `done`
    while its engine status is `current`."""
    return _pack_status().writes(None, run_id=run_id, with_vectors=with_vectors)


def tone_mark_writes(*, run_id: str = RUN_ID, with_vectors: bool = True) -> list[DocumentWrite]:
    """D904: the tone-mark and diacritic name sets, and the full-text chunks of research R6."""
    return _tone_marks().writes(None, run_id=run_id, with_vectors=with_vectors)


@dataclass(frozen=True, slots=True)
class RecallFixture:
    records: tuple[VectorRecord, ...]
    queries: tuple[tuple[float, ...], ...]
    top_10: tuple[tuple[str, ...], ...]


@functools.cache
def recall_fixture() -> RecallFixture:
    """3,000 chunk vectors of 64 dimensions, 30 queries and each query's exact top 10.

    The top 10 is by dot product, which is cosine on these unit vectors, then
    id, summed with `math.fsum` so it does not depend on the order of terms.
    """
    model = FakeEmbeddingModel(dimensions=RECALL_DIMENSIONS)
    texts = [
        f"Đoạn mẫu {n} về {_TOPICS[n % len(_TOPICS)]} của Công ty CP Alpha."
        for n in range(RECALL_RECORDS)
    ]
    records = tuple(
        VectorRecord(
            id=f"recall-{n:04d}",
            vector=tuple(vector),
            doc_id="recall",
            type=None,
            language="vi",
            run_id=RUN_ID,
            text_norm=None,
        )
        for n, vector in enumerate(model.embed_documents(texts))
    )
    questions = [f"Câu hỏi {n} về {_TOPICS[n % len(_TOPICS)]}?" for n in range(RECALL_QUERIES)]
    queries = tuple(tuple(vector) for vector in model.embed_queries(questions))
    top_10 = tuple(
        tuple(
            record.id
            for _, record in sorted(
                ((-math.fsum(map(mul, query, record.vector)), record) for record in records),
                key=lambda scored: (scored[0], scored[1].id),
            )[:RECALL_K]
        )
        for query in queries
    )
    return RecallFixture(records=records, queries=queries, top_10=top_10)
