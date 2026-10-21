"""Store records (data-model §2 to §4 and §7.5, contracts/protocols.md).

Standard library only, so the engine can depend on them. Each record is a
frozen, slotted, keyword-only dataclass whose `__post_init__` checks shape
only (data-model §1): non-empty ids, spans in order, known literal values,
aware times. What the engine owns, such as a status transition, is never
checked here. `AnyScope` and `JsonValue` live here rather than in `stores`
because the records use them.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum, StrEnum
from typing import Final, Literal, TypeAlias, get_args

JsonValue: TypeAlias = str | int | float | bool | list["JsonValue"] | dict[str, "JsonValue"] | None

Collection = Literal["chunks", "entities", "chunk_questions"]
AliasOrigin = Literal["surface", "former_name", "translation", "glossary", "reviewer"]
SameAsOrigin = Literal[
    "embedding",
    "llm_unsure",
    "ambiguous_alias",
    "ambiguous_key",
    "ambiguous_version",
    "same_name",
    "key_name_conflict",
]
SameAsStatus = Literal["candidate", "confirmed", "rejected"]
ValidPrecision = Literal["day", "month", "year"]
ValidSource = Literal["text", "document"]
QuoteMatch = Literal["exact", "fuzzy"]
ObservedAtSource = Literal["caller", "card", "ingest"]
OwnerKind = Literal["event", "fact"]
TargetKind = Literal["entity", "event"]
ItemKind = Literal["relation", "fact", "event"]
VerdictMethod = Literal["llm", "reviewer"]

OWNER_MAX_LENGTH: Final = 200


def _require_ids(record: object, *names: str) -> None:
    for name in names:
        if not getattr(record, name):
            raise ValueError(f"{type(record).__name__}.{name} is empty; give the engine's id")


def _require_span(record: object, start_name: str, end_name: str) -> None:
    start, end = getattr(record, start_name), getattr(record, end_name)
    if not 0 <= start <= end:
        raise ValueError(
            f"{type(record).__name__}.{start_name} is {start} and {end_name} is {end}; "
            f"a span needs 0 <= {start_name} <= {end_name}"
        )


def _require_literal(record: object, name: str, literal: object, *, optional: bool = False) -> None:
    value = getattr(record, name)
    if optional and value is None:
        return
    allowed = get_args(literal)
    if value not in allowed:
        raise ValueError(
            f"{type(record).__name__}.{name} is {value!r}; use one of {', '.join(allowed)}"
        )


def _require_aware(record: object, name: str, *, optional: bool = False) -> None:
    value = getattr(record, name)
    if optional and value is None:
        return
    if value.utcoffset() is None:
        raise ValueError(
            f"{type(record).__name__}.{name} is a naive datetime; "
            "give an aware UTC time, such as datetime.now(UTC)"
        )


# §2.2 Document and chunk


@dataclass(frozen=True, slots=True, kw_only=True)
class DocumentRecord:
    doc_id: str
    source_uri: str
    content_hash: str
    pipeline_hash: str
    title: str | None
    title_norm: str | None
    code: str | None
    code_norm: str | None
    version_label: str | None
    doc_date: date | None
    effective_from: date | None
    effective_to: date | None
    language: str | None
    issuer_id: str | None
    issuer_source: str | None
    subject_type: str | None
    subject_id: str | None
    observed_at_source: ObservedAtSource
    run_id: str

    def __post_init__(self) -> None:
        _require_ids(self, "doc_id", "run_id")
        _require_literal(self, "observed_at_source", ObservedAtSource)


@dataclass(frozen=True, slots=True, kw_only=True)
class ChunkRecord:
    chunk_id: str
    doc_id: str
    ordinal: int
    start: int
    end: int
    text: str
    text_norm: str
    heading_path: tuple[str, ...]
    page_start: int | None
    page_end: int | None
    chunk_hash: str
    tokens: int
    language: str | None
    run_id: str

    def __post_init__(self) -> None:
        _require_ids(self, "chunk_id", "doc_id", "run_id")
        _require_span(self, "start", "end")


# §2.3 Entities, aliases and what hangs on them


@dataclass(frozen=True, slots=True, kw_only=True)
class EntityWrite:
    """An entity upsert. `attributes` are computed on read, `degree` by refresh_degrees."""

    entity_id: str
    type: str
    name: str
    name_norm: str
    label: str
    scope_path: tuple[str, ...]
    scope_source: str | None
    identity: Mapping[str, tuple[str, ...]]
    run_id: str

    def __post_init__(self) -> None:
        _require_ids(self, "entity_id", "type", "run_id")
        if "scope" in self.identity:
            raise ValueError("EntityWrite.identity holds 'scope'; pass the scope as scope_path")


@dataclass(frozen=True, slots=True, kw_only=True)
class AliasRow:
    entity_id: str
    alias: str
    alias_norm: str
    language: str | None
    origin: AliasOrigin
    run_id: str

    def __post_init__(self) -> None:
        _require_ids(self, "entity_id", "run_id")
        _require_literal(self, "origin", AliasOrigin)


@dataclass(frozen=True, slots=True, kw_only=True)
class AttributeSource:
    entity_id: str
    attribute: str
    value: JsonValue
    value_norm: str | None
    doc_id: str
    chunk_id: str
    quote: str
    quote_start: int
    quote_end: int
    observed_at: date | None
    run_id: str

    def __post_init__(self) -> None:
        _require_ids(self, "entity_id", "attribute", "doc_id", "chunk_id", "run_id")
        _require_span(self, "quote_start", "quote_end")


@dataclass(frozen=True, slots=True, kw_only=True)
class IdentityBlock:
    entity_id: str
    candidate_id: str
    attribute: str
    value: str
    candidate_value: str
    quote: str
    candidate_quote: str
    doc_id: str
    chunk_id: str
    run_id: str

    def __post_init__(self) -> None:
        _require_ids(self, "entity_id", "candidate_id", "doc_id", "chunk_id", "run_id")


@dataclass(frozen=True, slots=True, kw_only=True)
class Mention:
    entity_id: str
    chunk_id: str
    doc_id: str
    surface: str
    start: int
    end: int
    run_id: str

    def __post_init__(self) -> None:
        _require_ids(self, "entity_id", "chunk_id", "doc_id", "run_id")
        _require_span(self, "start", "end")


@dataclass(frozen=True, slots=True, kw_only=True)
class SameAsLink:
    entity_a: str
    entity_b: str
    score: float
    origin: SameAsOrigin
    status: SameAsStatus
    run_id: str

    def __post_init__(self) -> None:
        _require_ids(self, "entity_a", "entity_b", "run_id")
        if not self.entity_a < self.entity_b:
            raise ValueError(
                "SameAsLink.entity_a must sort before entity_b; put the smaller id first"
            )
        _require_literal(self, "origin", SameAsOrigin)
        _require_literal(self, "status", SameAsStatus)


# §2.4 Relations, events, facts, roles and links


def _check_item_row(row: RelationRow | FactRow) -> None:
    _require_literal(row, "valid_precision", ValidPrecision, optional=True)
    _require_literal(row, "valid_source", ValidSource)
    _require_aware(row, "recorded_at")
    _require_span(row, "quote_start", "quote_end")
    _require_literal(row, "quote_match", QuoteMatch)


@dataclass(frozen=True, slots=True, kw_only=True)
class RelationRow:
    """`attributes` holds pack attributes only; a pack `status` never touches `status` (FR-003)."""

    relation_id: str
    type: str
    subject_id: str
    object_id: str
    attributes: Mapping[str, JsonValue]
    valid_from: date | None
    valid_to: date | None
    valid_precision: ValidPrecision | None
    valid_source: ValidSource
    observed_at: date | None
    recorded_at: datetime
    status: str
    closed_at: date | None
    version_key: str | None
    doc_id: str
    chunk_id: str
    quote: str
    quote_start: int
    quote_end: int
    quote_match: QuoteMatch
    confidence: float
    pack: str
    pack_version: str
    run_id: str

    def __post_init__(self) -> None:
        _require_ids(
            self, "relation_id", "type", "subject_id", "object_id", "doc_id", "chunk_id", "run_id"
        )
        _check_item_row(self)


@dataclass(frozen=True, slots=True, kw_only=True)
class FactRow:
    fact_id: str
    type: str
    attributes: Mapping[str, JsonValue]
    valid_from: date | None
    valid_to: date | None
    valid_precision: ValidPrecision | None
    valid_source: ValidSource
    observed_at: date | None
    recorded_at: datetime
    status: str
    closed_at: date | None
    version_key: str | None
    doc_id: str
    chunk_id: str
    quote: str
    quote_start: int
    quote_end: int
    quote_match: QuoteMatch
    confidence: float
    pack: str
    pack_version: str
    run_id: str

    def __post_init__(self) -> None:
        _require_ids(self, "fact_id", "type", "doc_id", "chunk_id", "run_id")
        _check_item_row(self)


@dataclass(frozen=True, slots=True, kw_only=True)
class EventRecord:
    """Events have no status and no version key (engine brief §1)."""

    event_id: str
    type: str
    attributes: Mapping[str, JsonValue]
    identity: Mapping[str, tuple[str, ...]]
    valid_from: date | None
    valid_to: date | None
    valid_precision: ValidPrecision | None
    pack: str
    pack_version: str
    run_id: str

    def __post_init__(self) -> None:
        _require_ids(self, "event_id", "type", "run_id")
        _require_literal(self, "valid_precision", ValidPrecision, optional=True)


@dataclass(frozen=True, slots=True, kw_only=True)
class EventEvidence:
    event_id: str
    doc_id: str
    chunk_id: str
    quote: str
    quote_start: int
    quote_end: int
    quote_match: QuoteMatch
    observed_at: date | None
    run_id: str

    def __post_init__(self) -> None:
        _require_ids(self, "event_id", "doc_id", "chunk_id", "run_id")
        _require_span(self, "quote_start", "quote_end")
        _require_literal(self, "quote_match", QuoteMatch)


@dataclass(frozen=True, slots=True, kw_only=True)
class RoleRow:
    owner_id: str
    owner_kind: OwnerKind
    role: str
    target_id: str
    target_kind: TargetKind
    doc_id: str
    chunk_id: str
    run_id: str

    def __post_init__(self) -> None:
        _require_ids(self, "owner_id", "role", "target_id", "doc_id", "chunk_id", "run_id")
        _require_literal(self, "owner_kind", OwnerKind)
        _require_literal(self, "target_kind", TargetKind)


@dataclass(frozen=True, slots=True, kw_only=True)
class TextInLink:
    """`doc_id` holds the entity's text. `run_id` is None on a match_document_links candidate."""

    entity_id: str
    doc_id: str
    attribute: str
    run_id: str | None

    def __post_init__(self) -> None:
        _require_ids(self, "entity_id", "doc_id", "attribute")


# §7.5 Vectors


@dataclass(frozen=True, slots=True, kw_only=True)
class VectorRecord:
    """`doc_id` is None for entities, which span documents.

    `text_norm` is set where full text applies: chunks and chunk questions.
    """

    id: str
    vector: tuple[float, ...]
    doc_id: str | None
    type: str | None
    language: str | None
    run_id: str
    text_norm: str | None

    def __post_init__(self) -> None:
        _require_ids(self, "id", "run_id")


@dataclass(frozen=True, slots=True, kw_only=True)
class CollectionSpec:
    model_id: str
    dimensions: int

    def __post_init__(self) -> None:
        _require_ids(self, "model_id")
        if self.dimensions < 1:
            raise ValueError(
                f"CollectionSpec.dimensions is {self.dimensions}; use the embedding model's size"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class VectorSpec:
    chunks: CollectionSpec
    entities: CollectionSpec
    chunk_questions: CollectionSpec


@dataclass(frozen=True, slots=True, kw_only=True)
class VectorFilter:
    """Fields are AND-ed; None is no filter, and an empty tuple matches nothing."""

    types: tuple[str, ...] | None = None
    languages: tuple[str, ...] | None = None
    doc_ids: tuple[str, ...] | None = None
    exclude_run: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class Hit:
    id: str
    score: float
    doc_id: str | None


@dataclass(frozen=True, slots=True, kw_only=True)
class VectorCapabilities:
    text_search: bool
    fused_hybrid_only: bool
    eventual_sync: bool
    max_dimensions: int


# §2.1 The write unit


@dataclass(frozen=True, slots=True, kw_only=True)
class StatusChange:
    """`status` is the engine's value (`current`, `superseded`, `conflicting`), kept as a string."""

    item_id: str
    status: str
    closed_at: date | None

    def __post_init__(self) -> None:
        _require_ids(self, "item_id", "status")


# The rows of a DocumentWrite that carry its doc_id; text_in may name another document.
_OWN_DOCUMENT_ROWS: Final = (
    "chunks",
    "attribute_sources",
    "identity_blocks",
    "mentions",
    "relations",
    "event_evidence",
    "facts",
    "roles",
)


@dataclass(frozen=True, slots=True, kw_only=True)
class DocumentWrite:
    """One document's unit. `vectors` is set only when the graph store writes them (§7.5)."""

    document: DocumentRecord
    chunks: tuple[ChunkRecord, ...] = ()
    entities: tuple[EntityWrite, ...] = ()
    aliases: tuple[AliasRow, ...] = ()
    attribute_sources: tuple[AttributeSource, ...] = ()
    identity_blocks: tuple[IdentityBlock, ...] = ()
    mentions: tuple[Mention, ...] = ()
    relations: tuple[RelationRow, ...] = ()
    events: tuple[EventRecord, ...] = ()
    event_evidence: tuple[EventEvidence, ...] = ()
    facts: tuple[FactRow, ...] = ()
    roles: tuple[RoleRow, ...] = ()
    text_in: tuple[TextInLink, ...] = ()
    same_as: tuple[SameAsLink, ...] = ()
    status_changes: tuple[StatusChange, ...] = ()
    vectors: Mapping[Collection, tuple[VectorRecord, ...]] = field(default_factory=dict)
    run_id: str

    def __post_init__(self) -> None:
        _require_ids(self, "run_id")
        doc_id = self.document.doc_id
        for name in _OWN_DOCUMENT_ROWS:
            for row in getattr(self, name):
                if row.doc_id != doc_id:
                    raise ValueError(
                        f"DocumentWrite.{name} has a row of document {row.doc_id!r}, "
                        f"not {doc_id!r}; put each document's rows in its own DocumentWrite"
                    )


@dataclass(frozen=True, slots=True, kw_only=True)
class DocumentDelete:
    doc_id: str
    status_changes: tuple[StatusChange, ...] = ()
    run_id: str

    def __post_init__(self) -> None:
        _require_ids(self, "doc_id", "run_id")


# §3 Read records and keys


@dataclass(frozen=True, slots=True, kw_only=True)
class EntityRecord:
    """`attributes` are computed on read from the newest source (data-model §3.1)."""

    entity_id: str
    type: str
    name: str
    name_norm: str
    label: str
    scope_path: tuple[str, ...]
    scope_source: str | None
    attributes: Mapping[str, JsonValue]
    identity: Mapping[str, tuple[str, ...]]
    aliases: tuple[AliasRow, ...]
    degree: int
    run_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class Evidence:
    doc_id: str
    chunk_id: str
    quote: str
    quote_start: int
    quote_end: int
    quote_match: QuoteMatch
    observed_at: date | None

    def __post_init__(self) -> None:
        _require_span(self, "quote_start", "quote_end")


@dataclass(frozen=True, slots=True, kw_only=True)
class ItemRecord:
    """A relation, fact or event as read. Event-only gaps are None (data-model §3.2)."""

    item_id: str
    kind: ItemKind
    type: str
    subject_id: str | None
    object_id: str | None
    roles: tuple[RoleRow, ...]
    attributes: Mapping[str, JsonValue]
    valid_from: date | None
    valid_to: date | None
    valid_precision: ValidPrecision | None
    valid_source: ValidSource | None
    observed_at: date | None
    recorded_at: datetime | None
    status: str | None
    closed_at: date | None
    version_key: str | None
    evidence: tuple[Evidence, ...]
    confidence: float | None
    pack: str
    pack_version: str
    run_id: str

    def __post_init__(self) -> None:
        _require_literal(self, "kind", ItemKind)
        _require_aware(self, "recorded_at", optional=True)


class AnyScope(Enum):
    """An IdentityKey scope that matches every scope. An enum member, never an entity id."""

    ANY = "any"


ANY_SCOPE: Final = AnyScope.ANY


@dataclass(frozen=True, slots=True, kw_only=True)
class IdentityKey:
    """Matches an entity of `type` in `scope` (None: unscoped) whose identity holds every value."""

    type: str
    scope: str | AnyScope | None
    names: tuple[str, ...]
    values: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.names:
            raise ValueError("IdentityKey.names is empty; name at least one key")
        if len(self.values) != len(self.names):
            raise ValueError(
                f"IdentityKey.values has {len(self.values)} values for {len(self.names)} names; "
                "give one value per name"
            )
        if "scope" in self.names:
            raise ValueError("IdentityKey.names holds 'scope'; pass the scope as IdentityKey.scope")


@dataclass(frozen=True, slots=True, kw_only=True)
class NameMatch:
    """`matched` is the name_norm (origin None) or alias_norm (its origin) that matched."""

    entity_id: str
    type: str
    scope_path: tuple[str, ...]
    matched: str
    origin: str | None
    score: float


@dataclass(frozen=True, slots=True, kw_only=True)
class DocumentLinkKey:
    """Exactly one side: `doc_id` finds entities, `entity_id` finds documents (data-model §3.3)."""

    attribute: str
    value_norm: str
    doc_id: str | None = None
    entity_id: str | None = None
    entity_types: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if (self.doc_id is None) == (self.entity_id is None):
            raise ValueError("DocumentLinkKey needs exactly one of doc_id and entity_id")


@dataclass(frozen=True, slots=True, kw_only=True)
class DocumentState:
    content_hash: str
    pipeline_hash: str
    run_id: str


# §4 Runs, caches and the lease


class RunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    INTERRUPTED = "interrupted"
    FAILED = "failed"


@dataclass(frozen=True, slots=True, kw_only=True)
class RunRecord:
    """`pack`, `pack_version` and `pack_hash` copy 002's Stamp; `stats` is opaque to the store."""

    run_id: str
    status: RunStatus
    started_at: datetime | None
    finished_at: datetime | None
    stage_hashes: Mapping[str, str]
    prompt_versions: Mapping[str, str]
    pack: str
    pack_version: str
    pack_hash: str
    stats: Mapping[str, JsonValue]

    def __post_init__(self) -> None:
        _require_ids(self, "run_id")
        _require_aware(self, "started_at", optional=True)
        _require_aware(self, "finished_at", optional=True)


@dataclass(frozen=True, slots=True, kw_only=True)
class Verdict:
    pair_key: str
    verdict: str
    method: VerdictMethod
    model: str | None
    run_id: str

    def __post_init__(self) -> None:
        _require_ids(self, "pair_key", "run_id")
        _require_literal(self, "method", VerdictMethod)


@dataclass(frozen=True, slots=True, kw_only=True)
class WriterLease:
    """The index's single-writer lease (ADR 0024). `fence` and `expires_at` come from the store."""

    index_id: str
    owner: str
    fence: int
    expires_at: datetime

    def __post_init__(self) -> None:
        _require_ids(self, "index_id")
        if not 1 <= len(self.owner) <= OWNER_MAX_LENGTH:
            raise ValueError(
                f"WriterLease.owner has {len(self.owner)} characters; "
                f"use 1 to {OWNER_MAX_LENGTH}, such as host:pid:random"
            )
        _require_aware(self, "expires_at")
