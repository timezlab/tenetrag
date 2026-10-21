"""The reference store's server: tables per index id, one lock and a clock (research R19).

Several store objects can share one `ReferenceDatabase`, as clients share a
real server, so the lease, isolation and replay cases run as they would on
Postgres or Neo4j. A write unit copies an index's `Tables`, changes the copy
and swaps it in at the end, so a unit that raises leaves the old tables.
Records are frozen, so a copy of each container is enough.
"""

from __future__ import annotations

import dataclasses
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from tenetrag.protocols import (
    AliasRow,
    AttributeSource,
    ChunkRecord,
    Collection,
    CollectionSpec,
    DocumentRecord,
    EntityWrite,
    EventEvidence,
    EventRecord,
    FactRow,
    IdentityBlock,
    Mention,
    RelationRow,
    RoleRow,
    RunRecord,
    SameAsLink,
    StoreSchema,
    TextInLink,
    VectorRecord,
    Verdict,
)

# The layout this code writes and reads (data-model §9). Tests patch it to see a mismatch.
LAYOUT_VERSION = 1

Clock = Callable[[], datetime]


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class LeaseRow:
    owner: str
    fence: int
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class CacheEntry:
    payload: bytes
    created_at: datetime


@dataclass(slots=True)
class Tables:
    """One index's rows, by the table names of data-model §6."""

    layout_version: int | None = None
    schema: StoreSchema | None = None
    lease: LeaseRow | None = None
    runs: dict[str, RunRecord] = field(default_factory=dict)
    documents: dict[str, DocumentRecord] = field(default_factory=dict)
    chunks: dict[str, ChunkRecord] = field(default_factory=dict)
    entities: dict[str, EntityWrite] = field(default_factory=dict)
    degrees: dict[str, int] = field(default_factory=dict)
    aliases: dict[tuple[str, str, str], AliasRow] = field(default_factory=dict)
    attribute_sources: list[AttributeSource] = field(default_factory=list)
    identity_blocks: list[IdentityBlock] = field(default_factory=list)
    mentions: list[Mention] = field(default_factory=list)
    relations: dict[str, RelationRow] = field(default_factory=dict)
    events: dict[str, EventRecord] = field(default_factory=dict)
    event_evidence: list[EventEvidence] = field(default_factory=list)
    facts: dict[str, FactRow] = field(default_factory=dict)
    roles: list[RoleRow] = field(default_factory=list)
    text_in: dict[tuple[str, str, str], TextInLink] = field(default_factory=dict)
    same_as: dict[tuple[str, str], SameAsLink] = field(default_factory=dict)
    resolution_decisions: dict[str, Verdict] = field(default_factory=dict)
    extraction_cache: dict[str, CacheEntry] = field(default_factory=dict)
    collections: dict[Collection, CollectionSpec] = field(default_factory=dict)
    vectors: dict[Collection, dict[str, VectorRecord]] = field(default_factory=dict)

    def copy(self) -> Tables:
        """A copy whose containers can change without touching these."""
        copied = {}
        for spec in dataclasses.fields(self):
            value = getattr(self, spec.name)
            if spec.name == "vectors":
                value = {collection: dict(rows) for collection, rows in value.items()}
            elif isinstance(value, dict | list):
                value = type(value)(value)
            copied[spec.name] = value
        return Tables(**copied)


class ReferenceDatabase:
    """Plays a server: every store object on it sees the same tables, under one lock."""

    def __init__(self, *, clock: Clock = utc_now) -> None:
        self.lock = threading.RLock()
        self.clock = clock
        self._indexes: dict[str, Tables] = {}

    def tables(self, index_id: str) -> Tables:
        """The index's tables, empty on first use. Call under `lock`."""
        return self._indexes.setdefault(index_id, Tables())

    def swap(self, index_id: str, tables: Tables) -> None:
        """Make `tables` the index's tables, ending a unit. Call under `lock`."""
        self._indexes[index_id] = tables
