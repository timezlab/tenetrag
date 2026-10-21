# Data model: Store protocols, the reference store, the contract suite and the Postgres and Neo4j stores (M1, part 2)

The shapes feature 003 defines, with their validation rules. Names here
are public unless marked private (`_name`). The reasons are in
[research.md](research.md), and call signatures are in
[contracts/](contracts/). Columns follow the logical tables of
[engine brief §1](../../docs/product/engine-brief.md#logical-tables);
this file names what the brief leaves open and what this feature adds.

## 1. Common rules

- Every record is a frozen dataclass with `slots=True` and
  `kw_only=True`, in `tenetrag.protocols.records` or
  `tenetrag.protocols.stores`. Sequences are tuples. Mappings are plain
  `dict`s typed `Mapping`, never mutated by a store.
- Dates are `datetime.date`. Times are UTC `datetime`s with `tzinfo`; a
  naive time raises `ValueError` in `__post_init__`.
- `JsonValue` is `str | int | float | bool | None | list[JsonValue] |
  dict[str, JsonValue]`. Pack attributes are `Mapping[str, JsonValue]`;
  dates inside them are ISO strings.
- Ids are opaque strings that the engine computes
  ([§1](../../docs/product/engine-brief.md#ids-and-hashes)). A store
  checks only that an id is non-empty.
- `run_id` on a row is the run that wrote it. Entities, aliases and
  events keep the run that first wrote them; an upsert never changes it
  (research R2). Every other row is rewritten with its document.
- `__post_init__` checks shape only: non-empty ids, spans with
  `start <= end`, a known literal value, paired fields present together.
  It never checks what the engine owns, such as a status transition.

## 2. Write records

### 2.1 `DocumentWrite` and `DocumentDelete`

```
DocumentWrite(document: DocumentRecord, chunks, entities, aliases, attribute_sources,
              identity_blocks, mentions, relations, events, event_evidence, facts, roles,
              text_in, same_as, status_changes, vectors, run_id)
DocumentDelete(doc_id, status_changes, run_id)
StatusChange(item_id, status, closed_at: date | None)
```

- Every field after `document` is a tuple of the row records below,
  empty by default. `vectors` is a `Mapping[Collection, tuple[VectorRecord,
  ...]]`, empty unless the graph store writes the vectors (§7.5).
- Every row's `doc_id` equals `document.doc_id`, except `text_in` rows,
  which may name another document (§2.4); a mismatch raises `ValueError`.
- `status_changes` name relation or fact ids, usually of other
  documents' rows. `status` is the engine's value (`current`,
  `superseded`, `conflicting`); the store keeps the string.

### 2.2 Document and chunk

```
DocumentRecord(doc_id, source_uri, content_hash, pipeline_hash, title, title_norm, code,
               code_norm, version_label, doc_date, effective_from, effective_to, language,
               issuer_id, issuer_source, subject_type, subject_id, observed_at_source, run_id)
ChunkRecord(chunk_id, doc_id, ordinal, start, end, text, text_norm, heading_path: tuple[str, ...],
            page_start, page_end, chunk_hash, tokens, language, run_id)
```

- `title_norm` and `code_norm` are new matching columns for
  `match_document_links` (research R2). Both are `None` when the card has
  no title or code.
- `observed_at_source` is `caller`, `card` or `ingest`.
- The same records come back from `get_documents` and `get_chunks`.

### 2.3 Entities, aliases and what hangs on them

```
EntityWrite(entity_id, type, name, name_norm, label, scope_path: tuple[str, ...], scope_source,
            identity: Mapping[str, tuple[str, ...]], run_id)
AliasRow(entity_id, alias, alias_norm, language, origin, run_id)
AttributeSource(entity_id, attribute, value: JsonValue, value_norm, doc_id, chunk_id, quote,
                quote_start, quote_end, observed_at: date | None, run_id)
IdentityBlock(entity_id, candidate_id, attribute, value, candidate_value, quote,
              candidate_quote, doc_id, chunk_id, run_id)
Mention(entity_id, chunk_id, doc_id, surface, start, end, run_id)
SameAsLink(entity_a, entity_b, score: float, origin, status, run_id)
```

- `EntityWrite` has no `attributes` and no `degree`. The shown
  attributes are computed on read (§3.1), and the degree is set by
  `refresh_degrees` (§5.3).
- `scope_path` lists entity ids from the outermost scope in; its last id
  is the direct scope, and an empty path means unscoped.
- `identity` maps each key or veto name to its normalized values, every
  value a list even when single. `scope` is never a key here; it is
  `scope_path`.
- An upsert of an existing entity replaces every field but `run_id`.
- `AliasRow.origin` is one of `surface`, `former_name`, `translation`,
  `glossary`, `reviewer`. An alias is keyed by `(entity_id, alias,
  origin)`.
- `SameAsLink` requires `entity_a < entity_b`. `origin` is one of the
  seven values of §1 and `status` one of `candidate`, `confirmed`,
  `rejected`. It is keyed by the pair, and a later write replaces score,
  origin and status.
- `Mention` is also what `entities_in_chunks` returns.

### 2.4 Relations, events, facts, roles and links

```
RelationRow(relation_id, type, subject_id, object_id, attributes, valid_from, valid_to,
            valid_precision, valid_source, observed_at, recorded_at, status, closed_at,
            version_key, doc_id, chunk_id, quote, quote_start, quote_end, quote_match,
            confidence, pack, pack_version, run_id)
FactRow(fact_id, type, …same as RelationRow without subject_id and object_id…)
EventRecord(event_id, type, attributes, identity: Mapping[str, tuple[str, ...]], valid_from,
            valid_to, valid_precision, pack, pack_version, run_id)
EventEvidence(event_id, doc_id, chunk_id, quote, quote_start, quote_end, quote_match,
              observed_at, run_id)
RoleRow(owner_id, owner_kind, role, target_id, target_kind, doc_id, chunk_id, run_id)
TextInLink(entity_id, doc_id, attribute, run_id)
```

- `attributes` holds only pack attributes. A pack attribute named
  `status` (on `Decision` or `ActionItem`) stays inside `attributes`
  and never touches the engine's `status` column (FR-003).
- `valid_precision` is `day`, `month`, `year` or `None`. `valid_source`
  is `text` or `document`. `quote_match` is `exact` or `fuzzy`.
- `recorded_at` is a UTC time; `observed_at`, `valid_from`, `valid_to`
  and `closed_at` are dates.
- Events have no status and no version key (engine brief §1). The same
  `EventRecord` comes back from `find_events`.
- `owner_kind` is `event` or `fact`; `target_kind` is `entity` or
  `event`.
- `TextInLink.doc_id` is the document that holds the entity's text. A
  link may come from the linked document's own unit or from another
  document whose entity names it (§2.9 of the brief), so links are
  keyed by `(entity_id, doc_id, attribute)` and merged.
- The same `TextInLink` comes back from `match_document_links` (with the
  candidate's `run_id` as `None`).

## 3. Read records and keys

### 3.1 `EntityRecord`

```
EntityRecord(entity_id, type, name, name_norm, label, scope_path, scope_source,
             attributes: Mapping[str, JsonValue], identity, aliases: tuple[AliasRow, ...],
             degree: int, run_id)
```

- `attributes` is computed on read: for each attribute, the value of the
  source with the newest `observed_at` (a missing date loses), ties
  broken by `doc_id`, `chunk_id`, then `quote_start`. It is never
  stored, so a delete never leaves a stale value (FR-009).
- `aliases` are sorted by `alias_norm`, then origin. `degree` is 0 until
  `refresh_degrees` sets it.

### 3.2 `ItemRecord`

```
ItemRecord(item_id, kind: "relation" | "fact" | "event", type, subject_id, object_id,
           roles: tuple[RoleRow, ...], attributes, valid_from, valid_to, valid_precision,
           valid_source, observed_at, recorded_at, status, closed_at, version_key,
           evidence: tuple[Evidence, ...], confidence, pack, pack_version, run_id)
Evidence(doc_id, chunk_id, quote, quote_start, quote_end, quote_match, observed_at)
```

- A relation has `subject_id` and `object_id` and no roles. A fact or an
  event has roles, sorted by role, then target id.
- A relation or a fact has exactly one evidence entry, from its row. An
  event has one per evidence row, sorted by `doc_id`, `chunk_id`,
  `quote_start`.
- Event-only gaps are `None`: `valid_source`, `observed_at`,
  `recorded_at`, `status`, `closed_at`, `version_key`, `confidence`.
- `get_items` and `get_version_groups` return it.

### 3.3 Keys and matches

```
ANY_SCOPE = AnyScope.ANY             # an enum member, never an entity id
IdentityKey(type, scope: str | None | AnyScope, names: tuple[str, ...], values: tuple[str, ...])
NameMatch(entity_id, type, scope_path, matched, origin: str | None, score: float)
DocumentLinkKey(attribute, value_norm, doc_id: str | None = None, entity_id: str | None = None,
                entity_types: tuple[str, ...] = ())
DocumentState(content_hash, pipeline_hash, run_id)
```

- `IdentityKey`: `names` and `values` have the same non-zero length, and
  `names` never holds `scope`. An entity matches when its type equals
  `type`, its direct scope equals `scope` (`None`: unscoped;
  `ANY_SCOPE`: any), and for every position `i`, `values[i]` is among
  `identity[names[i]]`. For `find_events`, `scope` must be `ANY_SCOPE`.
- `NameMatch.matched` is the normalized text that matched: the entity's
  `name_norm` (origin `None`) or an alias's `alias_norm` (its origin).
  `score` is 1.0 from `match_names` and the trigram similarity from
  `search_names` (research R7, R10).
- `DocumentLinkKey` has exactly one of `doc_id` and `entity_id`.
  - Document side (`doc_id`): entities whose type is in `entity_types`
    and that have an attribute source with this `attribute` and this
    `value_norm`. Each gives `TextInLink(entity_id, doc_id, attribute)`.
  - Entity side (`entity_id`): documents whose `code_norm` or
    `title_norm` equals `value_norm`. Each gives `TextInLink(entity_id,
    doc_id, attribute)`.
  - The engine then applies the issuer and version-label conditions.

## 4. Runs, caches and the lease

```
RunStatus(StrEnum): RUNNING, COMPLETED, COMPLETED_WITH_ERRORS, INTERRUPTED, FAILED
RunRecord(run_id, status: RunStatus, started_at: datetime | None, finished_at: datetime | None,
          stage_hashes: Mapping[str, str], prompt_versions: Mapping[str, str], pack, pack_version,
          pack_hash, stats: Mapping[str, JsonValue])
Verdict(pair_key, verdict, method: "llm" | "reviewer", model: str | None, run_id)
WriterLease(index_id, owner, fence: int, expires_at: datetime)
```

- `begin_run` stores the record with status `running` and `started_at`
  from the store's clock, ignoring the given status and times.
  `finish_run(run_id, status, stats)` sets status, stats and
  `finished_at` from the store's clock. An unknown run id raises
  `QueryError`; `RUNNING` as the final status raises `ValueError`.
- `get_runs(limit)` returns the newest `started_at` first, then run id.
- `pack`, `pack_version` and `pack_hash` are the fields of 002's
  `Stamp`, copied as plain values since `protocols` cannot import
  `packs`.
- `stats` is opaque to the store: drops, counts, model calls and tokens,
  as the engine writes them.
- Extraction cache: `cache_key → bytes`, with `created_at` from the
  store's clock. A put replaces.
- Resolution decisions: keyed by `pair_key`. A put replaces, except that
  a `method="llm"` verdict never replaces a stored `reviewer` verdict
  (FR-018); it is skipped, not an error.
- The lease (research R4, ADR 0024): `owner` is non-empty and at most
  200 characters; `ttl_s` is from 1 to 86,400. `expires_at` and `fence`
  come from the store. The lease rules are in
  [contracts/stores.md §2](contracts/stores.md#2-writer-lease).

## 5. Store schema, steps and hop

### 5.1 `StoreSchema`

```
StoreSchema(entity_types: tuple[str, ...], event_types: tuple[str, ...],
            fact_types: tuple[str, ...], relation_types: tuple[str, ...])
```

- Each tuple is sorted and has no repeats. `__post_init__` raises
  `ConfigError` when a name breaks its pattern (`[A-Z][A-Za-z0-9]*` for
  types, `[A-Z][A-Z0-9]*(_[A-Z0-9]+)*` for relations), when two kinds
  share a name, or when a name is reserved:

| Reserved | Names |
|---|---|
| labels (type names) | `Document`, `Chunk`, `Entity`, `Event`, `Fact`, `Alias`, `IdentityValue`, `AttributeSource`, `IdentityBlock`, `Run`, `ExtractionCache`, `ResolutionDecision`, `WriterLease`, `StoreMeta`, `Collection`, `Community`, `ChunkVector`, `EntityVector`, `ChunkQuestionVector` |
| edge types (relation names) | `IN_DOCUMENT`, `MENTIONED_IN`, `ROLE`, `SUPPORTED_BY`, `ALIAS_OF`, `TEXT_IN`, `SAME_AS`, `IN_COMMUNITY` |

- A type may equal its own kind's base label: an event type `Event`, an
  entity type `Entity`, a fact type `Fact`.
- `StoreSchema.merged(other)` returns the union, for the additive rule
  of `ensure_schema`.
- `tenetrag.packs.store_schema(stack)` builds it from a `PackStack`'s
  `entities`, `events`, `facts` and `relations`.

### 5.2 `WriteStep`

```
WriteStep(StrEnum): DELETE_PREVIOUS, INSERT, STATUS_CHANGES, DELETE_ORPHANS, DOCUMENT_ROW
StepHook = Callable[[WriteStep, str], None]      # (step, doc_id)
```

The store calls the hook after each step, inside the unit (research
R14). `delete_documents` calls it after `DELETE_PREVIOUS`,
`STATUS_CHANGES`, `DELETE_ORPHANS` and `DOCUMENT_ROW` (the document row's
removal).

### 5.3 Degree

`refresh_degrees(entity_ids)` sets, for each given entity, the number of
distinct other entities that share a relation row with it (either
direction) or are role targets of an item it is a role target of. Rows
and repeats do not count twice. Unknown ids are skipped.

### 5.4 Hop

```
HopSpec(relation_types: tuple[str, ...] | None = None, item_types: tuple[str, ...] | None = None,
        statuses: tuple[str, ...] | None = None, starts_before: date | None = None,
        overlaps: tuple[date | None, date | None] | None = None, include_same_as: bool = False,
        neighbour_limit: int = 20, item_limit: int = 50)
HopResult(edges: tuple[HopEdge, ...], items: tuple[HopItem, ...])
HopEdge(from_id, to_id, via_kind: "relation" | "role" | "same_as", via_type,
        item_ids: tuple[str, ...], support: int, to_degree: int)
HopItem(item_id, kind: "event" | "fact", type, entity_id, role, chunk_ids: tuple[str, ...])
```

- Limits are from 1 to 1,000. `None` means no filter; an empty tuple
  means nothing passes that filter.
- Neighbours of a start entity `e`:
  - `relation`: relation rows with `e` as subject or object. `via_type`
    is the relation type, `item_ids` the relation ids.
  - `role`: other role targets of an item whose roles name `e`.
    `via_type` is the item type, `item_ids` the shared items.
  - `same_as`: links of `e` whose status is not `rejected`, when
    `include_same_as` is set. `via_type` is the link status, `item_ids`
    is empty.
- Filters: `relation_types` on relation rows; `item_types` on items,
  for both `role` neighbours and items; `statuses` on relations and
  facts, never on events; `starts_before = D` drops rows with
  `valid_from > D`; `overlaps = (a, b)` keeps rows whose
  `[valid_from, valid_to]` meets `[a, b]`, an open end being unbounded on
  either side.
- An edge's `support` is the number of distinct rows behind it (1 for a
  `same_as` link). A neighbour's support is the sum over its edges, and
  its recency is the newest `observed_at` behind it.
- Order and caps, per start entity, inside the query (FR-023):
  neighbours by support descending, then recency descending (missing
  last), then neighbour id; cut to `neighbour_limit`. Items by support
  (evidence rows of an event, 1 for a fact) descending, then
  `observed_at` descending, then item id; cut to `item_limit`. An edge
  keeps at most `item_limit` item ids, in the same order.
- `to_degree` is the neighbour's stored degree. The engine applies the
  hub penalty.
- `HopItem.entity_id` is the start entity and `role` the role naming it;
  an item naming the entity in two roles appears twice. `chunk_ids` are
  its evidence chunks, sorted.
- Edges are returned sorted by `from_id`, then rank; items by
  `entity_id`, then rank.

## 6. Postgres layout

One schema per index, `tenetrag_<index_id>`, in a database whose
`LC_CTYPE` is UTF-8 (research R5). Id columns are `text COLLATE "C"`.
`LAYOUT_VERSION = 1`.

| Table | Key | Columns beyond §2 | Indexes |
|---|---|---|---|
| `meta` | `key` | `value jsonb`: `layout_version`, `schema` (the merged `StoreSchema`) | |
| `writer_lease` | `index_id` | `owner`, `expires_at timestamptz`, `fence bigint` | |
| `runs` | `run_id` | jsonb for hashes, versions and stats | `started_at` |
| `documents` | `doc_id` | | `code_norm`, `title_norm` |
| `chunks` | `chunk_id` | `heading_path text[]` | `doc_id` |
| `entities` | `entity_id` | `scope_path text[]`, `scope_id` generated (last of the path), `identity jsonb`, `degree int` | `(type, scope_id)`, `name_norm`, GIN `identity jsonb_path_ops`, GIN `name_norm gin_trgm_ops` |
| `aliases` | `(entity_id, alias, origin)` | | `alias_norm`, GIN `alias_norm gin_trgm_ops` |
| `attribute_sources` | none | `value jsonb` | `entity_id`, `doc_id`, `(attribute, value_norm)` |
| `identity_blocks` | none | | `entity_id`, `candidate_id`, `doc_id` |
| `mentions` | none | | `chunk_id`, `entity_id`, `doc_id` |
| `relations` | `relation_id` | `attributes jsonb` | `subject_id`, `object_id`, `doc_id`, `version_key` |
| `events` | `event_id` | `attributes jsonb`, `identity jsonb` | `type`, GIN `identity jsonb_path_ops` |
| `event_evidence` | none | | `event_id`, `doc_id` |
| `facts` | `fact_id` | `attributes jsonb` | `doc_id`, `version_key` |
| `roles` | none | | `owner_id`, `target_id`, `doc_id` |
| `text_in` | `(entity_id, doc_id, attribute)` | | `doc_id` |
| `same_as` | `(entity_a, entity_b)` | | `entity_b` |
| `resolution_decisions` | `pair_key` | | |
| `extraction_cache` | `cache_key` | `payload bytea`, `created_at` | |
| `collections` | `collection` | `model_id`, `dimensions` | |
| `vec_chunks`, `vec_entities`, `vec_chunk_questions` | `id` | `tsv` generated (research R6), `embedding vector(d)` | HNSW `vector_cosine_ops`, GIN `tsv`, `doc_id` |

- Vector tables are created by `ensure_collections`, once the dimensions
  are known; the rest by `ensure_schema`.
- No foreign keys: the write order and orphan step keep the rows whole,
  and a foreign key would force an order inside each step.
- The text of every statement is built from these names through
  `psycopg.sql.Identifier`; every value is a parameter (FR-034).

## 7. Neo4j layout

Every node carries `index_id`. Every query starts with `CYPHER 25`.
`LAYOUT_VERSION = 1`.

### 7.1 Nodes

| Label(s) | Unique on (with `index_id`) | Other indexes | Holds |
|---|---|---|---|
| `Document` | `doc_id` | `code_norm`, `title_norm` | §2.2 |
| `Chunk` | `chunk_id` | `doc_id` | §2.2 |
| `Entity` + type | `entity_id` | `name_norm`, `(type, scope_id)`; full text on `(trigrams, index_id, type)` | §2.3, `attributes` absent, `identity` as JSON text, `degree` |
| `Alias` | `(entity_id, alias, origin)` | `alias_norm`; full text on `(trigrams, index_id, type)` | §2.3 plus the entity's `type` |
| `IdentityValue` | `(owner_id, attribute, value)` | `(type, attribute, value)` | one per identity value of an entity or event; `owner_kind` |
| `AttributeSource` | none | `entity_id`, `doc_id` | §2.3, `value` as JSON text |
| `IdentityBlock` | none | `entity_id`, `doc_id` | §2.3 |
| `Event` + type | `event_id` | `type` | §2.4, JSON text for attributes and identity |
| `Fact` + type | `fact_id` | `doc_id`, `version_key` | §2.4, evidence as properties |
| `Run` | `run_id` | | §4 |
| `ExtractionCache` | `cache_key` | | payload as a byte array |
| `ResolutionDecision` | `pair_key` | | §4 |
| `WriterLease` | `index_id` alone | | §4 |
| `StoreMeta` | `index_id` alone | | `layout_version`, `schema` as JSON text |
| `Collection` | `collection` | | `model_id`, `dimensions` |
| `ChunkVector`, `EntityVector`, `ChunkQuestionVector` | `id` | vector index per dimensions; full text on `(text_norm, index_id)` | §7.5 |

- `scope_id` on `Entity` is the last id of `scope_path`, kept as a
  property for the index.
- `trigrams` is the space-separated trigram tokens of `name_norm` or
  `alias_norm` (research R10).

### 7.2 Edges

| Type | From → to | Properties | Written |
|---|---|---|---|
| `IN_DOCUMENT` | Chunk → Document | `index_id` | step 5, with the document node |
| `MENTIONED_IN` | Entity → Chunk | `index_id`, `doc_id`, `surface`, `start`, `end`, `run_id` | step 2 |
| relation type | Entity → Entity | every `RelationRow` column | step 2, one edge per row |
| `ROLE` | Event or Fact → Entity or Event | `index_id`, `name`, `doc_id`, `chunk_id`, `run_id` | step 2 |
| `SUPPORTED_BY` | Event or Fact → Chunk | the evidence columns | step 2 |
| `ALIAS_OF` | Alias → Entity | `index_id` | with the alias |
| `TEXT_IN` | Entity → Document | `index_id`, `attribute`, `run_id` | merged: step 2 for a link to another document, step 5 for a link to the unit's own document |
| `SAME_AS` | Entity → Entity (`a` to `b`) | `index_id`, `score`, `origin`, `status`, `run_id` | merged |

- Each relation type has a uniqueness constraint on `(index_id,
  relation_id)` and range indexes on `(index_id, doc_id)` and
  `(index_id, version_key)`, all created by `ensure_schema`.
- `TEXT_IN` needs both nodes. A link to another document names one that
  exists, since the engine found it with `match_document_links`. A link
  to the unit's own document waits for step 5, which creates the
  document node; on a first write that node does not exist before then.

### 7.3 Indexes by name

| Name | What |
|---|---|
| `tenetrag_<label>_<property>` | range and uniqueness indexes, for example `tenetrag_entity_name_norm` |
| `tenetrag_rel_<type>_<property>` | per relation type, for example `tenetrag_rel_owner_of_doc_id` |
| `tenetrag_entity_trigrams`, `tenetrag_alias_trigrams` | full text, `whitespace` analyzer |
| `tenetrag_<collection>_text` | full text on `text_norm` and `index_id`, `standard-no-stop-words`, `fulltext.eventually_consistent: false` |
| `tenetrag_<collection>_<dims>` | vector, cosine, quantization off, expansion factor 10, filter properties `index_id`, `type`, `language`, `doc_id` |

Indexes are shared by every index id in the database; each query
filters on `index_id`.

### 7.4 Deleting

- Step 1 deletes chunks by `doc_id` with `DETACH DELETE` (taking their
  `IN_DOCUMENT`, `MENTIONED_IN` and `SUPPORTED_BY` edges), relation
  edges by `doc_id` through the static type union (research R8), facts
  and `ROLE` edges by `doc_id`, attribute sources and identity blocks by
  `doc_id`, and `TEXT_IN` edges to the document.
- Step 4 deletes orphan entities and events with `DETACH DELETE`, plus
  their aliases, identity values, attribute sources and identity blocks.

### 7.5 Vectors on both backends

```
Collection = Literal["chunks", "entities", "chunk_questions"]
VectorRecord(id, vector: tuple[float, ...], doc_id: str | None, type: str | None,
             language: str | None, run_id, text_norm: str | None)
CollectionSpec(model_id, dimensions: int)
VectorSpec(chunks: CollectionSpec, entities: CollectionSpec, chunk_questions: CollectionSpec)
VectorFilter(types: tuple[str, ...] | None = None, languages: tuple[str, ...] | None = None,
             doc_ids: tuple[str, ...] | None = None, exclude_run: str | None = None)
Hit(id, score: float, doc_id: str | None)
VectorCapabilities(text_search: bool, fused_hybrid_only: bool, eventual_sync: bool,
                   max_dimensions: int)
```

- `doc_id` is set for `chunks` and `chunk_questions` and `None` for
  `entities`, which span documents. `text_norm` is set where full text
  applies (`chunks`, `chunk_questions`).
- `dimensions` is from 1 to `max_dimensions`.
- Paired writes (research R13): step 1 deletes the document's `chunks`
  and `chunk_questions` vectors; step 2 upserts every vector of
  `DocumentWrite.vectors`; step 4 deletes the vectors of orphan
  entities.
- Neo4j keeps each vector in the property `embedding_<dims>` of its
  vector node, so two index ids of different dimensions share a
  database (research R11).

## 8. Profile index section (delta to M0 data model §2)

```
IndexSettings(id: IndexId, graph: ConnectionName, vectors: ConnectionName | None = None)
    # all fields Operational; vectors defaults to graph
Profile(…, index: Annotated[IndexSettings | None, Operational()] = None)
IndexId = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,39}$")]
VECTOR_MAX_DIMENSIONS: Mapping[str, int] = {"postgres": 2000, "neo4j": 4096}
Profile(…, text_languages: Annotated[tuple[LanguageCode, ...], IndexTime(Stage.CHUNK)] = ())
LanguageCode = Annotated[str, Field(pattern=r"^[a-z]{2,3}$")]
    # sorted, without repeats; the languages whose rules norm() runs (ADR 0025, §11)
```

Checks at load (FR-039), each a `ConfigError` through M0's load errors:

| Rule | Fails when |
|---|---|
| `index.graph` exists | `graph` names no connection |
| `index.vectors` exists | `vectors` names no connection |
| kind serves role | a connection's kind is not `postgres` or `neo4j` (both serve both roles today) |
| dimensions fit | `models.embedding.dimensions`, or the capability override `embedding_dimensions`, exceeds `VECTOR_MAX_DIMENSIONS` of the vector connection's kind |

A test keeps `VECTOR_MAX_DIMENSIONS` equal to each vector store's
`capabilities.max_dimensions`.

## 9. Layout version and setup states

| Store holds | `ensure_schema` | Any other call |
|---|---|---|
| nothing for this index | creates everything, records version 1 and the schema | `StorageError`: "index `<id>` has no schema; call ensure_schema" |
| version 1 | adds what the new schema lacks, merges the recorded schema | works |
| another version | `ConfigError` naming both versions, before any DDL | the same `ConfigError` |

The check runs once per store instance and is cached.

## 10. Contract cases

`tests/contract/cases.py` holds one entry per case (FR-044):

```
ContractCase(id, source: "adr-0008" | "brief-10" | "spec", text, tests: tuple[str, ...])
```

`tests` are pytest node ids without the backend parameter, such as
`tests/contract/test_writes.py::test_replay_changes_no_count`.

| Id | Source | Case |
|---|---|---|
| `counts-after-write-and-replay` | adr-0008, brief-10 | counts after a batch write; a replay changes no count (SC-005) |
| `end-state-after-delete` | adr-0008 | deleting D1, D2 and D5 leaves zero rows of every kind (SC-005) |
| `supersession-flags` | adr-0008 | statuses and close dates match `graph.json` after writes and after D2's deletion |
| `provenance-reachability` | adr-0008 | every item reaches its chunks and documents through `get_items` |
| `type-time-status-filters` | adr-0008 | hop and search filters by type, time and status |
| `hop-membership` | adr-0008 | one hop and two composed hops reach the same sets on every store (SC-008) |
| `hop-caps` | brief-10 | at most `neighbour_limit` and `item_limit` per entity, in store order |
| `hub-invariants` | adr-0008 | the 5,000-relation hub: caps, support, distinct-neighbour degree (SC-007) |
| `tone-mark-matching` | adr-0008, brief-10 | tone-mark pairs match and diacritic pairs stay apart in name match, name search and full text (SC-009) |
| `killed-run-atomicity` | adr-0008, brief-10 | every kill point leaves each document whole or absent; replay equals a clean run (SC-006) |
| `orphan-cleanup` | brief-10 | orphans go after an edit and after a delete, with their hanging rows |
| `status-changes-in-unit` | brief-10 | status changes apply in the unit; an unknown item fails it |
| `exclude-run` | brief-10 | the current run's rows are hidden from name and vector lookups |
| `identity-scope` | brief-10 | `find_by_identity` with a scope id, `None` and `ANY_SCOPE` |
| `sources-deleted-with-document` | brief-10 | attribute sources and identity blocks go with their document; shown attributes recompute |
| `text-in-added-and-removed` | brief-10 | links from either side, removed with either side |
| `cache-round-trip` | brief-10 | extraction cache and decisions round-trip; a reviewer verdict wins |
| `writer-lease` | adr-0008, brief-10 | one writer; renew; release; expiry; a fenced writer fails |
| `as-of-prefilter` | brief-10 | `starts_before` and `overlaps` in `hop` |
| `split-crash-recovery` | brief-10 | a crash between the vector write and the graph write, then a replay |
| `one-of-two-sources` | spec (FR-010) | deleting one source keeps the other's row and edge |
| `pack-attributes-apart` | spec (FR-003) | a pack `status` attribute and the engine `status` both read back |
| `isolation` | spec (SC-011) | no read method sees another index's rows |
| `recall-floor` | spec (SC-010) | recall at 10 at least 0.9 on the recall fixture |
| `schema-and-layout` | spec (FR-035, FR-036) | `ensure_schema` idempotent and additive; a layout mismatch fails |
| `collections` | spec (FR-025) | a model or dimension change fails, naming both values |
| `runs-and-states` | spec (FR-016, FR-017) | run records and document states |

## 11. Tone-mark table (`norm()`, the `vi` rule)

The rule of `tenetrag.engine.text.vi`, run only when the languages
passed to `norm()` include `vi`
([ADR 0025](../../docs/decisions/0025-normalize-text-by-the-languages-the-profile-names.md)).
Applied after NFC and casefolding, only when the vowel pair ends the
syllable (no letter follows) and, for `uy`, the `u` does not follow `q`:

| Old placement | New placement |
|---|---|
| `oà oá oả oã oạ` | `òa óa ỏa õa ọa` |
| `oè oé oẻ oẽ oẹ` | `òe óe ỏe õe ọe` |
| `uỳ uý uỷ uỹ uỵ` | `ùy úy ủy ũy ụy` |

Upper and mixed case map the same way before casefolding. Examples are
in research R18.
