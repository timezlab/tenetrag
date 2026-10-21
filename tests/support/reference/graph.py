"""The reference graph store (research R19): the protocols written plainly in Python.

Each write unit copies the index's tables, applies its steps to the copy
and swaps the copy in after the last step's hook, so a unit that raises
leaves the previous version whole (stores.md §3). Every call holds the
database lock, as one transaction would.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import date, datetime, timedelta
from typing import Final, Literal, TypeVar

from tenetrag.protocols import (
    AliasRow,
    AttributeSource,
    ChunkRecord,
    ConfigError,
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
    HopResult,
    HopSpec,
    IdentityKey,
    ItemRecord,
    JsonValue,
    Mention,
    NameMatch,
    QueryError,
    RelationRow,
    RoleRow,
    RunRecord,
    RunStats,
    RunStatus,
    StatusChange,
    StepHook,
    StorageError,
    StoreSchema,
    TextInLink,
    Verdict,
    WriterBusyError,
    WriterLease,
    WriteStep,
)
from tenetrag.protocols.stores import LIMIT_MAX
from tests.support.reference import database
from tests.support.reference.database import CacheEntry, LeaseRow, ReferenceDatabase, Tables
from tests.support.reference.vectors import (
    ReferenceVectorStore,
    delete_document_vectors,
    delete_vectors,
    upsert_vectors,
)

TTL_MAX_S: Final = 86_400

_Row = TypeVar("_Row")
_Kept = TypeVar("_Kept", EntityWrite, AliasRow, EventRecord)


def _todo(task: str) -> NotImplementedError:
    return NotImplementedError(f"the reference graph store gets this in {task}")


def _check_ttl(ttl_s: int) -> None:
    if not 1 <= ttl_s <= TTL_MAX_S:
        raise ValueError(f"ttl_s is {ttl_s}; use 1 to {TTL_MAX_S} seconds")


def _keep(rows: list[_Row], drop: Callable[[_Row], bool]) -> list[_Row]:
    """The rows `drop` rejects, and `rows` emptied of them in place."""
    dropped = [row for row in rows if drop(row)]
    rows[:] = [row for row in rows if not drop(row)]
    return dropped


def _started(run: RunRecord) -> datetime:
    if run.started_at is None:
        raise StorageError(f"run '{run.run_id}' has no started_at; begin_run sets it")
    return run.started_at


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


def _attribute_order(source: AttributeSource) -> tuple[bool, int, str, str, int]:
    """Newest observed_at first, a missing date last, then doc, chunk and quote start."""
    observed = source.observed_at
    return (
        observed is None,
        -(observed or date.min).toordinal(),
        source.doc_id,
        source.chunk_id,
        source.quote_start,
    )


def _version_order(item: ItemRecord) -> tuple[str, bool, date, str]:
    return (
        item.version_key or "",
        item.valid_from is not None,
        item.valid_from or date.min,
        item.item_id,
    )


class ReferenceGraphStore:
    """`vectors` set: paired, the units write the vectors (stores.md §3.3)."""

    def __init__(
        self,
        db: ReferenceDatabase,
        index_id: str,
        *,
        vectors: ReferenceVectorStore | None = None,
        step_hook: StepHook | None = None,
    ) -> None:
        self._db = db
        self._index_id = index_id
        self._vectors = vectors
        self._step_hook = step_hook
        self._lease: WriterLease | None = None
        self._layout_checked = False

    # Layout and lease checks; call each under the lock.

    def _check_version(self, recorded: int) -> None:
        if recorded != database.LAYOUT_VERSION:
            raise ConfigError(
                f"Index `{self._index_id}` has layout version {recorded}, and this code reads "
                f"version {database.LAYOUT_VERSION}; rebuild it under a new index id"
            )

    def _tables(self) -> Tables:
        """The index's tables, after the layout check of data-model §9."""
        tables = self._db.tables(self._index_id)
        if not self._layout_checked:
            if tables.layout_version is None:
                raise StorageError(f"index `{self._index_id}` has no schema; call ensure_schema")
            self._check_version(tables.layout_version)
            self._layout_checked = True
        return tables

    def _writable(self) -> Tables:
        """The tables, once the lease this store holds is still the index's (stores.md §2)."""
        tables = self._tables()
        if self._lease is None:
            raise StorageError(
                f"This store holds no writer lease on index `{self._index_id}`; "
                "call acquire_writer before writing"
            )
        held, mine = tables.lease, self._lease
        if held is None:
            raise WriterBusyError(owner=mine.owner, expires_at=mine.expires_at)
        if (held.owner, held.fence) != (
            mine.owner,
            mine.fence,
        ) or held.expires_at <= self._db.clock():
            raise WriterBusyError(owner=held.owner, expires_at=held.expires_at)
        return tables

    def _schema(self, tables: Tables) -> StoreSchema:
        if tables.schema is None:
            raise StorageError(f"index `{self._index_id}` has no schema; call ensure_schema")
        return tables.schema

    # Setup, writer lease, runs

    def ensure_schema(self, schema: StoreSchema) -> None:
        with self._db.lock:
            tables = self._db.tables(self._index_id)
            if tables.layout_version is None:
                tables.layout_version = database.LAYOUT_VERSION
                tables.schema = schema
            else:
                self._check_version(tables.layout_version)
                tables.schema = self._schema(tables).merged(schema)
            self._layout_checked = True

    def acquire_writer(self, owner: str, ttl_s: int) -> WriterLease:
        _check_ttl(ttl_s)
        with self._db.lock:
            tables = self._tables()
            now = self._db.clock()
            held = tables.lease
            if held is not None and held.owner != owner and held.expires_at > now:
                raise WriterBusyError(owner=held.owner, expires_at=held.expires_at)
            # A new holder fences the last one out; the same owner keeps its fence.
            fence = 1 if held is None else held.fence + (held.owner != owner)
            lease = WriterLease(
                index_id=self._index_id,
                owner=owner,
                fence=fence,
                expires_at=now + timedelta(seconds=ttl_s),
            )
            tables.lease = LeaseRow(owner=owner, fence=fence, expires_at=lease.expires_at)
            self._lease = lease
            return lease

    def renew_writer(self, lease: WriterLease, ttl_s: int) -> WriterLease:
        _check_ttl(ttl_s)
        with self._db.lock:
            tables = self._tables()
            now = self._db.clock()
            held = tables.lease
            if held is None:
                raise WriterBusyError(owner=lease.owner, expires_at=lease.expires_at)
            if (held.owner, held.fence) != (lease.owner, lease.fence) or held.expires_at <= now:
                raise WriterBusyError(owner=held.owner, expires_at=held.expires_at)
            renewed = dataclasses.replace(lease, expires_at=now + timedelta(seconds=ttl_s))
            tables.lease = LeaseRow(
                owner=held.owner, fence=held.fence, expires_at=renewed.expires_at
            )
            self._lease = renewed
            return renewed

    def release_writer(self, lease: WriterLease) -> None:
        with self._db.lock:
            tables = self._tables()
            held = tables.lease
            if held is not None and (held.owner, held.fence) == (lease.owner, lease.fence):
                ended = min(held.expires_at, self._db.clock())
                tables.lease = dataclasses.replace(held, expires_at=ended)
            if self._lease is not None and (self._lease.owner, self._lease.fence) == (
                lease.owner,
                lease.fence,
            ):
                self._lease = None

    def begin_run(self, run: RunRecord) -> None:
        with self._db.lock:
            tables = self._writable()
            tables.runs[run.run_id] = dataclasses.replace(
                run, status=RunStatus.RUNNING, started_at=self._db.clock(), finished_at=None
            )

    def finish_run(self, run_id: str, status: RunStatus, stats: RunStats) -> None:
        if status is RunStatus.RUNNING:
            raise ValueError("finish_run got status running; pass the run's final status")
        with self._db.lock:
            tables = self._writable()
            run = tables.runs.get(run_id)
            if run is None:
                raise QueryError(
                    f"index `{self._index_id}` has no run '{run_id}'; call begin_run first"
                )
            tables.runs[run_id] = dataclasses.replace(
                run, status=status, stats=dict(stats), finished_at=self._db.clock()
            )

    def get_runs(self, limit: int) -> list[RunRecord]:
        if not 1 <= limit <= LIMIT_MAX:
            raise ValueError(f"limit is {limit}; use 1 to {LIMIT_MAX}")
        with self._db.lock:
            runs = list(self._tables().runs.values())
        return sorted(runs, key=lambda run: (-_started(run).timestamp(), run.run_id))[:limit]

    # Change detection and caches

    def document_states(self) -> dict[str, DocumentState]:
        with self._db.lock:
            documents = self._tables().documents
            return {
                doc_id: DocumentState(
                    content_hash=document.content_hash,
                    pipeline_hash=document.pipeline_hash,
                    run_id=document.run_id,
                )
                for doc_id, document in documents.items()
            }

    def get_cached_extractions(self, keys: Sequence[str]) -> dict[str, bytes]:
        with self._db.lock:
            cache = self._tables().extraction_cache
            return {key: cache[key].payload for key in keys if key in cache}

    def put_cached_extractions(self, entries: Mapping[str, bytes]) -> None:
        with self._db.lock:
            tables = self._writable()
            now = self._db.clock()
            for key, payload in entries.items():
                tables.extraction_cache[key] = CacheEntry(payload=payload, created_at=now)

    def get_resolution_decisions(self, pair_keys: Sequence[str]) -> dict[str, Verdict]:
        with self._db.lock:
            decisions = self._tables().resolution_decisions
            return {key: decisions[key] for key in pair_keys if key in decisions}

    def put_resolution_decisions(self, decisions: Sequence[Verdict]) -> None:
        with self._db.lock:
            stored = self._writable().resolution_decisions
            for decision in decisions:
                previous = stored.get(decision.pair_key)
                # FR-018: a model never overrides a reviewer; skipped, not an error.
                if (
                    previous is not None
                    and previous.method == "reviewer"
                    and decision.method == "llm"
                ):
                    continue
                stored[decision.pair_key] = decision

    # Resolution and linking

    def find_by_identity(self, keys: Sequence[IdentityKey]) -> list[EntityRecord]:
        raise _todo("T039")

    def find_events(self, keys: Sequence[IdentityKey]) -> list[EventRecord]:
        raise _todo("T039")

    def match_names(
        self,
        names_norm: Sequence[str],
        types: Sequence[str] | None,
        exclude_run: str | None = None,
    ) -> list[NameMatch]:
        raise _todo("T039")

    def search_names(
        self, text_norm: str, types: Sequence[str] | None, limit: int, min_similarity: float
    ) -> list[NameMatch]:
        raise _todo("T039")

    def match_document_links(self, keys: Sequence[DocumentLinkKey]) -> list[TextInLink]:
        raise _todo("T039")

    # Versions

    def get_version_groups(self, version_keys: Sequence[str]) -> list[ItemRecord]:
        wanted = set(version_keys)
        with self._db.lock:
            tables = self._tables()
            items = [
                self._relation_item(row)
                for row in tables.relations.values()
                if row.version_key in wanted
            ]
            items += [
                self._fact_item(tables, row)
                for row in tables.facts.values()
                if row.version_key in wanted
            ]
        return sorted(items, key=_version_order)

    def get_document_version_keys(self, doc_ids: Sequence[str]) -> dict[str, list[str]]:
        with self._db.lock:
            tables = self._tables()
            found = {doc_id: set[str]() for doc_id in doc_ids if doc_id in tables.documents}
            rows: Iterable[RelationRow | FactRow] = [
                *tables.relations.values(),
                *tables.facts.values(),
            ]
            for row in rows:
                if row.version_key is not None and row.doc_id in found:
                    found[row.doc_id].add(row.version_key)
        return {doc_id: sorted(keys) for doc_id, keys in found.items()}

    # Writes

    def write_documents(self, writes: Sequence[DocumentWrite]) -> None:
        for write in writes:
            with self._db.lock:
                tables = self._writable()
                self._check_types(self._schema(tables), write)
                if self._vectors is None and any(write.vectors.values()):
                    raise StorageError(
                        f"Document '{write.document.doc_id}' carries vectors, but this graph "
                        "store's vectors live on another connection; upsert them through the "
                        "vector store and leave DocumentWrite.vectors empty"
                    )
                unit = tables.copy()
                self._write_unit(unit, write)
                self._db.swap(self._index_id, unit)

    def delete_documents(self, deletes: Sequence[DocumentDelete]) -> None:
        for delete in deletes:
            with self._db.lock:
                unit = self._writable().copy()
                self._delete_unit(unit, delete)
                self._db.swap(self._index_id, unit)

    def refresh_degrees(self, entity_ids: Sequence[str]) -> None:
        raise _todo("T040")

    # Retrieval reads

    def entities_in_chunks(self, chunk_ids: Sequence[str]) -> list[Mention]:
        wanted = set(chunk_ids)
        with self._db.lock:
            mentions = [row for row in self._tables().mentions if row.chunk_id in wanted]
        return sorted(mentions, key=lambda row: (row.chunk_id, row.start, row.entity_id))

    def hop(self, entity_ids: Sequence[str], spec: HopSpec) -> HopResult:
        raise _todo("T040")

    def get_entities(self, entity_ids: Sequence[str]) -> list[EntityRecord]:
        wanted = sorted(set(entity_ids))
        with self._db.lock:
            tables = self._tables()
            return [
                self._entity_record(tables, tables.entities[entity_id])
                for entity_id in wanted
                if entity_id in tables.entities
            ]

    def get_items(self, item_ids: Sequence[str]) -> list[ItemRecord]:
        items = []
        with self._db.lock:
            tables = self._tables()
            for item_id in sorted(set(item_ids)):
                if item_id in tables.relations:
                    items.append(self._relation_item(tables.relations[item_id]))
                elif item_id in tables.facts:
                    items.append(self._fact_item(tables, tables.facts[item_id]))
                elif item_id in tables.events:
                    items.append(self._event_item(tables, tables.events[item_id]))
        return items

    def get_chunks(self, chunk_ids: Sequence[str]) -> list[ChunkRecord]:
        with self._db.lock:
            chunks = self._tables().chunks
            return [chunks[chunk_id] for chunk_id in sorted(set(chunk_ids)) if chunk_id in chunks]

    def get_documents(self, doc_ids: Sequence[str]) -> list[DocumentRecord]:
        with self._db.lock:
            documents = self._tables().documents
            return [documents[doc_id] for doc_id in sorted(set(doc_ids)) if doc_id in documents]

    # The units of stores.md §3; each runs on a copy of the tables.

    def _hook(self, step: WriteStep, doc_id: str) -> None:
        if self._step_hook is not None:
            self._step_hook(step, doc_id)

    def _check_types(self, schema: StoreSchema, write: DocumentWrite) -> None:
        named = (
            [("Entity", row.type, schema.entity_types) for row in write.entities]
            + [("Relation", row.type, schema.relation_types) for row in write.relations]
            + [("Fact", row.type, schema.fact_types) for row in write.facts]
            + [("Event", row.type, schema.event_types) for row in write.events]
        )
        for kind, type_name, known in named:
            if type_name not in known:
                raise ConfigError(
                    f"{kind} type '{type_name}' in document '{write.document.doc_id}' is not in "
                    f"the schema of index `{self._index_id}`; add its pack and call ensure_schema"
                )

    def _write_unit(self, unit: Tables, write: DocumentWrite) -> None:
        doc_id = write.document.doc_id
        entity_ids, event_ids = self._delete_previous(unit, doc_id)
        self._hook(WriteStep.DELETE_PREVIOUS, doc_id)
        self._insert(unit, write)
        entity_ids |= {row.entity_id for row in write.entities}
        event_ids |= {row.event_id for row in write.events}
        self._hook(WriteStep.INSERT, doc_id)
        self._change_statuses(unit, write.status_changes)
        self._hook(WriteStep.STATUS_CHANGES, doc_id)
        self._delete_orphans(unit, entity_ids, event_ids)
        self._hook(WriteStep.DELETE_ORPHANS, doc_id)
        unit.documents[doc_id] = write.document
        self._hook(WriteStep.DOCUMENT_ROW, doc_id)

    def _delete_unit(self, unit: Tables, delete: DocumentDelete) -> None:
        doc_id = delete.doc_id
        entity_ids, event_ids = self._delete_previous(unit, doc_id)
        self._hook(WriteStep.DELETE_PREVIOUS, doc_id)
        self._change_statuses(unit, delete.status_changes)
        self._hook(WriteStep.STATUS_CHANGES, doc_id)
        self._delete_orphans(unit, entity_ids, event_ids)
        self._hook(WriteStep.DELETE_ORPHANS, doc_id)
        unit.documents.pop(doc_id, None)
        self._hook(WriteStep.DOCUMENT_ROW, doc_id)

    def _delete_previous(self, unit: Tables, doc_id: str) -> tuple[set[str], set[str]]:
        """Remove the document's rows; return the entities and events they held."""
        entity_ids: set[str] = set()
        event_ids: set[str] = set()
        for chunk_id in [key for key, chunk in unit.chunks.items() if chunk.doc_id == doc_id]:
            del unit.chunks[chunk_id]
        for relation_id in [key for key, row in unit.relations.items() if row.doc_id == doc_id]:
            row = unit.relations.pop(relation_id)
            entity_ids |= {row.subject_id, row.object_id}
        for fact_id in [key for key, row in unit.facts.items() if row.doc_id == doc_id]:
            del unit.facts[fact_id]
        entity_ids |= {row.entity_id for row in _keep(unit.mentions, lambda r: r.doc_id == doc_id)}
        for role in _keep(unit.roles, lambda r: r.doc_id == doc_id):
            (entity_ids if role.target_kind == "entity" else event_ids).add(role.target_id)
            if role.owner_kind == "event":
                event_ids.add(role.owner_id)
        event_ids |= {
            row.event_id for row in _keep(unit.event_evidence, lambda r: r.doc_id == doc_id)
        }
        _keep(unit.attribute_sources, lambda r: r.doc_id == doc_id)
        _keep(unit.identity_blocks, lambda r: r.doc_id == doc_id)
        for key in [key for key, link in unit.text_in.items() if link.doc_id == doc_id]:
            del unit.text_in[key]
        if self._vectors is not None:
            delete_document_vectors(unit, "chunks", [doc_id])
            delete_document_vectors(unit, "chunk_questions", [doc_id])
        return entity_ids, event_ids

    def _insert(self, unit: Tables, write: DocumentWrite) -> None:
        for chunk in write.chunks:
            unit.chunks[chunk.chunk_id] = chunk
        for entity in write.entities:
            unit.entities[entity.entity_id] = _first_run(
                unit.entities.get(entity.entity_id), entity
            )
        for alias in write.aliases:
            key = (alias.entity_id, alias.alias, alias.origin)
            unit.aliases[key] = _first_run(unit.aliases.get(key), alias)
        unit.attribute_sources.extend(write.attribute_sources)
        unit.identity_blocks.extend(write.identity_blocks)
        unit.mentions.extend(write.mentions)
        for relation in write.relations:
            unit.relations[relation.relation_id] = relation
        for event in write.events:
            unit.events[event.event_id] = _first_run(unit.events.get(event.event_id), event)
        unit.event_evidence.extend(write.event_evidence)
        for fact in write.facts:
            unit.facts[fact.fact_id] = fact
        unit.roles.extend(write.roles)
        for link in write.text_in:
            unit.text_in[(link.entity_id, link.doc_id, link.attribute)] = link
        for same_as in write.same_as:
            unit.same_as[(same_as.entity_a, same_as.entity_b)] = same_as
        if self._vectors is not None:
            for collection, records in write.vectors.items():
                upsert_vectors(unit, collection, records, self._index_id)

    def _change_statuses(self, unit: Tables, changes: Sequence[StatusChange]) -> None:
        for change in changes:
            status, closed_at = change.status, change.closed_at
            if change.item_id in unit.relations:
                relation = unit.relations[change.item_id]
                unit.relations[change.item_id] = dataclasses.replace(
                    relation, status=status, closed_at=closed_at
                )
            elif change.item_id in unit.facts:
                fact = unit.facts[change.item_id]
                unit.facts[change.item_id] = dataclasses.replace(
                    fact, status=status, closed_at=closed_at
                )
            else:
                raise QueryError(
                    f"A status change names item '{change.item_id}', which index "
                    f"`{self._index_id}` holds no relation or fact for; the unit was rolled back"
                )

    def _delete_orphans(self, unit: Tables, entity_ids: set[str], event_ids: set[str]) -> None:
        """Research R15: only the entities and events this unit touched or emptied."""
        with_evidence = {row.event_id for row in unit.event_evidence}
        gone_events = {
            event_id for event_id in event_ids - with_evidence if event_id in unit.events
        }
        for event_id in gone_events:
            del unit.events[event_id]
        for role in _keep(
            unit.roles,
            lambda r: (
                r.owner_id in gone_events
                or (r.target_kind == "event" and r.target_id in gone_events)
            ),
        ):
            if role.target_kind == "entity":
                entity_ids.add(role.target_id)
        alive = {row.entity_id for row in unit.mentions}
        alive |= {row.target_id for row in unit.roles if row.target_kind == "entity"}
        alive |= {end for row in unit.relations.values() for end in (row.subject_id, row.object_id)}
        orphans = {entity_id for entity_id in entity_ids - alive if entity_id in unit.entities}
        if not orphans:
            return
        for entity_id in orphans:
            del unit.entities[entity_id]
            unit.degrees.pop(entity_id, None)
        for alias_key in [key for key in unit.aliases if key[0] in orphans]:
            del unit.aliases[alias_key]
        _keep(unit.attribute_sources, lambda r: r.entity_id in orphans)
        _keep(unit.identity_blocks, lambda r: r.entity_id in orphans or r.candidate_id in orphans)
        for link_key in [key for key in unit.text_in if key[0] in orphans]:
            del unit.text_in[link_key]
        for pair in [pair for pair in unit.same_as if pair[0] in orphans or pair[1] in orphans]:
            del unit.same_as[pair]
        if self._vectors is not None:
            delete_vectors(unit, "entities", orphans)

    # Read records of data-model §3

    def _entity_record(self, tables: Tables, entity: EntityWrite) -> EntityRecord:
        attributes: dict[str, JsonValue] = {}
        sources = [row for row in tables.attribute_sources if row.entity_id == entity.entity_id]
        for source in sorted(sources, key=_attribute_order):
            attributes.setdefault(source.attribute, source.value)
        aliases = sorted(
            (row for key, row in tables.aliases.items() if key[0] == entity.entity_id),
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
            degree=tables.degrees.get(entity.entity_id, 0),
            run_id=entity.run_id,
        )

    def _relation_item(self, row: RelationRow) -> ItemRecord:
        return _stated_item(
            row,
            item_id=row.relation_id,
            kind="relation",
            subject_id=row.subject_id,
            object_id=row.object_id,
            roles=(),
        )

    def _fact_item(self, tables: Tables, row: FactRow) -> ItemRecord:
        return _stated_item(
            row,
            item_id=row.fact_id,
            kind="fact",
            subject_id=None,
            object_id=None,
            roles=_roles(tables, row.fact_id),
        )

    def _event_item(self, tables: Tables, event: EventRecord) -> ItemRecord:
        evidence = sorted(
            (row for row in tables.event_evidence if row.event_id == event.event_id),
            key=lambda row: (row.doc_id, row.chunk_id, row.quote_start),
        )
        return ItemRecord(
            item_id=event.event_id,
            kind="event",
            type=event.type,
            subject_id=None,
            object_id=None,
            roles=_roles(tables, event.event_id),
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


def _first_run(previous: _Kept | None, row: _Kept) -> _Kept:
    """Entities, aliases and events keep the run that first wrote them (data-model §1)."""
    return row if previous is None else dataclasses.replace(row, run_id=previous.run_id)


def _roles(tables: Tables, owner_id: str) -> tuple[RoleRow, ...]:
    owned = (row for row in tables.roles if row.owner_id == owner_id)
    return tuple(sorted(owned, key=lambda row: (row.role, row.target_id)))


def _stated_item(
    row: RelationRow | FactRow,
    *,
    item_id: str,
    kind: Literal["relation", "fact"],
    subject_id: str | None,
    object_id: str | None,
    roles: tuple[RoleRow, ...],
) -> ItemRecord:
    """A relation or a fact as a read record; the two share every stated field."""
    return ItemRecord(
        item_id=item_id,
        kind=kind,
        type=row.type,
        subject_id=subject_id,
        object_id=object_id,
        roles=roles,
        attributes=row.attributes,
        valid_from=row.valid_from,
        valid_to=row.valid_to,
        valid_precision=row.valid_precision,
        valid_source=row.valid_source,
        observed_at=row.observed_at,
        recorded_at=row.recorded_at,
        status=row.status,
        closed_at=row.closed_at,
        version_key=row.version_key,
        evidence=(_evidence(row),),
        confidence=row.confidence,
        pack=row.pack,
        pack_version=row.pack_version,
        run_id=row.run_id,
    )
