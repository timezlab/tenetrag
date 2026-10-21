---

description: "Task list for the store protocols, the reference store, the contract suite and the Postgres and Neo4j stores (M1, part 2)"
---

# Tasks: Store protocols, the reference store, the contract suite and the Postgres and Neo4j stores (M1, part 2)

**Input**: Design documents from `specs/003-stores-and-contract-suite/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: Required. The constitution (Development Workflow, Tests)
overrides the template's "tests are optional" note. In every story phase,
write the tests first and watch them fail before implementing.

**Organization**: Tasks are grouped by user story. The stories are layered.
US1's protocols, fixture helpers and reference store feed everything
else. US2 completes the suite on the reference store. US3 (Postgres) and
US4 (Neo4j) must pass that suite unchanged. US5 adds server-side kills
and needs both backends. US6 builds the stores from a profile, so it
needs both backends too, although its config half can start any time
after Phase 2. Across stories, the shared files that grow are
`tests/contract/cases.py`, `tests/support/contract/backends.py`,
`tests/contract/conftest.py`, `tests/contract/test_schema_and_layout.py`
and `tests/unit/storage/test_store_classes.py`. Edits to them are small
and sequential.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: the user story the task belongs to (US1–US6)
- Paths are from the repository root. Layout: `src/tenetrag/`, `tests/`
- Each task is one reviewable unit. A test task leaves the suite failing
  only on its new tests; the implementation task after it turns them green.
- Contract tests compare what [contract-suite.md §3](contracts/contract-suite.md#3-what-the-suite-compares)
  allows, and nothing else (FR-045). Every test function in
  `tests/contract/` is named by an entry of `tests/contract/cases.py`
  (T042). The one exception is `test_open_stores.py`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: the import rules for `engine`, the empty packages, and
the image pins in a place both Docker suites share

- [X] T001 Place `engine` in the import rules and create the empty packages
  (research R1, contracts/text.md):
  - in `[tool.importlinter]` of `pyproject.toml`:
    - the top layer becomes `"engine | llm | storage"`;
    - add a forbidden contract named "engine imports no auth, model or
      store SDK". Its source is `tenetrag.engine`, and it forbids
      `tenetrag.auth`, `openai`, `databricks`, `neo4j`, `psycopg`,
      `psycopg_pool` and `pyspark`. If `lint-imports` refuses
      `pyspark` because it is not installed, drop it and record the
      departure in the Result;
    - the comment "The engine contract arrives with tenetrag.engine in
      M1" now says the engine contract is in place;
  - `src/tenetrag/engine/__init__.py` holds only a module docstring. It
    says the engine arrives in 004 and links
    `specs/003-stores-and-contract-suite/contracts/text.md`;
  - empty `__init__.py` files in `tests/unit/protocols/`,
    `tests/unit/engine/`, `tests/contract/`, `tests/support/reference/`
    and `tests/support/contract/`.

  Probes, each reverted after `uv run lint-imports` fails as expected:
  - `import tenetrag.storage` in `engine/__init__.py` breaks the layers
    contract;
  - `import tenetrag.auth` breaks the new forbidden contract;
  - `import neo4j` breaks it too.

  Then run `make check`.
- [X] T002 [P] Move the image pins and the Docker check out of
  `tests/integration/conftest.py` into a new `tests/support/containers.py`
  (research R20):
  - move `NEO4J_IMAGE` and `PGVECTOR_IMAGES` unchanged, with their digest
    comment;
  - add `require_docker() -> None`, the body of `_require_docker`. It
    pings the daemon and calls `pytest.skip("Docker not available")`
    when no daemon answers;
  - `tests/integration/conftest.py` imports all three and keeps its
    fixtures and marks;
  - `tests/unit/test_local_stack.py` imports the pins from
    `tests.support.containers`, not from `tests.integration.conftest`.

  This is a pure move, and the existing tests are the safety net:
  `make check` passes, `tests/unit/test_local_stack.py` still checks that
  `deploy/compose.yaml` uses the same digests, and
  `uv run pytest -m docker tests/integration -q` collects the same tests
  as before.

  Result (2026-10-21): `make check` passes with 1168 unit tests, and
  `make integration` passes its 19 Docker tests (neo4j 2026.09, pgvector
  pg16 and pg17) in 120 s.
  - T001: creating `src/tenetrag/engine/__init__.py` before placing it
    failed the exhaustive layers contract ("The following modules are not
    listed as layers: tenetrag.engine"). With the pyproject change,
    `lint-imports` keeps 4 contracts. `pyspark` stays in the forbidden
    list: `lint-imports` accepts it uninstalled and still catches the
    import, so no departure is needed. Probes in `engine/__init__.py`,
    each reverted:
    - `import tenetrag.storage` broke both the layers contract and the
      engine contract (through storage, auth and `databricks`);
    - `import tenetrag.auth` broke only the engine contract, which is
      why it lists `tenetrag.auth`: the layers allow the import;
    - `import neo4j` and `import pyspark` each broke the engine contract.
  - The import-rules paragraph of `ARCHITECTURE.md` names the new layer
    and the third contract (the boundary rule of the Notes). T078 does
    the module table.
  - T002: the integration suite collects the same 19 tests before and
    after the move, compared node id for node id. The "Upgrading an image"
    note in `docs/guides/local-stack.md` now names
    `tests/support/containers.py`.

**Checkpoint**: the engine has a layer and a contract, and the pins are
shared

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the pieces every story uses: `norm()` for the fixture
text, `WriterBusyError` for the lease, and the pg_trgm-equal trigrams
for name search on the reference store and on Neo4j

**⚠️ CRITICAL**: no story work begins until this phase is complete

- [X] T003 [P] Write `tests/unit/engine/test_text.py`, the seven tests of
  [contracts/text.md](contracts/text.md#behaviour-pinned-by-tests):
  - `test_tone_marks_moved`: the five named examples, plus all fifteen
    pairs of [data-model §11](data-model.md#11-tone-mark-table-norm-the-vi-rule),
    in lower and upper case;
  - `test_tone_marks_kept`;
  - `test_diacritics_kept_apart` (`lãi`, `lại`, `lai`, and `đ`);
  - `test_nfd_equals_nfc`;
  - `test_whitespace_collapsed` (tabs, newlines, NBSP, runs of spaces,
    trimmed ends);
  - `test_idempotent`, over every example and every entity name in
    `tests/fixtures/corpus/facts/world.yaml`;
  - `test_engine_imports`. In a subprocess, it imports `tenetrag.engine`
    and `tenetrag.engine.text`, then checks that `sys.modules` holds no
    `tenetrag.storage`, `tenetrag.llm`, `tenetrag.auth` or driver
    module.

  Red: `ModuleNotFoundError: No module named 'tenetrag.engine.text'`.
- [X] T004 Implement `src/tenetrag/engine/text.py`, standard library only
  (research R18):
  - `norm(text: str) -> str`: NFC, then the tone-mark table, then
    `casefold()`, then NFC again, then whitespace collapse;
  - the table is a module constant of fifteen pairs. It applies only when
    no letter follows the vowel pair, and never to a `uy` after `q`.

  T003 passes. Depends on T001 and T003.
- [X] T005 [P] Write `tests/unit/protocols/test_errors.py` with
  `test_writer_busy_error` (contracts/protocols.md §1):
  - it is a `StorageError`;
  - its keyword-only `owner` and `expires_at` (an aware `datetime`) are
    kept as attributes;
  - the message names the owner and the end time in UTC ISO form, and
    says to wait for the end time or release the other writer;
  - a naive `expires_at` raises `ValueError`.

  Red: `ImportError` for `WriterBusyError` from `tenetrag.protocols`.
- [X] T006 Add `WriterBusyError(StorageError)` to
  `src/tenetrag/protocols/errors.py` and export it from
  `tenetrag.protocols`. T005 passes, and `tests/unit/test_errors.py`
  passes unchanged. Depends on T005.
- [X] T007 [P] Write `tests/unit/storage/test_trigram.py`
  ([contracts/stores.md §4.3](contracts/stores.md#43-shared-modules)):
  - `test_trigrams_match_pg_trgm`: `similarity` equals pg_trgm's value
    to four places for each of the eight pairs of research R10
    (`ngân hàng phương đông`~`ngân hàng phương nam` 0.6957,
    `nguyễn văn hòa`~`nguyễn văn hoà` 0.6667, `lãi`~`lai` 0.1429,
    `lãi`~`lại` 0.1429, `a_b`~`a b` 1.0, `công ty số 12`~`công ty số 21`
    0.6471, `đ/c hà`~`đc hà` 0.4444, `phòng-ban`~`phòng ban` 1.0);
  - `test_trigram_tokens`: `lãi` gives `__l _lã lãi ãi_`;
  - two empty strings have similarity 0.0, and `trigrams` of a text with
    no word is empty.

  Red: `ModuleNotFoundError` for `tenetrag.storage._trigram`.
- [X] T008 Implement `src/tenetrag/storage/_trigram.py`, standard library
  only:
  - `trigrams(text)`: words are runs of `[^\W_]`, and each is padded as
    `"  " + word + " "`;
  - `similarity(a, b)`: the Jaccard index of the two sets;
  - `trigram_tokens(text)`: the tokens, sorted, joined by spaces, with
    the inner spaces of each token written as `_`.

  T007 passes. `uv run lint-imports` still passes, since the module
  imports nothing from `tenetrag`. Depends on T007.

  Result (2026-10-21): `make check` passes with 1248 unit tests (80 new:
  64 in `test_text.py`, 11 in `test_trigram.py`, 3 in
  `protocols/test_errors.py`, and 2 new cases in M0's `test_errors.py`).
  `lint-imports` keeps 4 contracts.
  - Red: the three new files failed to collect, each on its missing
    module or name (`No module named 'tenetrag.engine.text'`,
    `cannot import name 'WriterBusyError' from 'tenetrag.protocols'`,
    `No module named 'tenetrag.storage._trigram'`).
  - T003 departures: ten tests instead of seven. The fifteen pairs have
    their own `test_tone_mark_pairs_moved` (lower, upper and mixed case,
    alone and after a consonant). Two tests were added after green,
    because a planted fault survived without them:
    - `test_casefolded` (`Straße` and `STRASSE`): `lower()` in place of
      `casefold()` survived;
    - `test_result_is_nfc` (`ǰ`, which casefolding decomposes): dropping
      the second NFC survived.
  - T004 departure: `norm` casefolds before the table, so the table holds
    lower case only. The output is the contract's, because casefolding
    keeps each mark on its letter, and data-model §11 maps upper case the
    same way before casefolding. The docstring says so.
  - T005: two more tests, one for the naive `expires_at` and one for the
    keyword-only arguments. The first green failed on the message text
    ("wait" in lower case), and the fix was in the message, not the test.
  - T006 departure: M0's `tests/unit/test_errors.py` does not pass
    unchanged. Its `test_no_unlisted_error_classes` needs every error
    class in `PARENTS`, so `WriterBusyError` was added there first (red:
    3 failed, 39 passed). Its `test_reexported_from_protocols_and_package`
    needs the class in `tenetrag` as well, so it is exported from both
    `tenetrag.protocols` and `tenetrag`.
  - T007: two more tests:
    - `test_trigrams_padded_per_word`: the padding, `_` splitting words,
      and lower-casing;
    - `test_no_word_no_trigrams`.
  - T008: `trigrams` lower-cases the text as pg_trgm does, which the task
    text left out. `test_trigrams_padded_per_word` pins it.
  - Planted faults, each reverted, all caught:
    - `text.py`: `uy` after `q` moved; an ending followed by a letter
      moved; one table pair wrong; no whitespace collapse;
      `import tenetrag.storage` in the module (caught by
      `test_engine_imports`, and `lint-imports` breaks the layers and
      engine contracts);
    - `_trigram.py`: no lower-casing; one-space padding; `\w+` for words;
      the overlap over the larger set instead of the union; unsorted
      tokens;
    - `errors.py`: no UTC conversion; microseconds in the text; a naive
      `expires_at` accepted.

  Follow-up (2026-10-21, [ADR 0025](../../docs/decisions/0025-normalize-text-by-the-languages-the-profile-names.md)):
  review found the tone-mark table running on every text, a Vietnamese
  default in an open-source SDK. The rules now go by language.
  `make check` passes with 1285 unit tests, and `lint-imports` keeps 4
  contracts.
  - `src/tenetrag/engine/text.py` became the package
    `src/tenetrag/engine/text/`:
    - `__init__.py`: `norm(text, *, languages=())` and `LANGUAGE_RULES`;
    - `vi.py`: the table and `move_tone_marks`.
    Rules run after the shared steps, in the order of their codes. A
    language with no rule adds nothing.
  - The profile gains `text_languages`: ISO 639 codes, sorted, without
    repeats, empty by default. It is index-time in the chunk stage.
    M0's golden hashes were pinned again: the chunk hash changed, and
    it equals the spec recipe with `text_languages: []`.
  - The tests moved to `tests/unit/engine/text/`:
    - `test_norm.py`: the shared steps and how languages are picked;
    - `test_vi.py`: the tone marks, all with `languages=("vi",)`.
  - Red: 86 failed, 252 passed. `norm()` had no `languages` argument,
    `hoà` was moved with no language named, `tenetrag.engine.text.vi`
    was not loaded, and the profile refused `text_languages` as an
    unknown field. A test bug was fixed before any code (an ASCII
    example in `test_nfd_equals_nfc`).
  - `test_text_languages_rejected` passed in red for the wrong reason
    (the unknown-field message names the field). A planted fault
    confirmed that it catches unchecked codes once the field exists.
  - One test was added after green, `test_rules_run_in_language_order`:
    with a single rule, rules running in the caller's order could not
    fail.
  - Planted faults, each reverted, all caught: the earlier `text.py`
    faults, now in `__init__.py` and `vi.py`; the vi rule always on;
    rules in the caller's order; only the first rule run; codes
    unchecked; the list not sorted; repeats kept; the extract stage in
    place of the chunk stage.
  - Later tasks that normalize fixture text now pass
    `languages=("vi",)`: T015, T016, T028 and T034.

**Checkpoint**: `norm()`, `WriterBusyError` and the trigrams are ready

---

## Phase 3: User Story 1 - Protocols and the reference store (Priority: P1) 🎯 MVP

**Goal**: one stdlib-only module that states everything the engine may
ask of storage, and an in-memory reference store that implements it,
written to be read as a specification

**Independent Test**: follow
[quickstart.md §1](quickstart.md#1-protocols-and-the-reference-store-story-1-sc-004-sc-012),
including its negative check. Then run
`uv run pytest tests/contract -m "not docker" -q`, which passes on
`reference` and `reference-split`, with no Docker and no network.

### Tests for User Story 1

- [X] T009 [P] [US1] Write `tests/unit/protocols/test_records.py`, the
  record tests of [contracts/protocols.md](contracts/protocols.md#behaviour-pinned-by-tests):
  - `test_records_frozen`: for every record of data-model §2–§4 and
    §7.5, setting a field raises; each record is slotted and keyword-only;
  - `test_naive_datetime_refused`: `RunRecord` and `WriterLease`;
  - `test_spans_checked`: a mention, a chunk and a quote span;
  - `test_document_write_doc_ids`: a row with another `doc_id` raises,
    except a `text_in` row;
  - `test_same_as_order`;
  - `test_identity_key_shape`;
  - `test_document_link_key_one_side`.

  Red: `ImportError` for the record names from `tenetrag.protocols`.
- [X] T010 [P] [US1] Write `tests/unit/protocols/test_stores.py`:
  - `test_protocols_stdlib_only`: in a subprocess, `import
    tenetrag.protocols` adds no module outside the standard library and
    `tenetrag` to `sys.modules` (FR-001, SC-012);
  - `test_protocol_methods`: the method names of `GraphStore` equal engine
    brief §6.1 less its six community methods, plus `renew_writer` and
    `release_writer`. Those of `VectorStore` equal §6.2. Both lists are
    written in the test;
  - `test_hop_spec_limits`;
  - `test_store_schema_patterns`, `test_store_schema_reserved` and
    `test_store_schema_merged`;
  - `test_name_patterns_match_packs`: `TYPE_NAME.pattern` and
    `RELATION_NAME.pattern` equal the patterns in
    `src/tenetrag/packs/format.py`.

  Red: `ImportError` for `GraphStore` and the rest.
- [X] T011 [P] [US1] Write `tests/unit/packs/test_store.py` with
  `test_store_schema_shipped`. `core`, `enterprise-docs` and the `finance`
  draft each build a schema. In `core`, `PART_OF` is a relation and
  `Event` an event type, and a type with `extract: false` is included.

  Red: `ImportError` for `store_schema` from `tenetrag.packs`.
- [X] T012 [US1] Implement `src/tenetrag/protocols/records.py`
  ([data-model §2–§4 and §7.5](data-model.md#2-write-records), research
  R2):
  - frozen, slotted, keyword-only dataclasses;
  - checks in `__post_init__` raise `ValueError` naming the field;
  - each record is exported from `tenetrag.protocols`.

  T009 passes, except the `WriterLease` case of
  `test_naive_datetime_refused`, which T013 turns green. Depends on T009.
- [X] T013 [US1] Implement `src/tenetrag/protocols/stores.py`
  (contracts/protocols.md §2–§4, data-model §5):
  - `GraphStore` and `VectorStore` as `typing.Protocol` classes marked
    `@runtime_checkable`, since quickstart §1 checks them with
    `isinstance`;
  - `StoreSchema` with `merged()` and its pattern, reserved-name and
    one-kind checks raising `ConfigError`;
  - `WriterLease`, `WriteStep`, `HopSpec` (defaults 20 and 50, limits 1
    to 1,000), `HopResult`, `HopEdge` and `HopItem`;
  - `AnyScope`, `ANY_SCOPE`, `RESERVED_LABELS`, `RESERVED_EDGE_TYPES`,
    `TYPE_NAME`, `RELATION_NAME`, `JsonValue`, `RunStats` and
    `StepHook`, all exported.

  T009 and T010 pass. Depends on T010 and T012.
- [X] T014 [US1] Implement `src/tenetrag/packs/store.py` with
  `store_schema(stack) -> StoreSchema`, and export it from
  `tenetrag.packs`. It covers every entity, event, fact and relation type
  of the stack, `extract: false` included. A name that `StoreSchema`
  refuses raises `ConfigError`. T011 passes. Depends on T011 and T013.
- [X] T015 [P] [US1] Write `tests/unit/test_support_contract.py`, part 1.
  It pins the fixture helpers of
  [contract-suite.md §2](contracts/contract-suite.md#2-fixture-data),
  in the way `tests/unit/test_support_packs.py` pins `tests/support/packs.py`:
  - `corpus_writes(["D1", "D2", "D5"])`:
    - gives three writes for those documents, with `run_id` `run-1`;
    - the ids of one chunk, one entity and one relation equal the
      SHA-256 recipes of engine brief §1, recomputed in the test;
    - chunks split at blank lines, and their offsets slice the document
      text back;
    - every quote is the chunk text at its span;
    - every `*_norm` field equals `norm(…, languages=("vi",))` of its
      source;
  - `corpus_writes()` gives the 41 documents in corpus order;
  - `expected_statuses()` equals graph.json `versions`, and
    `corpus_delete("D2")` carries the status changes graph.json
    `deletions` lists for D2;
  - `with_vectors=False` gives writes with no vectors, and
    `corpus_vectors` gives the same ids the paired writes carry;
  - `SCHEMA == store_schema(load_pack("enterprise-docs"))`, and
    `VECTOR_SPEC` names `fake-embed`, 8 dimensions and each collection;
  - `edited_write(write, run_id=...)` drops the last chunk and every row
    quoting it, and changes `content_hash`. It is a helper the contract
    does not name, recorded as a departure in T081;
  - `expected_counts(doc_ids)` equals the rows counted from the writes,
    keyed by the table names of [data-model §6](data-model.md#6-postgres-layout);
  - `two_source_writes()` states one relation in two documents;
    `pack_status_writes()` holds a `Decision` whose pack `status`
    attribute differs from its engine status; `tone_mark_writes()` holds
    the pairs `Hoà`/`Hòa` and `Thuỷ`/`Thủy` and the set `Lãi`/`Lại`/`Lai`;
  - `recall_fixture()` gives 3,000 vectors of 64 dimensions and 30
    queries. Its exact top 10 matches a brute-force recount for three
    queries, and two calls give equal data;
  - every generated name is fictional, checked as `test_fictional_only`
    in `tests/unit/packs/test_corpus.py` checks the corpus;
  - `test_reference_satisfies_protocols`: `isinstance` holds for both
    reference stores. Annotated assignments
    `graph: GraphStore = ReferenceGraphStore(...)` and
    `vectors: VectorStore = ReferenceVectorStore(...)` let mypy check
    them structurally (US1 scenario 1).

  Red: `ModuleNotFoundError` for `tests.support.contract.writes`.

### Implementation for User Story 1

- [X] T016 [US1] Implement `tests/support/contract/writes.py`
  (contract-suite.md §2, §4; research R20):
  - `corpus_writes`, `corpus_vectors`, `corpus_delete`,
    `expected_statuses`, `edited_write`, `expected_counts`, `SCHEMA` and
    `VECTOR_SPEC`;
  - `snapshot(stores) -> dict[str, list[object]]`: every row the
    protocols can read for a set of ids, sorted. Kill-point and replay
    tests compare stores with it;
  - `write_all(stores, writes)`. Paired, it calls `write_documents`.
    Split, it runs the four steps of
    [§4](contracts/contract-suite.md#4-the-split-pairing). It keeps the
    vector ids per document on the `ContractStores` object (T019);
  - inputs: tables from `tests.support.corpus` (`read_facts`,
    `derive.statuses`, `world_ids`) and the committed
    `tests/fixtures/corpus/generated/` files; vectors from
    `FakeEmbeddingModel(dimensions=8)`; text through
    `tenetrag.engine.text.norm` with `languages=("vi",)`, the corpus's
    languages (ADR 0025).

  The T015 tests for writes.py pass. Depends on T004, T014 and T015.
- [X] T017 [US1] Implement `tests/support/contract/generated.py`, part 1:
  `two_source_writes`, `pack_status_writes`, `tone_mark_writes` and
  `recall_fixture`, all with fictional names and deterministic output.
  The T015 tests for generated.py pass. Depends on T016.
- [X] T018 [US1] Create the reference store skeleton in
  `tests/support/reference/` (research R19):
  - `database.py`: `ReferenceDatabase`, with one `threading.RLock`,
    per-index tables and an injectable clock that defaults to
    `datetime.now(UTC)`;
  - `graph.py`: `ReferenceGraphStore(db, index_id, *, vectors=None,
    step_hook=None)`;
  - `vectors.py`: `ReferenceVectorStore(db, index_id)`, whose
    `capabilities.max_dimensions` is 4096;
  - `__init__.py` exports the three classes;
  - every protocol method has its full signature and raises
    `NotImplementedError` naming the task that builds it (T029, T030,
    T031, T039 or T040).

  `test_reference_satisfies_protocols` passes, and `make types` accepts
  the annotated assignments. Depends on T013 and T015.
- [X] T019 [US1] Create the `stores` fixture
  ([contract-suite.md §1](contracts/contract-suite.md#1-the-stores-fixture)):
  - `tests/support/contract/backends.py`:
    - `ContractStores` with the fields and methods of §1:
      `open_graph`, `open_vectors`, and `kill_running_unit`, which calls
      `pytest.skip` on the reference store;
    - plus three members the contract does not name, recorded in T081:
      `layout_module`, the module whose `LAYOUT_VERSION` a test patches;
      `row_counts() -> dict[str, int]`, keyed by the table names of
      data-model §6; and `text_in_links() -> set[tuple[str, str, str]]`;
    - `index_id_for(node_id)`: `"t"` plus 12 hex digits of the node id's
      SHA-256;
    - builders for `reference` (vectors in the same database) and
      `reference-split` (vectors in their own database);
  - `tests/contract/conftest.py`:
    - `stores` is parametrized over `reference` and `reference-split`;
    - each test gets a fresh index id, calls `ensure_schema(SCHEMA)` and
      `ensure_collections(VECTOR_SPEC)`, then acquires the lease as
      `contract:<backend>`.

  `uv run pytest tests/contract --collect-only -q` collects nothing yet
  and raises no error. Depends on T016 and T018.
- [X] T020 [P] [US1] Write `tests/contract/test_writes.py`, for the cases
  `counts-after-write-and-replay`, `pack-attributes-apart` and
  `one-of-two-sources`:
  - `test_counts_after_write`: D1, D2 and D5, then all 41, each against
    `expected_counts`;
  - `test_replay_changes_no_count`: the same writes again under
    `run-2` change no count and no `snapshot` row, and entity, alias and
    event run ids keep `run-1`;
  - `test_records_read_back_equal`: every record of D1 read back by id
    equals what was written, field by field, and `entities_in_chunks`
    returns its mentions (US1 scenario 3);
  - `test_ids_and_text_kept`: a write whose `name_norm` is deliberately
    not normalized reads back unchanged, and no id appears that was not
    written (US1 scenario 5);
  - `test_unknown_type_refused`: a type outside the schema raises
    `ConfigError` before the unit, and nothing is written;
  - `test_vectors_follow_pairing`. Paired, the chunk vectors are
    readable after `write_documents`. Split, a write that carries vectors
    raises `StorageError` before the unit;
  - `test_pack_attributes_apart` (US1 scenario 4);
  - `test_one_of_two_sources`: deleting one source keeps the other
    document's row of that relation (US2 scenario 3).

  Red: every test errors in fixture setup with the skeleton's
  `NotImplementedError` from `ensure_schema`, naming T029. A collection
  error does not count as red, so each new file in T020–T028 is also run
  with `--collect-only`.
- [X] T021 [P] [US1] Write `tests/contract/test_deletes.py`, for the cases
  `end-state-after-delete`, `orphan-cleanup`,
  `sources-deleted-with-document` and `text-in-added-and-removed`:
  - `test_delete_all_leaves_nothing`: write D1, D2 and D5, delete all
    three, and every `row_counts()` value is 0. No vector is left, on
    either pairing (SC-005);
  - `test_delete_d2_end_state` (US2 scenario 2): r1 is `current` again,
    D2's rows are gone, entities that only D2 mentioned are gone with
    their aliases, and those D1 mentions remain;
  - `test_orphans_after_edit` and `test_orphans_after_delete`, through
    `edited_write`. An orphan's aliases, identity values, attribute
    sources, identity blocks, `text_in` and `same_as` rows go with it
    (FR-008);
  - `test_sources_deleted_with_document`: shown attributes are
    recomputed from the sources left;
  - `test_text_in_added_and_removed`: a link written from the document
    side or from the entity side, removed when either side goes;
  - `test_unknown_delete`: an unknown `doc_id` is a no-op, and its
    status changes still apply.

  Red as T020.
- [X] T022 [P] [US1] Write `tests/contract/test_statuses.py`, for the
  cases `supersession-flags` and `status-changes-in-unit`:
  - `test_statuses_match_graph_json`: all 41 written, then statuses and
    `closed_at` equal `expected_statuses()`;
  - `test_statuses_after_d2_deleted`;
  - `test_unknown_item_fails_unit`: `QueryError` names the id, that
    document's unit rolls back, earlier documents stay written, and later
    ones are not tried (FR-011, stores.md §3.1);
  - `test_version_reads`: the order of `get_version_groups` (version
    key, then `valid_from` with missing first, then item id); and
    `get_document_version_keys`, where a document with none gives an
    empty list and an unknown one is absent.

  Red as T020.
- [X] T023 [P] [US1] Write `tests/contract/test_provenance.py`, for the
  case `provenance-reachability`:
  - `test_every_item_reaches_its_chunks_and_documents`: for every item of
    D1, D2 and D5, `get_items` leads through its evidence to
    `get_chunks` and `get_documents`, and every quote is its chunk's text
    at its span;
  - `test_entities_in_chunks_order`: by chunk id, then `start`, then
    entity id;
  - `test_reads_by_id`: results are sorted by id, unknown ids are left
    out, a duplicated id is read once, and an empty input gives an empty
    result (contracts/protocols.md §2).

  Red as T020.
- [X] T024 [P] [US1] Write `tests/contract/test_lease.py`, for the case
  `writer-lease` ([stores.md §2](contracts/stores.md#2-writer-lease)):
  - `test_second_writer_busy`: `WriterBusyError` names the holder and
    the end time;
  - `test_same_owner_reacquires`: the fence is kept;
  - `test_renew_moves_end`;
  - `test_release_lets_next_acquire`: releasing a lease already gone
    raises nothing;
  - `test_expiry_lets_next_acquire`: `ttl_s=1`, then a wait past it.
    The new holder gets fence + 1;
  - `test_fenced_writer_fails`: after a takeover, the old store's
    `write_documents` raises `WriterBusyError` and writes nothing;
  - `test_every_write_needs_the_lease`: on a store from `open_graph()`
    that never acquired, `write_documents`, `delete_documents`,
    `begin_run`, `finish_run`, `put_cached_extractions` and
    `put_resolution_decisions` each raise `StorageError` saying to call
    `acquire_writer`. T035 adds `refresh_degrees`;
  - `test_two_objects_one_lease`;
  - quickstart §1's negative check, run as a test.

  Red as T020.
- [X] T025 [P] [US1] Write `tests/contract/test_runs_and_caches.py`, for
  the cases `runs-and-states` and `cache-round-trip`:
  - `test_runs_round_trip`: `begin_run`, `finish_run` and
    `get_runs(limit)`. A limit of 0 or 1,001 raises, and an unknown run
    id in `finish_run` raises `QueryError`;
  - `test_document_states`: one state per written document, with its
    hashes and run;
  - `test_extraction_cache_round_trip`: only found keys come back;
  - `test_resolution_decisions_round_trip`: a reviewer verdict wins
    over a model verdict for the same pair.

  Red as T020.
- [X] T026 [P] [US1] Write `tests/contract/test_schema_and_layout.py`, the
  store-neutral part of the case `schema-and-layout` (FR-035, FR-036,
  [data-model §9](data-model.md#9-layout-version-and-setup-states)):
  - `test_ensure_schema_idempotent`: a second call changes no
    `snapshot` row;
  - `test_ensure_schema_additive`: a schema merged with a new relation
    type accepts that type, and existing rows are untouched;
  - `test_layout_mismatch_fails`: with `LAYOUT_VERSION` patched to 2 on
    `stores.layout_module`, a new store object raises `ConfigError`
    naming both versions and saying to rebuild under a new index id;
  - `test_call_before_ensure_schema`: on a fresh index id, a read raises
    `StorageError` saying to call `ensure_schema`.

  Red as T020.
- [X] T027 [P] [US1] Write `tests/contract/test_vectors.py`, for the cases
  `recall-floor`, `collections` and `exclude-run` (vectors):
  - `test_recall_floor`: the recall fixture under a fresh index id and
    a 64-dimension spec gives recall at 10 of at least 0.9 (SC-010). The
    value is printed for the record;
  - `test_reference_vector_scores`: on three hand-made vectors, the
    scores are within 1e-3 of the cosine computed in the test;
  - `test_search_shape`: one list per query vector, in input order, at
    most `k` hits each. A `k` of 0 or 1,001 raises;
  - `test_collection_change_fails`: a model or dimension change raises
    `ConfigError` naming the collection and both values (FR-025);
  - `test_dimensions_over_maximum`: `capabilities.max_dimensions + 1`
    is refused with the message of contracts/config.md §2;
  - `test_wrong_length_refused`: `QueryError` before any write;
  - `test_filters`: fields are AND-ed, `None` means no filter, and an
    empty tuple matches nothing;
  - `test_exclude_run_vectors`;
  - `test_upsert_replaces`, `test_delete_skips_unknown`, and
    `test_get_vectors_round_trip` (within 1e-6).

  Red as T020.
- [X] T028 [P] [US1] Write `tests/contract/test_text_search.py`, for the
  case `tone-mark-matching` (full text, [research R6](research.md#r6-postgres-full-text)).
  It runs on the `tone_mark_writes()` chunks plus chunks holding the R6
  texts, and checks membership only, never a score:
  - `test_syllables_match_whole`: `lãi`, `lại` and `lai` each find only
    their own chunk (US4 scenario 6, SC-009);
  - `test_tone_mark_pairs_match`: after `norm()` with `vi`, `hoà` finds
    `hòa`;
  - `test_numbers_and_punctuation`: `2.500.000`, `vnd/ngày` and
    `phòng-ban` hit, and `500` misses;
  - `test_any_syllable`: a three-syllable query finds a chunk holding
    one of them (OR);
  - `test_operators_harmless`: `a & b | c:* !d` and `o'neil` run as
    plain words, and `'` or `...` gives no rows.

  Red as T020.
- [X] T029 [US1] Implement the reference store's database, setup and
  bookkeeping in `tests/support/reference/`:
  - `ensure_schema`: the merged schema and `LAYOUT_VERSION = 1`
    recorded per index, with the layout check of data-model §9 on each
    store object's first call;
  - `acquire_writer`, `renew_writer` and `release_writer` by the table
    of stores.md §2, against the database clock;
  - the lease check at the start of every write method;
  - `begin_run`, `finish_run`, `get_runs`, `document_states`, and the
    cache and decision methods.

  `test_lease.py` and `test_runs_and_caches.py` pass on both reference
  parameters. So do the tests of `test_schema_and_layout.py` that need no
  document write. Depends on T019–T026.
- [X] T030 [US1] Implement the reference store's write units and reads
  ([stores.md §3](contracts/stores.md#3-write-units)):
  - `write_documents` and `delete_documents` copy the index's tables,
    apply the five steps (four for a delete) to the copy, call
    `step_hook(step, doc_id)` after each, and swap the copy in at the
    end;
  - paired, the vectors are written and deleted in steps 1, 2 and 4.
    Split, a write that carries vectors raises `StorageError`;
  - orphans are searched only among the entities and events the unit
    touched or emptied (research R15);
  - shown attributes are computed on read from the attribute sources;
  - `get_entities`, `get_items`, `get_chunks`, `get_documents`,
    `entities_in_chunks`, `get_version_groups` and
    `get_document_version_keys`, in the orders of contracts/protocols.md §2.

  `test_writes.py`, `test_deletes.py`, `test_statuses.py`,
  `test_provenance.py` and `test_schema_and_layout.py` pass on both
  reference parameters, except the vector parts that T031 completes.
  Depends on T029.
- [X] T031 [US1] Implement `ReferenceVectorStore`:
  - `ensure_collections`, with the model and dimension check and the
    4096 maximum;
  - `upsert`, `delete`, `delete_documents` and `get_vectors`;
  - `search`: exact cosine, by score descending, then id;
  - `search_text`: the R6 split and OR rule written in Python over
    `text_norm`, ranked by matched syllables, then id;
  - filters and `exclude_run`.

  The graph store's paired writes call this class's write code.
  `test_vectors.py`, `test_text_search.py` and the vector parts of
  T020–T021 pass. Depends on T030.
- [X] T032 [US1] Run `uv run pytest tests/contract -m "not docker" -q`,
  `tests/unit/protocols`, `tests/unit/packs/test_store.py` and
  `tests/unit/test_support_contract.py`. Run quickstart §1 with its
  negative check, and `make check`. Check SC-012 in two scratch
  environments:
  - built with `uv venv` and `uv pip install .`, no extras and no dev
    group: `python -I -c "import sys, tenetrag.protocols; ..."` lists no
    third-party module;
  - synced with `uv sync --locked --no-extras` into
    `UV_PROJECT_ENVIRONMENT=$SCRATCH/venv-noextras`, with psycopg absent:
    `uv run pytest tests/contract -m "not docker" -q` passes. A support
    import that pulls a driver moves inside its function.

  Try deliberate faults in the reference store, for example:
  - `get_items` returns ids unsorted;
  - `get_items` drops `closed_at`;
  - the swap happens before the last step's hook;
  - `search_text` folds diacritics;
  - `search_text` ANDs syllables;
  - a same-owner `acquire_writer` bumps the fence;
  - `release_writer` raises on a lease already gone.

  A fault that survives gets a test. Record the red runs of T009–T011,
  T015 and T020–T028, the results and the suite's duration here, as M0
  did.

  Result (2026-10-21): `make check` passes with 1486 tests, 201 of them
  new: 91 unit tests, and the contract suite's 55 tests run on
  `reference` and `reference-split`. `uv run pytest tests/contract -m
  "not docker" -q` passes its 110 runs in 8 s, with no Docker and no
  network.
  - Red:
    - T009–T011: the three files failed to collect, each on a missing
      production name (`cannot import name 'ANY_SCOPE' from
      'tenetrag.protocols'`, the same for `RELATION_NAME`, and
      `cannot import name 'store_schema' from 'tenetrag.packs'`), 3
      errors in 0.29 s;
    - T015: `No module named 'tests.support.contract.generated'`;
    - T020–T028: every test collected, then errored in the fixture on
      `NotImplementedError: the reference graph store gets this in T029`
      (108 errors in 0.72 s).
  - Quickstart §1 prints `(True, True)` and `['D1', 'D2', 'D5']`. In the
    negative check, the second store raises `StorageError` ("call
    acquire_writer before writing"), then `WriterBusyError` naming
    `quickstart` and the end time to the second.
  - SC-012:
    - in a `uv venv` with `uv pip install .`, importing
      `tenetrag.protocols` loads no third-party module (the base
      dependencies are installed, and none is imported);
    - in a venv synced with `uv sync --locked`, psycopg is absent and the
      contract suite passes. The task's `--no-extras` is not a uv flag;
      uv installs no extra unless asked. No support import had to move.
  - Planted faults, each run against the whole suite:
    - six were caught by the tests written for them: unsorted
      `get_items` by `test_reads_by_id`; a dropped `closed_at` by
      `test_statuses_match_graph_json`; folded diacritics by
      `test_diacritics_not_folded`; AND-ed syllables by
      `test_any_syllable_matches`; a fence bumped for the same owner by
      `test_same_owner_reacquires`; and a release that raises by
      `test_release_lets_next_acquire`;
    - a swap before the last step's hook survived, since no test set a
      step hook. `tests/contract/test_kill_points.py` now holds
      `test_failure_in_last_step_writes_nothing`, which catches it. T037
      adds the other steps to that file.
  - A test-helper bug found in green: `snapshot()` read
    `document_states()` for the whole index, against its docstring, so
    `test_schema_additive` failed once D901 was written. It now keeps
    the states of the writes' documents. `test_replay_changes_no_count`,
    its only other caller, rewrites the same documents and loses nothing.
  - Departures:
    - `LIMIT_MAX` (1,000) lives in `tenetrag.protocols.stores`. `k`,
      `limit` and `ttl_s` out of range raise `ValueError`. The reference
      store's ttl maximum (86,400 s) is its own constant, since the
      protocols define none;
    - a same-owner `acquire_writer` keeps its fence, even after its
      lease expired, as long as no other owner took it;
    - before `ensure_collections`, the reference vector store raises
      `StorageError` naming the collection;
    - an orphan's identity blocks go by either id, `entity_id` or
      `candidate_id`;
    - `text_in` rows ride on the linked document's write. Version keys
      are the readable group names of `graph.json`, and fixture scope
      paths join names with U+203A, spelled by code point;
    - `pack_status_writes` uses an `ActionItem` and a `Decision` (D903);
    - fixture helpers beyond contract-suite.md: `writer_owner`,
      `edited_write`, `expected_counts`, `count_rows`, `snapshot`,
      `delete_all`, `store_id`, `entity_id`, `corpus_table`,
      `question_id` and `corpus_delete(written=)`, and on
      `ContractStores`, `layout_module`, `row_counts`, `text_in_links`
      and `vector_ids`. Each backend implements the `Server` protocol,
      as `ReferenceServer` does;
    - mypy now checks `tests.contract`, `tests.support.contract`,
      `tests.support.reference` and the protocol shape tests. Untyped
      test functions are allowed under `tests.contract` and `tests.unit`.
  - Known gap until T039: an orphan's identity values are checked only
    through the entity being gone, since `find_by_identity` comes with
    T039.

**Checkpoint**: the protocols exist, the reference store holds the
corpus, and the write-side suite runs offline. MVP reached.

---

## Phase 4: User Story 2 - One contract suite for every backend (Priority: P1)

**Goal**: the rest of the suite (lookups, hop, isolation, kill points),
the case map that ties every case of ADR 0008 §5 and engine brief §10 to
a test, and planted faults that show each case's tests can fail

**Independent Test**: follow
[quickstart.md §2](quickstart.md#2-one-suite-every-case-mapped-story-2-sc-001-sc-003),
including its negative check. `make faults` prints 27 lines, each
`caught`, and exits 0.

### Tests for User Story 2

- [ ] T033 [P] [US2] Add to `tests/unit/test_support_contract.py`, part 2:
  - `hub_writes(n=5000)` gives one entity with `n` relations to `n`
    neighbours over 50 documents. Types, statuses and dates are mixed,
    the names are fictional, and two calls are equal. A small `n` is
    used for speed where the shape is all that is checked;
  - `write_split_crashing(stores, write)` upserts the new vectors, then
    raises before `write_documents`, which a spy store shows was never
    called (contract-suite.md §4).

  Red: `ImportError` for `hub_writes` and `write_split_crashing`.
- [ ] T034 [P] [US2] Write `tests/contract/test_identity_and_names.py`,
  for the cases `identity-scope`, `exclude-run` and `tone-mark-matching`
  (names):
  - `test_find_by_identity_scope`: a scope id, `None` and `ANY_SCOPE`.
    An entity matched by two keys appears once;
  - `test_find_events`: keys with `scope=ANY_SCOPE`;
  - `test_match_names_exclude_run`: an entity created by the run and an
    alias added by it are hidden (FR-020);
  - `test_match_names_tone_marks`: the `norm()` forms with `vi` of `hoà` and
    `hòa` match. `lãi`, `lại` and `lai` each match only their own entity
    (US2 scenario 5, SC-009);
  - `test_search_names_candidates`: every must-find name is in the
    candidates and no must-not-find name is. The result is the best match
    per entity, within `limit`, and limits outside 1–1,000 or a
    similarity outside 0–1 raise (US2 scenario 6). Scores are compared
    only against the threshold;
  - `test_match_document_links`: each `(entity_id, doc_id, attribute)`
    comes back once.

  Red: `NotImplementedError` from the methods, naming T039.
- [ ] T035 [P] [US2] Write `tests/contract/test_hop.py`, for the cases
  `type-time-status-filters`, `hop-membership`, `hop-caps`,
  `hub-invariants` and `as-of-prefilter`
  ([data-model §5.4](data-model.md#54-hop), research R12):
  - `test_hop_filters`: `relation_types`, `item_types` and `statuses`
    each drop what they should. Events pass a status filter;
  - `test_hop_membership` and `test_two_composed_hops`: from two seeds
    that D1 and D2 both mention, the neighbour and item sets equal
    literal world ids. The ids are worked out by hand from the fact
    table and written in the test, and they are the oracle (SC-008);
  - `test_hop_caps`: the caps apply per start entity, in store order
    (support, then the newest `observed_at`, then id);
  - `test_same_as_in_hop`: with `include_same_as`, links that are not
    rejected are followed;
  - `test_hub_invariants`: after `hub_writes()` and `refresh_degrees`,
    the hub gives at most 20 neighbours and 50 items, the support of
    each edge, and a degree equal to its distinct neighbours. On Docker
    parameters the hop takes under 1 s, and the time is printed
    (SC-007);
  - `test_as_of_prefilter`: `starts_before`, and `overlaps` with an
    open end;
  - also add `refresh_degrees` to `test_every_write_needs_the_lease` in
    `tests/contract/test_lease.py`.

  Red: `NotImplementedError` naming T040.
- [ ] T036 [P] [US2] Write `tests/contract/test_isolation.py`, for the
  case `isolation` (SC-011, US6 scenario 4):
  - `test_no_read_sees_another_index`: the corpus is written under this
    index. Every graph and vector read method, called on
    `open_graph(index_id=other)` and `open_vectors(index_id=other)`,
    returns nothing. The list of read methods in the test is checked
    against the protocols' method names, so a new read method cannot be
    missed;
  - `test_delete_in_one_index_leaves_the_other`: the same documents go
    in two indexes. Deleting one from the first leaves every read of the
    second unchanged (`snapshot`).

  Red: `NotImplementedError` from the lookups and `hop`.
- [ ] T037 [P] [US2] Write `tests/contract/test_kill_points.py`, for the
  cases `killed-run-atomicity` and `split-crash-recovery` (FR-046,
  [stores.md §3.4](contracts/stores.md#34-killed-units)):
  - `test_kill_at_each_step`, parametrized over every `WriteStep` of a
    write and of a delete. A `step_hook` raises at D2's step in a batch
    of D1, D2 and D5 whose previous versions are written and whose new
    versions come from `edited_write`. Afterwards D1 is new, D2 and D5
    are previous, and no orphan or dangling row exists. A replay equals a
    clean run, row for row (`snapshot`, SC-006);
  - `test_paired_vectors_roll_back`: paired, no vector of the new
    version is visible after the kill (US5 scenario 5). On a split
    pairing it is skipped with the reason;
  - `test_split_crash_recovery`: split only, through
    `write_split_crashing`. The graph keeps the previous version, and the
    extra vectors name chunk ids the graph lacks. After `write_all`
    again, the vector ids equal the graph's chunk ids (US5 scenario 4).
    Skipped on paired parameters with the reason.

  These may pass on arrival on the reference store, since T030 already
  copies and swaps. If they do, record it. Their can-fail evidence is the
  `killed-run-atomicity` and `split-crash-recovery` faults of T044.

### Implementation for User Story 2

- [ ] T038 [US2] Add `hub_writes` to `tests/support/contract/generated.py`,
  and `write_split_crashing` to `tests/support/contract/writes.py`. T033
  passes. Depends on T033.
- [ ] T039 [US2] Implement the reference store's lookups:
  - `find_by_identity` (scope id, `None`, and `ANY_SCOPE` across scopes)
    and `find_events`;
  - `match_names`: exact on `name_norm` and `alias_norm`, with
    `exclude_run` on the matched row;
  - `search_names`: `tenetrag.storage._trigram.similarity` at or above
    the floor, best per entity, by similarity, then id;
  - `match_document_links`.

  `test_identity_and_names.py` passes on both reference parameters.
  Depends on T034.
- [ ] T040 [US2] Implement the reference store's `refresh_degrees`
  (distinct neighbours through relations and role-mates, data-model §5.3)
  and `hop` (the R12 neighbours, items, filters, caps and order).
  `test_hop.py`, `test_isolation.py` and `test_kill_points.py` pass on
  both reference parameters. Depends on T035–T039.
- [ ] T041 [US2] Write `tests/contract/test_case_map.py`
  ([contract-suite.md §5](contracts/contract-suite.md#5-the-case-map)).
  It fails when:
  - a case of ADR 0008 §5 or engine brief §10 has no entry. Both lists
    are written in the test as literal case ids;
  - an entry names a test that does not exist. Each
    `tests/contract/test_*.py` is parsed with `ast` for its top-level
    `test_` functions, so no fixture runs;
  - a test function appears in no entry. Exempt are
    `test_open_stores.py`, which tests the builder, and
    `test_case_map.py` itself. The second exemption is a departure,
    recorded in T081;
  - two entries share an id, or an entry has an empty `tests`.

  Red: `ModuleNotFoundError` for `tests.contract.cases`.
- [ ] T042 [US2] Write `tests/contract/cases.py`: `ContractCase` and
  `CASES`, the 27 cases of [data-model §10](data-model.md#10-contract-cases),
  each with its source, text and node ids. Every test function written
  in T020–T028 and T034–T037 is named. T041 passes. Depends on T040 and
  T041.
- [ ] T043 [US2] Add to `tests/unit/test_support_contract.py`:
  - `test_every_case_has_one_fault`: the keys of `faults.FAULTS` equal
    the ids of `CASES`;
  - `test_fault_report`: given a result map, `report()` prints one line
    per case, `<case id>: caught` or `<case id>: survived`, and returns
    1 when any fault survived, else 0.

  Red: `ModuleNotFoundError` for `tests.support.contract.faults`.
- [ ] T044 [US2] Implement `tests/support/contract/faults.py` and a
  `faults` target in `Makefile`
  (`uv run python -m tests.support.contract.faults`;
  [contract-suite.md §6](contracts/contract-suite.md#6-planted-faults)):
  - `FAULTS` maps each case id to a context manager that patches the
    reference store with `unittest.mock.patch.object`;
  - `main()` runs, for each case, `pytest -q -p no:cacheprovider` on that
    case's node ids with `-k reference` and the fault in place, in a
    subprocess. The fault is chosen through an environment variable read
    by a plugin module given with `-p`. A fault is caught when any test
    fails;
  - the twelve faults of the §6 table, plus one each for the other
    fifteen cases:

    | Case | Fault |
    |---|---|
    | `type-time-status-filters` | `hop` ignores `statuses` |
    | `hop-membership` | `hop` follows relations only from subject to object |
    | `orphan-cleanup` | step 4 skips entities whose rows step 1 removed |
    | `status-changes-in-unit` | a change naming an unknown item is skipped |
    | `sources-deleted-with-document` | step 1 keeps attribute sources |
    | `text-in-added-and-removed` | deleting an entity keeps its `text_in` rows |
    | `cache-round-trip` | a model verdict overwrites a reviewer verdict |
    | `as-of-prefilter` | `starts_before` is ignored |
    | `split-crash-recovery` | `ReferenceVectorStore.delete` does nothing |
    | `one-of-two-sources` | a delete removes every row of a relation id |
    | `pack-attributes-apart` | the engine status is written into `attributes["status"]` |
    | `recall-floor` | `search` returns ranks k+1 to 2k |
    | `schema-and-layout` | the layout version check is skipped |
    | `collections` | `ensure_collections` accepts a dimension change |
    | `runs-and-states` | `document_states` leaves out the last document written |

  T043 passes. Depends on T042 and T043.
- [ ] T045 [US2] Run quickstart §2 with its negative check:
  - `make faults` prints 27 lines, each `caught`, and exits 0;
  - with one fault made a no-op, that case reads `survived` and the exit
    is 1;
  - with the `writer-lease` entry commented out, `test_case_map.py`
    fails naming it.

  Run `uv run pytest tests/contract -m "not docker" -q --durations=10`.
  The suite on both reference parameters takes under 20 s (SC-004,
  reference half). Run `make check`. Record SC-001, SC-003, the
  `make faults` output and the duration here. A fault that survives gets
  a test, not a weaker fault. Also record the red runs of T033–T037,
  T041 and T043, and whether T037 passed on arrival.

**Checkpoint**: one suite, every case mapped, every case's tests shown
to fail under a planted fault. Both P1 stories are done.

---

## Phase 5: User Story 3 - The Postgres store (Priority: P2)

**Goal**: `PostgresGraphStore` and `PostgresVectorStore` pass the whole
suite on Postgres 16 and 17, one schema per index, vectors written in the
document's transaction

**Independent Test**: follow
[quickstart.md §3](quickstart.md#3-the-postgres-store-story-3-sc-002-sc-009-sc-010)
up to its `open_stores` snippet, which T077 runs once US6 exists.
`uv run pytest tests/contract -m docker -k "postgres-pg16 or postgres-pg17" -q`
passes.

### Tests for User Story 3

- [ ] T046 [P] [US3] Write `tests/unit/storage/test_names.py` with
  `test_names_refused`. `checked_label` and `checked_edge_type` raise
  `ConfigError` naming the name for each of these: a name outside the
  schema, a reserved name (`Chunk`, `IN_DOCUMENT`), and a pattern break
  (`vendor`, `OWNS-BY`, a name holding a backtick or `$`). Valid names
  come back unchanged.

  Red: `ModuleNotFoundError` for `tenetrag.storage._names`.
- [ ] T047 [US3] Implement `src/tenetrag/storage/_names.py` (stores.md
  §4.3). T046 passes. Depends on T046.
- [ ] T048 [P] [US3] Write the Postgres unit tests, with no server:
  - in a new `tests/unit/storage/test_store_classes.py`:
    - `test_index_id_pattern`: `Alpha`, `1a`, `a-b` and a 41-character
      id each raise `ConfigError`, parametrized over the constructors of
      `PostgresGraphStore` and `PostgresVectorStore`, on connections from
      `tests/support/fake_stores.py`;
    - `test_paired_needs_same_connection`;
    - the Postgres half of `test_stores_without_extras`: with psycopg
      hidden, as M0's `test_missing_extra` does, `import tenetrag.storage`
      works, and building a Postgres store raises `MissingExtraError`
      naming `postgres`;
  - in `tests/unit/storage/test_postgres_unit.py`,
    `test_postgres_error_drops_detail`: a psycopg `UniqueViolation` whose
    DETAIL line holds a planted value from `tests/support/secrets.py`
    gives a `QueryError` naming the constraint and not the value
    (research R21).

  Red: `ImportError` for `PostgresGraphStore` from `tenetrag.storage`.
  `test_postgres_error_drops_detail` is expected to pass on arrival,
  since M0 keeps only the first line. Its can-fail evidence is a
  deliberate fault in T055 that appends the detail.
- [ ] T049 [US3] Add the Postgres parameters:
  - `tests/support/containers.py` gains `postgres_server(image)`, a
    context manager that starts a pgvector container from the pinned
    digest and gives its host, port, admin user and database. A UTF-8
    locale is set explicitly;
  - in `tests/contract/conftest.py`, session fixtures start one
    container per image, after `require_docker()`;
  - `postgres-pg16` and `postgres-pg17` join the `stores` parameters as
    `pytest.param(..., marks=[pytest.mark.docker,
    pytest.mark.enable_socket])`;
  - `backends.py` builds a paired Postgres pair through M0's
    `open_connection`, with the credential passed explicitly. Its
    `row_counts`, `text_in_links` and `layout_module` read the test's
    schema. The store import is inside the builder, so a missing module
    errors only these parameters (SC-004).

  Red: on the two parameters, every contract test errors with
  `ImportError` for the Postgres stores. `make test` is unchanged, since
  the parameters are marked `docker`. Depends on T042 and T048.
- [ ] T050 [P] [US3] Add the Postgres-only Docker tests to
  `tests/contract/test_schema_and_layout.py`. Each asks for its backend
  by name, is skipped elsewhere with the reason, and is added to the
  `schema-and-layout` entry of `tests/contract/cases.py`:
  - `test_postgres_c_locale_refused`: on a database created with
    `LOCALE 'C' TEMPLATE template0`, the first store call raises
    `UnsupportedServerError` naming `datctype` and asking for a UTF-8
    locale such as `C.UTF-8`;
  - `test_postgres_extension_refused`: on a fresh database, a role that
    cannot create `vector` gets `UnsupportedServerError` from
    `ensure_schema`. It names `vector`, not the trusted `pg_trgm`, and
    says an administrator must create it (US3 scenario 3);
  - `test_postgres_schema_contents`: the schema `tenetrag_<id>` holds
    the tables of data-model §6 and both extensions exist (US3
    scenario 2).

  Red: `ImportError` as T049.

### Implementation for User Story 3

- [ ] T051 [US3] Implement the Postgres store, slice 1: setup and
  bookkeeping ([stores.md §1, §2, §4.1](contracts/stores.md#41-postgres),
  [data-model §6](data-model.md#6-postgres-layout), research R4, R5,
  R16):
  - `src/tenetrag/storage/postgres_store/__init__.py`;
  - `ddl.py`: the schema under `pg_advisory_xact_lock`, the tables and
    indexes of §6 (all but the vector tables), the extensions with their
    refusal, the locale check, `meta` with `LAYOUT_VERSION = 1`;
  - `lease.py`: the `writer_lease` row, with one conditional statement
    per call and `SELECT … FOR SHARE` in each write unit;
  - in `writes.py` and `reads.py`: runs, caches, decisions and
    `document_states`;
  - `graph.py` and `vectors.py`: the two classes, with every method not
    yet built raising `NotImplementedError` naming its slice;
  - exports from `tenetrag.storage`, with the driver imported only when a
    store is built;
  - every identifier goes through `_names` and `psycopg.sql.Identifier`,
    and every value is a parameter (FR-034).

  T048 passes. `test_lease.py`, `test_runs_and_caches.py` and the
  setup tests of `test_schema_and_layout.py`, including T050's, pass on
  both Postgres parameters. Depends on T047, T049 and T050.
- [ ] T052 [US3] Implement the Postgres store, slice 2: vectors in
  `postgres_store/vectors.py` (research R6, R11):
  - `ensure_collections` creates `vec_*` tables with HNSW
    `vector_cosine_ops` and the generated `tsv` column with its GIN
    index;
  - `upsert`, `delete`, `delete_documents` and `get_vectors`;
  - `search`: a `LATERAL` over `unnest`, with `SET LOCAL
    hnsw.ef_search = 100` and `hnsw.iterative_scan = relaxed_order`;
  - `search_text`: the R6 split and OR query in one statement;
  - `max_dimensions` 2000;
  - the paired write functions that the graph store calls in steps 1, 2
    and 4.

  `test_vectors.py` and `test_text_search.py` pass on both Postgres
  parameters. Depends on T051.
- [ ] T053 [US3] Implement the Postgres store, slice 3: write units and
  reads, in `postgres_store/writes.py` and `reads.py`:
  - the five steps in one transaction through M0's `transaction()`, one
    statement per table per step, rows passed as arrays;
  - `step_hook` after each step;
  - status changes, orphans and `delete_documents`;
  - reads by id, `entities_in_chunks` and the version reads.

  `test_writes.py`, `test_deletes.py`, `test_statuses.py`,
  `test_provenance.py` and the kill-point tests of `test_kill_points.py`
  pass on both Postgres parameters. Depends on T052.
- [ ] T054 [US3] Implement the Postgres store, slice 4: lookups, degrees
  and hop (research R7, R12):
  - `find_by_identity` through the `identity jsonb_path_ops` index;
  - `find_events`;
  - `match_names` as one union;
  - `search_names` with a transaction-local
    `set_config('pg_trgm.similarity_threshold', …, true)`;
  - `match_document_links`;
  - `refresh_degrees` as one statement;
  - `hop` with `unnest(...) CROSS JOIN LATERAL (… ORDER BY … LIMIT …)`
    and `DESC NULLS LAST`.

  The whole suite passes on both Postgres parameters. Depends on T053.
- [ ] T055 [US3] Run
  `uv run pytest tests/contract -m docker -k "postgres-pg16 or postgres-pg17" -q`.
  Every test passes, unchanged from the reference run (SC-002). Each
  version takes under five minutes, container start included (SC-004,
  Docker half).
  - Check with `psql` that the schema `tenetrag_<index_id>` holds the
    §6 tables and that the extensions are present.
  - Run quickstart §3's negative check by building the store in code on a
    `C`-locale database. The profile form waits for T077.
  - Record SC-009, the recall at 10 of SC-010, and the hub hop time
    (SC-007, Postgres half).

  Try deliberate faults, for example:
  - a session-level `set_config`;
  - `SET` instead of `SET LOCAL` for `hnsw.ef_search`;
  - `commit()` after step 2;
  - the `LIMIT` outside the `LATERAL`;
  - `QueryError` text that appends the DETAIL line.

  A fault that survives gets a test. Run `make check`, and record the red
  runs of T046, T048–T050 and the results here.

**Checkpoint**: Postgres passes the suite on 16 and 17

---

## Phase 6: User Story 4 - The Neo4j store (Priority: P2)

**Goal**: `Neo4jGraphStore` and `Neo4jVectorStore` pass the whole suite
on Neo4j 2026.09 Community, with typed relation edges and `index_id` on
every node. They also run as a split pairing with Postgres vectors.

**Independent Test**: follow
[quickstart.md §4](quickstart.md#4-the-neo4j-store-story-4-sc-002-sc-007-sc-008-sc-011),
including its negative check.
`uv run pytest tests/contract -m docker -k "neo4j" -q` passes on `neo4j`
and on `neo4j-graph+postgres-vectors`.

### Tests for User Story 4

- [ ] T056 [P] [US4] Add `test_neo4j_error_drops_message` to
  `tests/unit/storage/test_neo4j_unit.py` (research R21, the regression
  test that fails first). A scripted `neo4j_error(code, message)` whose
  message holds a planted value from `tests/support/secrets.py` gives a
  `QueryError` that names the code and the address, and not the value.

  Red: the value appears, since `src/tenetrag/storage/neo4j.py` puts
  `exc.message` into the text.
- [ ] T057 [US4] Fix `src/tenetrag/storage/neo4j.py`. The `QueryError`
  for a `Neo4jError` keeps `exc.code` and drops `exc.message`, and the
  text says where to look (the server log). T056 passes, and M0's
  `test_other_server_errors_are_query_errors` passes unchanged or with
  its expected text updated in the same change, said in the Result.
  Depends on T056.
- [ ] T058 [P] [US4] Add the Neo4j halves to
  `tests/unit/storage/test_store_classes.py`:
  - `Neo4jGraphStore` and `Neo4jVectorStore` join the parameters of
    `test_index_id_pattern` and `test_paired_needs_same_connection`;
  - with `neo4j` hidden, building a Neo4j store raises
    `MissingExtraError` naming `neo4j`.

  Red: `ImportError` for `Neo4jGraphStore`.
- [ ] T059 [US4] Add the Neo4j parameters:
  - `tests/support/containers.py` gains `neo4j_server(image)`;
  - `neo4j` (paired) and `neo4j-graph+postgres-vectors` (split, vectors
    in the pg17 container) join the `stores` parameters with the `docker`
    and `enable_socket` marks;
  - in `backends.py`, the Neo4j `row_counts` maps the labels and edge
    types of [data-model §7](data-model.md#7-neo4j-layout) to the
    table names of §6.

  Red: `ImportError` for the Neo4j stores on these parameters. Depends on
  T049 and T058.
- [ ] T060 [P] [US4] Add the Neo4j-only Docker tests to
  `tests/contract/test_schema_and_layout.py`, each skipped elsewhere with
  the reason and added to `schema-and-layout` in `cases.py`:
  - `test_neo4j_constraints_include_index_id`: every uniqueness
    constraint in `SHOW CONSTRAINTS` includes `index_id`;
  - `test_neo4j_vector_indexes_unquantized`: `SHOW INDEXES` shows
    quantization off;
  - `test_neo4j_edge_types_follow_relations`: the edge types written for
    D1 equal D1's relation types (US4 scenario 2);
  - `test_neo4j_new_relation_type`: a merged schema with a new relation
    type gets its schema, and existing data is untouched;
  - `test_neo4j_parallel_edges_per_chunk`: one `OWNER_OF` statement in
    two chunks gives two parallel edges, each with its own quote and
    chunk (US4 scenario 3).

  Red: `ImportError` as T059.

### Implementation for User Story 4

- [ ] T061 [US4] Implement the Neo4j store, slice 1: setup and
  bookkeeping ([stores.md §4.2](contracts/stores.md#42-neo4j),
  data-model §7, research R4, R8, R16):
  - `src/tenetrag/storage/neo4j_store/__init__.py`;
  - `ddl.py`: uniqueness constraints that include `index_id`, range
    indexes, `StoreMeta` with `LAYOUT_VERSION = 1`;
  - `lease.py`: the `WriterLease` node, through `MERGE` and `SET
    l._lock`;
  - runs, caches, decisions and `document_states`;
  - the class shells in `graph.py` and `vectors.py`, and the exports;
  - every query starts with `CYPHER 25`, and every dynamic name comes
    through `_names`.

  T058 passes. `test_lease.py`, `test_runs_and_caches.py` and the setup
  tests of `test_schema_and_layout.py` pass on `neo4j`. Depends on T057,
  T059 and T060.
- [ ] T062 [US4] Implement the Neo4j store, slice 2: vectors in
  `neo4j_store/vectors.py` (research R9, R11):
  - `Collection` nodes;
  - vector indexes with filter properties and quantization off;
  - `SEARCH` for vectors, with `exclude_run` applied after `SEARCH`;
  - full text through `standard-no-stop-words`, with the
    `+index_id:"<id>" +text_norm:(…)` query and escaped terms;
  - `max_dimensions` 4096;
  - the paired write functions.

  `test_vectors.py` and `test_text_search.py` pass on `neo4j`. Depends on
  T061.
- [ ] T063 [US4] Implement the Neo4j store, slice 3: write units and
  reads in `neo4j_store/writes.py` and `reads.py`:
  - the five steps in one `write()` unit;
  - labels and edge types through `$(…)`;
  - deletes through the static union of the schema's relation types;
  - `DETACH DELETE` for orphans;
  - `IN_DOCUMENT` and `TEXT_IN` in step 5;
  - reads by id and the version reads.

  The write-side suite passes on both Neo4j parameters, the split
  crash included. Depends on T062.
- [ ] T064 [US4] Implement the Neo4j store, slice 4: lookups, degrees and
  hop (research R8, R10, R12):
  - `find_by_identity` through `IdentityValue` nodes;
  - `match_names`;
  - `search_names`: candidates from the trigram full-text index of
    `trigram_tokens`, filtered with `_trigram.similarity`;
  - `match_document_links` and `refresh_degrees`;
  - `hop`: `UNWIND $ids … CALL (e) { … ORDER BY … LIMIT $k }` with
    `$any(...)`, and `coalesce(observed_at, date('0001-01-01'))`.

  The whole suite passes on both Neo4j parameters. Depends on T063.
- [ ] T065 [US4] Run `uv run pytest tests/contract -m docker -k "neo4j" -q`.
  Every test passes on both parameters, unchanged from the reference run
  (SC-002), in under five minutes each (SC-004).
  - Check `SHOW CONSTRAINTS` and `SHOW INDEXES` by hand.
  - Run quickstart §4's negative check: the corpus under index `a`,
    every read under `b` returns nothing.
  - Record SC-007 (the hub hop time on Neo4j), SC-008 and SC-011.

  Try deliberate faults, for example:
  - a `MATCH` without `index_id`;
  - quantization on;
  - a folding analyzer;
  - the `LIMIT` outside `CALL`;
  - an untyped relation lookup in step 1.

  A fault that survives gets a test. Run `make check`, and record the red
  runs of T056 and T058–T060 and the results here.

**Checkpoint**: Neo4j passes the suite, paired and split

---

## Phase 7: User Story 5 - A killed run never leaves half a document (Priority: P2)

**Goal**: the consistency floor holds against real server-side kills,
and a lease takeover waits for a unit in flight

**Independent Test**: follow
[quickstart.md §5](quickstart.md#5-killed-runs-story-5-sc-005-sc-006),
including its negative check. Both of its commands pass on every
parameter.

### Tests for User Story 5

- [ ] T066 [P] [US5] Add the server-kill tests to
  `tests/contract/test_kill_points.py`, each added to
  `killed-run-atomicity` in `cases.py` (stores.md §3.4, research R14):
  - `test_postgres_server_kill`. The step hook calls
    `stores.kill_running_unit()` during D2's `INSERT` step:
    - with `open_graph(max_attempts=1)`, the write raises
      `StoreUnavailableError` and D2 keeps its previous version;
    - with the default retry, M0 replays the unit and D2's new version is
      whole;
  - `test_neo4j_server_kill`: the same kill raises `QueryError`, and D2
    keeps its previous version. A second call writes the new version
    whole;
  - each is skipped with the reason on other parameters, and
    `kill_running_unit` skips on the reference store.

  Red: `TypeError` for `open_graph(max_attempts=...)`, and
  `NotImplementedError` from `kill_running_unit`. Both are test support,
  so this red only shows the tests run. Once T068 lands they may pass on
  arrival, since T053 and T063 write each document in one transaction.
  Their can-fail evidence is the deliberate faults of T070.
- [ ] T067 [P] [US5] Add `test_takeover_waits_for_running_unit` to
  `tests/contract/test_lease.py` (stores.md §2). A's unit pauses in its
  step hook on a `threading.Event` after A's 1-second lease has expired.
  B's `acquire_writer` in a thread is still blocked after 0.5 s. Once A
  is released, A's document is committed and B holds fence + 1. It runs
  on every parameter.
- [ ] T068 [US5] Implement, in `tests/support/contract/backends.py`:
  - `ContractStores.kill_running_unit()`, from a second connection:
    - Postgres: `pg_terminate_backend` on the `pg_stat_activity` row
      that is `idle in transaction` and whose last query names the
      test's schema;
    - Neo4j: `SHOW TRANSACTIONS`, then `TERMINATE TRANSACTIONS` on the
      write transaction that is not the caller's own;
  - `open_graph(..., max_attempts=None)`, which opens a second connection
    with that retry setting.

  Both are departures from contract-suite.md §1, recorded in T081.
  Depends on T066 and T067.
- [ ] T069 [US5] Fix whatever T066 and T067 find in the Postgres, Neo4j
  or reference store, each fix with the failing test named in the Result.
  If both pass on arrival, record that, together with the T070 faults
  that show they can fail. Depends on T068.
- [ ] T070 [US5] Run quickstart §5 on every parameter:
  - `uv run pytest tests/contract/test_kill_points.py tests/contract/test_writes.py -q`;
  - `uv run pytest tests/contract/test_kill_points.py -m docker -q`;
  - its negative check: with the `killed-run-atomicity` fault of
    `make faults` in place, the kill-point tests fail on the reference
    store.

  Record SC-005 and SC-006 on every store. Try deliberate faults, for
  example:
  - the Postgres unit commits after step 2;
  - the Neo4j unit writes in auto-commit;
  - the lease check is made without `FOR SHARE`;
  - the Neo4j lease check takes no lock.

  A fault that survives gets a test. Run `make check` and
  `make integration`, and record the results here.

**Checkpoint**: every store keeps each document whole or absent under a
hook, a server kill and a takeover

---

## Phase 8: User Story 6 - The profile names the index and its stores (Priority: P3)

**Goal**: the profile's `index` section, checked at load, and
`open_stores`, which builds and pairs the stores from it

**Independent Test**: follow
[quickstart.md §6](quickstart.md#6-the-profile-names-the-index-story-6),
including its negative check. Then run the `open_stores` snippet of §3
against `make dev-up`.

### Tests for User Story 6

- [ ] T071 [P] [US6] Write `tests/unit/config/test_index.py`, the ten tests
  of [contracts/config.md](contracts/config.md#behaviour-pinned-by-tests):
  - `test_index_optional`;
  - `test_index_id_pattern`;
  - `test_vectors_default_to_graph`;
  - `test_unknown_connection`;
  - `test_dimensions_over_maximum`;
  - `test_capability_override_dimensions`;
  - `test_problems_listed_together`: this is quickstart §6's profile,
    with both lines;
  - `test_index_is_operational`;
  - `test_index_moves_no_hash`;
  - `test_extra_field_refused`.

  Red: `AttributeError` for `profile.index`, and `index` refused as an
  unknown field. This task can start any time after Phase 2.
- [ ] T072 [US6] Implement the index section
  ([data-model §8](data-model.md#8-profile-index-section-delta-to-m0-data-model-2),
  research R17):
  - in `src/tenetrag/config/profile.py`: `IndexId`, `IndexSettings`
    with `vector_connection`, `Profile.index` (operational, default
    `None`), and the load checks of contracts/config.md §2 in one model
    validator that lists every problem;
  - `VECTOR_MAX_DIMENSIONS = {"postgres": 2000, "neo4j": 4096}`;
  - `IndexSettings` and `VECTOR_MAX_DIMENSIONS` are exported from
    `tenetrag.config`.

  T071 passes, and `tests/unit/config` passes unchanged. Depends on T071.
- [ ] T073 [P] [US6] Add `test_max_dimensions_match_config` to
  `tests/unit/storage/test_store_classes.py`. Each store's
  `capabilities.max_dimensions` equals `VECTOR_MAX_DIMENSIONS` for its
  kind. Red: `ImportError` for `VECTOR_MAX_DIMENSIONS` until T072.
- [ ] T074 [P] [US6] Write `tests/contract/test_open_stores.py`
  ([stores.md §5](contracts/stores.md#5-open_stores)). With the fake
  drivers of `tests/support/fake_stores.py`, no Docker:
  - `test_index_required`: a profile with no `index` raises
    `ConfigError` saying to add an `index` section;
  - `test_missing_credential_fails_closed`: a connection with no
    credential and no source raises `MissingCredentialError` naming the
    connection, and no other identity is tried (the fakes record every
    connect, FR-040);
  - `test_paired_when_same_connection` and
    `test_split_when_two_connections`, checking `graph_writes_vectors`;
  - `test_each_connection_opened_once`;
  - `test_closes_on_failure`: a failing `health()` on the second
    connection closes the first;
  - `test_missing_extra`;
  - `test_close_and_context_manager`: each connection is closed once.

  Then one Docker test per backend, `test_open_stores_on_<backend>`,
  marked `docker` and `enable_socket`. It builds the stores from a
  generated profile against the session containers.

  Red: `ImportError` for `open_stores`.

### Implementation for User Story 6

- [ ] T075 [US6] Implement `src/tenetrag/storage/stores.py` with
  `open_stores` and `Stores`, exported from `tenetrag.storage`. It opens
  each named connection once through `open_connection`, runs
  `health()`, builds and pairs the stores, closes what it opened on any
  failure, and runs no DDL. T073 and T074 pass. Depends on T072–T074.
- [ ] T076 [US6] Switch the Docker parameters in
  `tests/support/contract/backends.py` to `open_stores` over a generated
  profile with explicit credentials, so the suite runs the pairing rule
  of stores.md §5 (contract-suite.md §1). The reference parameters stay
  built in code. `uv run pytest tests/contract -m docker -q` passes
  unchanged. Depends on T075.
- [ ] T077 [US6] Run quickstart §6 with its negative check. Then, against
  `make dev-up`, run §3's `open_stores` snippet (`graph_writes_vectors`
  is `True`, and `max_dimensions` is 2000), and §3's negative check
  through a profile that points at a `C`-locale database. Run
  `make check` and `make integration`, and record the red runs of
  T071, T073 and T074 and the results here.

**Checkpoint**: an operator names the index and its stores in the profile

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: docs that change with the code (FR-049, research R22), and
the final validation

- [ ] T078 [P] Update `ARCHITECTURE.md`:
  - the `engine` row: only the `text/` package so far, importing protocols,
    config, packs and the standard library, under its forbidden
    contract;
  - the `protocols` row gains the store protocols and records;
  - the `storage` row gains `_names`, `_trigram`, the two store
    subpackages and `open_stores`;
  - the layers read `engine | llm | storage`;
  - `tests/support/reference` and `tests/contract` are named as test
    support.
- [ ] T079 [P] Update `docs/product/engine-brief.md` (research R22):
  - §1: the Chunk→Document edge is `IN_DOCUMENT`; documents gain
    `code_norm` and `title_norm`; entity attributes are computed on read
    from attribute sources; entities, aliases and events keep their
    creating run; the Neo4j node list adds `IdentityValue`,
    `ResolutionDecision`, `WriterLease`, `StoreMeta`, `Collection` and
    the vector labels;
  - §6.1 and §6.5: `renew_writer` and `release_writer`, the lease
    record on both backends, and trigram `search_names` on Neo4j;
  - §6.1 and §6.2 link to `src/tenetrag/protocols/stores.py` instead of
    keeping a copy;
  - §7: the tone-mark rule of R18 (rewritten with ADR 0025; check it
    against the code);
- [ ] T080 [P] Update the platform and run docs:
  - `docs/product/domain-packs.md`: `PART_OF` becomes `IN_DOCUMENT` in
    the infrastructure table;
  - `docs/reference/neo4j-platform.md`: the [run] facts of research R8
    to R12 replace "untested" for the shapes this feature uses.
    Paraphrase and link; never paste Neo4j documentation text;
  - `docs/guides/local-stack.md`: how to run the contract suite on
    Docker (`make integration`, one backend with `-k`), and
    `make faults`.
- [ ] T081 [P] Update the records of what landed:
  - `docs/tech-debt.md`: `halfvec` above 2,000 dimensions on Postgres
    (research R11), plus any gap found in the run tasks;
  - `contracts/contract-suite.md`: the departures:
    - `ContractStores` lives in `tests/support/contract/backends.py`;
    - its extra members `layout_module`, `row_counts()`,
      `text_in_links()` and `open_graph(max_attempts=...)`;
    - the writes.py helpers `edited_write`, `expected_counts` and
      `snapshot`;
    - the Docker parameters were built in code until T076;
    - `test_case_map.py` exempts itself;
    - anything else recorded in a Result;
  - `AGENTS.md`: the status line (003 implemented, 004 next) and a
    `make faults` line in Commands. Keep it under 150 lines.
- [ ] T082 Run [quickstart.md](quickstart.md) end to end, §1 to §7,
  including every negative check and the "Done when" list:
  - `make check` and `make integration` on Python 3.11 and on 3.14, the
    second in a scratch environment
    (`UV_PROJECT_ENVIRONMENT=$SCRATCH/venv314 uv sync --locked --all-extras --python 3.14`).
    CI is off, so this stands in for its matrix;
  - `make faults` exits 0;
  - §7's `lint-imports` output and its negative check.

  Fill in "Results" in `quickstart.md`: one line per row, with the
  SC-004 timings, SC-007 per Docker backend, SC-010 per backend, and the
  unit suite's duration, in the form of 002's. Depends on T078–T081.
- [ ] T083 Mark `spec.md` Implemented. Record in this task's Result a map
  from every FR and SC to the tests or quickstart sections that show it,
  in the form of 002's T054, naming each gap (such as CI being off).
  Depends on T082.

---

## Dependencies & Execution Order

### Phase dependencies

- Setup (T001–T002) runs first. T001 and T002 touch different files.
- Foundational (T003–T008) needs Setup and blocks every story.
- US1 (T009–T032) needs Foundational. It is the MVP.
- US2 (T033–T045) needs US1's protocols, fixture helpers and reference
  store.
- US3 (T046–T055) needs US2: the case map must be complete before a
  backend adds tests to it, and a backend must pass the whole suite.
- US4 (T056–T065) needs US2 and T047's `_names`. The
  `neo4j-graph+postgres-vectors` parameter needs US3's
  `PostgresVectorStore` (T052). The R21 fix (T056, T057) can land at any
  time.
- US5 (T066–T070) needs US3 and US4.
- US6 (T071–T077) needs US3 and US4 for `open_stores`. Its config half
  (T071, T072) needs only Phase 2.
- Polish (T078–T083) needs every story it documents.

### Within each story

- Tests are written first and must fail. Then come implementation and
  the story's run task (T032, T045, T055, T065, T070, T077).
- In US1, the shapes come first (records, then protocols, then
  `store_schema`). Then come the fixture helpers, the reference store
  skeleton and the fixture. Then the contract test files, and the
  reference store last, by method group.
- In US3 and US4, the unit tests and parameters come first. The store
  is then built in four slices, setup, vectors, writes and lookups, each
  turning more of the suite green.
- A test added to `tests/contract/` after T042 is added to its case in
  `cases.py` in the same task, or `test_case_map.py` fails.
- A test that passes on arrival is recorded as such, with the fault that
  shows it can fail.

### Parallel opportunities

- Setup: T001 and T002 together.
- Foundational: T003, T005 and T007 together, then T004, T006 and T008
  together.
- US1: T009, T010, T011 and T015 together. Once T019 is done, T020–T028
  together.
- US2: T033–T037 together. T041 can be written alongside T038–T040.
- US3: T046, T048 and T050 together. US4: T056, T058 and T060 together.
- US4's `neo4j` parameter and slices T061–T064 can run alongside US3's
  slices once T047 and T049 are done. Only the split parameter waits for
  T052.
- US5: T066 and T067 together.
- US6: T071 any time after Phase 2. T073 and T074 together.
- Polish: T078–T081 together.

---

## Parallel Example: User Story 1

```bash
# Unit tests and helper tests first, all at once (different files):
Task: "Write tests/unit/protocols/test_records.py"
Task: "Write tests/unit/protocols/test_stores.py"
Task: "Write tests/unit/packs/test_store.py"
Task: "Write tests/unit/test_support_contract.py, part 1"

# After the fixture (T019), the contract test files together:
Task: "Write tests/contract/test_writes.py"
Task: "Write tests/contract/test_deletes.py"
Task: "Write tests/contract/test_statuses.py"
Task: "Write tests/contract/test_provenance.py"
Task: "Write tests/contract/test_lease.py"
Task: "Write tests/contract/test_runs_and_caches.py"
Task: "Write tests/contract/test_schema_and_layout.py"
Task: "Write tests/contract/test_vectors.py"
Task: "Write tests/contract/test_text_search.py"
```

---

## Implementation Strategy

### MVP first

1. Setup, then Foundational.
2. US1: the protocols, the fixture helpers, and a reference store that
   holds the corpus and passes the write-side suite offline.
3. Stop and validate quickstart §1. Every later story runs this suite or
   builds on these protocols.

### Incremental delivery

1. US2: lookups, hop, isolation, kill points, the case map and the
   faults. Validate quickstart §2. Both P1 stories are then done, and
   feature 004 can start against the reference store.
2. US3 (Postgres), then US4 (Neo4j). Validate quickstart §3 and §4 after
   each. US4's paired parameter can run alongside US3.
3. US5 (server kills), then US6 (profile and `open_stores`). Validate
   quickstart §5 and §6.
4. Polish: docs, the end-to-end quickstart on 3.11 and 3.14, and the spec
   marked Implemented.

## Notes

- One commit per phase, on `main`, made and pushed at the phase's
  checkpoint with `make check` green, after the `git status` and grep
  check for adopter material. The red run of each test task is recorded
  in the phase's Result, since no test commit shows it.
- No dependency is added (plan.md). Any that turns out to be needed goes
  through M0's dependency gate (M0 T005) first.
- A task that changes a module boundary updates `ARCHITECTURE.md` in the
  same change. T078 collects this feature's changes.
- CI is off, so the Docker parameters run only locally, through
  `make integration`. Each Docker run task records its timings.
- Every fixture name is fictional. No adopter document, name or figure
  enters a fixture, a test or an error message.
- Estimate: about 13 working days (plan.md): four for the protocols, the
  reference store and the suite (US1, US2), four for Postgres (US3), and
  five for Neo4j (US4). US5 and US6 fit inside them.
