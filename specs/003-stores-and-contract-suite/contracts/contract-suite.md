# Contract: the contract suite (`tests/contract/`, `tests/support/`)

Test code, not shipped. It may import anything the dev dependencies
hold: pytest, testcontainers, the drivers, `tenetrag` and the corpus
support of 002. The cases are in
[data-model.md §10](../data-model.md#10-contract-cases); the reasons in
[research.md R19 and R20](../research.md#r19-the-reference-store).

## 1. The `stores` fixture

```python
@dataclass
class ContractStores:
    backend: str                        # one of the six parameters below
    graph: GraphStore
    vectors: VectorStore
    graph_writes_vectors: bool
    index_id: str                       # "t" + 12 hex digits of the test node id's SHA-256
    def open_graph(self, *, index_id: str | None = None,
                   step_hook: StepHook | None = None) -> GraphStore: ...
        # Another store object on the same server: for the lease, isolation and
        # kill-point cases. index_id=None means this test's index.
    def open_vectors(self, *, index_id: str | None = None) -> VectorStore: ...
    def kill_running_unit(self) -> None: ...
        # From a second connection: pg_terminate_backend on Postgres,
        # TERMINATE TRANSACTIONS on Neo4j. Raises pytest.skip on the reference store.
```

`tests/contract/conftest.py` parametrizes `stores` over:

| Parameter | Graph | Vectors | Paired | Marks |
|---|---|---|---|---|
| `reference` | reference | reference, same database | yes | |
| `reference-split` | reference | reference, own database | no | |
| `postgres-pg16` | Postgres 16 | the same connection | yes | `docker`, `enable_socket` |
| `postgres-pg17` | Postgres 17 | the same connection | yes | `docker`, `enable_socket` |
| `neo4j` | Neo4j 2026.09 | the same connection | yes | `docker`, `enable_socket` |
| `neo4j-graph+postgres-vectors` | Neo4j | Postgres 17 | no | `docker`, `enable_socket` |

- The stores are built with `open_stores` from a generated profile, so
  the pairing rule of stores.md §5 is what the suite runs.
- Containers are session-scoped, from the digests in
  `tests/support/containers.py`, which `tests/integration/conftest.py`
  imports too. A Docker parameter is skipped with a reason when no daemon
  answers; the reference parameters never need one (SC-004).
- Each test gets a fresh index id, so tests share containers without
  sharing rows. Each fixture calls `ensure_schema` with the
  `enterprise-docs` schema and `ensure_collections` with 8 dimensions,
  then acquires the lease as `contract:<backend>`.
- A test that applies to one backend only (a locale refusal, a killed
  server transaction) asks for its backend by name and is skipped on the
  others, with the reason given.

## 2. Fixture data

`tests/support/contract/writes.py` turns the committed corpus of 002
into store records (FR-042):

```python
def corpus_writes(doc_ids: Sequence[str] | None = None, *, run_id: str = "run-1",
                  with_vectors: bool = True) -> list[DocumentWrite]: ...
    # doc_ids=None: all 41, in corpus order. Each write carries the status
    # changes that the version rule of 002 (tests.support.corpus.derive.statuses)
    # gives over the documents written so far. Vectors are on the write when
    # with_vectors is set; split callers take them with corpus_vectors instead.
def corpus_vectors(doc_ids: Sequence[str] | None = None, *,
                   run_id: str = "run-1") -> dict[Collection, list[VectorRecord]]: ...
def corpus_delete(doc_id: str, *, run_id: str = "run-2") -> DocumentDelete: ...
    # Status changes from graph.json `deletions` when every document is written,
    # else from the same rule over the documents left.
def expected_statuses(doc_ids: Sequence[str] | None = None) -> dict[str, tuple[str, date | None]]: ...
    # item id -> (status, closed_at); equals graph.json `versions` for all 41.
def write_all(stores: ContractStores, writes: Sequence[DocumentWrite]) -> None: ...
    # Paired: graph.write_documents. Split: the sequence of §4.
SCHEMA: StoreSchema                     # store_schema(load_pack("enterprise-docs"))
VECTOR_SPEC: VectorSpec                 # model "fake-embed", 8 dimensions, each collection
```

| Store field | Comes from |
|---|---|
| documents | `documents.jsonl`: title, issuer, dates, language; `content_hash` of `docs/D*.md`; `pipeline_hash` a constant |
| chunks | the document text split at blank lines, with character offsets; an item's chunk is the one holding its quote |
| entities | each `world` id once per index, with its type, name, scope path and identity values from `world.yaml` |
| aliases, mentions, attribute sources | each entity item's surface, span and attribute quotes |
| relations, facts, events, roles, evidence | the relation and statement items, with their quotes and dates |
| `text_in` | graph.json `text_in` |
| ids | the SHA-256 recipes of [engine brief §1](../../../docs/product/engine-brief.md#ids-and-hashes), with world ids standing for resolved identities |
| normalized text | `tenetrag.engine.text.norm` |
| vectors | `FakeEmbeddingModel(dimensions=8)` over chunk texts, entity labels and one question per chunk |

`tests/support/contract/generated.py` builds the data the corpus lacks,
all with fictional names:

| Function | Data | Case |
|---|---|---|
| `hub_writes(n=5000)` | one entity with `n` relations to `n` neighbours over 50 documents, mixed types, statuses and dates | `hub-invariants` (SC-007) |
| `tone_mark_writes()` | entities and chunks whose names differ only in tone-mark placement (`Hoà`/`Hòa`, `Thuỷ`/`Thủy`) or only in diacritics (`Lãi`/`Lại`/`Lai`) | `tone-mark-matching` (SC-009) |
| `recall_fixture()` | 3,000 chunk vectors of 64 dimensions from `FakeEmbeddingModel(dimensions=64)`, 30 queries, and the exact top 10 of each computed in Python | `recall-floor` (SC-010) |
| `two_source_writes()` | one relation stated in two documents | `one-of-two-sources` |
| `pack_status_writes()` | a `Decision` whose pack attribute `status` differs from its engine `status` | `pack-attributes-apart` |

## 3. What the suite compares

- Sets and counts: rows per kind, ids returned, candidate sets of
  `search_names`, hop membership per start entity, `text_in` pairs.
- Exact values: records read back equal records written (attributes,
  quotes, dates, statuses, run ids), vectors within 1e-6.
- Order only where the protocol fixes it on a unique key: the hop and
  read orders of protocols.md §2.
- Never (FR-045): scores of `search_text`; `search_names` scores beyond
  the threshold; vector scores beyond 1e-3 on the three reference
  vectors; ANN results beyond the recall floor; order among equal scores.

## 4. The split pairing

`write_all` on a split pairing, which 004's engine will repeat:

1. look up the vector ids the previous version had. The protocols have
   no read for that, so the helper keeps a map from each document to the
   ids it wrote; where 004 gets them is a note for later (research);
2. `vectors.upsert` the new vectors of every collection;
3. `graph.write_documents` with `vectors` empty;
4. `vectors.delete` the previous ids the new version lacks.

`write_split_crashing(stores, write)` runs steps 1 and 2, then raises
before step 3. The `split-crash-recovery` test checks that the graph
still holds the previous version, that the extra vectors are present,
and that after `write_all` again the vector ids equal the graph's chunk
ids.

## 5. The case map

```python
# tests/contract/cases.py
@dataclass(frozen=True)
class ContractCase:
    id: str
    source: Literal["adr-0008", "brief-10", "spec"]
    text: str
    tests: tuple[str, ...]      # node ids without the parameter

CASES: tuple[ContractCase, ...]   # the 27 cases of data model §10
```

`tests/contract/test_case_map.py` (a unit test, no Docker) fails when:
- a case of ADR 0008 §5 or engine brief §10 has no entry, checked
  against a list of the two sources' cases written in the test;
- an entry has no test, or names a test pytest cannot collect;
- a test function in `tests/contract/` appears in no entry, except in
  `test_open_stores.py`, which tests the builder rather than a case.

## 6. Planted faults

```text
uv run python -m tests.support.contract.faults      # make faults
```

`tests/support/contract/faults.py` holds one fault per case, each a
context manager that patches the reference store. For each, it runs
that case's tests on the `reference` parameter with the fault in place
and records whether any failed. It prints one line per case and exits 1
when a fault survives (SC-003). Faults, for example:

| Case | Fault |
|---|---|
| `counts-after-write-and-replay` | a replay inserts the mentions again |
| `end-state-after-delete` | delete leaves identity blocks |
| `supersession-flags` | status changes are skipped |
| `provenance-reachability` | `get_items` drops the evidence's chunk id |
| `hop-caps` | the cap applies across all start entities instead of per entity |
| `hub-invariants` | `refresh_degrees` counts rows, not distinct neighbours |
| `tone-mark-matching` | `match_names` strips diacritics before comparing |
| `killed-run-atomicity` | the unit writes in place instead of on a copy |
| `exclude-run` | `exclude_run` is ignored for aliases |
| `identity-scope` | `ANY_SCOPE` is treated as unscoped |
| `writer-lease` | a write unit skips the fence check |
| `isolation` | `search_names` ignores the index id |

Every case has one. The script runs outside `make test` for time; its
output is recorded in quickstart.md.

## 7. Running

| Command | Runs |
|---|---|
| `make test` | the reference parameters and `test_case_map.py`, network blocked |
| `make integration` | the four Docker parameters, with M0's integration tests |
| `uv run pytest tests/contract -m docker -k postgres-pg17` | one backend |
| `make faults` | §6 |

## Behaviour pinned by tests

| File | Cases (data model §10) |
|---|---|
| `test_writes.py` | `counts-after-write-and-replay`, `pack-attributes-apart`, `one-of-two-sources` |
| `test_deletes.py` | `end-state-after-delete`, `orphan-cleanup`, `sources-deleted-with-document`, `text-in-added-and-removed` |
| `test_statuses.py` | `supersession-flags`, `status-changes-in-unit` |
| `test_provenance.py` | `provenance-reachability` |
| `test_lease.py` | `writer-lease` |
| `test_runs_and_caches.py` | `runs-and-states`, `cache-round-trip` |
| `test_identity_and_names.py` | `identity-scope`, `exclude-run`, `tone-mark-matching` (names) |
| `test_hop.py` | `type-time-status-filters`, `hop-membership`, `hop-caps`, `hub-invariants`, `as-of-prefilter` |
| `test_vectors.py` | `recall-floor`, `collections`, `exclude-run` (vectors) |
| `test_text_search.py` | `tone-mark-matching` (full text) |
| `test_isolation.py` | `isolation` |
| `test_kill_points.py` | `killed-run-atomicity`, `split-crash-recovery` |
| `test_schema_and_layout.py` | `schema-and-layout` |
| `test_open_stores.py` | the pairing rule and credential failures of stores.md §5 |
