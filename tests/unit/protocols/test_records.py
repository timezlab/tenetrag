"""Store records (contracts/protocols.md, data-model §2 to §4 and §7.5).

Behaviours:
1. Every record is a frozen, slotted, keyword-only dataclass.
2. A naive time on a run record or a lease raises ValueError.
3. A mention, chunk or quote span with start after end raises ValueError.
4. A row of a DocumentWrite with another doc_id raises, except a text_in row.
5. A same_as link names its pair in order.
6. An identity key has names and values of one non-zero length, and no
   `scope` among its names.
7. A document link key has exactly one of doc_id and entity_id.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from datetime import UTC, date, datetime

import pytest

from tenetrag.protocols import (
    ANY_SCOPE,
    AliasRow,
    AttributeSource,
    ChunkRecord,
    CollectionSpec,
    DocumentDelete,
    DocumentLinkKey,
    DocumentRecord,
    DocumentState,
    DocumentWrite,
    EntityRecord,
    EntityWrite,
    EventEvidence,
    EventRecord,
    Evidence,
    FactRow,
    Hit,
    IdentityBlock,
    IdentityKey,
    ItemRecord,
    Mention,
    NameMatch,
    RelationRow,
    RoleRow,
    RunRecord,
    RunStatus,
    SameAsLink,
    StatusChange,
    TextInLink,
    VectorCapabilities,
    VectorFilter,
    VectorRecord,
    VectorSpec,
    Verdict,
    WriterLease,
)

NOW = datetime(2026, 10, 21, 2, 30, tzinfo=UTC)
NAIVE = datetime(2026, 10, 21, 2, 30)


def document(doc_id: str = "d1") -> DocumentRecord:
    return DocumentRecord(
        doc_id=doc_id,
        source_uri="docs/d1.md",
        content_hash="c1",
        pipeline_hash="p1",
        title="Quy chế công tác phí",
        title_norm="quy chế công tác phí",
        code=None,
        code_norm=None,
        version_label="1",
        doc_date=date(2025, 1, 10),
        effective_from=date(2025, 2, 1),
        effective_to=None,
        language="vi",
        issuer_id="e-alpha",
        issuer_source="card",
        subject_type=None,
        subject_id=None,
        observed_at_source="card",
        run_id="run-1",
    )


def chunk(doc_id: str = "d1", *, start: int = 0, end: int = 12) -> ChunkRecord:
    return ChunkRecord(
        chunk_id="c1",
        doc_id=doc_id,
        ordinal=0,
        start=start,
        end=end,
        text="Mức phụ cấp.",
        text_norm="mức phụ cấp.",
        heading_path=("Quy chế",),
        page_start=None,
        page_end=None,
        chunk_hash="h1",
        tokens=3,
        language="vi",
        run_id="run-1",
    )


def entity() -> EntityWrite:
    return EntityWrite(
        entity_id="e1",
        type="Policy",
        name="Quy chế công tác phí",
        name_norm="quy chế công tác phí",
        label="Quy chế công tác phí",
        scope_path=("e-alpha",),
        scope_source="card",
        identity={"title": ("quy chế công tác phí",)},
        run_id="run-1",
    )


def alias() -> AliasRow:
    return AliasRow(
        entity_id="e1",
        alias="QUY CHẾ CÔNG TÁC PHÍ",
        alias_norm="quy chế công tác phí",
        language="vi",
        origin="surface",
        run_id="run-1",
    )


def attribute_source(doc_id: str = "d1") -> AttributeSource:
    return AttributeSource(
        entity_id="e1",
        attribute="version_label",
        value="1",
        value_norm="1",
        doc_id=doc_id,
        chunk_id="c1",
        quote="Phiên bản 1",
        quote_start=0,
        quote_end=11,
        observed_at=date(2025, 1, 10),
        run_id="run-1",
    )


def identity_block(doc_id: str = "d1") -> IdentityBlock:
    return IdentityBlock(
        entity_id="e1",
        candidate_id="e2",
        attribute="scope",
        value="e-alpha",
        candidate_value="e-beta",
        quote="Công ty CP Alpha",
        candidate_quote="Công ty CP Beta",
        doc_id=doc_id,
        chunk_id="c1",
        run_id="run-1",
    )


def mention(doc_id: str = "d1", *, start: int = 0, end: int = 4) -> Mention:
    return Mention(
        entity_id="e1",
        chunk_id="c1",
        doc_id=doc_id,
        surface="Mức ",
        start=start,
        end=end,
        run_id="run-1",
    )


def same_as(entity_a: str = "e1", entity_b: str = "e2") -> SameAsLink:
    return SameAsLink(
        entity_a=entity_a,
        entity_b=entity_b,
        score=0.91,
        origin="embedding",
        status="candidate",
        run_id="run-1",
    )


def relation(doc_id: str = "d1", *, quote_start: int = 0, quote_end: int = 4) -> RelationRow:
    return RelationRow(
        relation_id="r1",
        type="OWNER_OF",
        subject_id="e2",
        object_id="e1",
        attributes={},
        valid_from=date(2025, 2, 1),
        valid_to=None,
        valid_precision="day",
        valid_source="document",
        observed_at=date(2025, 1, 10),
        recorded_at=NOW,
        status="current",
        closed_at=None,
        version_key="v1",
        doc_id=doc_id,
        chunk_id="c1",
        quote="Mức ",
        quote_start=quote_start,
        quote_end=quote_end,
        quote_match="exact",
        confidence=1.0,
        pack="enterprise-docs",
        pack_version="1",
        run_id="run-1",
    )


def fact(doc_id: str = "d1") -> FactRow:
    return FactRow(
        fact_id="f1",
        type="Decision",
        attributes={"status": "approved"},
        valid_from=None,
        valid_to=None,
        valid_precision=None,
        valid_source="document",
        observed_at=date(2025, 1, 10),
        recorded_at=NOW,
        status="current",
        closed_at=None,
        version_key=None,
        doc_id=doc_id,
        chunk_id="c1",
        quote="Mức ",
        quote_start=0,
        quote_end=4,
        quote_match="fuzzy",
        confidence=0.7,
        pack="enterprise-docs",
        pack_version="1",
        run_id="run-1",
    )


def event() -> EventRecord:
    return EventRecord(
        event_id="ev1",
        type="Meeting",
        attributes={},
        identity={"held_on": ("2025-03-04",)},
        valid_from=date(2025, 3, 4),
        valid_to=None,
        valid_precision="day",
        pack="enterprise-docs",
        pack_version="1",
        run_id="run-1",
    )


def event_evidence(doc_id: str = "d1") -> EventEvidence:
    return EventEvidence(
        event_id="ev1",
        doc_id=doc_id,
        chunk_id="c1",
        quote="Mức ",
        quote_start=0,
        quote_end=4,
        quote_match="exact",
        observed_at=date(2025, 3, 4),
        run_id="run-1",
    )


def role(doc_id: str = "d1") -> RoleRow:
    return RoleRow(
        owner_id="f1",
        owner_kind="fact",
        role="source",
        target_id="e1",
        target_kind="entity",
        doc_id=doc_id,
        chunk_id="c1",
        run_id="run-1",
    )


def text_in(doc_id: str = "d1") -> TextInLink:
    return TextInLink(entity_id="e1", doc_id=doc_id, attribute="title", run_id="run-1")


def vector(doc_id: str | None = "d1") -> VectorRecord:
    return VectorRecord(
        id="c1",
        vector=(1.0, 0.0),
        doc_id=doc_id,
        type=None,
        language="vi",
        run_id="run-1",
        text_norm="mức phụ cấp.",
    )


def write(**rows: object) -> DocumentWrite:
    return DocumentWrite(document=document(), run_id="run-1", **rows)  # type: ignore[arg-type]


def run_record(*, started_at: datetime | None = NOW) -> RunRecord:
    return RunRecord(
        run_id="run-1",
        status=RunStatus.RUNNING,
        started_at=started_at,
        finished_at=None,
        stage_hashes={"chunk": "s1"},
        prompt_versions={"extract": "1"},
        pack="enterprise-docs",
        pack_version="1",
        pack_hash="ph",
        stats={},
    )


def evidence() -> Evidence:
    return Evidence(
        doc_id="d1",
        chunk_id="c1",
        quote="Mức ",
        quote_start=0,
        quote_end=4,
        quote_match="exact",
        observed_at=date(2025, 1, 10),
    )


def every_record() -> list[object]:
    """One instance of each record of data-model §2 to §4 and §7.5."""
    spec = CollectionSpec(model_id="fake-embed", dimensions=8)
    return [
        write(chunks=(chunk(),), vectors={"chunks": (vector(),)}),
        DocumentDelete(doc_id="d1", status_changes=(), run_id="run-2"),
        StatusChange(item_id="r1", status="superseded", closed_at=date(2026, 1, 1)),
        document(),
        chunk(),
        entity(),
        alias(),
        attribute_source(),
        identity_block(),
        mention(),
        same_as(),
        relation(),
        fact(),
        event(),
        event_evidence(),
        role(),
        text_in(),
        EntityRecord(
            entity_id="e1",
            type="Policy",
            name="Quy chế công tác phí",
            name_norm="quy chế công tác phí",
            label="Quy chế công tác phí",
            scope_path=(),
            scope_source=None,
            attributes={"version_label": "1"},
            identity={},
            aliases=(alias(),),
            degree=0,
            run_id="run-1",
        ),
        ItemRecord(
            item_id="r1",
            kind="relation",
            type="OWNER_OF",
            subject_id="e2",
            object_id="e1",
            roles=(),
            attributes={},
            valid_from=None,
            valid_to=None,
            valid_precision=None,
            valid_source="text",
            observed_at=None,
            recorded_at=NOW,
            status="current",
            closed_at=None,
            version_key=None,
            evidence=(evidence(),),
            confidence=1.0,
            pack="enterprise-docs",
            pack_version="1",
            run_id="run-1",
        ),
        evidence(),
        IdentityKey(type="Person", scope=ANY_SCOPE, names=("employee_id",), values=("nv-1",)),
        NameMatch(
            entity_id="e1",
            type="Policy",
            scope_path=(),
            matched="quy chế công tác phí",
            origin=None,
            score=1.0,
        ),
        DocumentLinkKey(attribute="title", value_norm="quy chế công tác phí", doc_id="d1"),
        DocumentState(content_hash="c1", pipeline_hash="p1", run_id="run-1"),
        run_record(),
        Verdict(pair_key="e1|e2", verdict="same", method="llm", model="fake-chat", run_id="run-1"),
        WriterLease(index_id="alpha", owner="host-a:1", fence=1, expires_at=NOW),
        vector(),
        spec,
        VectorSpec(chunks=spec, entities=spec, chunk_questions=spec),
        VectorFilter(types=("Policy",)),
        Hit(id="c1", score=0.5, doc_id="d1"),
        VectorCapabilities(
            text_search=True, fused_hybrid_only=False, eventual_sync=False, max_dimensions=4096
        ),
    ]


@pytest.mark.parametrize("record", every_record(), ids=lambda record: type(record).__name__)
def test_records_frozen(record: object):
    assert dataclasses.is_dataclass(record)
    first = dataclasses.fields(record)[0]

    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(record, first.name, getattr(record, first.name))
    assert hasattr(type(record), "__slots__")
    assert not hasattr(record, "__dict__")
    assert all(field.kw_only for field in dataclasses.fields(record))
    positional: Callable[..., object] = type(record)
    with pytest.raises(TypeError):
        positional(*(getattr(record, field.name) for field in dataclasses.fields(record)))


def test_naive_datetime_refused():
    with pytest.raises(ValueError, match="started_at"):
        run_record(started_at=NAIVE)
    with pytest.raises(ValueError, match="expires_at"):
        WriterLease(index_id="alpha", owner="host-a:1", fence=1, expires_at=NAIVE)
    with pytest.raises(ValueError, match="recorded_at"):
        dataclasses.replace(relation(), recorded_at=NAIVE)
    assert run_record(started_at=None).started_at is None


def test_spans_checked():
    with pytest.raises(ValueError, match="start"):
        mention(start=5, end=3)
    with pytest.raises(ValueError, match="start"):
        chunk(start=10, end=2)
    with pytest.raises(ValueError, match="quote_start"):
        relation(quote_start=4, quote_end=1)
    assert mention(start=3, end=3).end == 3


@pytest.mark.parametrize(
    ("field", "row"),
    [
        ("chunks", chunk("d2")),
        ("attribute_sources", attribute_source("d2")),
        ("identity_blocks", identity_block("d2")),
        ("mentions", mention("d2")),
        ("relations", relation("d2")),
        ("event_evidence", event_evidence("d2")),
        ("facts", fact("d2")),
        ("roles", role("d2")),
    ],
)
def test_document_write_doc_ids(field: str, row: object):
    with pytest.raises(ValueError, match=field):
        write(**{field: (row,)})


def test_document_write_text_in_may_name_another_document():
    assert write(text_in=(text_in("d2"),)).text_in[0].doc_id == "d2"


def test_document_write_defaults_empty():
    written = write()

    assert written.chunks == ()
    assert written.status_changes == ()
    assert dict(written.vectors) == {}


def test_same_as_order():
    with pytest.raises(ValueError, match="entity_a"):
        same_as("b", "a")
    with pytest.raises(ValueError, match="entity_a"):
        same_as("a", "a")
    assert same_as("a", "b").entity_b == "b"


def test_identity_key_shape():
    with pytest.raises(ValueError, match="names"):
        IdentityKey(type="Person", scope=None, names=(), values=())
    with pytest.raises(ValueError, match="values"):
        IdentityKey(type="Person", scope=None, names=("employee_id",), values=("a", "b"))
    with pytest.raises(ValueError, match="scope"):
        IdentityKey(type="Person", scope="e-alpha", names=("scope",), values=("e-alpha",))
    key = IdentityKey(type="Person", scope="e-alpha", names=("employee_id",), values=("nv-1",))
    assert key.scope == "e-alpha"


def test_document_link_key_one_side():
    with pytest.raises(ValueError, match="doc_id"):
        DocumentLinkKey(attribute="title", value_norm="x")
    with pytest.raises(ValueError, match="doc_id"):
        DocumentLinkKey(attribute="title", value_norm="x", doc_id="d1", entity_id="e1")
    key = DocumentLinkKey(attribute="code", value_norm="x", entity_id="e1")
    assert key.entity_types == ()
