# Research: Store protocols, the reference store, the contract suite and the Postgres and Neo4j stores (M1, part 2)

Checked on 2026-10-21. This feature adds no package. Most of the work
was reading this repository and running the pinned servers. Labels:
- **[source]**: read in this repository's code or docs, or in a locked
  library's installed code;
- **[run]**: a script or query run on 2026-10-21, from a scratch
  directory outside the repository. Server checks ran against the images
  pinned in `deploy/compose.yaml` and `tests/integration/conftest.py`,
  in throwaway containers; the images, the method and every check are
  listed in [Platform checks run](#platform-checks-run);
- **[inferred]**: our reasoning.

Neo4j documentation is CC BY-NC-SA, so this file paraphrases it and
links to it, and never copies its text.

## Versions and the dependency gate

No new dependency. Everything below is already locked by M0 (versions in
[001 research](../001-sdk-foundation/research.md#versions-and-the-dependency-gate)),
so the gate has nothing new to check.

| Need | Met by | Already locked as |
|---|---|---|
| Postgres driver, pool, `COPY`, SQL identifiers | psycopg, psycopg-pool (`psycopg.sql.Identifier`) | `postgres` extra: psycopg 3.3.6 (+ binary), psycopg-pool 3.3.3 |
| Neo4j driver, managed transactions | neo4j | `neo4j` extra, 6.3.1 |
| Docker servers for the contract suite | testcontainers, docker | dev: testcontainers 4.15.0, docker 7.2.0 |
| Test runner, network block, markers | pytest with M0's `--disable-socket` | dev: pytest 9.1.1 |
| Records, protocols, `norm()`, trigrams, JSON, hashing | `dataclasses`, `typing`, `enum`, `unicodedata`, `re`, `json`, `hashlib` | standard library |
| Fake vectors | `tenetrag.llm.FakeEmbeddingModel` (8 dimensions by default) | M0 |

Three candidates were rejected because what is locked is enough:
- **`pgvector` (Python).** Its psycopg adapter sends vectors in binary.
  A text literal cast to `vector` or `vector[]` worked in every probe
  [run], and the reads parse the text form. One more package for one
  adapter is not worth the gate.
- **An in-memory graph library** (networkx and the like) for the
  reference store. Dictionaries and sorted lists are enough, and the
  reference store must stay readable as the definition of the contract.
- **APOC or GDS.** Excluded by ADR 0008, and nothing below needs them.

## R1. Layers and new modules

- **Decision:**
  - The layers contract becomes `"engine | llm | storage"`, `"auth"`,
    `"config | packs"`, `"protocols | _retry | _yaml"`. `engine` sits
    beside `llm` and `storage`, so none of the three may import another.
  - A new forbidden contract keeps `tenetrag.engine` off
    `tenetrag.auth`, openai, databricks, neo4j, psycopg, psycopg_pool and
    pyspark. The layers contract already keeps it off `llm` and
    `storage`.
  - `tenetrag.engine` holds only `engine/text.py` with `norm()` in this
    feature (R18). The rest of the engine arrives in 004.
  - `tenetrag.protocols` gains `records.py` (the row and read records)
    and `stores.py` (`GraphStore`, `VectorStore`, `StoreSchema`, the hop
    and lease records, `WriteStep`). Both import only the standard
    library. `WriterBusyError(StorageError)` joins `errors.py`.
  - `tenetrag.packs` gains `store.py`: `store_schema(stack) ->
    StoreSchema` (R3). `packs` already imports `protocols`.
  - `tenetrag.storage` gains a package per backend
    (`postgres_store/`, `neo4j_store/`), a shared trigram module
    (`_trigram.py`), a shared name check (`_names.py`) and the builder
    (`stores.py`, R17). Storage imports `protocols`, `config`, `auth` and
    `_retry` (FR-048), as M0's connections do.
- **Rationale:**
  - `engine` may import only protocols, `config` and `packs`
    ([ARCHITECTURE.md](../../ARCHITECTURE.md)). Placing it now, with one
    module, makes the rule real before 004 adds code.
  - Records and protocols in two files keeps the protocol file short
    enough to read as the contract.
- **Alternatives:**
  - Putting `norm()` in `protocols` so stores could call it: rejected.
    Normalization is engine-owned (ADR 0008 §4), and no store calls it
    (FR-047).
  - One file per store class: the Postgres store alone needs DDL, writes,
    reads, the lease and vectors, so a package per backend keeps each
    file to one job.

## R2. Records and protocol shapes

- **Decision:**
  - Records are frozen dataclasses with `slots=True`, as in M0's
    `protocols/models.py`, plus `kw_only=True`, since most have more than
    five fields and a call site should name each one. Sequences are
    tuples and mappings are read-only, so records compare by value in
    tests.
  - Dates are `datetime.date`. `recorded_at`, the run times and the
    cache's `created_at` are UTC `datetime`s. The store stamps
    `started_at` in `begin_run`, `finished_at` in `finish_run` and
    `created_at` in `put_cached_extractions` from its own clock: the
    server's on Postgres and Neo4j, an injected clock in the reference
    store. `begin_run` ignores the record's times and status.
  - Pack attributes are a mapping from attribute name to a JSON value
    (string, number, boolean, null or a list of these). Dates inside
    attributes are ISO strings; the engine parses them (002 notes). They
    are stored as one JSON value per row, apart from every engine column,
    so a Decision's `status` attribute never meets the engine's `status`
    column (FR-003).
  - Write records carry exactly what the engine computes. `EntityWrite`
    has no `attributes` and no `degree`: the store derives the shown
    attributes from attribute sources on read (FR-009) and the degree in
    `refresh_degrees` (FR-012). `EventRecord` has no status, since events
    have none (engine brief §1).
  - `EntityRecord.attributes` is computed on read: per attribute, the
    value of the source with the newest `observed_at`, ties broken by
    `doc_id`, `chunk_id`, then `quote_start`. Nothing is stored, so a
    delete can never leave a stale value.
  - Entities, aliases and events keep the `run_id` of the run that first
    wrote them. An upsert never changes it. `exclude_run` (FR-020) then
    hides what the current run created, and an entity that existed
    before stays visible when the run adds an alias to it. Every other
    row is rewritten with its document and carries the writing run.
  - `IdentityKey(type, scope, names, values)`: `scope` is an entity id,
    `None` for an unscoped entity, or the sentinel `ANY_SCOPE` (an enum
    member, so it type-checks and cannot collide with an id). `names`
    never contains `scope`; the scope is its own field.
  - `NameMatch.origin` is `None` when the canonical `name_norm` matched,
    else the alias's origin. Its score is 1.0 for `match_names` and the
    trigram similarity for `search_names` (R7, R10).
  - `DocumentLinkKey` has exactly one of `entity_id` and `doc_id`
    (checked in `__post_init__`), plus `attribute`, `value_norm` and
    `entity_types`. A document-side key finds entities of those types
    whose attribute sources hold that normalized value for that
    attribute. An entity-side key finds documents whose `code_norm` or
    `title_norm` equals the value. The store returns candidate
    `TextInLink` rows; the engine applies the issuer and version-label
    conditions of [§2.9](../../docs/product/engine-brief.md#29-text_in).
  - Documents gain `code_norm` and `title_norm` matching columns for
    that lookup.
  - `RunStatus` is a `StrEnum`: `running`, `completed`,
    `completed_with_errors`, `interrupted`, `failed`. `Verdict` carries
    `pair_key`, `verdict`, `method` (`llm` or `reviewer`), `model` and
    `run_id`.
  - `write_documents` writes the batch in order, one unit per document.
    A failing document raises; the documents before it stay written, and
    the ones after it are not tried.
  - A status change naming an item the store does not hold raises
    `QueryError` naming the item id, and its document's unit rolls back
    (FR-011). Ids are hashes, so naming them leaks no content (FR-005).
  - Every read takes ids or keys. Unknown ids are left out, and each id
    appears once (FR-024). An empty input returns an empty result with no
    query.
- **Rationale:**
  - Frozen, slotted records match M0's `protocols.models` style and keep
    the module standard library only (FR-001).
  - Store clocks for run times keep `finished_at` after `started_at`
    when the client and server clocks disagree.
  - Computing shown attributes on read meets FR-009 with no write-path
    bookkeeping.
- **Alternatives:**
  - pydantic models for records: rejected, since `protocols` imports only
    the standard library.
  - Storing `entities.attributes` and refreshing it on each write:
    another place to forget after a delete, for a read that is already
    batched.
  - A `run_id` that follows the last writer on entities: the run's own
    alias additions would then hide whole pre-existing entities from the
    hints.

## R3. The store schema and reserved names

- **Decision:**
  - `StoreSchema(entity_types, event_types, fact_types, relation_types)`
    holds sorted tuples of type names only. The index id and the layout
    version belong to the store, which is opened for one index and knows
    its own layout (R16).
  - `__post_init__` refuses, with `ConfigError`:
    - a type name that breaks `[A-Z][A-Za-z0-9]*`, or a relation name
      that breaks `[A-Z][A-Z0-9]*(_[A-Z0-9]+)*`. The patterns are
      written again in `protocols/stores.py`, since `protocols` cannot
      import `packs`; a test keeps them equal to `packs/format.py`, as
      M0 does for `PACK_NAME`;
    - a name used by two kinds;
    - a reserved label as a type name. The reserved labels are the
      infrastructure labels of R8: `Document`, `Chunk`, `Entity`,
      `Event`, `Fact`, `Alias`, `IdentityValue`, `AttributeSource`,
      `IdentityBlock`, `Run`, `ExtractionCache`, `ResolutionDecision`,
      `WriterLease`, `StoreMeta`, `Collection`, `Community`,
      `ChunkVector`, `EntityVector`, `ChunkQuestionVector`. A type may
      equal its own kind's base label: `core` has an event type `Event`;
    - a reserved edge type as a relation name: `IN_DOCUMENT`,
      `MENTIONED_IN`, `ROLE`, `SUPPORTED_BY`, `ALIAS_OF`, `TEXT_IN`,
      `SAME_AS`, `IN_COMMUNITY`.
  - Every store checks each name again before it builds it into a query
    (FR-034), through `storage/_names.py`, and refuses a type that is not
    in the schema it was given.
  - **The Chunk→Document edge is renamed from `PART_OF` to
    `IN_DOCUMENT`.** `core` defines the relation `PART_OF` (an
    organization part of another), so the infrastructure edge would
    collide with a pack relation on Neo4j. Renaming the edge costs
    nothing, since no store exists yet; refusing `PART_OF` would break
    `core`.
  - `tenetrag.packs.store_schema(stack)` builds the schema from a loaded
    `PackStack`. The engine (004) will call it before `ensure_schema`.
  - A test loads `core`, `enterprise-docs` and the `finance` draft and
    builds each schema [run: all three load, and only `Event` and
    `PART_OF` meet a reserved name].
- **Rationale:** names become Neo4j labels and edge types, where a
  parameter cannot stand in for a name in DDL. Two checks (the pack's
  patterns and the store's) make an injection need two bugs.
- **Alternatives:**
  - Index id and layout version inside `StoreSchema`, as the spec's Key
    Entities said: rejected. One store instance serves one index, and a
    schema record carrying another index id would be a second source of
    truth (spec edit, R22).
  - A namespace prefix on every pack label (`T_Policy`): rejected. Neo4j
    Browser and Cypher users should see the pack's names (ADR 0008 §6).

## R4. The writer lease

- **Decision:** a lease record, the same design on both backends,
  recorded in [ADR 0024](../../docs/decisions/0024-hold-the-writer-lease-in-a-fenced-lease-record.md):
  - one lease row (Postgres table `writer_lease`) or node
    (`WriterLease`, unique on `index_id`) per index, with `owner`,
    `expires_at` from the server clock, and a `fence` counter;
  - `acquire_writer(owner, ttl_s)` is one conditional upsert: it takes
    the lease when it is free, expired or already held by the same owner.
    A new holder increments `fence`. Otherwise it raises
    `WriterBusyError` naming the holder and `expires_at`;
  - `renew_writer(lease, ttl_s)` extends the lease while owner and fence
    still match, else raises `WriterBusyError`. `release_writer(lease)`
    ends it, and does nothing when the lease is already gone or taken;
  - the store remembers the lease it holds. Every write unit
    (`write_documents`, `delete_documents`, `refresh_degrees`,
    `begin_run`, `finish_run`, both cache puts) first reads the lease
    row under a lock (Postgres `SELECT … FOR SHARE`; Neo4j a write lock
    taken by `SET`) and checks owner, fence and expiry, else raises
    `WriterBusyError`. A write with no lease raises `StorageError`
    saying to call `acquire_writer`. `ensure_schema` needs no lease;
  - the owner string must be unique per process. The engine (004) will
    use host, process id and a random suffix.
- **Evidence** [run]:
  - Session advisory locks survive commit and stay with the connection
    until it disconnects; with `idle_session_timeout` and `lock_timeout`
    at 0 by default, a hung client holds the index for good. A pooled
    connection returned to the pool keeps the lock. Transaction-level
    advisory locks end with each document's transaction, so they cannot
    span a run.
  - Postgres lease row: 12 concurrent acquirers, exactly one won
    (fence 1). An expired lease was taken over with fence 2. A takeover
    issued while a unit held `FOR SHARE` on the row waited until that
    unit committed (39.743 s → 40.731 s), then won with fence 3.
  - Neo4j lease node: `MERGE` on the unique `index_id`, `SET l._lock =
    true` to take the node's write lock, then conditional `SET`s. 12
    concurrent acquirers, exactly one won.
- **Rationale:** FR-015 needs a lease that ends by itself, can be renewed
  and released, and names its holder. An advisory lock ends only with
  its connection, works badly with a pool, and carries no owner or time.
  The fence plus the in-unit check stop a writer that paused past its
  lease from writing after a takeover.
- **Alternatives:** advisory locks as ADR 0008 §7 says (rejected, above);
  a lease checked only at acquire time (a paused writer could still
  commit after a takeover).

## R5. Postgres layout

- **Decision:**
  - One schema per index, `tenetrag_<index_id>`. The index id matches
    `^[a-z][a-z0-9_]{0,39}$`, so the schema name stays under Postgres's
    63-byte identifier limit and needs no quoting. Every identifier goes
    through `psycopg.sql.Identifier`, and every value is a parameter.
  - Tables follow the logical tables of
    [§1](../../docs/product/engine-brief.md#logical-tables), with the
    columns of data-model §6. Id columns are `text COLLATE "C"`, so
    `ORDER BY id` is code-point order, as in Python and Neo4j.
  - `entities.identity` is `jsonb` with every value a list, indexed by
    GIN `jsonb_path_ops`; `find_by_identity` uses containment.
    `entities.scope_id` is a generated column (the last id of
    `scope_path`), indexed with `type`.
  - A `meta` table holds the layout version (R16). A `collections` table
    holds each collection's model id and dimensions (R11).
  - `ensure_schema` runs in one transaction under
    `pg_advisory_xact_lock` on a hash of the schema name, so two
    processes setting up one index cannot race on `CREATE … IF NOT
    EXISTS`. The lock ends with that transaction (unlike R4's case).
  - **Extensions** (FR-031): `ensure_schema` runs `CREATE EXTENSION IF
    NOT EXISTS` for `vector` and `pg_trgm`. When the role cannot, it
    raises `UnsupportedServerError` naming the missing extensions and
    saying an administrator must create them in that database.
  - **Locale check:** `health()` already checks the server version (16 or
    later) and the extensions. The store adds `SELECT 'ã' ~
    '^[[:alnum:]]$'`; false raises `UnsupportedServerError` naming the
    database's `datctype` and asking for a UTF-8 locale such as
    `C.UTF-8`.
- **Evidence** [run]:
  - In a database with the `C` locale, pg_trgm and `[[:alnum:]]` treat
    Vietnamese letters as separators: `show_trgm('lãi')` gives only ASCII
    trigrams, and the split rule of R6 turns `ngày phòng` into
    `ng y ph ng`. `C.UTF-8` (libc) works on pg16 and pg17, the builtin
    `C.UTF-8` provider on pg17, and `en_US.utf8` on both.
  - `vector` is not a trusted extension (creating it needs a
    superuser); `pg_trgm` is trusted. Versions: pg_trgm 1.6, vector
    0.8.7.
- **Rationale:** one schema per index is engine brief §1's layout. The
  locale check turns silent wrong matches into a named error.
- **Alternatives:** an `index_id` column on every table, as on Neo4j:
  every query and index would carry it, for no gain on a server that has
  schemas.

## R6. Postgres full text

- **Decision:**
  - Each vector table has a generated column
    `tsv tsvector GENERATED ALWAYS AS (to_tsvector('simple', <split>(text_norm))) STORED`
    with a GIN index, where `<split>` is
    `regexp_replace(x, '[^[:alnum:].,]+|(?<![[:digit:]])[.,]|[.,](?![[:digit:]])', ' ', 'g')`:
    every run of characters other than letters, digits, `.` and `,`
    becomes a space, and so does a `.` or `,` not between two digits.
  - The query side applies the same split to the query's `text_norm`,
    takes the lexemes of `to_tsvector('simple', …)`, quotes each with
    `quote_literal`, and joins them with ` | ` into one `to_tsquery`. An
    empty result gives no rows. All of it is one statement; the query
    text is a parameter.
  - Ranking is `ts_rank(tsv, query)` descending, then id, limited to k.
    The score is the rank; the contract never compares it (FR-045).
- **Evidence** [run] on pg16 and pg17:
  - Documents: `t1 lãi suất cho vay`, `t2 quay lại sau`,
    `t3 lai lịch nhân viên`, `t4 phụ cấp 2.500.000 vnd/ngày cho phòng-ban
    và đơn vị.`, `t5` text with `(đơn vị)`, `t6` a circular code with
    `2016` and `nhnn`.
  - Hits: `lãi`→t1, `lại`→t2, `lai`→t3, `và`, `ngày`, `vnd/ngày`,
    `phòng-ban`, `2.500.000`→t4, `500`→none, `2016` and `nhnn`→t6.
  - OR queries: `lãi suất vay` → `'lãi' | 'suất' | 'vay'` (t1);
    `(đơn vị)` → `'vị' | 'đơn'`; `a & b | c:* !d` → a harmless OR of four
    words (no operator survives); `'`, `...` → null, no rows;
    `o'neil` → `'neil' | 'o'`.
  - The raw `simple` parser, without the split, gave `vnd/ng` and `ày`
    for `vnd/ngày`; `plainto_tsquery` joins terms with AND.
- **Rationale:** FR-027 asks for syllables with no stemming, stop words
  or folding. The split keeps numbers such as `2.500.000` whole, as the
  Neo4j analyzer does (R9), and OR matches the Neo4j default operator,
  so both backends find the same chunks for a multi-word query.
- **Alternatives:** `plainto_tsquery` (AND: a chunk must hold every
  query syllable, unlike Neo4j); `websearch_to_tsquery` (parses user
  operators); a custom text search parser (needs C code on the server).

## R7. Postgres name matching

- **Decision:**
  - `match_names`: B-tree indexes on `entities(name_norm)` and
    `aliases(alias_norm)`. One statement unions both, filtered by type
    and by `run_id <> exclude_run` on the matched row, and returns the
    entity's scope path and the alias origin (`None` for a name match).
  - `search_names`: `SELECT set_config('pg_trgm.similarity_threshold',
    %s, true)` in the read transaction, then `%` against GIN
    `gin_trgm_ops` indexes on `entities(name_norm)` and
    `aliases(alias_norm)`, the two unioned in one statement, keeping
    each entity's best match, ordered by `similarity` descending, then
    entity id, limited.
- **Evidence** [run]: `set_config(…, true)` is local to the transaction
  (back to 0.3 after commit). `%` used a bitmap index scan on 20,000
  aliases. `ngân hàng phương đông` found itself (1.00) and a one-word
  variant (0.70); `lãi` found only itself (`lại` and `lai` score 0.14);
  `nguyễn văn hòa` found itself (1.00) and `hoà` (0.67, before `norm()`).
- **Rationale:** pg_trgm is engine brief §6.5's choice, and the
  transaction-local threshold keeps pooled connections clean.

## R8. Neo4j layout and DDL

- **Decision:**
  - Every node carries `index_id`. Each label has a composite uniqueness
    constraint on `index_id` plus its key, created by `ensure_schema`
    with `IF NOT EXISTS`. Community has no existence constraints, so the
    store always sets `index_id` itself and no query matches without it.
  - Labels: `Document`, `Chunk`, `Entity` plus the pack type,
    `Event` plus its type, `Fact` plus its type, `Alias`, `IdentityValue`,
    `AttributeSource`, `IdentityBlock`, `Run`, `ExtractionCache`,
    `ResolutionDecision`, `WriterLease`, `StoreMeta`, `Collection`, and
    the vector labels of R11. Type filters use a `type` property, never
    the second label, since `core`'s event type `Event` is the base label
    itself.
  - Edges: `IN_DOCUMENT` (chunk→document), `MENTIONED_IN` (entity→chunk,
    with surface, start, end and doc id), typed relation edges
    (entity→entity) with every relation column, `ROLE` (event or fact →
    entity or event, with name, doc id and chunk id), `SUPPORTED_BY`
    (event or fact → chunk, with the evidence columns), `ALIAS_OF`
    (alias→entity), `TEXT_IN` (entity→document, with the attribute),
    `SAME_AS` (with score, origin and status). A fact also keeps its
    evidence as node properties.
  - Pack attributes are one property, `attributes`, holding a JSON
    string, and `identity` likewise. No property name comes from a pack.
  - `IdentityValue` nodes (owner id, owner kind, type, attribute, value)
    give `find_by_identity` and `find_events` an indexed lookup through a
    composite range index on `(index_id, type, attribute, value)`, since
    Neo4j cannot index list elements or JSON. They are rewritten with
    their entity or event.
  - Relation edges get a uniqueness constraint per type on
    `(index_id, relation_id)`, created by `ensure_schema` for each
    relation type in the schema. A new type adds its constraint; nothing
    is dropped (FR-035).
  - Rows scoped to a document (chunks, mentions, relations, facts, roles,
    evidence, attribute sources, identity blocks) are deleted by `doc_id`
    in step 1 and then created, so they need no `MERGE`. Entities,
    events, aliases, identity values, `text_in` and `same_as` links,
    documents, runs, cache entries, decisions, the lease and meta are
    merged on their keys (FR-033), since another document's unit may
    already have written them.
  - Labels and edge types from the pack use the dynamic forms
    `SET n:$(row.type)` and `MERGE (a)-[r:$(row.type) {…}]->(b)` when
    writing, after the name check of R3.
  - Finding relation edges by a property (`relation_id` in `get_items`,
    `doc_id` in step 1, `version_key` in `get_version_groups`) uses a
    static union of the schema's relation types, `[r:OWNER_OF|USES|…]`,
    built from names that passed the check. Each type has a range index
    on `(index_id, doc_id)` and one on `(index_id, version_key)`, besides
    its uniqueness constraint. Expanding from a known entity in `hop`
    keeps `$any($types)`.
  - Every query starts with `CYPHER 25`.
- **Evidence** [run]:
  - Composite uniqueness on `(index_id, entity_id)` for `Entity` and
    `(index_id, community_id)` for `Community`: two indexes can share an
    entity id; a duplicate in one index fails. Four properties
    `(index_id, entity_id, alias, origin)` work.
  - Relationship uniqueness is per type
    (`FOR ()-[r:T]-() REQUIRE (r.index_id, r.relation_id) IS UNIQUE`).
  - A node without `index_id` is accepted. An existence constraint fails
    on Community.
  - `SET n:$(row.type)`, `MERGE` with `$(row.t)`, `$all([...])`,
    `$any($types)` and `REMOVE n:$(...)` all work. A parameter value
    becomes a literal label, so no injection, but names are checked
    anyway (R3).
  - `MERGE` of 5,000 edges of two types with a dynamic type: 1,493 ms
    the first time, 527 ms on replay. One static statement per type:
    873 ms. Dynamic types are fast enough, so the per-type fallback of
    ADR 0008 §6 is not needed.
  - Lookups on 30,000 relation edges of three types, by
    `relation_id IN $ids`: a static union `[r:A|B|C]` ran three unique
    index seeks (15 db hits); `[r:$any($types)]` and an `UNWIND` over
    single dynamic types scanned every edge of the types (60,009 db
    hits, 180,009 after 60,000 more edges); an untyped pattern scanned
    all edges (90,000). By `doc_id` equality the static union seeked the
    per-type indexes (78 db hits).
  - An `IdentityValue` lookup by `(index_id, type, attribute, value)` ran
    a node index seek on the composite range index (6 db hits on 20,000
    nodes).
  - A duplicate key raises `Neo.ClientError.Schema.ConstraintValidationFailed`
    with the property values in its message (`Hoà`), which is why R21
    wraps every message.
- **Rationale:** typed edges and pack labels are ADR 0008 §6. JSON for
  attributes keeps pack attribute names out of Cypher identifiers
  entirely, and keeps engine fields and pack attributes apart (FR-003).
- **Alternatives:** one property per attribute (pack names become
  property names); a `REL` edge type (rejected in ADR 0008); `MERGE` for
  rows scoped to a document (slower, and step 1 has already deleted
  them).

## R9. Neo4j full text

- **Decision:** a full-text index per vector label that has text, on
  `(text_norm, index_id)`, analyzer `standard-no-stop-words`,
  `fulltext.eventually_consistent: false`. The query string is built in
  Python: `+index_id:"<id>" +text_norm:(<terms>)`, where each term of
  the normalized query is escaped for Lucene. It is passed as a
  parameter to `SEARCH c IN (FULLTEXT INDEX … FOR $q LIMIT $k) SCORE AS
  s`, with no filter inside `SEARCH`.
- **Evidence** [run]:
  - Analyzers available: `standard`, `standard-folding`,
    `standard-no-stop-words`, `classic`, `simple`, `whitespace`,
    `unicode_whitespace`, `keyword`.
  - On the R6 documents: `lãi`→t1 only, `lại`→t2, `lai`→t3; `và`, `vnd`,
    `ngày`, `phòng`, `ban`, `phòng-ban`, `2.500.000`→t4; `2`→none;
    `nhnn`→t6. Lucene's fuzzy `lai~` returned t2, t3, t1 and t4, which is
    why name search does not use it (R10).
  - A `WHERE` inside a full-text `SEARCH` fails (42N14); a `WHERE` after
    it filters the results. An unescaped `(` fails (50N00); escaped, it
    works. The default operator is OR.
  - With the index on `[text_norm, index_id]`, the query
    `+index_id:"idx_alpha" +text_norm:(lãi suất)` returned only that
    index's chunks. An unqualified term also matches the `index_id`
    field, so the text field is always named.
  - Read your write: 0 misses in 50, writing then searching in the next
    transaction.
- **Rationale:** the index id inside the Lucene query filters before the
  limit, so another index's chunks never take the top k (SC-011). The
  analyzer keeps diacritics, as engine brief §7 requires.
- **Alternatives:** a filter after `SEARCH` with an over-fetch (another
  index's chunks can fill the limit); `standard-folding` (merges `lãi`,
  `lại` and `lai`).

## R10. Neo4j name search

- **Decision:**
  - `match_names`: range indexes on `(index_id, name_norm)` for `Entity`
    and `(index_id, alias_norm)` for `Alias`; exact equality, filtered by
    the `type` property and `run_id`.
  - `search_names`: each `Entity` node (for its `name_norm`) and each
    `Alias` node (for its `alias_norm`) carries `trigrams`, the trigrams
    of that text as space-separated tokens, with spaces inside a trigram
    written `_` (`lãi` → `__l _lã lãi ãi_`). Two full-text indexes with
    the `whitespace` analyzer, one per label, cover `(trigrams, index_id,
    type)`. One statement queries both with the query's trigrams OR-ed,
    `+index_id:"…"` and the types, fetching `4 × limit` candidates (at
    least 50) from each. Python then computes the exact similarity with
    `storage/_trigram.py`, keeps those at or above `min_similarity`, the
    best per entity, sorted by similarity then entity id, and cuts to
    `limit`. A canonical-name hit has origin `None`.
  - `_trigram.py` matches pg_trgm: words are runs of letters and digits
    (`[^\W_]+`), each padded as two spaces before and one after, and the
    similarity is the Jaccard index of the trigram sets. The reference
    store uses it too.
- **Evidence** [run]:
  - The Python function equals pg_trgm on 8 pairs (0.6957, 0.6667,
    0.1429, 0.1429, 1.0, 0.6471, 0.4444, 1.0).
  - Over 22,000 aliases: `ngân hàng phương đông` → the two right
    entities first (90 ms); `lãi` → `lãi`, `lai`, `lại` (9 ms), which the
    exact filter then cuts to `lãi`; `nguyễn văn hoà` → `hòa` first
    (15 ms); `công ty số 12` first (27 ms).
- **Rationale:** the same measure on both backends makes the candidate
  sets equal, not just similar (FR-021, SC-009). Lucene's fuzzy query is
  edit distance and matched `lai~` across diacritics.
- **Alternatives:** Lucene fuzzy, as engine brief §6.5 says (different
  measure, diacritic-blind at distance 1; brief edit, R22); a scan with
  the similarity in Cypher (no index).

## R11. Vectors

- **Decision:**
  - **Layout.** Vectors live in their own tables or nodes on every
    pairing, so the graph and vector protocols stay apart even when one
    database holds both:
    - Postgres: `vec_chunks`, `vec_entities`, `vec_chunk_questions` with
      `id`, `doc_id`, `type`, `language`, `run_id`, `text_norm`, the
      generated `tsv` (R6) and `embedding vector(d)`, an HNSW index
      (`vector_cosine_ops`) and a B-tree on `doc_id`.
    - Neo4j: nodes `ChunkVector`, `EntityVector`, `ChunkQuestionVector`,
      unique on `(index_id, id)`, with the vector in a property named for
      its dimensions (`embedding_768`). One vector index per collection
      and dimensions (`tenetrag_chunks_768`), with filter properties
      `index_id`, `type`, `language` and `doc_id`.
      `vector.quantization.enabled: false` and
      `vector.default_search_expansion_factor: 10.0`. Vectors are
      `LIST<FLOAT>`.
  - **`ensure_collections`** records each collection's model id and
    dimensions in `collections` (Postgres table, Neo4j `Collection`
    node), creates the table or index, and raises `ConfigError` naming
    the collection, both model ids and both dimensions when a later call
    differs, saying to rebuild under a new index id (FR-025). Dimensions
    above `capabilities.max_dimensions` raise the same error.
  - **Scores.** `Hit.score` is the cosine similarity in [-1, 1] on every
    backend: `1 - (a <=> b)` on Postgres, `2s - 1` from Neo4j's score `s`
    (which is (1 + cos) / 2). The engine's thresholds (0.75, 0.85) are
    raw cosine. A test checks scores of about 1, 0 and -1 within 1e-3.
  - **Search.** One call takes many query vectors:
    - Postgres: `SET LOCAL hnsw.ef_search = 100` and
      `hnsw.iterative_scan = relaxed_order`, then
      `unnest(%s::vector[]) WITH ORDINALITY q(v, ord) CROSS JOIN LATERAL
      (… WHERE <filters> ORDER BY embedding <=> q.v LIMIT k)`, re-sorted
      by score per query in Python.
    - Neo4j: `UNWIND range(0, size($qs) - 1) AS i CALL (i) { MATCH (n:L)
      SEARCH n IN (VECTOR INDEX … FOR $qs[i] WHERE n.index_id = $ix AND
      n.type IN $types … LIMIT $k) SCORE AS s RETURN … }`.
    - Filters: type, language and document lists, and `exclude_run`.
      An empty list means nothing can match and returns empty lists with
      no query; `None` means no filter. On Neo4j `exclude_run` cannot go
      inside `SEARCH` (no `<>`), so it filters after, with the limit
      doubled up to three times until k hits remain.
  - **Writes** check every vector's length against the collection's
    dimensions and raise `QueryError` before any statement, since Neo4j
    silently leaves a wrong-length list out of the index.
  - **`get_vectors`** returns the stored values. Postgres stores
    float32, so values match the input within 1e-6; the contract
    compares with that tolerance.
  - **Capabilities:** `text_search=True`, `fused_hybrid_only=False`,
    `eventual_sync=False` on all three stores; `max_dimensions` 2000 on
    Postgres (`vector` with HNSW), 4096 on Neo4j and the reference
    store.
- **Evidence** [run]:
  - pgvector: HNSW allows 2,000 dimensions on `vector` and 4,000 on
    `halfvec` (the type allows 16,000). A wrong length fails ("expected
    4 dimensions, not 2"). `1 - (a <=> b)` gives 0.000 for orthogonal and
    -1.000 for opposite vectors.
  - pgvector batching: the LATERAL query used `Index Scan using
    v_embedding_idx` on 40,000 rows (the planner chose a sequential scan
    on 4,000), ran 20 queries in 33 ms, and each query's list came back
    sorted even under `relaxed_order`.
  - pgvector recall at 10 against exact search (30 queries, filter after
    the scan):

    | Data | Filter passes | ef 40 | ef 100 | ef 200 | ef 400 |
    |---|---|---|---|---|---|
    | 3,000 × 64 random | 2/3 | 0.930 | 0.997 | | |
    | 40,000 × 64 random | all | 0.513 | 0.763 | 0.903 | 0.980 |
    | 40,000 × 64 random | 1/3 | 0.497 | 0.733 | 0.883 | 0.987 |
    | 3,000 × 8 random | either | 1.000 | 1.000 | 1.000 | 1.000 |

    Random 64-dimension vectors are a worst case: real embeddings
    cluster. The filter does not lower recall.
  - Neo4j: dimensions 1 to 4096 (4097 fails, 22N03). The default index
    uses binary quantization and an expansion factor of 3.
    `quantization.enabled: false` shows as type `NONE`. Inside `SEARCH`,
    `=`, `IN $list`, `IS NULL` and `<` work, on filter properties only
    (22ND3 otherwise); `<>`, `NOT` and `OR` fail. A wrong-length list is
    stored and not indexed.
  - Neo4j recall at 10 (3,000 random vectors, 2/3 pass the filter):

    | Setting | 8 dims | 64 dims |
    |---|---|---|
    | binary, expansion 3 | 0.753 | 0.687 |
    | none, expansion 3 | 0.990 | 0.717 |
    | none, expansion 10 | | 1.000 |
    | binary, expansion 10 | | 0.933 |
    | scalar, expansion 10 | | 0.987 |

  - Neo4j batching: both `CALL (i)` over `UNWIND range(…)` and `CALL
    (qv)` over `UNWIND $qs` returned 15 rows for 5 queries × 3, equal to
    the exact top 3 of each. Two indexes on one label with properties
    `embedding_8` and `embedding_4` kept their vectors apart. The
    `exclude_run` filter after `SEARCH` kept only the other run's rows.
    Read your write: 0 misses in 50.
- **Rationale:**
  - One score scale lets the engine's thresholds work on every backend.
    FR-026 is edited to say so (R22).
  - Quantization off and expansion 10 give Neo4j recall 1.0 where the
    defaults give 0.69; ef_search 100 gives Postgres 0.997 on the
    recall fixture. SC-010's fixture is 3,000 vectors of 64 dimensions
    from `FakeEmbeddingModel` (R20), the case with a measured margin on
    both.
  - A property per dimension lets an index id be rebuilt at a new
    dimension without touching another index's vectors in the same
    database.
- **Alternatives:**
  - `halfvec` on Postgres up to 4,000 dimensions: deferred. Lakebase's
    pgvector version is not stated in
    [databricks-platform.md](../../docs/reference/databricks-platform.md),
    and every listed embedding model of M0 fits 2,000. Recorded in
    tech-debt with the code.
  - Raising ef_search to 200 or 400: costs latency for a recall the
    fixture already meets. The engine can pass it later as a setting.
  - Vectors as properties of `Chunk` and `Entity` nodes when paired:
    would tie the vector store to the graph store's nodes and make the
    split pairing a second layout.

## R12. Hop

- **Decision:** `hop(entity_ids, spec)` reads, for each start entity,
  in one query on every backend:
  - **Neighbours** through three kinds of link: relation rows in either
    direction (`via_kind="relation"`, `via_type` the relation type);
    items whose roles name both entities (`role`, `via_type` the item
    type); and `same_as` rows that are not rejected, when
    `include_same_as` is set (`same_as`, `via_type` the link's status).
  - **Items:** events and facts with a role naming the start entity.
  - **Filters:** `relation_types` on relation rows, `item_types` on
    items, `statuses` on relations and facts (events have no status and
    pass), `starts_before=D` drops rows whose `valid_from` is after D,
    `overlaps=(start, end)` keeps rows whose valid time meets the range
    (an open end is unbounded). `None` means no filter on every field.
  - **Caps and order:** per start entity, neighbours ranked by support
    (the number of distinct relation rows, shared items and links behind
    them) descending, then the newest `observed_at` (missing last), then
    neighbour id, cut to `neighbour_limit`; items ranked by support
    (evidence rows for an event, 1 for a fact) descending, then
    `observed_at`, then item id, cut to `item_limit`. One edge is
    returned per kept neighbour, link kind and type, carrying up to
    `item_limit` row ids in the same order, its support, and the
    `degree` stored on the neighbour.
  - The order ends on a unique id, so caps cut at the same place on every
    backend, and membership is a must-match even though order among ties
    of scores may differ.
  - Postgres: `unnest(%s::text[]) AS s(id) CROSS JOIN LATERAL (… ORDER
    BY … LIMIT …)` for neighbours and for items, `DESC NULLS LAST`.
    Neo4j: `UNWIND $ids … CALL (e) { … ORDER BY … LIMIT $k }`, with
    `coalesce(observed_at, date('0001-01-01'))` because Cypher sorts null
    first in a descending order.
- **Evidence** [run]: on a hub with 5,000 `WORKS_FOR` edges and one
  `MEMBER_OF`, `CALL (e) { MATCH (e)-[r:$any($types)]-(n:Entity) WHERE
  r.index_id = $ix RETURN r, n ORDER BY r.support DESC, r.observed_at
  DESC, r.relation_id LIMIT $k }` returned the right top 5, in 454 ms
  cold and 56 ms warm on the server.
- **Rationale:** engine brief §4.1 step 5 and ADR 0014: one hop per call,
  caps inside the query, store order fixed, so the engine composes hops
  and applies the hub penalty from the degree it gets back.
- **Alternatives:** quantified path patterns (cannot cap per hop, per
  neo4j-platform.md); returning every row and capping in Python (a hub
  sends 5,000 rows across the wire).

## R13. Who writes the vectors

- **Decision:**
  - `open_stores` pairs the stores when the index's graph and vector
    connections are the same connection name. The graph store then holds
    the vector store's write code and writes `DocumentWrite.vectors`
    inside the document's unit, and deletes the previous version's
    vectors in step 1. `Stores.graph_writes_vectors` is true.
  - Otherwise the pairing is split: a `DocumentWrite` with vectors
    raises `StorageError` on the graph store, and the caller (the engine
    in 004, a test helper here) upserts the vectors first, writes the
    graph, then deletes the vectors the previous version had and the new
    one lacks ([§6.3](../../docs/product/engine-brief.md#63-which-store-writes-the-vectors)).
  - Both kinds can serve both roles, so the profile accepts Postgres or
    Neo4j for each. The contract suite runs the split pairing as a Neo4j
    graph with Postgres vectors, plus a split reference pairing.
- **Rationale:** the same connection means the same database, so one
  transaction covers both writes. FR-013 then holds with no flag in the
  profile.
- **Alternatives:** a `writes_vectors` profile flag (one more setting to
  get wrong; the connection name already says it).

## R14. Write units, kill points and recovery

- **Decision:**
  - Each document is one transaction through M0's `transaction()` on
    Postgres and `write()` on Neo4j, in the five steps of FR-006. Each
    step is a bounded number of statements: one per table or label per
    step, rows passed as arrays (`unnest`, `UNWIND`) or `COPY`, never a
    statement per row (FR-014).
  - `WriteStep` (protocols) names the steps: `DELETE_PREVIOUS`,
    `INSERT`, `STATUS_CHANGES`, `DELETE_ORPHANS`, `DOCUMENT_ROW`. Store
    constructors take a keyword-only `step_hook: Callable[[WriteStep,
    str], None] | None = None`, called with the step and the doc id after
    each step inside the unit. Normal runs pass nothing; the call is the
    only difference (FR-046).
  - A hook that raises aborts the unit. M0's retry replays only transient
    server errors, so the hook's exception rolls back and propagates; the
    old version stays whole.
  - A killed server transaction is tested too: the hook ends the unit
    from a second connection.
    - Postgres: `pg_terminate_backend`. With `retry.max_attempts = 1`
      the write raises `StoreUnavailableError` and the old version
      stays; with the default retry, M0 replays the whole unit and the
      new version is whole.
    - Neo4j: `TERMINATE TRANSACTIONS`. The driver raises
      `Neo.ClientError.Transaction.Terminated`, a client error that it
      does not retry, so M0 raises `QueryError` and the old version
      stays. Calling the write again writes the new version whole.
  - The split pairing's crash is a test helper: it upserts the new
    vectors, raises before the graph write, then replays. The graph
    keeps the old version, the extra vectors have ids the graph lacks,
    and after the replay the vector ids equal the graph's chunk ids.
- **Rationale:** a hook between steps reaches every kill point of FR-046
  on every backend with no test-only branch in the store. A real dropped
  connection checks that the server, not only the client, rolls back.
- **Alternatives:** killing the process (slow, and the same rollback as
  a dropped connection); a fault-injecting proxy (more machinery).
- **Evidence** [run]: on Community, `TERMINATE TRANSACTIONS` ended a
  write transaction that had created a node and was still running. The
  client got `Neo.ClientError.Transaction.Terminated`, and the node was
  not committed.

## R15. Deletes, orphans, degrees and status changes

- **Decision:**
  - Step 1 deletes by `doc_id`: chunks, mentions, relations, facts,
    roles, event evidence, attribute sources, identity blocks, `text_in`
    rows naming the document, and, when paired, its vectors.
  - Step 4 deletes orphans among the entities and events the unit
    touched or whose rows step 1 removed: an entity with no mention, role
    or relation row, an event with no evidence. An orphan's aliases,
    identity values, attribute sources, identity blocks, `text_in` and
    `same_as` rows go with it (FR-008). `same_as` and aliases are
    entity-level, so they are deleted only with their entity.
  - `delete_documents` runs steps 1, 3, 4 and then deletes the document
    row, as one unit per document.
  - `refresh_degrees(ids)` counts, per entity, distinct neighbour
    entities through relation rows and role-mates, and stores it. It is
    one statement per call.
  - Status changes update `status` and `closed_at` on relation and fact
    rows only. A change naming an unknown id raises `QueryError` (R2).
- **Rationale:** the order of engine brief §2.10, with the orphan search
  bounded to what the unit touched so a document's unit never scans the
  graph.

## R16. Layout version

- **Decision:** each backend has a `LAYOUT_VERSION = 1` constant. The
  `meta` table (Postgres) or `StoreMeta` node (Neo4j) records it at
  `ensure_schema`. The store checks it once per instance, on the first
  call, and `ensure_schema` checks it before any DDL:
  - nothing recorded and no schema: `StorageError` saying to call
    `ensure_schema` (except in `ensure_schema` itself, which creates it);
  - another version: `ConfigError` naming both versions and saying to
    rebuild the index under a new index id (FR-036). There are no
    migrations in v1.
- **Rationale:** a lazy check costs one read per store instance and
  catches a store opened on an index built by another SDK version.

## R17. Profile index section and the builder

- **Decision:**
  - `Profile.index: IndexSettings | None = None`, all fields
    operational: `id` (the R5 pattern), `graph: ConnectionName`,
    `vectors: ConnectionName | None` (defaults to `graph`).
  - A profile validator raises `ConfigError` (through M0's load errors)
    when a named connection is missing, when a connection's kind cannot
    serve its role (both kinds serve both today; the check exists for
    M2's kinds), or when stated embedding dimensions
    (`models.embedding.dimensions` or its capability override) exceed
    the vector connection's maximum. The maxima are a constant table in
    `config` (`postgres: 2000`, `neo4j: 4096`), kept equal to the stores'
    capabilities by a test. Dimensions left to the shipped capability
    profile are checked by `ensure_collections` with the same error.
  - `tenetrag.storage.open_stores(profile, *, credentials=None) ->
    Stores`: credentials map connection names to M0 `Credential`s. It
    opens each connection once through `open_connection`, runs
    `health()` (version, extensions, edition) and the Postgres locale
    check, builds the graph and vector stores for `profile.index.id`,
    pairs them (R13), and returns `Stores(graph, vectors,
    graph_writes_vectors)` with `close()`. A profile without `index`
    raises `ConfigError`. A missing credential raises `AuthError` from
    M0's resolution, with no other identity tried; a missing extra
    raises `MissingExtraError`.
- **Rationale:** FR-038 to FR-040. `serving` will compose the stores
  later; until then 004 and the tests need one function.

## R18. `norm()` and the tone-mark table

- **Decision:** `tenetrag.engine.text.norm(text) -> str`:
  1. NFC;
  2. the tone-mark table, which moves the mark from the second vowel to
     the first in the endings `oa`, `oe` and `uy` when nothing follows
     them in the syllable: `oà oá oả oã oạ` → `òa óa ỏa õa ọa`, the same
     for `oe`, and `uỳ uý uỷ uỹ uỵ` → `ùy úy ủy ũy ụy`. `uy` after `q`
     is left alone (`quý`), and so is any ending followed by a letter
     (`hoàng`, `khuỷu`). Upper case maps the same way;
  3. `casefold()`, then NFC again, since casefolding can decompose a few
     non-Vietnamese letters;
  4. whitespace collapse: `" ".join(text.split())`.
- **Tests:** `hoà`→`hòa`, `Hoà`→`hòa`, `thuỷ`→`thủy`, `khoẻ`→`khỏe`,
  `uỷ ban`→`ủy ban`; unchanged: `hoàng`, `quý`, `khuỷu`, `toàn`; kept
  apart: `lãi`, `lại`, `lai`; `đ` kept; decomposed input equals
  precomposed; NBSP and runs of spaces collapse.
- **Rationale:** engine brief §7 names the table by example only. The
  old placement (`hòa`) is the one the table targets, and the endings
  rule is what makes `hoàng` safe.
- **Alternatives:** a library such as underthesea (heavy, and the table
  is fifteen pairs).

## R19. The reference store

- **Decision:** `tests/support/reference/`:
  - `ReferenceDatabase` plays a server: dictionaries per index id, one
    lock, an injected clock. Several store objects can share one, so the
    lease, isolation and replay cases run as on a real server.
  - `ReferenceGraphStore(db, index_id, *, vectors=None, step_hook=None)`
    and `ReferenceVectorStore(db, index_id)`. A unit copies the index's
    tables, applies the steps to the copy, and swaps it in at the end, so
    a hook that raises leaves the old state.
  - Exact cosine search, full text by the R6 split and OR rule written in
    Python, name search through `_trigram.py`, hop by the R12 order.
  - `max_dimensions` 4096, to match the larger real backend.
- **Rationale:** FR-029. Copy-and-swap makes per-document atomicity
  obvious to read.

## R20. The contract suite

- **Decision:**
  - `tests/contract/` holds the suite. Its `conftest.py` parametrizes a
    `stores` fixture over: `reference`, `reference-split`, `postgres-pg16`,
    `postgres-pg17`, `neo4j`, and `neo4j-graph+postgres-vectors`. The
    Docker parameters carry the `docker` and `enable_socket` marks, so
    `make test` runs the reference ones and `make integration` the rest.
    Containers are session-scoped; each test gets a fresh index id
    (`t` plus 12 hex digits of its node id's hash).
  - The image pins and the Docker check move from
    `tests/integration/conftest.py` to `tests/support/containers.py`, so
    both suites share them.
  - `tests/support/contract/writes.py` turns the corpus into
    `DocumentWrite`s: documents from `documents.jsonl`, world entities
    from the fact table, ids by the SHA-256 recipes of
    [§1](../../docs/product/engine-brief.md#ids-and-hashes), normalized
    text through `engine.text.norm`, vectors from
    `FakeEmbeddingModel(dimensions=8)`, statuses and deletions from
    `graph.json`. D1, D2 and D5 are the core; the rest of the 41
    documents feed the counts and isolation cases.
  - Generated data, all fictional: the 5,000-relation hub (SC-007), the
    tone-mark and diacritic name sets (SC-009), and the recall fixture
    of 3,000 texts embedded at 64 dimensions (SC-010).
  - `tests/contract/cases.py` maps each case of FR-043 to test node ids.
    A unit test fails when a case has no test or names a missing one
    (FR-044, SC-001).
  - Planted faults (SC-003): `tests/support/contract/faults.py` patches
    the reference store with one fault per must-match case and runs that
    case's tests, reporting every fault that survives. It runs as
    `uv run python -m tests.support.contract.faults`, outside `make test`
    for time, and its result is recorded in quickstart.md.
- **Rationale:** one suite, many fixtures (FR-041). Faults planted in the
  reference store show the tests can fail, which a green run alone
  cannot.
- **Alternatives:** a pytest plugin per backend (more machinery than a
  parametrized fixture); mutation testing tools (a new dependency for
  what a hand-written fault list does).

## R21. Error-message hygiene

- **Decision:**
  - The Neo4j connection's `QueryError` keeps the server's code and
    drops `exc.message`, which can carry property values (R8). A
    regression test feeds a message holding a value and checks that the
    value is absent. Postgres keeps the first line of the message and
    drops details, as M0 does; a test checks that a unique violation
    names the constraint and not the value.
  - Store errors name ids, types, collection names and counts, never a
    quote, a chunk's text, an alias or a credential (FR-005).
- **Rationale:** a value from a document is adopter content. Error text
  reaches logs and agents.

## R22. Spec and doc edits made with this plan

Small wording changes, with the reason in the section named. Made in
spec.md with this plan:
- FR-030: the writer lease is a lease record that ends at its time, as
  on Neo4j, instead of "a lock that ends with its session or its time"
  (R4). FR-015 already asks for renew, release and an end time, and
  stays as written.
- FR-026: a hit's score is the cosine similarity, from -1 to 1, on every
  backend (R11).
- Key Entities, "Store schema": the pack's type names only; the index id
  and the layout version belong to the store (R3).
- FR-047: casefold is followed by NFC again (R18).

Made with this plan outside the spec:
- [ADR 0024](../../docs/decisions/0024-hold-the-writer-lease-in-a-fenced-lease-record.md)
  amends ADR 0008 §7. ADR 0008's status line and docs/index.md note it,
  and the AGENTS.md status says the design is settled through ADR 0024.

With the code (FR-049):
- Engine brief §1: the Chunk→Document edge is `IN_DOCUMENT` (R3);
  documents gain `code_norm` and `title_norm` (R2); `entities.attributes`
  is computed on read from attribute sources (R2); entities, aliases and
  events keep their creating run (R2); the Neo4j node list adds
  `IdentityValue`, `ResolutionDecision`, `WriterLease`, `StoreMeta`,
  `Collection` and the vector labels (R8, R11). domain-packs.md's
  infrastructure table renames `PART_OF` to `IN_DOCUMENT` too.
- Engine brief §6.1 and §6.5: `renew_writer` and `release_writer`; the
  lease record on both backends; `search_names` uses trigram similarity
  on Neo4j through trigram tokens (R10). §6.1 and §6.2 then link to the
  protocol code instead of keeping a copy.
- Engine brief §7: the tone-mark rule of R18.
- neo4j-platform.md: the [run] facts of R8 to R12 replace "untested" for
  the shapes this feature uses.
- tech-debt.md: `halfvec` above 2,000 dimensions on Postgres (R11).

## Platform checks run

All on 2026-10-21, on a Linux host with Docker, in containers started
for the check and removed after it. Scripts were throwaway Python (the
locked psycopg 3.3.6 and neo4j 6.3.1 drivers) and `psql` or
`cypher-shell` inside the containers.

| Image | Digest |
|---|---|
| `neo4j:2026.09.0-community` | `sha256:0dfcadbd51e1d2e5a0cf86d054a0bb537a4bce212796d967cbd88445aaf3fbf3` |
| `pgvector/pgvector:0.8.7-pg17` (Postgres 17.11) | `sha256:ac08538c6f8b9904c33c8224c5e5706dbe760aca29db1d096972b4052c22a75d` |
| `pgvector/pgvector:0.8.7-pg16` | `sha256:7b822b0aac60967beb1ea5e576b8602c94c300a157d187f385ae3e0da199b90a` |

Neo4j reported Cypher versions 5 and 25 and the store format
`record-aligned-1.1`.

| # | Check | Server | What was run | Result | Used in |
|---|---|---|---|---|---|
| 1 | Locale | pg16, pg17 | databases with `C`, `C.UTF-8` (libc and builtin), `en_US.utf8`; `show_trgm('lãi')`, `lower('Ã')`, the R6 split | `C` breaks Vietnamese; the UTF-8 locales work | R5 |
| 2 | Extensions | pg16, pg17 | `pg_available_extensions`, create as a non-superuser | `vector` untrusted, `pg_trgm` trusted | R5 |
| 3 | Full-text split | pg16, pg17 | generated `tsv` column with GIN; 13 single-term queries | table in R6 | R6 |
| 4 | OR tsquery | pg17 | the R6 query builder on 10 inputs, operators and quotes included | table in R6 | R6 |
| 5 | Advisory locks | pg16, pg17 | session and transaction locks across commit and two sessions; `SHOW idle_session_timeout, lock_timeout` | session lock survives commit; both timeouts 0 | R4 |
| 6 | Lease row | pg17 | 12 concurrent acquirers; expiry takeover; takeover against a unit holding `FOR SHARE` | one winner; fence 2; waited, fence 3 | R4 |
| 7 | pg_trgm | pg17 | transaction-local threshold; `EXPLAIN` of `%` on 20,000 aliases; 3 queries | R7 | R7 |
| 8 | Python trigrams | pg17 | 8 pairs through `similarity()` and the Python function | equal to 4 places | R10 |
| 9 | pgvector limits | pg17 | HNSW at 2,001 and 4,001 dims on `vector` and `halfvec`; wrong length; cosine of orthogonal and opposite vectors | R11 | R11 |
| 10 | pgvector batching | pg17 | LATERAL over `unnest(vector[])`, 40,000 × 64; `EXPLAIN`; per-query order | index scan; 33 ms for 20 | R11 |
| 11 | pgvector recall | pg17 | ef_search 40 to 400 with `relaxed_order`; exact via `enable_indexscan = off` | tables in R11 | R11 |
| 12 | Uniqueness | Neo4j | composite on `Entity`, `Community`, 4-property `Alias`, per-type relationship; existence constraint | R8 | R8 |
| 13 | Dynamic names | Neo4j | `SET n:$(…)`, dynamic `MERGE`, `$all`, `$any`, `REMOVE n:$(…)` | all work | R8 |
| 14 | Dynamic `MERGE` time | Neo4j | 5,000 edges of two types, dynamic first and replay, static per type | 1,493, 527, 873 ms | R8 |
| 15 | Vector index | Neo4j | create with filter properties; dims 4096 and 4097; quantization settings; `WHERE` forms inside `SEARCH`; wrong-length list | R11 | R11 |
| 16 | Vector recall | Neo4j | 3,000 random vectors, quantization × expansion, exact via `vector.similarity.cosine` | table in R11 | R11 |
| 17 | Batched `SEARCH` | Neo4j | `CALL (i)` and `CALL (qv)` over `UNWIND`; two dimension properties; `exclude_run` after `SEARCH`; score scale | R11 | R11 |
| 18 | Full text | Neo4j | analyzers list; `standard-no-stop-words` on the R6 documents; fuzzy; escaping; `index_id` in the Lucene query | R9 | R9 |
| 19 | Read your write | Neo4j | 50 write-then-search pairs on vector and full-text indexes | 0 misses | R9, R11 |
| 20 | Hop | Neo4j | 5,000-edge hub, `CALL (e) { … LIMIT }`, `PROFILE` | top 5 right; 454 / 56 ms | R12 |
| 21 | Lease node | Neo4j | 12 concurrent acquirers with `MERGE` + `SET l._lock` | one winner | R4 |
| 22 | Trigram tokens | Neo4j | 22,000 aliases in a `whitespace` full-text index; 4 queries | R10 | R10 |
| 23 | Relation lookups | Neo4j | `PROFILE` of lookups by `relation_id IN` and by `doc_id` on 30,000 and 90,000 edges: static union, `$any`, `UNWIND` of single dynamic types, untyped | static union seeks; the others scan | R8 |
| 24 | Identity values | Neo4j | `PROFILE` of an `UNWIND` lookup on a composite range index, 20,000 nodes | node index seek, 6 db hits | R8 |
| 25 | Killed transaction | Neo4j | `SHOW TRANSACTIONS`, then `TERMINATE TRANSACTIONS` on a running write | `Transaction.Terminated`; nothing committed | R14 |

Checks 23 to 25 ran later the same day, while writing the data model.
Not checked by running: anything on Aura or Lakebase.

## Notes for later features

- **Engine, feature 004.**
  - The engine owns the split-pairing sequence (R13). To delete the
    previous version's stale vectors it needs their ids: the previous
    chunk ids, read before the write. If that proves awkward, the vector
    protocol can grow a `delete_documents` that keeps one run.
  - The engine renews the lease between documents (R4), and builds the
    owner string from host, process id and a random suffix.
  - The fixture helper's id recipes (R20) are a test-only copy of §1.
    When 004 writes the engine's id module, the helper switches to it.
- **Retrieval, feature 005.** Real-model recall is measured there; the
  fixture floor here is on fake vectors. ef_search and the Neo4j
  expansion factor may become settings if the benchmark asks.
- **M2.** Lakebase's pgvector version decides whether `halfvec` raises
  the Postgres maximum to 4,000. Delta's lease row follows ADR 0024.
- **Packs.** No shipped pack has a multivalued attribute. Shown
  attributes keep one value per attribute (R2); a multivalued attribute
  will need the newest value per distinct value.
- **Open.** A pack type named like a future infrastructure label would
  be refused only once the label is reserved; reserving names in the
  pack format itself would catch it at load.
