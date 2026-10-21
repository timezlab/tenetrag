"""Store protocols, the store schema, write steps and hop (contracts/protocols.md, data-model §5).

Standard library only, so the engine can depend on them. The lease and
write rules every store follows are in contracts/stores.md; the contract
suite pins them on every backend.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Final, Literal, Protocol, runtime_checkable

from tenetrag.protocols.errors import ConfigError
from tenetrag.protocols.records import (
    ChunkRecord,
    Collection,
    DocumentDelete,
    DocumentLinkKey,
    DocumentRecord,
    DocumentState,
    DocumentWrite,
    EntityRecord,
    EventRecord,
    Hit,
    IdentityKey,
    ItemRecord,
    JsonValue,
    Mention,
    NameMatch,
    RunRecord,
    RunStatus,
    TextInLink,
    VectorCapabilities,
    VectorFilter,
    VectorRecord,
    VectorSpec,
    Verdict,
    WriterLease,
)

# Equal to tenetrag.packs.format, which protocols cannot import; a unit test keeps them equal.
TYPE_NAME: Final = re.compile(r"[A-Z][A-Za-z0-9]*")
RELATION_NAME: Final = re.compile(r"[A-Z][A-Z0-9]*(_[A-Z0-9]+)*")

# Labels and edge types the stores use themselves (data-model §5.1).
RESERVED_LABELS: Final = frozenset(
    {
        "Document",
        "Chunk",
        "Entity",
        "Event",
        "Fact",
        "Alias",
        "IdentityValue",
        "AttributeSource",
        "IdentityBlock",
        "Run",
        "ExtractionCache",
        "ResolutionDecision",
        "WriterLease",
        "StoreMeta",
        "Collection",
        "Community",
        "ChunkVector",
        "EntityVector",
        "ChunkQuestionVector",
    }
)
RESERVED_EDGE_TYPES: Final = frozenset(
    {
        "IN_DOCUMENT",
        "MENTIONED_IN",
        "ROLE",
        "SUPPORTED_BY",
        "ALIAS_OF",
        "TEXT_IN",
        "SAME_AS",
        "IN_COMMUNITY",
    }
)

# The upper bound of every read limit: hop caps, get_runs, search k and search_names.
LIMIT_MAX: Final = 1000

RunStats = Mapping[str, JsonValue]

_KINDS: Final = ("entity_types", "event_types", "fact_types", "relation_types")
# A type may equal its own kind's base label: an event type `Event`, for example.
_BASE_LABELS: Final = {"entity_types": "Entity", "event_types": "Event", "fact_types": "Fact"}


@dataclass(frozen=True, slots=True, kw_only=True)
class StoreSchema:
    """The pack types a store holds. Each tuple comes out sorted and without repeats."""

    entity_types: tuple[str, ...] = ()
    event_types: tuple[str, ...] = ()
    fact_types: tuple[str, ...] = ()
    relation_types: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        kind_of: dict[str, str] = {}
        for kind in _KINDS:
            names = tuple(sorted(set(getattr(self, kind))))
            object.__setattr__(self, kind, names)
            for name in names:
                _check_name(kind, name)
                if name in kind_of:
                    raise ConfigError(
                        f"Store schema name '{name}' is in both {kind_of[name]} and {kind}; "
                        "rename one of them in its pack"
                    )
                kind_of[name] = kind

    def merged(self, other: StoreSchema) -> StoreSchema:
        """The union, for the additive rule of ensure_schema."""
        return StoreSchema(
            entity_types=self.entity_types + other.entity_types,
            event_types=self.event_types + other.event_types,
            fact_types=self.fact_types + other.fact_types,
            relation_types=self.relation_types + other.relation_types,
        )


def _check_name(kind: str, name: str) -> None:
    is_relation = kind == "relation_types"
    pattern = RELATION_NAME if is_relation else TYPE_NAME
    if pattern.fullmatch(name) is None:
        raise ConfigError(
            f"Store schema name '{name}' in {kind} breaks the pattern {pattern.pattern}; "
            "rename it in its pack"
        )
    reserved = RESERVED_EDGE_TYPES if is_relation else RESERVED_LABELS
    if name in reserved and name != _BASE_LABELS.get(kind):
        raise ConfigError(
            f"Store schema name '{name}' in {kind} is reserved by the stores; rename it in its pack"
        )


class WriteStep(StrEnum):
    """The steps of a write unit; a delete unit skips INSERT (data-model §5.2)."""

    DELETE_PREVIOUS = "delete_previous"
    INSERT = "insert"
    STATUS_CHANGES = "status_changes"
    DELETE_ORPHANS = "delete_orphans"
    DOCUMENT_ROW = "document_row"


StepHook = Callable[[WriteStep, str], None]


@dataclass(frozen=True, slots=True, kw_only=True)
class HopSpec:
    """None is no filter; an empty tuple lets nothing through (data-model §5.4)."""

    relation_types: tuple[str, ...] | None = None
    item_types: tuple[str, ...] | None = None
    statuses: tuple[str, ...] | None = None
    starts_before: date | None = None
    overlaps: tuple[date | None, date | None] | None = None
    include_same_as: bool = False
    neighbour_limit: int = 20
    item_limit: int = 50

    def __post_init__(self) -> None:
        for name in ("neighbour_limit", "item_limit"):
            value = getattr(self, name)
            if not 1 <= value <= LIMIT_MAX:
                raise ValueError(f"HopSpec.{name} is {value}; use 1 to {LIMIT_MAX}")


@dataclass(frozen=True, slots=True, kw_only=True)
class HopEdge:
    from_id: str
    to_id: str
    via_kind: Literal["relation", "role", "same_as"]
    via_type: str
    item_ids: tuple[str, ...]
    support: int
    to_degree: int


@dataclass(frozen=True, slots=True, kw_only=True)
class HopItem:
    """An event or fact naming the start entity `entity_id` in `role`."""

    item_id: str
    kind: Literal["event", "fact"]
    type: str
    entity_id: str
    role: str
    chunk_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class HopResult:
    edges: tuple[HopEdge, ...]
    items: tuple[HopItem, ...]


@runtime_checkable
class GraphStore(Protocol):
    """Engine brief §6.1 without the community methods (M5), plus renew and release (ADR 0024).

    Every read takes ids or keys: an empty sequence returns an empty result,
    and a repeated id is read once.
    """

    # Setup, writer lease, runs
    def ensure_schema(self, schema: StoreSchema) -> None: ...
    def acquire_writer(self, owner: str, ttl_s: int) -> WriterLease: ...
    def renew_writer(self, lease: WriterLease, ttl_s: int) -> WriterLease: ...
    def release_writer(self, lease: WriterLease) -> None: ...
    def begin_run(self, run: RunRecord) -> None: ...
    def finish_run(self, run_id: str, status: RunStatus, stats: RunStats) -> None: ...
    def get_runs(self, limit: int) -> list[RunRecord]: ...

    # Change detection and caches
    def document_states(self) -> dict[str, DocumentState]: ...
    def get_cached_extractions(self, keys: Sequence[str]) -> dict[str, bytes]: ...
    def put_cached_extractions(self, entries: Mapping[str, bytes]) -> None: ...
    def get_resolution_decisions(self, pair_keys: Sequence[str]) -> dict[str, Verdict]: ...
    def put_resolution_decisions(self, decisions: Sequence[Verdict]) -> None: ...

    # Resolution and linking
    def find_by_identity(self, keys: Sequence[IdentityKey]) -> list[EntityRecord]: ...
    def find_events(self, keys: Sequence[IdentityKey]) -> list[EventRecord]: ...
    def match_names(
        self,
        names_norm: Sequence[str],
        types: Sequence[str] | None,
        exclude_run: str | None = None,
    ) -> list[NameMatch]: ...
    def search_names(
        self, text_norm: str, types: Sequence[str] | None, limit: int, min_similarity: float
    ) -> list[NameMatch]: ...
    def match_document_links(self, keys: Sequence[DocumentLinkKey]) -> list[TextInLink]: ...

    # Versions
    def get_version_groups(self, version_keys: Sequence[str]) -> list[ItemRecord]: ...
    def get_document_version_keys(self, doc_ids: Sequence[str]) -> dict[str, list[str]]: ...

    # Writes: each document is atomic
    def write_documents(self, writes: Sequence[DocumentWrite]) -> None: ...
    def delete_documents(self, deletes: Sequence[DocumentDelete]) -> None: ...
    def refresh_degrees(self, entity_ids: Sequence[str]) -> None: ...

    # Retrieval reads
    def entities_in_chunks(self, chunk_ids: Sequence[str]) -> list[Mention]: ...
    def hop(self, entity_ids: Sequence[str], spec: HopSpec) -> HopResult: ...
    def get_entities(self, entity_ids: Sequence[str]) -> list[EntityRecord]: ...
    def get_items(self, item_ids: Sequence[str]) -> list[ItemRecord]: ...
    def get_chunks(self, chunk_ids: Sequence[str]) -> list[ChunkRecord]: ...
    def get_documents(self, doc_ids: Sequence[str]) -> list[DocumentRecord]: ...


@runtime_checkable
class VectorStore(Protocol):
    """Engine brief §6.2. Vector writes take no lease (contracts/protocols.md §3)."""

    capabilities: VectorCapabilities

    def ensure_collections(self, spec: VectorSpec) -> None: ...
    def upsert(self, collection: Collection, records: Sequence[VectorRecord]) -> None: ...
    def delete(self, collection: Collection, ids: Sequence[str]) -> None: ...
    def delete_documents(self, collection: Collection, doc_ids: Sequence[str]) -> None: ...
    def search(
        self,
        collection: Collection,
        vectors: Sequence[Sequence[float]],
        k: int,
        where: VectorFilter | None,
    ) -> list[list[Hit]]: ...
    def search_text(
        self, collection: Collection, text_norm: str, k: int, where: VectorFilter | None
    ) -> list[Hit]: ...
    def get_vectors(self, collection: Collection, ids: Sequence[str]) -> dict[str, list[float]]: ...
