"""The committed corpus of 002 as store records (contract-suite.md §2 and §4, research R20).

Test support, not SDK code. Ids follow the SHA-256 recipes of engine brief §1,
with world ids standing for resolved identities; the parts of an id are
joined by U+001F and hashed to hex. Text is normalized by `norm()` with the
corpus's language, `vi` (ADR 0025). Statuses come from the version rule of
002 (`tests.support.corpus.derive.statuses`) over the documents written so
far, so the 41 documents end at graph.json.

`Corpus` builds any fact table, so `generated.py` shares these recipes.
`edited_write`, `expected_counts`, `snapshot`, `delete_all`, `store_id`,
`entity_id` and the `written` argument of `corpus_delete` are helpers the
contract does not name (tasks.md T081).
"""

from __future__ import annotations

import dataclasses
import functools
import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Final, NamedTuple, TypedDict, TypeVar

from tenetrag.engine.text import norm
from tenetrag.llm.fake import FakeEmbeddingModel
from tenetrag.packs import PackStack, load_pack, store_schema
from tenetrag.protocols import (
    AliasRow,
    AttributeSource,
    ChunkRecord,
    Collection,
    CollectionSpec,
    DocumentDelete,
    DocumentRecord,
    DocumentWrite,
    EntityWrite,
    EventEvidence,
    EventRecord,
    FactRow,
    JsonValue,
    Mention,
    RelationRow,
    RoleRow,
    StatusChange,
    TextInLink,
    VectorRecord,
    VectorSpec,
)
from tenetrag.protocols.records import OwnerKind, QuoteMatch, ValidPrecision, ValidSource
from tests.support.corpus.checks import STACK_NAME, refs
from tests.support.corpus.derive import Member, group_of, start_of, statuses, world_ids
from tests.support.corpus.facts import (
    Document,
    EntityItem,
    FactTable,
    Heading,
    RelationItem,
    StatementItem,
    WorldEntity,
    read_facts,
)
from tests.support.corpus.problems import CorpusError
from tests.support.packs import REPO_ROOT

if TYPE_CHECKING:
    from _typeshed import DataclassInstance

    from tests.support.contract.backends import ContractStores

CORPUS: Final = REPO_ROOT / "tests" / "fixtures" / "corpus"
LANGUAGES: Final = ("vi",)
RUN_ID: Final = "run-1"
DELETE_RUN_ID: Final = "run-2"
PIPELINE_HASH: Final = hashlib.sha256(b"tenetrag contract suite pipeline").hexdigest()
# Every relation and fact is recorded at this instant, so a rebuild gives equal rows.
RECORDED_AT: Final = datetime(2026, 1, 1, tzinfo=UTC)

_STACK: Final = load_pack(STACK_NAME)
_COLLECTION_SPEC: Final = CollectionSpec(model_id="fake-embed", dimensions=8)
SCHEMA: Final = store_schema(_STACK)
VECTOR_SPEC: Final = VectorSpec(
    chunks=_COLLECTION_SPEC, entities=_COLLECTION_SPEC, chunk_questions=_COLLECTION_SPEC
)
# The tables of data-model §6 that hold document rows, in its order.
COUNTED_TABLES: Final = (
    "documents",
    "chunks",
    "entities",
    "aliases",
    "attribute_sources",
    "identity_blocks",
    "mentions",
    "relations",
    "events",
    "event_evidence",
    "facts",
    "roles",
    "text_in",
    "same_as",
)

# U+203A, the scope path separator of engine brief §2, spelled by code point for the linter.
_SCOPE_SEPARATOR: Final = f" {chr(0x203A)} "

_Row = TypeVar("_Row", bound="DataclassInstance")
State = tuple[str, date | None]


def _sha(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()


def _norm(text: str) -> str:
    return norm(text, languages=LANGUAGES)


def _date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def question_id(chunk_id: str) -> str:
    """The id of a chunk's one generated question."""
    return _sha(chunk_id, "question", "0")


class _Chunk(NamedTuple):
    ordinal: int
    start: int
    end: int
    text: str
    heading_path: tuple[str, ...]
    chunk_hash: str
    chunk_id: str


class _ItemFields(TypedDict):
    """The fields a relation row and a fact row share."""

    attributes: dict[str, JsonValue]
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


def _chunks(document: Document, text: str) -> list[_Chunk]:
    """One chunk per block: the text split at blank lines, with offsets into the text."""
    parts = text.rstrip("\n").split("\n\n")
    if len(parts) != len(document.blocks):
        raise ValueError(
            f"{document.id} splits into {len(parts)} chunks for {len(document.blocks)} blocks; "
            "a block holds a blank line"
        )
    chunks = []
    headings: list[tuple[int, str]] = []
    start = 0
    for ordinal, (block, part) in enumerate(zip(document.blocks, parts, strict=True)):
        if isinstance(block, Heading):
            headings = [h for h in headings if h[0] < block.level] + [(block.level, block.heading)]
        chunk_hash = hashlib.sha256(part.encode()).hexdigest()
        chunk_id = _sha(document.id, str(ordinal), chunk_hash)
        path = tuple(heading for _, heading in headings)
        chunks.append(_Chunk(ordinal, start, start + len(part), part, path, chunk_hash, chunk_id))
        start += len(part) + len("\n\n")
    return chunks


def _place(chunks: Sequence[_Chunk], quoted: str, where: str) -> tuple[_Chunk, int, int]:
    """The first chunk holding `quoted`, and its span there."""
    for chunk in chunks:
        start = chunk.text.find(quoted)
        if start >= 0:
            return chunk, start, start + len(quoted)
    raise ValueError(f"{where}: no chunk holds {quoted!r}")


def _key_values(entity: WorldEntity, stack: PackStack) -> tuple[str, ...]:
    """The first key whose attributes the world gives, else the normalized name."""
    for key in stack.entities[entity.type].identity:
        names = [name for name in key.attributes if name != "scope"]
        if names and all(name in entity.attributes for name in names):
            return tuple(_norm(entity.attributes[name]) for name in names)
    return (_norm(entity.name),)


def _entity_ids(world: Mapping[str, WorldEntity], stack: PackStack) -> dict[str, str]:
    """Each world id's entity id; a scope's id comes before its members'."""
    ids: dict[str, str] = {}
    taken: set[str] = set()

    def resolve(world_id: str) -> str:
        if world_id not in ids:
            entity = world[world_id]
            scope = resolve(entity.scope) if entity.scope else ""
            parts = (entity.type, scope, *_key_values(entity, stack))
            entity_id, counter = _sha(*parts), 1
            while entity_id in taken:
                counter += 1
                entity_id = _sha(*parts, str(counter))
            taken.add(entity_id)
            ids[world_id] = entity_id
        return ids[world_id]

    for world_id in world:
        resolve(world_id)
    return ids


class Corpus:
    """A fact table as store records: ids and version members once, writes per call."""

    def __init__(self, table: FactTable, texts: Mapping[str, str]) -> None:
        self.table = table
        self.world = table.world.entities
        self.world_of = world_ids(table)
        self.entity_ids = _entity_ids(self.world, _STACK)
        self.documents = {document.id: document for document in table.documents}
        self.texts = dict(texts)
        self.chunks = {doc.id: _chunks(doc, self.texts[doc.id]) for doc in table.documents}
        self.store_ids: dict[str, str] = {}
        self.event_identity: dict[str, dict[str, tuple[str, ...]]] = {}
        self.groups: dict[str, str] = {}
        self.members: dict[str, list[tuple[str, Member]]] = {}
        for document in table.documents:
            self._index(document)

    # Ids

    def _index(self, document: Document) -> None:
        chunks = self.chunks[document.id]
        for item in document.items:
            if isinstance(item, EntityItem):
                self.store_ids[item.id] = self.entity_ids[item.world]
        # Events before facts, since an ActionItem may name its meeting.
        for item in document.items:
            if isinstance(item, StatementItem) and item.kind == "event":
                self.store_ids[item.id], self.event_identity[item.id] = self._event_id(
                    document, item, _place(chunks, item.quote, item.id)[0]
                )
        members = self.members.setdefault(document.id, [])
        for item in document.items:
            if isinstance(item, EntityItem) or (
                isinstance(item, StatementItem) and item.kind == "event"
            ):
                continue
            chunk = _place(chunks, item.quote, item.id)[0]
            self.store_ids[item.id] = self._item_id(document, item, chunk)
            group = group_of(self.table, document, item, self.world_of, _STACK)
            if group is None:
                continue
            start = start_of(item, document)
            if start is None:
                raise ValueError(f"{item.id} is in {group} but has no start")
            self.groups[item.id] = group
            members.append((group, Member(item.id, document.id, start, item.valid_to is not None)))

    def _event_id(
        self, document: Document, item: StatementItem, chunk: _Chunk
    ) -> tuple[str, dict[str, tuple[str, ...]]]:
        """The type and the identity values at creation; else the chunk and quote."""
        identity = {}
        for key in _STACK.events[item.type].identity[:1]:
            for name in key.attributes:
                values = self._event_values(document, item, name)
                if values:
                    identity[name] = values
        if not identity:
            return _sha(item.type, chunk.chunk_id, item.quote), identity
        parts = (f"{name}={','.join(values)}" for name, values in identity.items())
        return _sha(item.type, *parts), identity

    def _event_values(self, document: Document, item: StatementItem, name: str) -> tuple[str, ...]:
        if name == "time":
            start = start_of(item, document)
            return (start,) if start else ()
        if name in item.roles:
            return tuple(sorted(self.store_ids[ref] for ref in refs(item.roles[name])))
        if name in item.attributes:
            return (_norm(item.attributes[name].value),)
        return ()

    def _item_id(
        self, document: Document, item: RelationItem | StatementItem, chunk: _Chunk
    ) -> str:
        """chunk_id, type, resolved ends or roles, normalized attributes, valid time."""
        attributes = json.dumps(
            {name: _norm(quoted.value) for name, quoted in item.attributes.items()},
            sort_keys=True,
            ensure_ascii=False,
        )
        valid = (start_of(item, document) or "", item.valid_to or "")
        if isinstance(item, RelationItem):
            ends = (self.store_ids[item.from_], self.store_ids[item.to])
            return _sha(chunk.chunk_id, item.type, *ends, attributes, *valid)
        roles = ";".join(
            sorted(
                f"{role}={self.store_ids[ref]}"
                for role, targets in item.roles.items()
                for ref in refs(targets)
            )
        )
        return _sha(chunk.chunk_id, item.type, roles, attributes, *valid)

    def _ids(self, doc_ids: Sequence[str] | None) -> list[str]:
        if doc_ids is None:
            return list(self.documents)
        unknown = [doc_id for doc_id in doc_ids if doc_id not in self.documents]
        if unknown:
            raise KeyError(f"no document {', '.join(unknown)} in the corpus")
        return list(doc_ids)

    # Statuses

    def _grouped(self, doc_ids: Sequence[str]) -> dict[str, list[Member]]:
        grouped: dict[str, list[Member]] = {}
        for doc_id in doc_ids:
            for group, member in self.members[doc_id]:
                grouped.setdefault(group, []).append(member)
        return grouped

    def _state(self, entry: Mapping[str, str]) -> tuple[str, State]:
        return self.store_ids[entry["item"]], (entry["status"], _date(entry["closed_at"]))

    def expected_statuses(self, doc_ids: Sequence[str] | None) -> dict[str, State]:
        grouped = self._grouped(self._ids(doc_ids))
        return dict(
            self._state(entry) for members in grouped.values() for entry in statuses(members)
        )

    def delete(self, doc_id: str, *, run_id: str, written: Sequence[str] | None) -> DocumentDelete:
        """The status changes of graph.json `deletions`, over the documents written."""
        changes = []
        for members in self._grouped(self._ids(written)).values():
            remaining = [member for member in members if member.document != doc_id]
            if len(remaining) == len(members):
                continue
            kept = {member.item for member in remaining}
            after = statuses(remaining)
            if after != [entry for entry in statuses(members) if entry["item"] in kept]:
                for entry in after:
                    item_id, (status, closed_at) = self._state(entry)
                    changes.append(
                        StatusChange(item_id=item_id, status=status, closed_at=closed_at)
                    )
        return DocumentDelete(doc_id=doc_id, status_changes=tuple(changes), run_id=run_id)

    # Writes

    def writes(
        self, doc_ids: Sequence[str] | None, *, run_id: str, with_vectors: bool
    ) -> list[DocumentWrite]:
        """One write per document; each carries the status changes it causes to earlier ones."""
        grouped: dict[str, list[Member]] = {}
        current: dict[str, State] = {}
        writes = []
        for doc_id in self._ids(doc_ids):
            touched: dict[str, None] = {}
            for group, member in self.members[doc_id]:
                grouped.setdefault(group, []).append(member)
                touched[group] = None
            own: dict[str, State] = {}
            changes = []
            for group in touched:
                for entry in statuses(grouped[group]):
                    item_id, state = self._state(entry)
                    if entry["item"].split(".")[0] == doc_id:
                        own[item_id] = state
                    elif current[item_id] != state:
                        status, closed_at = state
                        changes.append(
                            StatusChange(item_id=item_id, status=status, closed_at=closed_at)
                        )
                    current[item_id] = state
            write = self.write(doc_id, run_id=run_id, states=own, status_changes=tuple(changes))
            writes.append(_with_vectors(write) if with_vectors else write)
        return writes

    def write(
        self,
        doc_id: str,
        *,
        run_id: str,
        states: Mapping[str, State],
        status_changes: tuple[StatusChange, ...],
    ) -> DocumentWrite:
        document = self.documents[doc_id]
        chunks = self.chunks[doc_id]
        observed_at = _date(document.dates.get("issued_on") or document.dates.get("held_on"))
        items = {item.id: item for item in document.items}
        entities: dict[str, EntityWrite] = {}
        aliases: dict[tuple[str, str, str], AliasRow] = {}
        sources, mentions, relations, facts, evidence, roles = [], [], [], [], [], []
        events: dict[str, EventRecord] = {}
        for item in document.items:
            if isinstance(item, EntityItem):
                entity_id = self.entity_ids[item.world]
                if entity_id not in entities:
                    entities[entity_id] = self._entity(item.world, run_id)
                chunk, start, end = _place(chunks, item.surface, item.id)
                mentions.append(
                    Mention(
                        entity_id=entity_id,
                        chunk_id=chunk.chunk_id,
                        doc_id=doc_id,
                        surface=item.surface,
                        start=start,
                        end=end,
                        run_id=run_id,
                    )
                )
                names = [(item.surface, "surface")] if item.is_name else []
                names += [(former.value, "former_name") for former in item.former_names]
                for alias, origin in names:
                    aliases.setdefault(
                        (entity_id, alias, origin),
                        AliasRow(
                            entity_id=entity_id,
                            alias=alias,
                            alias_norm=_norm(alias),
                            language=document.language,
                            origin="surface" if origin == "surface" else "former_name",
                            run_id=run_id,
                        ),
                    )
                for name, quoted in item.attributes.items():
                    chunk, start, end = _place(chunks, quoted.quote, f"{item.id}.{name}")
                    sources.append(
                        AttributeSource(
                            entity_id=entity_id,
                            attribute=name,
                            value=quoted.value,
                            value_norm=_norm(quoted.value),
                            doc_id=doc_id,
                            chunk_id=chunk.chunk_id,
                            quote=quoted.quote,
                            quote_start=start,
                            quote_end=end,
                            observed_at=observed_at,
                            run_id=run_id,
                        )
                    )
                continue
            chunk, start, end = _place(chunks, item.quote, item.id)
            item_id = self.store_ids[item.id]
            if isinstance(item, StatementItem):
                kind: OwnerKind = "event" if item.kind == "event" else "fact"
                for role, targets in item.roles.items():
                    for ref in refs(targets):
                        target = items[ref]
                        is_event = isinstance(target, StatementItem) and target.kind == "event"
                        roles.append(
                            RoleRow(
                                owner_id=item_id,
                                owner_kind=kind,
                                role=role,
                                target_id=self.store_ids[ref],
                                target_kind="event" if is_event else "entity",
                                doc_id=doc_id,
                                chunk_id=chunk.chunk_id,
                                run_id=run_id,
                            )
                        )
            if isinstance(item, StatementItem) and item.kind == "event":
                if item_id not in events:
                    events[item_id] = EventRecord(
                        event_id=item_id,
                        type=item.type,
                        attributes={name: q.value for name, q in item.attributes.items()},
                        identity=self.event_identity[item.id],
                        valid_from=_date(item.valid_from),
                        valid_to=_date(item.valid_to),
                        valid_precision="day" if item.valid_from else None,
                        pack=_STACK.stamp.name,
                        pack_version=str(_STACK.stamp.version),
                        run_id=run_id,
                    )
                evidence.append(
                    EventEvidence(
                        event_id=item_id,
                        doc_id=doc_id,
                        chunk_id=chunk.chunk_id,
                        quote=item.quote,
                        quote_start=start,
                        quote_end=end,
                        quote_match="exact",
                        observed_at=observed_at,
                        run_id=run_id,
                    )
                )
                continue
            valid_from = _date(start_of(item, document))
            status, closed_at = states.get(item_id, ("current", None))
            fields = _ItemFields(
                attributes={name: q.value for name, q in item.attributes.items()},
                valid_from=valid_from,
                valid_to=_date(item.valid_to),
                valid_precision="day" if valid_from else None,
                valid_source="text" if item.valid_from else "document",
                observed_at=observed_at,
                recorded_at=RECORDED_AT,
                status=status,
                closed_at=closed_at,
                version_key=self.groups.get(item.id),
                doc_id=doc_id,
                chunk_id=chunk.chunk_id,
                quote=item.quote,
                quote_start=start,
                quote_end=end,
                quote_match="exact",
                confidence=1.0,
                pack=_STACK.stamp.name,
                pack_version=str(_STACK.stamp.version),
                run_id=run_id,
            )
            if isinstance(item, RelationItem):
                relations.append(
                    RelationRow(
                        relation_id=item_id,
                        type=item.type,
                        subject_id=self.store_ids[item.from_],
                        object_id=self.store_ids[item.to],
                        **fields,
                    )
                )
            else:
                facts.append(FactRow(fact_id=item_id, type=item.type, **fields))
        return DocumentWrite(
            document=self._document(document, observed_at, run_id),
            chunks=tuple(
                ChunkRecord(
                    chunk_id=chunk.chunk_id,
                    doc_id=doc_id,
                    ordinal=chunk.ordinal,
                    start=chunk.start,
                    end=chunk.end,
                    text=chunk.text,
                    text_norm=_norm(chunk.text),
                    heading_path=chunk.heading_path,
                    page_start=None,
                    page_end=None,
                    chunk_hash=chunk.chunk_hash,
                    tokens=len(chunk.text.split()),
                    language=document.language,
                    run_id=run_id,
                )
                for chunk in chunks
            ),
            entities=tuple(entities.values()),
            aliases=tuple(aliases.values()),
            attribute_sources=tuple(sources),
            mentions=tuple(mentions),
            relations=tuple(relations),
            events=tuple(events.values()),
            event_evidence=tuple(evidence),
            facts=tuple(facts),
            roles=tuple(roles),
            text_in=tuple(
                TextInLink(
                    entity_id=self.entity_ids[link.entity],
                    doc_id=doc_id,
                    attribute="title",
                    run_id=run_id,
                )
                for link in self.table.graph.text_in
                if link.document == doc_id
            ),
            status_changes=status_changes,
            run_id=run_id,
        )

    def _entity(self, world_id: str, run_id: str) -> EntityWrite:
        entity = self.world[world_id]
        scopes: list[str] = []
        scope = entity.scope
        while scope is not None:
            scopes.insert(0, scope)
            scope = self.world[scope].scope
        label = entity.name
        if "version_label" in entity.attributes:
            label += f" · v{entity.attributes['version_label']}"
        if scopes:
            path = _SCOPE_SEPARATOR.join(self.world[scope].name for scope in scopes)
            label += f" ({path})"
        entity_type = _STACK.entities[entity.type]
        names = {name for key in entity_type.identity for name in key.attributes}
        names = (names | set(entity_type.vetoes)) - {"scope"}
        return EntityWrite(
            entity_id=self.entity_ids[world_id],
            type=entity.type,
            name=entity.name,
            name_norm=_norm(entity.name),
            label=label,
            scope_path=tuple(self.entity_ids[scope] for scope in scopes),
            scope_source="text" if scopes else None,
            identity={
                name: (_norm(entity.attributes[name]),)
                for name in sorted(names)
                if name in entity.attributes
            },
            run_id=run_id,
        )

    def _document(self, document: Document, doc_date: date | None, run_id: str) -> DocumentRecord:
        """The document card; code, version and subject come from its `text_in` entity."""
        link = next(
            (link for link in self.table.graph.text_in if link.document == document.id), None
        )
        subject = self.world[link.entity] if link is not None else None
        code = subject.attributes.get("code") if subject is not None else None
        return DocumentRecord(
            doc_id=document.id,
            source_uri=f"docs/{document.id}.md",
            content_hash=hashlib.sha256(self.texts[document.id].encode()).hexdigest(),
            pipeline_hash=PIPELINE_HASH,
            title=document.title,
            title_norm=_norm(document.title),
            code=code,
            code_norm=_norm(code) if code is not None else None,
            version_label=subject.attributes.get("version_label") if subject is not None else None,
            doc_date=doc_date,
            effective_from=_date(document.dates.get("effective_from")),
            effective_to=_date(document.dates.get("effective_to")),
            language=document.language,
            issuer_id=self.entity_ids[document.issuer],
            issuer_source="card",
            subject_type=subject.type if subject is not None else None,
            subject_id=self.entity_ids[link.entity] if link is not None else None,
            observed_at_source="card",
            run_id=run_id,
        )


def _with_vectors(write: DocumentWrite) -> DocumentWrite:
    """The write with its chunk, entity label and chunk question vectors."""
    model = FakeEmbeddingModel(dimensions=VECTOR_SPEC.chunks.dimensions)
    doc_id, language, run_id = write.document.doc_id, write.document.language, write.run_id
    questions = [f"Đoạn {chunk.ordinal} của {doc_id} nói gì?" for chunk in write.chunks]
    chunk_vectors = model.embed_documents([chunk.text for chunk in write.chunks])
    entity_vectors = model.embed_documents([entity.label for entity in write.entities])
    question_vectors = model.embed_documents(questions)
    vectors: dict[Collection, tuple[VectorRecord, ...]] = {
        "chunks": tuple(
            VectorRecord(
                id=chunk.chunk_id,
                vector=tuple(vector),
                doc_id=doc_id,
                type=None,
                language=language,
                run_id=run_id,
                text_norm=chunk.text_norm,
            )
            for chunk, vector in zip(write.chunks, chunk_vectors, strict=True)
        ),
        "entities": tuple(
            VectorRecord(
                id=entity.entity_id,
                vector=tuple(vector),
                doc_id=None,
                type=entity.type,
                language=None,
                run_id=run_id,
                text_norm=None,
            )
            for entity, vector in zip(write.entities, entity_vectors, strict=True)
        ),
        "chunk_questions": tuple(
            VectorRecord(
                id=question_id(chunk.chunk_id),
                vector=tuple(vector),
                doc_id=doc_id,
                type=None,
                language="vi",
                run_id=run_id,
                text_norm=_norm(question),
            )
            for chunk, question, vector in zip(
                write.chunks, questions, question_vectors, strict=True
            )
        ),
    }
    return dataclasses.replace(write, vectors=vectors)


@functools.cache
def _corpus() -> Corpus:
    table, problems = read_facts(CORPUS / "facts")
    if table is None:
        raise CorpusError(problems)
    docs = CORPUS / "generated" / "docs"
    texts = {doc.id: (docs / f"{doc.id}.md").read_bytes().decode() for doc in table.documents}
    return Corpus(table, texts)


def corpus_table() -> FactTable:
    """The committed fact table, read once."""
    return _corpus().table


def store_id(item_id: str) -> str:
    """The store id of a corpus item, such as `D1.5`; an entity item gives its entity's id."""
    return _corpus().store_ids[item_id]


def entity_id(world_id: str) -> str:
    """The entity id of a world id, such as `alpha`."""
    return _corpus().entity_ids[world_id]


def corpus_writes(
    doc_ids: Sequence[str] | None = None, *, run_id: str = RUN_ID, with_vectors: bool = True
) -> list[DocumentWrite]:
    """doc_ids=None: all 41, in corpus order. Vectors ride on the write when `with_vectors`."""
    return _corpus().writes(doc_ids, run_id=run_id, with_vectors=with_vectors)


def corpus_vectors(
    doc_ids: Sequence[str] | None = None, *, run_id: str = RUN_ID
) -> dict[Collection, list[VectorRecord]]:
    """The vectors of those writes, each id once, for split callers."""
    vectors: dict[Collection, dict[str, VectorRecord]] = {}
    for write in corpus_writes(doc_ids, run_id=run_id):
        for collection, records in write.vectors.items():
            for record in records:
                vectors.setdefault(collection, {}).setdefault(record.id, record)
    return {collection: list(records.values()) for collection, records in vectors.items()}


def corpus_delete(
    doc_id: str, *, run_id: str = DELETE_RUN_ID, written: Sequence[str] | None = None
) -> DocumentDelete:
    """graph.json `deletions` when every document is written, else the same rule over `written`."""
    return _corpus().delete(doc_id, run_id=run_id, written=written)


def expected_statuses(doc_ids: Sequence[str] | None = None) -> dict[str, State]:
    """Item id -> (status, closed_at) for every grouped item; graph.json `versions` for all 41."""
    return _corpus().expected_statuses(doc_ids)


def _rerun(rows: Iterable[_Row], run_id: str) -> tuple[_Row, ...]:
    return tuple(dataclasses.replace(row, run_id=run_id) for row in rows)


def edited_write(write: DocumentWrite, *, run_id: str) -> DocumentWrite:
    """The next version of a document: its last chunk gone, with every row that quoted it.

    Entities no longer named and events left without evidence go too; the
    status changes are kept as they were.
    """
    dropped = write.chunks[-1].chunk_id
    chunks = write.chunks[:-1]
    mentions = [row for row in write.mentions if row.chunk_id != dropped]
    relations = [row for row in write.relations if row.chunk_id != dropped]
    facts = [row for row in write.facts if row.chunk_id != dropped]
    evidence = [row for row in write.event_evidence if row.chunk_id != dropped]
    event_ids = {row.event_id for row in evidence}
    owners = event_ids | {row.fact_id for row in facts}
    roles = [
        row
        for row in write.roles
        if row.chunk_id != dropped
        and row.owner_id in owners
        and (row.target_kind == "entity" or row.target_id in event_ids)
    ]
    named = {row.entity_id for row in mentions}
    named |= {row.target_id for row in roles if row.target_kind == "entity"}
    named |= {end for row in relations for end in (row.subject_id, row.object_id)}
    gone = {entity.entity_id for entity in write.entities} - named
    surfaces = {(row.entity_id, row.surface) for row in mentions}
    vector_ids: dict[Collection, set[str]] = {
        "chunks": {chunk.chunk_id for chunk in chunks},
        "entities": named,
        "chunk_questions": {question_id(chunk.chunk_id) for chunk in chunks},
    }
    text = "\n\n".join(chunk.text for chunk in chunks) + "\n"
    return DocumentWrite(
        document=dataclasses.replace(
            write.document,
            content_hash=hashlib.sha256(text.encode()).hexdigest(),
            run_id=run_id,
        ),
        chunks=_rerun(chunks, run_id),
        entities=_rerun((row for row in write.entities if row.entity_id in named), run_id),
        aliases=_rerun(
            (
                row
                for row in write.aliases
                if row.entity_id in named
                and (row.origin != "surface" or (row.entity_id, row.alias) in surfaces)
            ),
            run_id,
        ),
        attribute_sources=_rerun(
            (row for row in write.attribute_sources if row.chunk_id != dropped), run_id
        ),
        identity_blocks=_rerun(
            (
                row
                for row in write.identity_blocks
                if row.chunk_id != dropped and row.entity_id not in gone
            ),
            run_id,
        ),
        mentions=_rerun(mentions, run_id),
        relations=_rerun(relations, run_id),
        events=_rerun((row for row in write.events if row.event_id in event_ids), run_id),
        event_evidence=_rerun(evidence, run_id),
        facts=_rerun(facts, run_id),
        roles=_rerun(roles, run_id),
        text_in=_rerun((row for row in write.text_in if row.entity_id not in gone), run_id),
        same_as=_rerun(
            (row for row in write.same_as if not {row.entity_a, row.entity_b} & gone), run_id
        ),
        status_changes=write.status_changes,
        vectors={
            collection: _rerun(
                (record for record in records if record.id in vector_ids[collection]), run_id
            )
            for collection, records in write.vectors.items()
        },
        run_id=run_id,
    )


def count_rows(writes: Sequence[DocumentWrite]) -> dict[str, int]:
    """Rows per table of data-model §6 after these writes; keyed tables count each key once."""

    def distinct(keys: Iterable[object]) -> int:
        return len(set(keys))

    return {
        "documents": distinct(w.document.doc_id for w in writes),
        "chunks": distinct(row.chunk_id for w in writes for row in w.chunks),
        "entities": distinct(row.entity_id for w in writes for row in w.entities),
        "aliases": distinct(
            (row.entity_id, row.alias, row.origin) for w in writes for row in w.aliases
        ),
        "attribute_sources": sum(len(w.attribute_sources) for w in writes),
        "identity_blocks": sum(len(w.identity_blocks) for w in writes),
        "mentions": sum(len(w.mentions) for w in writes),
        "relations": distinct(row.relation_id for w in writes for row in w.relations),
        "events": distinct(row.event_id for w in writes for row in w.events),
        "event_evidence": sum(len(w.event_evidence) for w in writes),
        "facts": distinct(row.fact_id for w in writes for row in w.facts),
        "roles": sum(len(w.roles) for w in writes),
        "text_in": distinct(
            (row.entity_id, row.doc_id, row.attribute) for w in writes for row in w.text_in
        ),
        "same_as": distinct((row.entity_a, row.entity_b) for w in writes for row in w.same_as),
    }


def expected_counts(doc_ids: Sequence[str] | None = None) -> dict[str, int]:
    """Rows per table after `corpus_writes(doc_ids)`."""
    return count_rows(corpus_writes(doc_ids, with_vectors=False))


def _without_run_ids(value: object) -> object:
    """A record as plain data, run ids left out at any depth."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _without_run_ids(getattr(value, field.name))
            for field in dataclasses.fields(value)
            if field.name != "run_id"
        }
    if isinstance(value, tuple | list):
        return [_without_run_ids(element) for element in value]
    if isinstance(value, Mapping):
        return {key: _without_run_ids(element) for key, element in value.items()}
    return value


def snapshot(stores: ContractStores, writes: Sequence[DocumentWrite]) -> dict[str, list[object]]:
    """Every row the protocols read back for the ids of `writes`, in read order.

    Run ids are left out, since a replay under a new run rewrites them; a test
    that checks run ids reads them itself.
    """
    graph, vectors = stores.graph, stores.vectors
    doc_ids = sorted({write.document.doc_id for write in writes})
    chunk_ids = sorted({row.chunk_id for write in writes for row in write.chunks})
    entity_ids = sorted({row.entity_id for write in writes for row in write.entities})
    item_ids = sorted(
        {row.relation_id for write in writes for row in write.relations}
        | {row.fact_id for write in writes for row in write.facts}
        | {row.event_id for write in writes for row in write.events}
    )
    version_keys = sorted(
        {row.version_key for write in writes for row in write.relations if row.version_key}
        | {row.version_key for write in writes for row in write.facts if row.version_key}
    )
    vector_ids: dict[Collection, list[str]] = {
        "chunks": chunk_ids,
        "entities": entity_ids,
        "chunk_questions": [question_id(chunk_id) for chunk_id in chunk_ids],
    }
    rows: dict[str, Sequence[object]] = {
        "documents": list(graph.get_documents(doc_ids)),
        "chunks": list(graph.get_chunks(chunk_ids)),
        "entities": list(graph.get_entities(entity_ids)),
        "items": list(graph.get_items(item_ids)),
        "mentions": list(graph.entities_in_chunks(chunk_ids)),
        "version_groups": list(graph.get_version_groups(version_keys)),
        "version_keys": sorted(graph.get_document_version_keys(doc_ids).items()),
        "states": sorted(
            (doc_id, state)
            for doc_id, state in graph.document_states().items()
            if doc_id in doc_ids
        ),
        "text_in": sorted(stores.text_in_links()),
    }
    for collection, ids in vector_ids.items():
        rows[f"vectors:{collection}"] = sorted(vectors.get_vectors(collection, ids).items())
    return {name: [_without_run_ids(row) for row in values] for name, values in rows.items()}


def _delete_stale(
    stores: ContractStores,
    previous: Mapping[Collection, set[str]],
    new: Mapping[Collection, set[str]],
) -> None:
    """Step 4 of the split sequence: the previous version's vectors the new one lacks.

    An entity vector goes only when the graph no longer holds the entity, since
    other documents may name it.
    """
    empty: set[str] = set()
    for collection in ("chunks", "chunk_questions"):
        stale = previous.get(collection, empty) - new.get(collection, empty)
        if stale:
            stores.vectors.delete(collection, sorted(stale))
    candidates = previous.get("entities", empty) - new.get("entities", empty)
    if candidates:
        alive = {entity.entity_id for entity in stores.graph.get_entities(sorted(candidates))}
        if candidates - alive:
            stores.vectors.delete("entities", sorted(candidates - alive))


def write_all(stores: ContractStores, writes: Sequence[DocumentWrite]) -> None:
    """Paired: `write_documents`. Split: the four steps of contract-suite.md §4, per document."""
    if stores.graph_writes_vectors:
        stores.graph.write_documents(writes)
        return
    for write in writes:
        doc_id = write.document.doc_id
        previous = stores.vector_ids.get(doc_id, {})
        for collection, records in write.vectors.items():
            stores.vectors.upsert(collection, records)
        stores.graph.write_documents([dataclasses.replace(write, vectors={})])
        new = {
            collection: {record.id for record in records}
            for collection, records in write.vectors.items()
        }
        _delete_stale(stores, previous, new)
        stores.vector_ids[doc_id] = new


def delete_all(stores: ContractStores, deletes: Sequence[DocumentDelete]) -> None:
    """`delete_documents`; split, then the deleted documents' vectors."""
    stores.graph.delete_documents(deletes)
    if stores.graph_writes_vectors:
        return
    for delete in deletes:
        _delete_stale(stores, stores.vector_ids.pop(delete.doc_id, {}), {})
