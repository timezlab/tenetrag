# Contract: `tenetrag.protocols` (store protocols and records)

Imports allowed: the standard library only, as for M0's
`protocols.models` (FR-001). The records are in
[data-model.md §2 to §5 and §7.5](../data-model.md#2-write-records). The
store classes that implement these protocols, and the lease and write
rules every implementation follows, are in [stores.md](stores.md).

## 1. Errors

```python
class WriterBusyError(StorageError): ...
    # Another writer holds the index, or this store's lease was taken over.
    # The message names the holder (its owner string) and the lease's end
    # time in UTC ISO form, and says to wait for the end time or release the
    # other writer. It never names a document or a value.
```

Every other failure uses M0's errors (FR-005):

| Error | When |
|---|---|
| `ConfigError` | a bad `StoreSchema`; a type outside the store's schema; a layout version or collection mismatch |
| `StorageError` | a write with no lease; a call before `ensure_schema`; vectors given to a graph store that does not hold them |
| `QueryError` | a status change naming an unknown item; an unknown run id in `finish_run`; a vector of the wrong length; a server error that is not transient |
| `StoreUnavailableError` | the server is unreachable after M0's retries |
| `UnsupportedServerError` | an old server, a missing extension, a non-UTF-8 Postgres locale |
| `MissingExtraError` | a store opened without its extra |
| `ValueError` | a malformed record, raised by its `__post_init__`: a caller bug |

## 2. `GraphStore`

```python
from collections.abc import Callable, Mapping, Sequence
from typing import Protocol

class GraphStore(Protocol):
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
    def match_names(self, names_norm: Sequence[str], types: Sequence[str] | None,
                    exclude_run: str | None = None) -> list[NameMatch]: ...
    def search_names(self, text_norm: str, types: Sequence[str] | None,
                     limit: int, min_similarity: float) -> list[NameMatch]: ...
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

RunStats = Mapping[str, JsonValue]
StepHook = Callable[[WriteStep, str], None]
```

These are the methods of engine brief §6.1 without the six community
methods (M5), plus `renew_writer` and `release_writer` (ADR 0024).
Engine brief §6.1 links here once the code exists (FR-049).

| Method | Returns | Rules |
|---|---|---|
| `ensure_schema` | | idempotent and additive (FR-035); creates the layout version on a new index, checks it on an old one (data model §9); needs no lease |
| `acquire_writer`, `renew_writer`, `release_writer` | the lease | [stores.md §2](stores.md#2-writer-lease) |
| `begin_run`, `finish_run`, `get_runs` | | data model §4; `limit` from 1 to 1,000 |
| `document_states` | `doc_id → DocumentState` for every document of the index | FR-017; the one read with no ids, since change detection needs them all |
| cache and decision gets | found keys only | data model §4; a missing key is absent, never `None` |
| `find_by_identity` | entities matching any key | data model §3.3; an entity matched by two keys appears once |
| `find_events` | events matching any key | keys have `scope=ANY_SCOPE` |
| `match_names` | distinct `(entity_id, matched, origin)` rows | exact on `name_norm` and `alias_norm`; `types=None` is every type; `exclude_run` hides an entity created by that run and an alias added by it (FR-020) |
| `search_names` | at most `limit` matches, the best per entity, by similarity descending then entity id | trigram similarity at or above `min_similarity` (0 to 1); `limit` from 1 to 1,000 (FR-021) |
| `match_document_links` | candidate links | data model §3.3; each `(entity_id, doc_id, attribute)` once |
| `get_version_groups` | every relation and fact with one of the keys, any status | ordered by version key, then `valid_from` (missing first), then item id |
| `get_document_version_keys` | `doc_id → sorted distinct version keys` of its relations and facts | a document with none maps to an empty list; an unknown one is absent |
| `write_documents`, `delete_documents` | | [stores.md §3](stores.md#3-write-units) |
| `refresh_degrees` | | data model §5.3; needs the lease |
| `entities_in_chunks` | mentions of the chunks | sorted by chunk id, then `start`, then entity id |
| `hop` | edges and items | data model §5.4 |
| `get_entities`, `get_items`, `get_chunks`, `get_documents` | one record per known id | sorted by id; unknown ids left out (FR-024) |

Every read takes ids or keys. An empty sequence returns an empty result
and runs no query. A duplicated id is read once.

## 3. `VectorStore`

```python
class VectorStore(Protocol):
    capabilities: VectorCapabilities
    def ensure_collections(self, spec: VectorSpec) -> None: ...
    def upsert(self, collection: Collection, records: Sequence[VectorRecord]) -> None: ...
    def delete(self, collection: Collection, ids: Sequence[str]) -> None: ...
    def delete_documents(self, collection: Collection, doc_ids: Sequence[str]) -> None: ...
    def search(self, collection: Collection, vectors: Sequence[Sequence[float]], k: int,
               where: VectorFilter | None) -> list[list[Hit]]: ...
    def search_text(self, collection: Collection, text_norm: str, k: int,
                    where: VectorFilter | None) -> list[Hit]: ...
    def get_vectors(self, collection: Collection, ids: Sequence[str]) -> dict[str, list[float]]: ...
```

| Method | Rules |
|---|---|
| `ensure_collections` | records model id and dimensions per collection; a change raises `ConfigError` naming the collection and both values, saying to rebuild under a new index id (FR-025); needs no lease |
| `upsert` | replaces a record with the same id; every vector's length must equal the collection's dimensions, else `QueryError` before any statement |
| `delete`, `delete_documents` | unknown ids and documents are skipped |
| `search` | one list per query vector, in input order; each list holds at most `k` hits, by score descending then id; `score` is cosine similarity in [-1, 1] (FR-026); `k` from 1 to 1,000 |
| `search_text` | syllable match on `text_norm`, any query syllable (OR), no stemming, stop words or folding (FR-027); at most `k` hits by the backend's rank descending, then id; the score is the backend's and is never compared |
| `get_vectors` | stored values for the known ids |
| filters | `VectorFilter` fields are AND-ed; `None` is no filter, an empty tuple matches nothing; `exclude_run` drops records with that `run_id` |

Vector writes take no lease: in a split pairing the vector store writes
before the graph, and the graph store's lease governs the run
([stores.md §3.3](stores.md#33-paired-and-split-vectors)).

## 4. Other exports

```python
class StoreSchema: ...                  # data model §5.1; frozen; merged(other) -> StoreSchema
class WriterLease: ...                  # data model §4
class WriteStep(StrEnum): ...           # data model §5.2
class HopSpec: ...; class HopResult: ...; class HopEdge: ...; class HopItem: ...
class AnyScope(Enum): ANY = "any"
ANY_SCOPE: Final = AnyScope.ANY
RESERVED_LABELS: frozenset[str]         # data model §5.1
RESERVED_EDGE_TYPES: frozenset[str]
TYPE_NAME: re.Pattern[str]              # [A-Z][A-Za-z0-9]*, equal to packs/format.py
RELATION_NAME: re.Pattern[str]          # [A-Z][A-Z0-9]*(_[A-Z0-9]+)*, equal to packs/format.py
JsonValue = str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]
```

`tenetrag.protocols` exports these, the records of data model §2 to §4
and §7.5, both protocols and `WriterBusyError`. The records live in
`protocols/records.py`, the protocols and the rest in
`protocols/stores.py`.

`tenetrag.packs` adds one function:

```python
def store_schema(stack: PackStack) -> StoreSchema: ...
    # Every entity, event, fact and relation type of the stack, extract: false
    # included, since a later pack version may extract a type the store must
    # already hold. Raises ConfigError when StoreSchema refuses a name.
```

## Example: the engine's view

```python
from tenetrag.packs import load_pack, store_schema
from tenetrag.protocols import GraphStore, HopSpec, IdentityKey, ANY_SCOPE

def first_hop(graph: GraphStore, seeds: list[str]) -> HopResult:
    return graph.hop(seeds, HopSpec(statuses=("current",), neighbour_limit=10))

graph.ensure_schema(store_schema(load_pack("enterprise-docs")))
lease = graph.acquire_writer("host-a:4242:9f3c", ttl_s=600)
graph.find_by_identity([IdentityKey(type="Person", scope="ent_9a…",
                                    names=("employee_id",), values=("nv-0042",))])
graph.find_by_identity([IdentityKey(type="Work", scope=ANY_SCOPE,      # issuer unknown
                                    names=("code",), values=("qđ-07/2026",))])
graph.release_writer(lease)
```

## Behaviour pinned by tests

Unit tests (`tests/unit/protocols/`, `tests/unit/packs/test_store.py`):

| Test | Asserts |
|---|---|
| `test_protocols_stdlib_only` | importing `tenetrag.protocols` loads no third-party module (FR-001, SC-012) |
| `test_protocol_methods` | `GraphStore` has the methods of engine brief §6.1 less the community ones, plus `renew_writer` and `release_writer`; `VectorStore` those of §6.2 |
| `test_records_frozen` | setting a field of any record raises; records are slotted and keyword-only |
| `test_naive_datetime_refused` | a `RunRecord` or `WriterLease` with a naive time raises `ValueError` |
| `test_spans_checked` | a mention, chunk or quote span with `start > end` raises `ValueError` |
| `test_document_write_doc_ids` | a row whose `doc_id` differs from the document's raises, except a `text_in` row |
| `test_same_as_order` | `SameAsLink(entity_a="b", entity_b="a")` raises |
| `test_identity_key_shape` | empty `names`, unequal lengths or `scope` among the names raise |
| `test_document_link_key_one_side` | both or neither of `doc_id` and `entity_id` raise |
| `test_hop_spec_limits` | limits of 0 and 1,001 raise; defaults are 20 and 50 |
| `test_store_schema_patterns` | a lower-case type, a relation with a dash, and a name used by two kinds raise `ConfigError` naming the name |
| `test_store_schema_reserved` | `Chunk` as an entity type and `IN_DOCUMENT` as a relation raise; `Event` as an event type passes |
| `test_store_schema_merged` | the union of two schemas is sorted and has no repeat |
| `test_name_patterns_match_packs` | `TYPE_NAME` and `RELATION_NAME` equal the patterns of `packs/format.py` |
| `test_writer_busy_error` | is a `StorageError`; its text names the holder and the end time |
| `test_store_schema_shipped` | `core`, `enterprise-docs` and the `finance` draft each build a schema; `PART_OF` is a relation and `Event` an event type in `core` |

The behaviour of every method on every store is pinned by the contract
suite ([contract-suite.md](contract-suite.md)).
