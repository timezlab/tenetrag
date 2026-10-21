# Feature Specification: Store protocols, the reference store, the contract suite and the Postgres and Neo4j stores (M1, part 2)

**Feature Branch**: none; solo development on `main`, and Spec Kit finds
this feature through `.specify/feature.json`

**Created**: 2026-10-21

**Status**: Draft

**Input**: User description: "Feature 003 (M1, part 2): the store protocols, the reference store, the contract suite, and the Postgres and Neo4j stores. Solo dev on main (feature.json, no branch). Follow the format and depth of specs/002-packs-and-corpus/spec.md. Scope from AGENTS.md, engine brief §1 (data model, ids), §6 (GraphStore, VectorStore, which store writes vectors, backend notes) and §10 (contract-suite cases), and ADR 0008/0014. One feature delivered in phases: protocols + in-memory reference store + parametrized contract suite first, then the Postgres store (pgvector, pg_trgm, full text), then the Neo4j store (vector and full-text indexes). Protocols hold only the M1 methods (no community methods until M5). Contract-suite fixtures come from the 002 corpus (D1, D2, D5 and graph.json as DocumentWrite records). Stores keep pack attributes (e.g. Decision.status) apart from engine-owned fields. Out of scope: engine extract/resolve/versions/retrieve (004), Delta/Lakebase/AI Search (M2), serving. CI is off, so Docker tests run locally."

M1 runs TenetRAG end to end on local Neo4j and Postgres
([SDK platform brief](../../docs/product/sdk-platform-brief.md), milestone
table). It is split into five features
([002](../002-packs-and-corpus/spec.md) holds the split). The numbers
after 003 are planned, not yet reserved:

| Feature | Contents |
|---|---|
| 002 (implemented) | domain packs, the shipped `core` and `enterprise-docs` packs, the identity cases, the synthetic corpus |
| 003 (this one) | store protocols, the in-memory reference store, the contract suite, the Postgres and Neo4j stores |
| 004 | the index pipeline: scan and apply, extraction, validation, resolution, versions, edit and delete, run record, trace |
| 005 | `retrieve()`, `answer()`, `explain`, the agent methods, the core retrieval metrics |
| 006 | the CLI's `trace --html` and the frontend workspace |

This feature comes before the engine because the engine reads and writes
the graph only through two protocols, `GraphStore` and `VectorStore`
([ADR 0008](../../docs/decisions/0008-build-databricks-and-open-branches-in-parallel.md)).
Fixing them first lets feature 004 code and test the engine against the
reference store, while the contract suite holds the Postgres and Neo4j
stores to the same behaviour. The engine computes ids, normalized text,
version statuses, rankings and fusion. The stores store, delete, filter
and cap. This feature makes no model call: vectors come from the fake
embedding model of M0.

Three kinds of people use it:
- **Contributors**: the author and AI agents who build features 004 and
  005. They code the engine against the protocols and run its unit tests
  on the reference store, with no Docker.
- **Backend implementers**: whoever adds a backend, such as Delta and
  Lakebase in M2. The contract suite tells them when they are done.
- **Operators**: a developer who runs TenetRAG on their own Postgres or
  Neo4j server. They name the index and its stores in the profile, and
  expect the same graph from either backend.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Protocols and the reference store (Priority: P1)

A contributor reads one module to learn everything the engine may ask of
storage: the methods of `GraphStore` and `VectorStore` that M1 needs, and
the plain records they pass. Beside it, in the test support code, an
in-memory reference store implements both protocols. It is written to be
read as a specification: plain data structures, exact search, no
indexes and no tricks. A contributor writes a document's records to it
and reads them back.

**Why this priority**: features 004 and 005 are written against these
protocols. Without the reference store, every engine test would need
Docker, and the contract suite would have no oracle before a real
backend exists ([engine brief §10](../../docs/product/engine-brief.md#10-testing)).

**Independent Test**: type-check the reference store against both
protocols. Write the running example's D1 as one `DocumentWrite`, read
every record back by id, and compare field by field.

**Acceptance Scenarios**:

1. **Given** the protocols module, **When** the type checker and the
   import rules run, **Then** the reference store satisfies `GraphStore`
   and `VectorStore`, and the protocols module imports only the standard
   library.
2. **Given** the protocols, **Then** `GraphStore` holds the setup, run,
   cache, resolution, version, write and retrieval methods of
   [engine brief §6.1](../../docs/product/engine-brief.md#61-graphstore),
   and none of its community methods, which arrive in M5.
3. **Given** D1 written as a `DocumentWrite`, **When** its document,
   chunks, entities, items and evidence are read back by id, **Then**
   every field of every record comes back equal.
4. **Given** a Decision event whose pack attribute `status` is `approved`,
   and a fact whose engine status is `superseded`, **When** both are read
   back, **Then** the pack attribute sits in the item's attributes, the
   engine status in its own field, and neither overwrites the other.
5. **Given** any write, **Then** the store keeps exactly the ids it
   received. It generates no id and normalizes no text.
6. **Given** a vector search on the reference store, **Then** it returns
   the exact cosine top k, and its full-text search matches whole
   syllables of `text_norm`.

---

### User Story 2 - One contract suite for every backend (Priority: P1)

One parametrized test suite states what every backend must do. It runs
against any pair of a graph store and a vector store handed to it. Its
inputs are the synthetic corpus of feature 002: a test helper turns
documents D1, D2 and D5, with the statuses `graph.json` records, into
`DocumentWrite` records. Cases the corpus cannot show, such as a hub with
5,000 relations, are generated in the test. The suite runs on the
reference store first, with no Docker, as part of the unit tests.

**Why this priority**: ADR 0008 keeps the engine thin only if the
backends agree. A difference caught by the suite costs an afternoon. The
same difference found as a drop in retrieval quality costs a benchmark
run and a search for its cause.

**Independent Test**: run the suite on the reference store. Check that
each case of the two lists (ADR 0008 §5, engine brief §10) maps to at
least one named test. Then plant one fault in the reference store, such
as ignoring `item_limit`, and check that the matching case fails.

**Acceptance Scenarios**:

1. **Given** D1, D2 and D5, **When** they are written, **Then** the count
   of rows of each kind equals what the fixtures expect. **When** the
   same writes run again, **Then** no count and no row changes.
2. **Given** D1 and D2 written with r1 `superseded` and r2 `current`,
   **When** D2 is deleted with the status changes `graph.json` lists for
   that deletion, **Then** r1 reads `current` again, D2's chunks,
   mentions, relations, facts, roles, attribute sources and identity
   blocks are gone, entities only D2 mentioned are deleted with their
   aliases, and entities D1 still mentions remain.
3. **Given** one relation stated in two documents, **When** one document
   is deleted, **Then** the other document's row, and its edge, remain
   ([ADR 0012](../../docs/decisions/0012-store-relations-and-facts-as-one-row-per-chunk.md)).
4. **Given** a `hop` with type, status and time filters, **Then** only
   items that pass every filter come back. **Given** an entity with more
   neighbours or items than the limits, **Then** the result holds at
   most `neighbour_limit` neighbours and `item_limit` items for it, and
   they are the same ones on every backend.
5. **Given** an entity whose alias is stored as the normalized form of
   `hoà`, **When** names are matched with the normalized form of `hòa`,
   **Then** the entity is found. **Given** entities named `lãi`, `lại`
   and `lai`, **Then** each name matches only its own entity, in name
   matching and in full-text search.
6. **Given** fuzzy name search with a similarity floor, **Then** every
   name the fixture marks must-find is in the candidates, and none marked
   must-not-find is. Scores are not compared across backends.
7. **Given** vector search, **Then** recall at 10 against exact search
   is at least 0.9 on the fixture vectors. Scores and the order among
   ties are not compared.
8. **Given** every case listed in ADR 0008 §5 and engine brief §10,
   **Then** the suite names at least one test for it, and a case with no
   test fails a check in the unit tests.

---

### User Story 3 - The Postgres store (Priority: P2)

An operator with Postgres 16 or later, with the `vector` and `pg_trgm`
extensions, names a Postgres connection for the index in the profile.
The Postgres graph store and vector store pass the whole contract suite.
The graph and its vectors live in one database, and the vectors are
written inside each document's transaction. Each index is its own schema.

**Why this priority**: Postgres is one code path for local, managed and
Lakebase servers, so it is the graph backend on Databricks too
([ADR 0008](../../docs/decisions/0008-build-databricks-and-open-branches-in-parallel.md)).
It comes after the reference store, since the suite must exist before a
backend can pass it.

**Independent Test**: start the pinned Postgres image of M0, run the
contract suite against it, then run the Postgres-only tests below.

**Acceptance Scenarios**:

1. **Given** the pinned Postgres image, **When** the contract suite runs
   against the Postgres stores, **Then** every case passes, unchanged
   from the reference run.
2. **Given** an empty database, **When** the store's schema is ensured,
   **Then** the index's schema, tables, indexes and extensions exist.
   **When** it is ensured again, **Then** nothing changes.
3. **Given** a database where the extensions are missing and the
   connection's role may not create them, **When** the schema is
   ensured, **Then** it fails, names each missing extension and says
   that an administrator must create it.
4. **Given** a connection dropped in the middle of a document's write,
   **Then** no row of that document's new version is visible, and its
   previous version is intact.
5. **Given** a hub entity with 5,000 relations, **When** it is expanded
   with the default limits (20 neighbours, 50 items), **Then** the limit
   is applied inside the database's query, and the call returns in under
   one second.

---

### User Story 4 - The Neo4j store (Priority: P2)

An operator with Neo4j 2026.09 or later (Community Edition is enough)
names a Neo4j connection for the index in the profile. The Neo4j graph
store and vector store pass the whole contract suite. Relations are
typed edges named after the pack's relation types, so a filtered
expansion reads only edges of those types and Neo4j Browser shows real
relation names. Roles are one `ROLE` edge type with a name. Every node
carries the index id.

**Why this priority**: Neo4j is the preferred graph backend outside
Databricks (ADR 0008). It comes last because its per-type schema and its
search clauses carry the most platform risk, and the suite should be
settled first.

**Independent Test**: start the pinned Neo4j Community image of M0, run
the contract suite against it, then run the Neo4j-only tests below.

**Acceptance Scenarios**:

1. **Given** the pinned Neo4j Community image, **When** the contract
   suite runs against the Neo4j stores, **Then** every case passes,
   unchanged from the reference run.
2. **Given** the `enterprise-docs` stack, **When** the schema is ensured,
   **Then** each of its relation types has its edge schema, and the edge
   types written for D1 are exactly the relation types of D1's records,
   such as `OWNER_OF`. **When** a later pack version adds a relation type
   and the schema is ensured again, **Then** the new type gets its schema
   and existing data is untouched.
3. **Given** one `OWNER_OF` statement in two chunks, **Then** two
   parallel edges exist, each with its own quote and chunk.
4. **Given** a label, edge type or property name that is not in the
   store's schema, **When** a write would use it, **Then** the store
   refuses it before any query reaches the server.
5. **Given** a server older than 2026.09, **When** the store opens,
   **Then** it fails with `UnsupportedServerError`, naming the version
   found and the version needed.
6. **Given** full-text search for `lãi`, **Then** chunks that hold only
   `lai` or `lại` are not returned: the analyzer keeps diacritics.

---

### User Story 5 - A killed run never leaves half a document (Priority: P2)

A run is killed: the process dies, the connection drops, or a second
writer starts. On every backend, each document is either its old version
or its new one, never a mix, and a replay of the run reaches the same end
state as a clean run. Only one writer works on an index at a time.

**Why this priority**: this is the consistency floor every backend must
meet (ADR 0008 §7). A half-written document would break provenance and
version statuses for every later query, silently.

**Independent Test**: on each store, stop a document's write at each of
its steps (delete the previous rows, insert, apply status changes,
delete orphans, write the document row, and for a split pairing, between
the vector write and the graph write). After each stop, check the
document is whole or absent, then replay and compare with a clean run.

**Acceptance Scenarios**:

1. **Given** a batch of three documents, **When** the write is stopped
   inside the second document's unit at any step, **Then** the first
   document has its new version, the second and third have their
   previous versions, and no orphan or dangling row exists.
2. **Given** the stopped run, **When** the same batch is written again,
   **Then** the end state equals that of a run never stopped, row for
   row.
3. **Given** a writer holding the index's writer lease, **When** a second
   writer asks for it, **Then** it gets `WriterBusyError`, naming the
   holder and when the lease ends. **When** the holder releases it or
   its time passes without renewal, **Then** the second writer gets it.
4. **Given** a pairing where the vector store is not the graph's
   database, **When** the run stops after the vectors are written and
   before the graph is, **Then** the graph has no row of the new
   version, the extra vectors name chunk ids the graph lacks, and the
   next write of that document leaves both stores consistent.
5. **Given** a pairing where the graph store also writes the vectors,
   **When** the run stops inside the document's unit, **Then** neither
   the graph rows nor the vectors of the new version are visible.

---

### User Story 6 - The profile names the index and its stores (Priority: P3)

An operator names, in the profile, the index id, the connection that
holds the graph, and the connection that holds the vectors, which is the
graph's connection unless they name another. Loading the profile checks
that the pairing can work before any query. Two indexes in one database
never see each other's rows. A store built by an older or newer layout
fails clearly instead of being read wrongly.

**Why this priority**: until `serving` composes the stores, tests and
feature 004 need one way to build them from a profile. It is P3 because
the stores can be built in code for every story above.

**Independent Test**: load profiles with valid and invalid pairings.
Write the same corpus into two indexes in one Postgres database and one
Neo4j database, delete from one, and read from the other.

**Acceptance Scenarios**:

1. **Given** a profile that names an index id and a Postgres connection,
   **When** the stores are built, **Then** the graph store and the vector
   store share that database, and the graph store writes the vectors.
2. **Given** a profile whose vector connection names a connection that
   does not exist, or whose embedding dimensions exceed what the vector
   store supports, **When** it loads, **Then** it fails with
   `ConfigError` naming the field and the limit, before any query.
3. **Given** an index id that is not a safe identifier, **When** the
   profile loads, **Then** it fails and names the allowed pattern.
4. **Given** indexes `alpha` and `beta` in one database with the same
   documents, **When** a document is deleted from `alpha`, **Then**
   every read of `beta` returns what it returned before.
5. **Given** a store whose recorded layout version differs from the
   code's, **When** it opens, **Then** it fails, naming both versions and
   saying that v1 has no migrations, so the index is rebuilt under a new
   id.
6. **Given** a store built without credentials while its connection
   requires them, **Then** building fails with `AuthError` and no other
   identity is tried
   ([ADR 0003](../../docs/decisions/0003-caller-supplied-credentials.md)).

---

### Edge Cases

**Writes and deletes**
- A batch that holds one document twice fails before any write, naming
  the document.
- Deleting a document the store does not hold changes nothing and raises
  nothing, so a replay after a crash is safe.
- One entity upserted by two documents in one batch is one row, with the
  aliases of both.
- A status change that names an item the store does not hold fails that
  document's unit and names the item. It points to an engine bug, and
  ignoring it would hide a wrong status.
- A document with 2,000 chunks is still one unit.
- Two documents with the same chunk text give two chunks, since a chunk
  id includes its document.
- A vector whose length differs from its collection's dimensions is
  refused, naming the collection and both lengths.
- An entity's shown attributes are recomputed from its remaining
  sources when a document is rewritten or deleted. An attribute with no
  source left disappears.

**Reads**
- A read with an empty list returns an empty result without a round
  trip.
- Unknown ids are absent from the result, not errors. Repeated ids give
  one record each.
- A read of 10,000 ids returns every record in a bounded number of round
  trips, never one per id.
- An entity with no edges expands to nothing.
- `same_as` links with status `rejected` are never crossed.
- The cap order is the store order of the engine brief: support, then
  `observed_at` newest first, then id. So the capped set is the same on
  every backend.

**Text**
- Stored text keeps its NFC original. Matching reads only the normalized
  fields the engine fills. No store folds diacritics or casefolds again.
- Full text uses no stemming and no stop words, so a frequent syllable
  such as `và` is still searchable.
- A search with text that normalizes to nothing returns nothing.

**Schema, layout and isolation**
- A pack name reaches a query only as an identifier the store schema
  holds. Every value is a parameter.
- Ensuring the schema never drops a table, index, label or row.
- A relation type removed from the pack keeps its existing edges until
  their documents are rewritten or deleted.
- Two indexes in one database share no row, index entry, lease or cache
  entry.

## Requirements *(mandatory)*

### Functional Requirements

**Protocols and records**

- **FR-001**: The protocols module MUST define `GraphStore` and
  `VectorStore` with the methods of
  [engine brief §6.1](../../docs/product/engine-brief.md#61-graphstore)
  and [§6.2](../../docs/product/engine-brief.md#62-vectorstore), except
  the community methods, which wait for M5. The records they pass are
  frozen dataclasses, and the module imports only the standard library.
- **FR-002**: Every method MUST be synchronous
  ([ADR 0014](../../docs/decisions/0014-use-synchronous-protocols-with-one-hop-per-store-call.md)).
  Every read takes a list of ids or keys. Expansion is one `hop` per
  call.
- **FR-003**: The records MUST carry the columns of the logical tables in
  [engine brief §1](../../docs/product/engine-brief.md#logical-tables).
  Pack attributes stay in an item's attributes, apart from the
  engine-owned fields. A pack attribute named like an engine field, such
  as a Decision's `status`, never overwrites that field, and both read
  back as written.
- **FR-004**: A store MUST NOT compute what the engine owns: ids,
  normalized text, version statuses, scores, ranking or fusion
  (ADR 0008 §4). It stores what it receives, deletes, filters and caps.
- **FR-005**: A second writer MUST get a new `WriterBusyError`, a
  subclass of `StorageError`. Other failures use the errors of M0:
  `StoreUnavailableError`, `QueryError`, `UnsupportedServerError`,
  `MissingExtraError`, `ConfigError` and the `AuthError` family. No error
  message repeats a credential, a document's text or a quote.

**Writes and deletes**

- **FR-006**: `write_documents` MUST write each document of a batch as
  one atomic unit, in the order of
  [engine brief §2.10](../../docs/product/engine-brief.md#210-write):
  delete the previous version's rows, insert and upsert, apply status
  changes, delete orphans, and write the document row last.
- **FR-007**: Writing the same `DocumentWrite` again MUST change no row.
- **FR-008**: `delete_documents` MUST remove every row of each document
  and apply its status changes in the same unit, then delete the
  orphans: entities with no mention, role or relation, and events with
  no evidence. An orphan's aliases, attribute sources, identity blocks,
  `text_in` rows and `same_as` rows go with it.
- **FR-009**: After a document is rewritten or deleted, each remaining
  entity's shown attributes MUST be recomputed from its remaining
  attribute sources, the newest `observed_at` winning.
- **FR-010**: Relations and facts MUST be one row per statement per
  chunk. Deleting one of two sources keeps the other's row, and on Neo4j
  its edge (ADR 0012).
- **FR-011**: Status changes MUST apply in the unit of the write or
  delete that carries them. A status change naming an item the store does
  not hold fails that unit, naming the item.
- **FR-012**: `refresh_degrees` MUST set each entity's degree to its
  number of distinct neighbour entities through relation and role rows
  ([§2.11](../../docs/product/engine-brief.md#211-after-all-documents)),
  not its number of rows.
- **FR-013**: When the graph store also holds the vectors, it MUST write
  them inside the document's unit. Otherwise the vector store writes them
  before the graph write, and the previous version's vectors are deleted
  after it ([§6.3](../../docs/product/engine-brief.md#63-which-store-writes-the-vectors)).
- **FR-014**: A document's rows MUST be written in a bounded number of
  statements, not one statement per row.

**Runs, caches and the writer lease**

- **FR-015**: `acquire_writer` MUST give one writer per index. The holder
  can renew and release the lease. A lease not renewed within its time
  ends, so a killed writer cannot block the index for good. A second
  writer gets `WriterBusyError` naming the holder and when the lease
  ends.
- **FR-016**: `begin_run`, `finish_run` and `get_runs` MUST keep the run
  record of [§1](../../docs/product/engine-brief.md#logical-tables):
  status, times, stage hashes, prompt versions, pack stamp and stats.
  `get_runs` returns the newest first.
- **FR-017**: `document_states` MUST return, for every document held, its
  content hash, pipeline hash and run id.
- **FR-018**: The extraction cache and the resolution decisions MUST
  round-trip exactly. Putting an existing key replaces its entry, except
  that a model verdict never replaces a reviewer verdict.

**Resolution and version reads**

- **FR-019**: `find_by_identity` MUST match a key with a scope id only
  against entities whose direct scope is that id, and a key with
  `ANY_SCOPE` against entities in any scope.
- **FR-020**: `match_names` MUST match normalized names exactly against
  normalized names and aliases, filtered by type. `exclude_run` hides
  rows written by that run. Each match carries the entity's scope path
  and the alias's origin. The store applies no scope or veto rule.
- **FR-021**: `search_names` MUST return at most `limit` candidates at or
  above `min_similarity`, by the backend's own fuzzy measure. The
  contract fixes candidate sets, never scores.
- **FR-022**: `find_events`, `match_document_links`, `get_version_groups`
  and `get_document_version_keys` MUST return what §6.1 states, batched.

**Retrieval reads**

- **FR-023**: `hop` MUST apply its relation-type, item-type, status,
  `starts_before` and `overlaps` filters, and cross `same_as` links that
  are not rejected when `include_same_as` is set. It caps each entity at
  `neighbour_limit` neighbours and `item_limit` items inside the
  backend's query, in the store order: support, then `observed_at`
  newest first, then id. Each edge carries its support and the degree of
  the entity it reaches.
- **FR-024**: `entities_in_chunks`, `get_entities`, `get_items`,
  `get_chunks` and `get_documents` MUST be batched, leave unknown ids out,
  and return each id once. `get_items` returns roles and evidence, so
  every item reaches its chunks and documents.

**Vector store**

- **FR-025**: `ensure_collections` MUST create the `chunks`, `entities`
  and `chunk_questions` collections with an embedding model id and
  dimensions each. A later call with another model id or other
  dimensions fails, naming the collection and both values, and says the
  index must be rebuilt.
- **FR-026**: `search` MUST take a list of query vectors in one call and
  return the top k per vector, filtered by type, language and document,
  with one run excluded when the filter says so. A hit's score is the
  cosine similarity, from -1 to 1, on every backend, so the engine's
  thresholds mean the same everywhere. Recall at 10 against exact search
  is at least 0.9 on the contract fixtures.
- **FR-027**: `search_text` MUST search `text_norm` by syllable, with no
  stemming, no stop words and no diacritic folding.
- **FR-028**: Each vector store MUST report its capabilities: text
  search, fused hybrid only, eventual sync, and maximum dimensions.

**Backends**

- **FR-029**: The reference store MUST live in the test support code, in
  memory, with exact search, and implement both protocols. It is not
  shipped in the package.
- **FR-030**: The Postgres stores MUST keep each index in its own schema,
  hold the graph and the vectors in one database, use trigram similarity
  for `search_names`, the `simple` text configuration on `text_norm` for
  `search_text`, and pgvector for vectors. One document is one
  transaction, and the writer lease is a lease record that ends at its
  time, as on Neo4j
  ([ADR 0024](../../docs/decisions/0024-hold-the-writer-lease-in-a-fenced-lease-record.md)).
- **FR-031**: Ensuring the Postgres schema MUST create the `vector` and
  `pg_trgm` extensions when they are missing, or fail naming the ones it
  cannot create.
- **FR-032**: The Neo4j stores MUST follow the mapping of
  [§1](../../docs/product/engine-brief.md#logical-tables): `index_id` on
  every node and in every uniqueness constraint; `Entity`, `Event` and
  `Fact` nodes with the pack type as a second label; typed relation
  edges, parallel per source; one `ROLE` edge type with a name; facts
  keep their evidence as properties. Vector and full-text search run
  through the `SEARCH` clause behind a `CYPHER 25` prefix, and the
  full-text analyzer is `standard-no-stop-words`, never a folding one
  ([neo4j-platform.md](../../docs/reference/neo4j-platform.md)).
- **FR-033**: The Neo4j stores MUST work on Community Edition 2026.09 and
  later, with no APOC and no GDS, and refuse an older server with
  `UnsupportedServerError`. Writes are idempotent: rows are merged on
  keys that a uniqueness constraint backs.
- **FR-034**: Every identifier a store builds into a query (schema,
  table, label, edge type, property or index name) MUST come from the
  store schema, which holds only names that passed the pack's name
  patterns and the index id's pattern, and the store checks it again
  before use. Every value is a query parameter. A name outside the
  schema is refused before any query.
- **FR-035**: `ensure_schema` MUST be idempotent and additive: a second
  run changes nothing, a new pack type or relation type adds its schema,
  and nothing is ever dropped.
- **FR-036**: Each store MUST record its layout version, and opening a
  store with another layout version fails, naming both. v1 has no
  migrations.
- **FR-037**: The Neo4j and Postgres drivers MUST load only with their
  extras. The protocols and the reference store need no extra, and
  opening a store without its extra raises `MissingExtraError` naming
  the extra.

**Profile**

- **FR-038**: The profile MUST gain an index section: the index id, the
  graph connection and the vector connection, which defaults to the
  graph connection. The index id has a safe identifier pattern.
- **FR-039**: Loading the profile MUST check the pairing: both
  connections exist, their kinds can serve their role, and the embedding
  dimensions fit the vector store's maximum. A failure raises
  `ConfigError` before any query.
- **FR-040**: A function MUST build the graph store and the vector store
  from a profile and caller-supplied credentials, through the M0
  connections, and decide which store writes the vectors (FR-013). A
  missing credential raises `AuthError`, and no other identity is tried.

**Contract suite**

- **FR-041**: One parametrized contract suite MUST run against any graph
  and vector store pair a test fixture supplies: the reference store in
  the unit tests, and the Postgres and Neo4j stores in the tests marked
  `docker`. The suite is the same code for every backend.
- **FR-042**: The suite's fixtures MUST come from the committed corpus of
  feature 002: at least D1, D2 and D5, with the statuses and deletions of
  `graph.json`, turned into `DocumentWrite` records by a test helper.
  Ids are computed as [§1](../../docs/product/engine-brief.md#ids-and-hashes)
  says, vectors come from the fake embedding model, and normalized text
  from the engine's normalization function (FR-047). Data the corpus
  lacks, such as a 5,000-relation hub or tone-mark name sets, is
  generated in the test and holds only fictional names.
- **FR-043**: The suite MUST cover every must-match case of ADR 0008 §5
  and every contract case of engine brief §10: counts after a write and
  a replay; the end state after a delete; supersession flags; provenance
  reachability; type, time and status filters; hop membership and caps;
  the hub invariants; normalized text matching that keeps diacritics;
  per-document atomicity after a killed run; orphan cleanup; status
  changes in the same unit; `exclude_run`; `find_by_identity` with a
  scope and with `ANY_SCOPE`; attribute sources and identity blocks
  deleted with their document; `text_in` added and removed; the
  extraction-cache round trip; writer lease exclusion; the as-of
  pre-filter; recovery from a crash between the vector write and the
  graph write; and one of two sources deleted.
- **FR-044**: The suite MUST keep a map from each case of FR-043 to its
  tests, and a unit test MUST fail when a case has no test or names a
  test that does not exist.
- **FR-045**: The suite MUST NOT compare what may differ: scores, the
  order among ties, ANN results beyond the recall floor, and fuzzy
  scores beyond candidate sets.
- **FR-046**: Each backend MUST let the suite stop a document's unit at
  each step of FR-006, and for a split pairing between the vector write
  and the graph write, without changing the store's code path for normal
  runs.

**Text normalization**

- **FR-047**: The engine's text module MUST provide the normalization of
  [engine brief §7](../../docs/product/engine-brief.md#7-text-and-language):
  NFC, casefold and NFC again, then the rules of each language named,
  then whitespace collapse, keeping diacritics and `đ`. Each language
  with extra rules has its own module; `vi` holds the tone-mark
  placement table (`hoà` → `hòa`). The languages come from the profile's
  `text_languages`, empty by default
  ([ADR 0025](../../docs/decisions/0025-normalize-text-by-the-languages-the-profile-names.md)). It is pure standard-library code. The fixtures use
  it now with `vi`, feature 004 uses it in the pipeline, and no store
  calls it.

**Architecture and docs**

- **FR-048**: The import rules MUST place every new module in a layer:
  the protocols import only the standard library; the stores import the
  protocols, `config`, `auth` and `_retry`; the engine imports no store,
  no `llm` and no driver.
- **FR-049**: The docs MUST change with the code: `ARCHITECTURE.md` (the
  protocols and storage rows, and the engine's text module); engine
  brief §6 links to the protocol code instead of keeping a copy, as §6.4
  does; neo4j-platform.md records the facts this feature verified by
  running the pinned server; the local-stack guide says how to run the
  Docker contract suite; the `AGENTS.md` status; and any gap goes to
  `docs/tech-debt.md`.

### Key Entities

- **GraphStore**: the engine's operations on the graph: setup, writer
  lease, runs, caches, resolution reads, version reads, document writes
  and deletes, and retrieval reads.
- **VectorStore**: vectors and chunk full-text search for the `chunks`,
  `entities` and `chunk_questions` collections, with its capabilities.
- **Store schema**: what `ensure_schema` builds from: the pack's entity,
  event, fact and relation type names. The index id and the layout
  version belong to the store, which serves one index.
- **DocumentWrite**: everything one document contributes: the document,
  chunks, entities, aliases, attribute sources, identity blocks,
  mentions, relations, events, event evidence, facts, roles, `text_in`,
  `same_as`, status changes, vectors when the graph store writes them,
  and the run id.
- **DocumentDelete**: a document id, the status changes its deletion
  causes, and the run id.
- **Status change**: an item id, its new status and its `closed_at`.
- **Hop spec and hop result**: the filters and limits of one expansion,
  and the edges and items it reached.
- **Writer lease**: the one writer of an index, its owner and when the
  lease ends.
- **Layout version**: the version of a store's tables and graph shape,
  recorded in the store.
- **Reference store**: the in-memory implementation of both protocols,
  in the test support code, which defines the expected behaviour.
- **Contract case**: one behaviour from ADR 0008 §5 or engine brief §10,
  mapped to the tests that check it.
- **Kill point**: a step of a document's unit where the suite stops the
  write.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100 % of the cases in ADR 0008 §5 and engine brief §10 map
  to at least one contract test, and the map check passes.
- **SC-002**: The same contract suite passes on the reference store, the
  Postgres stores and the Neo4j stores, with no backend-specific skip.
- **SC-003**: For every must-match case, a fault planted in the reference
  store makes at least one of its tests fail: 100 % of the cases.
- **SC-004**: On the reference store, the suite runs with no Docker and no
  network, inside `make test`, in under 20 seconds. On each Docker
  backend it runs in under five minutes, container start included.
- **SC-005**: Writing D1, D2 and D5 and replaying them gives identical
  counts on every store, and deleting all three leaves zero rows of
  every kind.
- **SC-006**: Stopping a write at every kill point on every store leaves
  100 % of documents whole or absent, and the replay matches a clean run
  row for row.
- **SC-007**: An entity with 5,000 relations to 5,000 neighbours expands,
  with the default limits, to at most 20 neighbours and 50 items, in
  under one second on each Docker backend.
- **SC-008**: Two composed hops from the same seeds reach identical
  entity and item sets on all three stores.
- **SC-009**: Every tone-mark pair in the fixtures matches, and every
  name that differs only in a diacritic stays apart, on every store, in
  name matching and in full-text search: 100 % of each set.
- **SC-010**: Vector search reaches recall at 10 of at least 0.9 against
  exact search on the fixture vectors, on each backend.
- **SC-011**: Zero rows of one index are visible from another index in
  the same database, across every read method.
- **SC-012**: A fresh install with no extras imports the protocols and
  runs the reference suite. Opening a Postgres or Neo4j store without its
  extra names the missing extra. All gates pass.

## Assumptions

- The reference store lives in `tests/support/`, as engine brief §10
  plans. An in-memory store for adopters' demos is not in scope.
- The engine's text module is created here with only the normalization
  function, because the fixtures need the same normalized values that
  feature 004 will write. The rest of the engine module arrives in 004.
- The engine computes version statuses, entity resolution and ids in
  feature 004. The suite feeds the stores the statuses that `graph.json`
  records, so the stores are tested on storing and applying statuses,
  not on computing them.
- The fake embedding model of M0 gives deterministic vectors with no
  network. The recall floor is measured on them. Real-model retrieval
  quality is measured in feature 005.
- Postgres means version 16 or later with pgvector and pg_trgm, as M0's
  connection checks. The Docker tests use the pinned images of
  `deploy/compose.yaml`. Lakebase shares the Postgres code path, and M2
  checks it in a workspace.
- Neo4j means 2026.09 or later, Community Edition, through the Apache
  driver behind the `neo4j` extra. No GPL component is shipped.
  neo4j-platform.md was checked by reading only (2026-10-04). This
  feature checks the facts it relies on by running the pinned server:
  the `SEARCH` clause for vectors and full text, the analyzer, dynamic
  labels and edge types, and composite uniqueness on Community.
- If merging edges with a dynamic type proves slow, the Neo4j writer
  groups rows by type and runs one statement per type, with names
  checked against the store schema, as ADR 0008 allows.
- `serving` composes the stores in a later feature. The builder of
  FR-040 serves the tests and feature 004 until then.
- CI is off (see [tech-debt.md](../../docs/tech-debt.md)), so the Docker
  tests run locally. When CI is back on, its Docker job runs them on
  both Python versions.
- A layout change in v1 means rebuilding the index under a new id.
  Migrations are out of scope.
- Out of scope: extraction, validation, resolution, version computation
  and retrieval (features 004 and 005); communities and their store
  methods (M5); Delta, Lakebase-specific setup and AI Search (M2);
  `serving`, tools and MCP.
- Depends on M0 (the connections, the errors, the retry policy, the
  profile, the fake models, the local stack) and on feature 002 (the
  pack's type names for the store schema, and the corpus).
- Estimate: about 13 working days for one developer with agents. The
  protocols, the reference store and the contract suite take four days,
  the Postgres stores four, and the Neo4j stores five, the kill points
  and the profile section included in each.
