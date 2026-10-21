# Contract: `tenetrag.storage` stores and `open_stores`

Imports allowed: `tenetrag.protocols`, `tenetrag.config`,
`tenetrag.auth`, `tenetrag._retry`, M0's `tenetrag.storage` connections,
and the drivers behind the `postgres` and `neo4j` extras (FR-048). The
stores implement [protocols.md](protocols.md). Layouts are in
[data-model.md §6 and §7](../data-model.md#6-postgres-layout); the
platform facts behind them are in [research.md](../research.md).

## 1. Store classes

```python
from tenetrag.protocols import StepHook
from tenetrag.storage import Neo4jConnection, PostgresConnection

class PostgresVectorStore:
    def __init__(self, connection: PostgresConnection, *, index_id: str) -> None: ...

class PostgresGraphStore:
    def __init__(self, connection: PostgresConnection, *, index_id: str,
                 paired_vectors: PostgresVectorStore | None = None,
                 step_hook: StepHook | None = None) -> None: ...

class Neo4jVectorStore:
    def __init__(self, connection: Neo4jConnection, *, index_id: str) -> None: ...

class Neo4jGraphStore:
    def __init__(self, connection: Neo4jConnection, *, index_id: str,
                 paired_vectors: Neo4jVectorStore | None = None,
                 step_hook: StepHook | None = None) -> None: ...
```

- `index_id` must match `^[a-z][a-z0-9_]{0,39}$`, else `ConfigError`.
- `paired_vectors` must use the same connection object, else
  `ConfigError`. The graph store then writes and deletes vectors inside
  each document's unit (§3.3).
- `step_hook` is for tests (FR-046). Normal runs pass nothing, and the
  only difference is the call.
- A constructor runs no query. The first call checks the layout version
  (data model §9) and, on Postgres, the locale; both are cached for the
  instance.
- The store does not own its connection: `Stores.close()` or the caller
  closes it.
- The classes are exported from `tenetrag.storage`. Importing it does not
  import a driver; the store modules import theirs when a store is
  built, and a missing one raises `MissingExtraError` naming the extra
  (FR-037), as M0's connections do.

## 2. Writer lease

ADR 0024, on every graph store, the reference store included:

| Call | Succeeds when | Then | Else |
|---|---|---|---|
| `acquire_writer(owner, ttl_s)` | no lease, an expired one, or one held by `owner` | holds the lease until now + `ttl_s` by the server clock; a new holder increments `fence`, the same owner keeps it | `WriterBusyError` naming the holder and its end time |
| `renew_writer(lease, ttl_s)` | owner and fence match the record, and it has not expired | end time moves to now + `ttl_s` | `WriterBusyError` |
| `release_writer(lease)` | owner and fence match | the record ends now; the next acquire succeeds | nothing: a lease already gone or taken is not an error |

- Each is one conditional statement, so two acquirers never both win.
- The store remembers the lease it acquired or renewed. These calls
  need it: `write_documents`, `delete_documents`, `refresh_degrees`,
  `begin_run`, `finish_run`, `put_cached_extractions` and
  `put_resolution_decisions`. Each such unit first reads the lease
  record under a lock (Postgres `SELECT … FOR SHARE`, Neo4j a write
  lock taken by `SET`) and checks owner, fence and end time. A lost
  lease raises `WriterBusyError` and writes nothing. No lease at all
  raises `StorageError` saying to call `acquire_writer`.
- A takeover waits for a unit that holds the record's lock, so a unit
  that began under the old lease commits before the new holder writes.
- `ensure_schema`, `ensure_collections`, vector writes and every read
  need no lease.
- Two store objects on one index, in one process or two, see one lease.

## 3. Write units

### 3.1 `write_documents`

For each `DocumentWrite` in order, one transaction with five steps; the
store calls `step_hook(step, doc_id)` after each (data model §5.2):

| Step | Postgres and reference | Neo4j |
|---|---|---|
| `DELETE_PREVIOUS` | delete the document's chunks, mentions, relations, facts, roles, event evidence, attribute sources, identity blocks and `text_in` rows naming it; paired: its `chunks` and `chunk_questions` vectors | the same nodes and edges by `doc_id`; relation edges through the static union of the schema's relation types |
| `INSERT` | insert the rows; upsert entities, aliases, events, `text_in` and `same_as`; paired: upsert the vectors | create the rows; merge entities, aliases, events, identity values, `TEXT_IN` to other documents and `SAME_AS` |
| `STATUS_CHANGES` | set `status` and `closed_at` on the named relations and facts | the same |
| `DELETE_ORPHANS` | among entities and events this unit touched or whose rows step 1 removed: entities with no mention, role or relation, events with no evidence, with what hangs on them (FR-008); paired: their entity vectors | the same with `DETACH DELETE` |
| `DOCUMENT_ROW` | upsert the document row | merge the `Document` node, then its `IN_DOCUMENT` edges and the unit's own `TEXT_IN` links |

- Each step is a bounded number of statements: one per table or label,
  rows passed as arrays (FR-014).
- A type outside the store's schema raises `ConfigError` before the
  unit starts. A status change naming an unknown item raises
  `QueryError` naming the id, and the unit rolls back (FR-011).
- A failure stops the batch: earlier documents stay written, later ones
  are not tried, and the error propagates.
- Writing the same `DocumentWrite` again changes no row (FR-007); entity,
  alias and event `run_id`s keep their first run (data model §1).

### 3.2 `delete_documents`

For each `DocumentDelete`, one transaction: `DELETE_PREVIOUS`,
`STATUS_CHANGES`, `DELETE_ORPHANS`, then `DOCUMENT_ROW` removes the
document row or node. An unknown `doc_id` with no status changes is a
no-op; its status changes still apply.

### 3.3 Paired and split vectors

| Pairing | Who writes vectors | `DocumentWrite.vectors` |
|---|---|---|
| paired (one connection) | the graph store, in steps 1, 2 and 4 | written in the unit |
| split | the caller, through the vector store, before the graph write; it deletes the previous version's extra vectors after | must be empty, else `StorageError` before the unit |

The caller's split sequence (engine 004, the suite's helper now) is in
[contract-suite.md §4](contract-suite.md#4-the-split-pairing).

### 3.4 Killed units

A hook that raises aborts the unit: the transaction rolls back, the
error propagates unchanged, and the previous version stays whole. A
server-side kill is the same, with M0's error mapping:

| Backend | Kill | Error with `retry.max_attempts = 1` | With the default retry |
|---|---|---|---|
| Postgres | `pg_terminate_backend` from a second connection | `StoreUnavailableError` | M0 replays the whole unit; the new version is whole |
| Neo4j | `TERMINATE TRANSACTIONS` from a second session | `QueryError` (`Neo.ClientError.Transaction.Terminated` is not retried) | the same `QueryError`; a second call writes the new version |

## 4. Backend rules

### 4.1 Postgres

- One schema per index, `tenetrag_<index_id>`, created by
  `ensure_schema` in one transaction under `pg_advisory_xact_lock` on a
  hash of the schema name.
- `ensure_schema` runs `CREATE EXTENSION IF NOT EXISTS` for `vector`
  and `pg_trgm`, and raises `UnsupportedServerError` naming the ones it
  cannot create and saying an administrator must create them (FR-031).
- Locale: `SELECT 'ã' ~ '^[[:alnum:]]$'` must be true, else
  `UnsupportedServerError` naming `datctype` and asking for a UTF-8
  locale such as `C.UTF-8`.
- Every identifier goes through `psycopg.sql.Identifier` after the
  `_names` check; every value is a parameter (FR-034).
- `search_names` sets `pg_trgm.similarity_threshold` with
  `set_config(…, true)`, local to its read transaction. `search` sets
  `hnsw.ef_search = 100` and `hnsw.iterative_scan = relaxed_order` with
  `SET LOCAL`.
- `capabilities.max_dimensions` is 2000.

### 4.2 Neo4j

- Community or Enterprise 2026.09 or later, no APOC, no GDS (FR-033).
  M0's `health()` refuses an older server.
- Every query starts with `CYPHER 25`. Every node carries `index_id`,
  and every uniqueness constraint includes it.
- Pack names become labels and edge types through `$(…)` in writes and
  `$any(…)` in `hop`; property lookups on relation edges use a static
  union of the schema's relation types, built after the `_names` check
  (research R8).
- Vector and full-text search run through `SEARCH`. The full-text
  query is `+index_id:"<id>" +text_norm:(<escaped terms>)` (research
  R9).
- `search_names` reads candidates from the trigram full-text indexes,
  then filters with `storage/_trigram.py` (research R10).
- `capabilities.max_dimensions` is 4096.
- The connection's `QueryError` keeps the server's code and drops its
  message, which can carry a value (research R21).

### 4.3 Shared modules

```python
# storage/_names.py
def checked_label(name: str, schema: StoreSchema) -> str: ...
def checked_edge_type(name: str, schema: StoreSchema) -> str: ...
    # Return the name when it matches its pattern, is not reserved and is in the
    # schema; else ConfigError naming it. Called just before a name enters a query.

# storage/_trigram.py
def trigrams(text: str) -> frozenset[str]: ...
    # pg_trgm's rule: words are runs of [^\W_]; each padded "  " + word + " ".
def similarity(a: str, b: str) -> float: ...
    # Jaccard index of the two trigram sets; 0.0 when both are empty.
def trigram_tokens(text: str) -> str: ...
    # The Neo4j `trigrams` property: tokens joined by spaces, inner spaces as "_".
```

## 5. `open_stores`

```python
from collections.abc import Mapping
from tenetrag.auth import Credential
from tenetrag.config import Profile

def open_stores(profile: Profile, *,
                credentials: Mapping[str, Credential] | None = None) -> Stores: ...

@dataclass(frozen=True, slots=True)
class Stores:
    graph: GraphStore
    vectors: VectorStore
    graph_writes_vectors: bool
    def close(self) -> None: ...         # closes each connection once
    def __enter__(self) -> Self: ...
    def __exit__(self, *exc: object) -> None: ...
```

- `profile.index` must be set, else `ConfigError` saying to add an
  `index` section.
- `credentials` maps connection names to credentials. A connection with
  none uses its profile source through M0's resolution; with neither, M0
  raises `MissingCredentialError` (an `AuthError`), and no other
  identity is tried (FR-040).
- It opens each named connection once through `open_connection`, runs
  `health()`, builds the stores for `profile.index.id`, and pairs them
  when `graph` and `vectors` name the same connection
  (`graph_writes_vectors=True`).
- On any failure it closes what it opened before raising.
- It runs no DDL: the caller calls `ensure_schema` and
  `ensure_collections`.

```python
from tenetrag.auth import Credentials, Secret
from tenetrag.config import load_profile
from tenetrag.storage import open_stores

profile = load_profile("profiles/local.yaml")   # index: {id: alpha, graph: pg}
pg_login = Credentials.basic("tenetrag", Secret.from_env("TENETRAG_PG_PASSWORD"))
with open_stores(profile, credentials={"pg": pg_login}) as s:
    s.graph_writes_vectors      # True: graph and vectors share "pg"
    s.graph.ensure_schema(schema)
    s.vectors.ensure_collections(spec)
```

## Behaviour pinned by tests

Unit tests (`tests/unit/storage/`), no server:

| Test | Asserts |
|---|---|
| `test_trigrams_match_pg_trgm` | `similarity` equals the eight pg_trgm values of research R10 to four places |
| `test_trigram_tokens` | `lãi` gives `__l _lã lãi ãi_` |
| `test_names_refused` | a name outside the schema, a reserved name and a pattern break each raise `ConfigError` before any query |
| `test_index_id_pattern` | `Alpha`, `1a`, `a-b` and a 41-character id raise `ConfigError` in every constructor |
| `test_paired_needs_same_connection` | a graph store paired with a vector store on another connection raises `ConfigError` |
| `test_neo4j_error_drops_message` | a `Neo4jError` whose message holds a value gives a `QueryError` with the code and without the value (R21) |
| `test_postgres_error_drops_detail` | a unique violation names the constraint and not the value |
| `test_stores_without_extras` | with the drivers hidden, `import tenetrag.storage` works and building a store raises `MissingExtraError` naming the extra (FR-037) |
| `test_max_dimensions_match_config` | each store's `capabilities.max_dimensions` equals `VECTOR_MAX_DIMENSIONS` for its kind |

Every other rule here is pinned by the contract suite on every backend
([contract-suite.md](contract-suite.md)). The Postgres locale and
extension refusals are Docker tests in
`tests/contract/test_schema_and_layout.py`, on a database created with
the `C` locale and a role that cannot create `vector`. The Neo4j version
refusal stays M0's unit test of `health()`.
