# Quickstart: validate the store protocols, the reference store, the contract suite and the Postgres and Neo4j stores (M1, part 2)

A run guide that proves each user story works. Shapes are in
[data-model.md](data-model.md), and signatures in [contracts/](contracts/).

## Prerequisites

- A checkout of `main` with M0 and feature 002 in place, and uv 0.12 or
  later.
- `uv sync --locked --all-extras`. This feature adds no package, so the
  lock file does not change.
- §1, §2 and §6 run offline with no Docker. §3, §4 and §5 need a Docker
  daemon and the images pinned in `tests/support/containers.py` (the
  same digests as `deploy/compose.yaml`).
- Scratch files go to any scratch directory; `$SCRATCH` below.

## 1. Protocols and the reference store (Story 1, SC-004, SC-012)

```python
from tenetrag.packs import load_pack, store_schema
from tenetrag.protocols import GraphStore, VectorStore, HopSpec
from tests.support.reference import ReferenceDatabase, ReferenceGraphStore, ReferenceVectorStore
from tests.support.contract.writes import corpus_writes, VECTOR_SPEC

db = ReferenceDatabase()
vectors = ReferenceVectorStore(db, "demo")
graph = ReferenceGraphStore(db, "demo", vectors=vectors)
isinstance(graph, GraphStore), isinstance(vectors, VectorStore)   # (True, True)

graph.ensure_schema(store_schema(load_pack("enterprise-docs")))
vectors.ensure_collections(VECTOR_SPEC)
lease = graph.acquire_writer("quickstart", ttl_s=60)
graph.write_documents(corpus_writes(["D1", "D2", "D5"]))
sorted(graph.document_states())                                  # ['D1', 'D2', 'D5']
```

**Expected:**
- both checks are `True`, and the three documents are held;
- `uv run pytest tests/contract -m "not docker" -q` passes on the
  `reference` and `reference-split` parameters, with no Docker and no
  network (SC-004);
- in a venv with no extras, `import tenetrag.protocols` loads no
  third-party module (SC-012).

**Negative check:** call `graph.write_documents(corpus_writes(["D1"]))`
on a second `ReferenceGraphStore(db, "demo")` that has not acquired the
lease: it raises `StorageError` saying to call `acquire_writer`. Then
`acquire_writer("other", ttl_s=60)` on it raises `WriterBusyError`
naming `quickstart` and the end time.

## 2. One suite, every case mapped (Story 2, SC-001, SC-003)

```sh
uv run pytest tests/contract/test_case_map.py -q
make faults
```

**Expected:** the case map test passes: every case of ADR 0008 §5 and
engine brief §10 has a test, and every test exists. `make faults`
prints one line per case of data model §10, each `caught`, and exits 0.

**Negative check:** comment out the `writer-lease` entry in
`tests/contract/cases.py`, and the case map test fails naming
`writer-lease`. Restore it. Disable one fault's patch (make it a no-op),
and `make faults` reports that case as `survived` and exits 1. Restore
it.

## 3. The Postgres store (Story 3, SC-002, SC-009, SC-010)

```sh
uv run pytest tests/contract -m docker -k "postgres-pg16 or postgres-pg17" -q
```

Then, against the local stack (`make dev-up`) with a profile whose
`index` names the Postgres connection:

```python
from tenetrag.config import load_profile
from tenetrag.storage import open_stores

with open_stores(load_profile("$SCRATCH/pg.yaml"), credentials={...}) as s:
    s.graph_writes_vectors                                   # True
    s.vectors.capabilities.max_dimensions                    # 2000
```

**Expected:** every contract test passes on both Postgres versions,
including tone-mark matching (SC-009) and recall at 10 of at least 0.9
(SC-010). `psql` shows the schema `tenetrag_<index_id>` with the tables
of data model §6 and the `vector` and `pg_trgm` extensions.

**Negative check:** create a database with `LOCALE 'C' TEMPLATE
template0` and point the profile at it: the first store call raises
`UnsupportedServerError` naming the locale and asking for a UTF-8 one.

## 4. The Neo4j store (Story 4, SC-002, SC-007, SC-008, SC-011)

```sh
uv run pytest tests/contract -m docker -k "neo4j" -q
```

**Expected:** every contract test passes on `neo4j` and on
`neo4j-graph+postgres-vectors`: the hub expands within its caps
(SC-007), two composed hops reach the same sets as on the reference
store (SC-008), and no read sees another index's rows (SC-011).
`SHOW CONSTRAINTS` lists `index_id` in every uniqueness constraint, and
`SHOW INDEXES` shows the vector indexes with quantization off.

**Negative check:** write the corpus under index `a`, then read under
index `b` on the same server: every read method returns nothing.

## 5. Killed runs (Story 5, SC-005, SC-006)

```sh
uv run pytest tests/contract/test_kill_points.py tests/contract/test_writes.py -q
uv run pytest tests/contract/test_kill_points.py -m docker -q
```

**Expected:** for every step of FR-006 on every store, a hook that
raises leaves each document whole or absent, and a replay ends equal to
a clean run (SC-006). The Postgres kill (`pg_terminate_backend`) and
the Neo4j kill (`TERMINATE TRANSACTIONS`) leave the previous version.
The split pairing's crash leaves extra vectors that the replay removes.
Writing D1, D2 and D5 twice gives the same counts, and deleting all
three leaves zero rows (SC-005).

**Negative check:** with the `killed-run-atomicity` fault of `make
faults` in place, the kill point tests fail on the reference store.

## 6. The profile names the index (Story 6)

```python
from tenetrag.config import profile_from_dict

profile_from_dict({
    "connections": {"pg": {"kind": "postgres", "host": "localhost", "database": "t"}},
    "models": {"embedding": {"provider": "fake", "model": "fake-embed", "dimensions": 3072}},
    "index": {"id": "alpha", "graph": "pg", "vectors": "pgvector"},
})
```

**Expected:** `ConfigError` with two lines: no connection `pgvector`,
and 3072 dimensions exceed the 2000 Postgres can index. With
`vectors` removed and `dimensions: 768`, the profile loads and
`profile.index.vector_connection == "pg"`.

**Negative check:** `"id": "Alpha"` fails with the index id pattern in
the message.

## 7. Gates

```sh
make check
make integration
```

**Expected:** every gate passes. `lint-imports` shows the layers
`engine | llm | storage`, the engine contract kept, and `tenetrag.engine`
importing only `protocols`, `config`, `packs` and the standard library.
`make integration` runs the four Docker parameters and M0's integration
tests.

**Negative check:** add `from tenetrag.storage import open_stores` to
`src/tenetrag/engine/text/__init__.py`, and `lint-imports` fails, naming the two
modules. Revert it.

## Done when

- `make check` and `make integration` pass locally on Python 3.11 and
  3.14 (CI is off; a second local environment stands in for its
  matrix).
- `make faults` exits 0, and SC-007 and SC-010 are measured and
  recorded below.
- ARCHITECTURE.md, engine brief §1, §6 and §7, domain-packs.md,
  neo4j-platform.md, the local-stack guide, tech-debt.md and the
  `AGENTS.md` status reflect what landed (FR-049, research R22).

## Results

Not run yet. Filled in by the last task of tasks.md.

| Check | Result |
|---|---|
| Protocols and reference store (§1, SC-004, SC-012) | |
| Case map and faults (§2, SC-001, SC-003) | |
| Postgres (§3, SC-002, SC-009, SC-010) | |
| Neo4j (§4, SC-002, SC-007, SC-008, SC-011) | |
| Killed runs (§5, SC-005, SC-006) | |
| Profile (§6) | |
| Gates (§7) | |
| Docs (FR-049) | |
