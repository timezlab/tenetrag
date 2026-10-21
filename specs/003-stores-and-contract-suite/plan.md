# Implementation Plan: Store protocols, the reference store, the contract suite and the Postgres and Neo4j stores (M1, part 2)

**Branch**: none (solo work on `main`) | **Date**: 2026-10-21 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/003-stores-and-contract-suite/spec.md`

## Summary

Feature 003 fixes the storage contract the engine codes against, and
builds the first three stores that meet it:
1. `GraphStore` and `VectorStore` in `tenetrag.protocols`, with their
   records, the store schema, the writer lease, the hop records and
   `WriterBusyError`, standard library only;
2. `tenetrag.engine.text.norm()`, the one engine module of this feature,
   so the fixtures hold the normalized text that feature 004 will write;
3. an in-memory reference store in `tests/support/reference/`, which
   defines the contract by example and runs in `make test`;
4. one contract suite in `tests/contract/`, parametrized over the
   reference store, Postgres 16 and 17, Neo4j, and a split pairing, fed
   from the 002 corpus, with a case map and planted faults;
5. the Postgres graph and vector stores (pg_trgm, `simple` full text,
   pgvector HNSW) and the Neo4j graph and vector stores (typed edges,
   vector and full-text indexes through `SEARCH`);
6. an `index` section in the profile and `open_stores()`, which opens
   the pair the profile names.

Technical approach, from [research.md](research.md):
- **No new dependency:** psycopg, psycopg-pool and neo4j from M0's
  extras, testcontainers for Docker, and the standard library.
- **Layers:** `engine` joins `llm` and `storage` in the top layer, with a
  forbidden contract that keeps it off the drivers and `auth` (R1).
- **Writer lease:** a fenced lease record with an end time on both
  backends, checked inside every write unit
  ([ADR 0024](../../docs/decisions/0024-hold-the-writer-lease-in-a-fenced-lease-record.md),
  R4). Advisory locks were rejected after running them.
- **Same answer on every backend:** cosine scores in [-1, 1] (R11); the
  same full-text split and OR query on Postgres as Neo4j's analyzer
  gives (R6, R9); the same trigram similarity for name search, through
  pg_trgm on Postgres and trigram tokens plus a Python filter on Neo4j
  (R7, R10); hop order ending on a unique id (R12).
- **Recall:** Neo4j vector indexes without quantization and with an
  expansion factor of 10; Postgres `ef_search` 100 with iterative scans.
  Both reach recall at 10 above 0.99 on the fixture shape (R11).
- **Kill points:** a step hook between the five write steps, plus a
  a transaction killed from a second connection, on every backend (R14).
- **Platform facts:** 25 checks run on the pinned images on 2026-10-21,
  listed in [research](research.md#platform-checks-run).

## Technical Context

**Language/Version**: Python 3.11–3.14 (CI matrix 3.11 and 3.14), as in M0

**Primary Dependencies**:
- `postgres` extra: psycopg 3.3.6 with its binary build, psycopg-pool
  3.3.3 (locked by M0, ADR 0017);
- `neo4j` extra: neo4j 6.3.1 (locked by M0);
- dev: testcontainers 4.15.0, docker 7.2.0, pytest 9.1.1 (locked by M0);
- standard library: `dataclasses`, `typing`, `enum`, `unicodedata`,
  `re`, `json`, `hashlib`, `threading`, `datetime`;
- no new package (research, dependency gate).

**Storage**:
- Postgres 16 or later with pgvector 0.8.7 and pg_trgm 1.6, one schema
  per index, in a UTF-8 locale (R5);
- Neo4j 2026.09 Community, every node keyed by `index_id`, typed labels
  and edges, vector and full-text indexes (R8, R9, R11);
- the reference store keeps everything in memory.

**Testing**:
- pytest. The reference parameters run in `make test` with the network
  blocked; the Docker parameters carry the `docker` mark and run in
  `make integration`;
- one contract suite for every store, fed from the 002 corpus and
  generated hub, tone-mark and recall fixtures;
- a case map with a unit check (SC-001), and a planted-fault script for
  the reference store (SC-003);
- unit tests for `norm()`, the records, the store schema, the profile
  section, the trigram function and the error texts.

**Target Platform**: a Linux or macOS host with Docker for the integration suite; the reference store anywhere the base install runs

**Project Type**: library (protocols, one engine module and two storage backends of the Python SDK), plus test support

**Performance Goals**:
- the reference contract suite under 20 s inside `make test` (SC-004);
- each Docker backend's suite under five minutes, container start
  included (SC-004);
- a 5,000-relation hub expands in under 1 s on each Docker backend, at
  most 20 neighbours and 50 items (SC-007);
- recall at 10 of at least 0.9 against exact search on the fixture
  vectors (SC-010).

**Constraints**:
- `protocols` and `engine` import only the standard library (and
  `protocols` for `engine`), enforced by import-linter (FR-048).
- Every value is a query parameter. Identifiers come only from the
  store schema after the name check, through `psycopg.sql.Identifier` on
  Postgres and the dynamic-label forms on Neo4j (FR-034).
- No APOC, GDS or other plugin on Neo4j; nothing beyond Community
  (FR-033).
- Error texts carry ids, types, names of collections and counts, never
  a quote, a text, an alias, a value or a credential (FR-005).
- No adopter data: fixtures are the synthetic corpus and generated
  fictional sets.

**Scale/Scope**:
- About 20 new source modules, about 15 test modules plus the contract
  suite, 6 user stories, 49 functional requirements.
- Estimate: about 13 working days (spec Assumptions): four for the
  protocols, reference store and suite, four for Postgres, five for
  Neo4j.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | How 003 meets it | Pre | Post |
|---|---|---|---|
| I. No adopter data in git | Fixtures come from the synthetic corpus of 002 and from generated sets of fictional names. Error texts never carry document content, so logs of a real index carry none either (R21). `git status` is checked before each commit | ✅ | ✅ |
| II. Fail closed on identity | `open_stores` resolves each connection's credential through M0's `open_connection`: a credential from code, or the profile's named source, and `AuthError` when it is missing. No other identity is tried. The profile names connections, never secrets | ✅ | ✅ |
| III. Engine depends only on protocols | The protocols are standard library only. The `engine/text/` package imports only the standard library. A forbidden contract keeps `engine` off `auth`, the drivers and pyspark, and the layers contract keeps it off `llm` and `storage` (R1). The reference store lives in test support, not in the engine | ✅ | ✅ |
| IV. Provenance and fidelity | Every mention, relation, event evidence, fact and attribute source row keeps its doc id, chunk id and quote span, and the suite checks that each item reaches its chunks and documents. Stores keep text as written: full text and name search fold nothing, so `lãi`, `lại` and `lai` stay apart (R6, R9, R10) | ✅ | ✅ |
| V. Time and versions | Stores keep every version's row with its status and close date, apply the status changes the engine sends inside the document's unit, and fail the unit on an unknown item. The suite feeds statuses from `graph.json` and checks them after writes and deletes, D2's deletion included | ✅ | ✅ |
| VI. Entity identity | The stores serve identity lookups by type, scope and declared values (`find_by_identity`, `IdentityValue` nodes on Neo4j), and never merge by name. Resolution and its zero-wrong-merge gate are feature 004 | ✅ | ✅ |
| VII. Reproducible indexes, comparable backends | One contract suite runs first on the reference store, then on every backend, with no backend skip (SC-002). It compares sets and invariants, never scores (FR-045). Each document is one transaction; one writer per index holds a fenced lease (ADR 0024). Replays write the same rows, since ids come from the engine's hashes | ✅ | ✅ |
| VIII. Measured, opt-in quality | No quality claim. The recall floor is a contract check on fake vectors; real-model quality waits for 005. Simplest design: no migrations, one layout version, dynamic types instead of per-type queries once they measured fast enough (R8) | ✅ | ✅ |
| IX. Dated facts, vetted dependencies | No new dependency. Every Neo4j and Postgres fact the design relies on was run on the pinned images and dated (research, 25 checks). Neo4j documentation is paraphrased and linked, not copied | ✅ | ✅ |
| Workflow: tests ship with behaviour | The contract suite ships with the reference store, and each backend lands only with the suite green on it. A planted fault proves each must-match case can fail (SC-003). The Neo4j error-text fix ships with a regression test (R21) | ✅ | ✅ |
| Workflow: decisions are ADRs | ADR 0024 records the lease record, which changes ADR 0008 §7. The other choices are implementation choices inside decided ADRs (0008, 0014), recorded in research.md | ✅ | ✅ |
| Workflow: docs with code | The engine brief §1, §6 and §7, domain-packs.md, neo4j-platform.md, ARCHITECTURE.md, the local-stack guide, tech-debt.md and the AGENTS.md status change with the code (FR-049, research R22) | ✅ | ✅ |

**Gate result:** pass, before and after the design. No principle needs
an exception, and Complexity Tracking is empty. The design adds one ADR
and four small spec edits (research R22), which narrow wording and keep
each requirement's intent.

## Project Structure

### Documentation (this feature)

```text
specs/003-stores-and-contract-suite/
├── spec.md
├── plan.md              # this file
├── research.md          # Phase 0, with the platform checks run
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/           # Phase 1: protocols, stores, config, text, contract-suite
├── checklists/requirements.md
└── tasks.md             # Phase 2 (/speckit-tasks)
docs/decisions/0024-hold-the-writer-lease-in-a-fenced-lease-record.md
```

### Source Code (repository root)

```text
pyproject.toml                 # layers: "engine | llm | storage"; engine forbidden contract
Makefile                       # + faults target: python -m tests.support.contract.faults
src/tenetrag/
├── protocols/
│   ├── errors.py              # + WriterBusyError(StorageError)
│   ├── records.py             # write rows, read records, keys, runs, verdicts (data-model §2–§4)
│   └── stores.py              # GraphStore, VectorStore, StoreSchema, WriterLease, HopSpec, WriteStep
├── engine/
│   ├── __init__.py            # docstring only: the engine arrives in 004
│   └── text/
│       ├── __init__.py        # norm() and LANGUAGE_RULES (ADR 0025)
│       └── vi.py              # the tone-mark table, the vi rule
├── packs/
│   ├── __init__.py            # + store_schema
│   └── store.py               # store_schema(stack) -> StoreSchema
├── config/
│   ├── __init__.py            # + IndexSettings, VECTOR_MAX_DIMENSIONS
│   └── profile.py             # + index section and its checks
└── storage/
    ├── __init__.py            # + open_stores, Stores, the store classes
    ├── _names.py              # identifier check against the store schema
    ├── _trigram.py            # pg_trgm-equal trigrams and similarity
    ├── stores.py              # open_stores, Stores, pairing
    ├── postgres_store/
    │   ├── __init__.py
    │   ├── ddl.py             # schema, tables, indexes, extensions, locale, layout version
    │   ├── lease.py           # writer_lease row
    │   ├── writes.py          # the five steps, runs, caches, degrees
    │   ├── reads.py           # identity, names, links, versions, hop, batched reads
    │   ├── graph.py           # PostgresGraphStore
    │   └── vectors.py         # PostgresVectorStore and the paired write code
    └── neo4j_store/
        ├── __init__.py
        ├── ddl.py             # constraints, indexes, layout version
        ├── lease.py           # WriterLease node
        ├── writes.py
        ├── reads.py
        ├── graph.py           # Neo4jGraphStore
        └── vectors.py         # Neo4jVectorStore and the paired write code
tests/
├── unit/
│   ├── protocols/             # records, StoreSchema, WriterBusyError text
│   ├── engine/text/           # norm()'s shared steps; the vi rule
│   ├── packs/test_store.py    # store_schema of the shipped packs
│   ├── config/                # index section, dimension maxima
│   └── storage/               # _trigram, _names, Neo4j error-text regression, extras
├── contract/
│   ├── conftest.py            # the stores fixture over six parameters
│   ├── cases.py               # the case map (FR-044)
│   ├── test_case_map.py       # every case has a test, every test exists
│   ├── test_writes.py  test_deletes.py  test_statuses.py  test_provenance.py
│   ├── test_lease.py  test_runs_and_caches.py  test_identity_and_names.py
│   ├── test_hop.py  test_vectors.py  test_text_search.py
│   ├── test_isolation.py  test_kill_points.py  test_schema_and_layout.py
│   └── test_open_stores.py
├── integration/conftest.py    # image pins move to tests/support/containers.py
└── support/
    ├── containers.py          # image pins, Docker check, session containers
    ├── reference/             # ReferenceDatabase, ReferenceGraphStore, ReferenceVectorStore
    └── contract/
        ├── writes.py          # corpus → DocumentWrite (ids, norm, fake vectors, graph.json)
        ├── generated.py       # hub, tone-mark and recall fixtures
        └── faults.py          # planted faults: python -m tests.support.contract.faults
```

**Structure decision:** each backend is one subpackage split by job:
DDL, the lease, writes, reads, and the two store classes that put them
together. The graph store of a paired setup holds the vector store's
write code, so `vectors.py` owns every vector statement either way. The
reference store and the suite are test support, as engine brief §10
plans; the suite is a separate tree so that one test runs on every
store.

## Complexity Tracking

No violations.
