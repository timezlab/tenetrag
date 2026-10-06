---

description: "Task list for the SDK foundation (M0)"
---

# Tasks: SDK foundation (M0)

**Input**: Design documents from `specs/001-sdk-foundation/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: Required. The constitution (Development Workflow, Tests)
overrides the template's "tests are optional" note. In every story phase,
write the tests first and watch them fail before implementing.

**Organization**: Tasks are grouped by user story. The stories are layered.
US2's profile models feed US3, US4 and US5, and US3's credentials feed
US4 and US5. Each story's tests still run on their own (see
Dependencies).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: the user story the task belongs to (US1–US5)
- Paths are from the repository root. Layout: `src/tenetrag/`, `tests/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: package, tooling configuration and the locked dependency set

- [X] T001 Create `pyproject.toml` with:
  - project `tenetrag`, version `0.1.0.dev0`, `requires-python = ">=3.11"`,
    license `Apache-2.0`, and hatchling as the build backend over a `src/`
    layout;
  - base dependencies `pydantic>=2.13,<3`, `PyYAML>=6.0.3`,
    `jsonschema>=4.26`;
  - extras `openai = ["openai>=3.24,<4"]`,
    `databricks = ["openai>=3.24,<4", "databricks-sdk>=0.146"]`,
    `neo4j = ["neo4j>=6.3.1,<7"]` and
    `postgres = ["psycopg[binary]>=3.3.6,<4", "psycopg-pool>=3.3.3,<4"]`;
  - `[dependency-groups] dev` with ruff, mypy, types-PyYAML, pytest,
    pytest-socket, import-linter and `testcontainers[neo4j]`;
  - `[tool.uv] exclude-newer = "24 hours"`.

  Use the research.md version table.
- [X] T002 [P] Add `LICENSE` with the official Apache-2.0 text, and
  `NOTICE` naming TenetRAG's copyright plus psycopg and psycopg-pool under
  LGPL-3.0-only, as ADR 0017 requires.
- [X] T003 [P] Create the package skeleton:
  - `src/tenetrag/__init__.py` with `__version__`, `src/tenetrag/py.typed`;
  - empty `__init__.py` files in `src/tenetrag/protocols/`, `config/`,
    `auth/`, `llm/` and `storage/`;
  - `tests/unit/`, `tests/integration/` and `tests/live/` with
    `__init__.py` where pytest needs them;
  - `.venv/`, `.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/`, `dist/`
    and `build/` appended to `.gitignore`.
- [X] T004 Add the tool configuration to `pyproject.toml`:
  - ruff: line length 100, rules `E F W I B UP S SIM RUF ANN PT TID BLE N`,
    `tests/**` ignoring `S101` and `ANN`, `COM812` and `ISC001` off;
  - mypy: `strict = true`, `packages = ["tenetrag"]`, the `pydantic.mypy`
    plugin with `init_forbid_extra`, `init_typed` and
    `warn_required_dynamic_aliases`;
  - pytest: `addopts = "--strict-markers --disable-socket"`, markers
    `docker` and `live`, `testpaths = ["tests"]`.

  Depends on T001.
- [X] T005 Run the dependency gate and lock:
  1. Run `uv lock`, so `exclude-newer` applies.
  2. Confirm each direct dependency's locked version is older than
     24 hours and matches research.md, adding `types-PyYAML`'s license and
     date to research.md.
  3. Query `https://api.osv.dev/v1/querybatch` for every package in
     `uv.lock`, transitive ones included. Save the request to a scratch
     file, not a shell pipe.
  4. Record "0 advisories" or the IDs in research.md, and stop if any
     `MAL-` entry appears.
  5. Run `uv sync --locked --all-extras` and commit-ready `uv.lock`.

  Depends on T001 and T004.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: errors, test harness and retry policy that every story uses

**⚠️ CRITICAL**: no story work begins until this phase is complete

- [X] T006 [P] Write `tests/unit/test_errors.py`. It asserts:
  - the hierarchy of data-model §1;
  - `ConfigError` is a `ValueError`;
  - every class is re-exported from `tenetrag.protocols` and `tenetrag`;
  - `StructuredOutputError` carries `strategy` and `attempts`.
- [X] T007 Implement `src/tenetrag/protocols/errors.py`, stdlib only,
  following data-model §1. Re-export it from
  `src/tenetrag/protocols/__init__.py` and `src/tenetrag/__init__.py`, so
  T006 passes.
- [X] T008 [P] Create `tests/conftest.py` and
  `tests/integration/conftest.py`.
  - **Root conftest:**
    - registers the markers;
    - adds a fixture that clears every `OPENAI_*`, `DATABRICKS_*`,
      `ARM_*`, `NEO4J_*` and `PG*` variable for each test.
  - **Integration conftest:**
    - applies `enable_socket` to every test under it;
    - skips with "Docker not available" when the Docker daemon cannot be
      reached;
    - holds the pinned image references: `neo4j:2026.09.0-community`,
      `pgvector/pgvector:0.8.7-pg16` and `-pg17`, each with its digest
      resolved through `docker buildx imagetools inspect` or the Docker
      Hub API when written.
- [X] T009 [P] Create `tests/support/secrets.py`.
  - `PLANTED` holds distinctive fake secret strings, such as
    `sk-planted-…` and `pw-planted-…`.
  - `assert_no_secret(*texts)` checks given strings.
  - `assert_exception_clean(exc)` walks `__cause__` and `__context__`,
    checking `str` and `repr` at each level.
  - `assert_logs_clean(caplog)` checks captured log records.
- [X] T010 [P] Write `tests/unit/test_retry.py`. It asserts:
  - attempts stop at `max_attempts`, and total time stops at
    `max_total_seconds`, using an injected clock and sleep;
  - full-jitter backoff stays within bounds;
  - `Retry-After` seconds and `retry-after-ms` replace the computed delay
    only when they fit the remaining budget;
  - the `reauth` verdict calls the invalidate hook once and does not
    consume an attempt;
  - a second `reauth` becomes `fail`;
  - `fail` re-raises at once.
- [X] T011 Implement `src/tenetrag/_retry.py`, stdlib only, following
  data-model §6 and research R10:
  - `RetryPolicy` built from `RetrySettings` values;
  - `Verdict` (`RETRY` with an optional delay, `REAUTH`, `FAIL`);
  - `run_with_retry(fn, classify, *, on_reauth, clock, sleep)`.

  T010 must pass.

**Checkpoint**: errors, test harness and retry policy are ready

---

## Phase 3: User Story 1 - Green gates from a fresh clone (Priority: P1) 🎯 MVP

**Goal**: one command runs every gate, locally and in CI, and import
rules are enforced by a tool

**Independent Test**: on a clean machine with only Python, uv and Docker,
follow [quickstart.md §1](quickstart.md#1-gates-from-a-fresh-clone-story-1-sc-001-sc-002-sc-008).
Then add `import neo4j` to `src/tenetrag/protocols/models.py`, and
`lint-imports` fails.

### Tests for User Story 1

- [X] T012 [P] [US1] Write `tests/unit/test_base_import.py`. It starts a
  subprocess (`sys.executable -c "import tenetrag, sys; print(sorted(sys.modules))"`)
  and asserts that none of `openai`, `httpx2`, `httpx`, `databricks`,
  `neo4j`, `psycopg` or `psycopg_pool` is loaded (FR-004, SC-008).
- [X] T013 [P] [US1] Write `tests/unit/test_network_blocked.py`. It
  asserts that opening a TCP socket in a unit test raises pytest-socket's
  `SocketBlockedError`, which proves FR-002's guard is active.

### Implementation for User Story 1

- [X] T014 [US1] Add the import-linter contracts of research R5 to
  `pyproject.toml` (`[tool.importlinter]`):
  - a forbidden contract keeping `tenetrag.protocols` from importing any
    other `tenetrag` module;
  - `tenetrag.config` may import only `tenetrag.protocols`;
  - `tenetrag.auth` may import only `config` and `protocols`;
  - an independence contract between `tenetrag.llm` and
    `tenetrag.storage`;
  - forbidden contracts keeping `protocols`, `config` and `auth` from
    importing `openai`, `databricks`, `neo4j` and `psycopg`, except
    `tenetrag.auth.databricks` for `databricks`.

  Then run `uv run lint-imports`.

  Built as one exhaustive `layers` contract plus two `forbidden`
  contracts; research R5 "As built" explains why.
- [X] T015 [P] [US1] Create `Makefile` with these targets:
  - `format-check` (`uv run ruff format --check .`);
  - `lint` (`uv run ruff check .`);
  - `types` (`uv run mypy`);
  - `imports` (`uv run lint-imports`);
  - `test` (`uv run pytest -m "not docker and not live"`);
  - `integration` (`uv run pytest -m docker`);
  - `check`, which runs the first five in order and stops at the first
    failure.
- [X] T016 [P] [US1] Create `.github/workflows/ci.yml`:
  - triggers: `push` and `pull_request`, with `permissions: contents:
    read`;
  - pins: `actions/checkout` pinned by its full SHA for v7.0.1 (resolve
    with `git ls-remote https://github.com/actions/checkout v7.0.1`), and
    `astral-sh/setup-uv@c18668ad3cf93ea998bef934396af7bb5c839dc7 # v10.2.0`;
  - job `gates`, with matrix Python 3.11 and 3.14: `uv sync --locked
    --all-extras`, then `make check`;
  - job `integration`, on Python 3.14: `uv sync --locked --all-extras`,
    then `make integration`.
- [X] T017 [US1] Fill the Commands section of `AGENTS.md` with the exact
  commands of T015 and the setup line `uv sync --locked --all-extras`.
  Replace "Not set up yet" and keep `AGENTS.md` under 150 lines.
- [X] T018 [US1] Run `make check` on the skeleton, and run the negative
  checks of quickstart §1: a formatting fault, a type error, a forbidden
  import and a failing test each fail their gate. Revert each one, and
  note the results in the task log.

  Result (2026-10-06): `make check` passes in about 1 s, with 87 unit
  tests, and the CI sequence passes locally on Python 3.11.14 and 3.14.8.
  Each fault stopped `make check` at its own gate with exit 2:
  - `x=1` in `llm/__init__.py` stopped at `ruff format --check`;
  - `count: int = "one"` stopped at `mypy` (`[assignment]`);
  - `import neo4j` in `protocols/models.py` stopped at `lint-imports`,
    naming `tenetrag.protocols.models -> neo4j`;
  - a failing unit test stopped at `pytest` (1 failed, 87 passed).

**Checkpoint**: gates are green and enforced. MVP reached.

---

## Phase 4: User Story 2 - Load and validate a profile (Priority: P1)

**Goal**: a validated profile from YAML or dict, each field phased, stage
hashes from index-time fields only

**Independent Test**: `uv run pytest tests/unit/config -q` passes with no
network or store. [quickstart.md §2](quickstart.md#2-profile-and-stage-hashes-story-2-sc-003-sc-004)
runs as written.

### Tests for User Story 2

- [ ] T019 [P] [US2] Add the synthetic fixture profiles
  `tests/fixtures/profiles/selfhosted.yaml` and `databricks.yaml`, copied
  from the two examples in [contracts/config.md](contracts/config.md), and
  `minimal_fake.yaml`, with three fake models.
- [ ] T020 [P] [US2] Write `tests/unit/config/test_loading.py` with the
  tests of contracts/config.md `test_duplicate_key_rejected`,
  `test_unknown_and_invalid_reported_together` and
  `test_secret_like_key_hint`, plus:
  - an empty document raises `ConfigError`;
  - a `!!python/object` tag is rejected;
  - an unreadable path raises `ConfigError` naming the path;
  - a loaded `Profile` is frozen;
  - `profile_from_dict` and `profile_from_yaml` give equal profiles.
- [ ] T021 [P] [US2] Write `tests/unit/config/test_phases.py`. It covers
  `test_every_leaf_has_phase` on `Profile`, plus synthetic models
  showing that:
  - a leaf with no marker fails, naming its path;
  - a `Content()` leaf with no phased ancestor fails;
  - an `Operational()` leaf under `IndexTime` resolves to query-time;
  - `models.answer.model` resolves to query-time and
    `models.extraction.model` to index-time `extract`.
- [ ] T022 [P] [US2] Write `tests/unit/config/test_hashing.py` with:
  - `test_hash_ignores_query_time`, `test_hash_embedding_only`,
    `test_hash_extraction_only`, `test_hash_default_equals_omitted` and
    `test_hash_golden` (pin the hashes of `selfhosted.yaml` and
    `databricks.yaml` after the first green run);
  - a key-order and YAML-vs-dict equality test;
  - a check that every `Stage` has a hash.

### Implementation for User Story 2

- [ ] T023 [P] [US2] Implement `src/tenetrag/config/phases.py`:
  - `Phase` and `Stage` enums, from data-model §8;
  - marker classes `IndexTime(stage)`, `QueryTime`, `Content` and
    `Operational`;
  - `field_phases(model)`, which walks `model_fields` recursively through
    nested models, unions and mappings, resolves markers by the
    nearest-phased-ancestor rule, and raises `ConfigError` listing the bad
    paths.
- [ ] T024 [P] [US2] Implement `src/tenetrag/config/sources.py`, the
  `CredentialSource` discriminated union on `kind` from data-model §3.
  - Variants: `none`, `api_key(env)`, `basic(user, password_env)`,
    `pat(token_env)`, `oauth_m2m(client_id, client_secret_env)`,
    `oauth_u2m`, `cli_profile(name, config_file=None)` and `runtime`.
  - Every model is frozen with `extra="forbid"`.
  - Environment variable names are validated against
    `^[A-Za-z_][A-Za-z0-9_]*$`.
  - Every leaf is marked `Operational()`.
- [ ] T025 [US2] Implement `src/tenetrag/config/profile.py`, following
  the tables of data-model §2, §5, §6 and §7:
  - `RetrySettings`, `PoolSettings`, `TlsMode` (`auto`, `require`,
    `verify`, `off`), `Neo4jSettings`, `PostgresSettings` (discriminated
    by `kind`);
  - `CapabilityOverrides` (every field optional);
  - `ChatModelSettings` and `EmbeddingModelSettings`, each discriminated
    by `provider`, with the per-provider required fields of data-model §2
    (`base_url` for `openai_compatible`; `workspace_url` for `databricks`
    unless the credential is `cli_profile` or `runtime`);
  - `ModelsSettings` with `extraction`
    (`Annotated[…, IndexTime(Stage.EXTRACT)]`), `answer` (`QueryTime()`)
    and `embedding` (`IndexTime(Stage.EMBED)`);
  - `Profile`, with `language` as `IndexTime(Stage.EXTRACT)`.

  Every leaf gets exactly one marker. All models are frozen with
  `extra="forbid"`. Depends on T023 and T024.
- [ ] T026 [US2] Implement `src/tenetrag/config/loading.py` with
  `load_profile`, `profile_from_yaml` and `profile_from_dict`:
  - a `yaml.SafeLoader` subclass whose `construct_mapping` raises on
    duplicate keys, with the line number;
  - Pydantic `ValidationError` converted into one `ConfigError`, with one
    dotted-path line per problem;
  - the credential hint added for secret-like key names.

  Export the names from `src/tenetrag/config/__init__.py`. Depends on
  T025.
- [ ] T027 [US2] Implement `src/tenetrag/config/hashing.py` with
  `stage_hashes(profile)`, following data-model §8:
  - collect the index-time leaves per stage through `field_phases`;
  - canonical JSON of `{"format": 1, "stage", "fields"}` with sorted keys,
    compact separators, `ensure_ascii=False` and NFC strings;
  - the result is `"sha256:<hex>"` for every `Stage`.

  Depends on T023 and T025.
- [ ] T028 [US2] Run `uv run pytest tests/unit/config -q`, pin the golden
  hashes in `test_hashing.py`, and run `make check`.

**Checkpoint**: profiles load, fail loudly, and hash by stage

---

## Phase 5: User Story 3 - Supply credentials that fail closed (Priority: P2)

**Goal**: explicit or profile-named credentials, the same identity on
refresh, secrets masked, warnings for the accepted SDK environment reads
(ADR 0018)

**Independent Test**: `uv run pytest tests/unit/auth -q` passes with fake
token sources, and [quickstart.md §3](quickstart.md#3-credentials-fail-closed-story-3-sc-005-sc-006)
holds with ambient variables exported.

### Tests for User Story 3

- [ ] T029 [P] [US3] Write `tests/unit/auth/test_secret.py`. It covers:
  - `repr` and `str` are `Secret('***')`;
  - `reveal()` returns the value;
  - an empty value and an unset or empty `from_env` name raise
    `CredentialSourceError`, naming the variable and never a value.
- [ ] T030 [P] [US3] Write `tests/unit/auth/test_resolve.py` with these
  tests from contracts/auth.md: `test_missing_credential` (with no socket
  opened), `test_ambient_vars_never_read`, `test_named_env_unset`,
  `test_override_wins` and `test_mismatch`. Add one parametrized test over
  the accepted-kinds table of contracts/auth.md.
- [ ] T031 [P] [US3] Write `tests/unit/auth/test_token_source.py`. It
  covers:
  - `test_refresh_same_identity`;
  - refresh happens once when 8 threads ask together;
  - `invalidate()` then rejection raises `CredentialRejectedError`;
  - `test_obo_not_refreshed`;
  - a token near `expires_at` is refreshed before use.
- [ ] T032 [P] [US3] Write `tests/unit/auth/test_databricks.py`. It
  injects a fake `Config` factory, so no Databricks SDK network is used,
  and covers:
  - `test_runtime_outside_databricks`;
  - `test_u2m_needs_terminal`, with `isatty` patched;
  - `test_databricks_env_warning`: one warning, the variable named and
    not its value, and once per process;
  - a missing CLI profile and an expired CLI login (the fake raises
    `ValueError`) map to `CredentialSourceError`, which names the profile
    and says to run `databricks auth login --profile <name>`;
  - `pat` and `obo` never import `databricks.sdk`;
  - `workspace_client` takes its headers from `client.config.authenticate()`.
- [ ] T033 [P] [US3] Write `tests/unit/test_secrets_never_leak.py`, part 1:
  - for every credential kind, build it with `PLANTED` values, then print
    it, log it at DEBUG and raise each auth error built from it;
  - check everything with the `tests/support/secrets.py` helpers.

### Implementation for User Story 3

- [ ] T034 [US3] Implement `src/tenetrag/auth/credentials.py`, following
  data-model §4 and contracts/auth.md:
  - `Secret`, `AccessToken`, `CredentialKind`, and the frozen
    `Credential` with `kind`, `identity`, `source` and `refreshable`;
  - private `_TokenSource`: a cached token, a refresh margin of 60 s
    before `expires_at`, a `threading.Lock` around refresh, and
    `invalidate()` that allows one refresh before
    `CredentialRejectedError`;
  - the `Credentials` constructors `none`, `api_key`, `basic`,
    `token_provider`, `pat`, `obo`, `oauth_m2m`, `oauth_u2m`,
    `cli_profile`, `runtime` and `workspace_client`. The Databricks ones
    delegate to `auth/databricks.py` lazily.
- [ ] T035 [US3] Implement `src/tenetrag/auth/databricks.py`, following
  research R11:
  - `databricks.sdk` is imported lazily inside functions, and its absence
    raises `MissingExtraError("databricks")`.
  - Builders for each kind:
    - `oauth_m2m`: `Config(host, client_id, client_secret,
      auth_type="oauth-m2m")`;
    - `oauth_u2m`: `Config(host, auth_type="external-browser")`, after
      checking that `sys.stdin.isatty()` and `sys.stdout.isatty()` are
      both true;
    - `cli_profile`: `Config(profile=name, config_file=…)`;
    - `runtime`: `Config(auth_type="runtime")`, after checking that
      `DATABRICKS_RUNTIME_VERSION` is present.
  - A token-source adapter reads `config.authenticate()["Authorization"]`.
    SDK `ValueError`s map to `CredentialSourceError`.
  - `warn_databricks_env()` logs one warning per process naming any set
    `DATABRICKS_*`, `ARM_*` or `GOOGLE_CREDENTIALS` variables.
  - `ModelServingUserCredentials` and `get_user_workspace_client` are
    never used. Add a comment citing ADR 0003.

  Depends on T034.
- [ ] T036 [US3] Implement `src/tenetrag/auth/resolve.py`:
  - `TargetKind` and the accepted-kinds table;
  - `resolve_credential(target, target_name, source, override)`: the
    override wins, a profile `CredentialSource` becomes a `Credential`
    (reading only the named variable), and the function raises
    `MissingCredentialError` or `CredentialMismatchError`.

  Export the public names from `src/tenetrag/auth/__init__.py`. Depends
  on T034 and T035.
- [ ] T037 [US3] Run `uv run pytest tests/unit/auth tests/unit/test_secrets_never_leak.py -q`,
  then `make check`, and run quickstart §3 with ambient variables
  exported.

**Checkpoint**: credentials fail closed and never leak

---

## Phase 6: User Story 4 - Call chat and embedding models through one interface (Priority: P2)

**Goal**: Databricks, OpenAI-compatible and fake models behind
`ChatModel` and `EmbeddingModel`, with capability profiles, structured
output strategies and the shared retry policy

**Independent Test**: `uv run pytest tests/unit/llm -q` passes on
`httpx2.MockTransport` with no network. `test_same_code_three_providers`
proves SC-009.

### Tests for User Story 4

- [ ] T038 [P] [US4] Write `tests/unit/llm/test_capabilities.py`:
  - prefix lookup picks the Databricks profile for `databricks-*` models;
  - `claude-sonnet-5` drops temperature;
  - an unknown model gets `[prompt_parse]` with no schema limits;
  - overrides replace single fields;
  - creating an embedding model without a known `max_input_tokens` raises
    `ConfigError`.
- [ ] T039 [P] [US4] Write `tests/unit/llm/test_structured.py`: the
  strategy order, the forbidden keyword and property-count checks before
  any call, re-asking with the validation error appended,
  `StructuredOutputError(strategy, attempts)`, and jsonschema with an
  empty registry refusing a remote `$ref`.
- [ ] T040 [P] [US4] Write `tests/unit/llm/test_openai_compatible.py`.
  It drives an `httpx2.MockTransport`, passed as `http_client`, and
  covers the contracts/llm.md tests `test_strategy_order` (with request
  bodies matching the research R9 table), `test_parse_retry_then_error`,
  `test_truncation`, `test_rate_limit_retry_after` (with an injected
  sleep), `test_auth_fails_fast`, `test_reauth_once`,
  `test_temperature_dropped`, `test_forbidden_schema`,
  `test_usage_unknown_not_zero`, `test_openai_env_not_used_for_key` and
  `test_openai_env_warning`.
- [ ] T041 [P] [US4] Write `tests/unit/llm/test_embeddings.py`:
  - `test_embedding_order_and_dimension` and `test_prefixes`;
  - empty and over-long texts are rejected before any request, by
    position;
  - `encoding_format: "float"` is sent;
  - batching respects `batch_size`.
- [ ] T042 [P] [US4] Write `tests/unit/llm/test_fake.py`. It covers
  `test_fake_deterministic`, scripted exceptions, the callable script,
  call recording, and different vectors for query and passage prefixes.
- [ ] T043 [P] [US4] Write `tests/unit/llm/test_same_code_three_providers.py`.
  One function takes a `Profile` and calls `generate` with a schema and
  `embed_documents`. It runs against fake, OpenAI-compatible (mock) and
  Databricks (mock) profiles, changing only the profile (SC-009).
- [ ] T044 [P] [US4] Write `tests/live/test_databricks_live.py`, marked
  `live`.
  - It is skipped unless `TENETRAG_LIVE_DATABRICKS_PROFILE` is set.
  - It runs one chat call with a small schema and one embedding call.
  - It asserts the embedding dimension against the shipped profile.
  - With `DATABRICKS_HOST` set, it expects the warning.

### Implementation for User Story 4

- [ ] T045 [P] [US4] Implement `src/tenetrag/protocols/models.py`,
  stdlib only, following data-model §9 and contracts/llm.md:
  - `Message`, `Usage` and `ChatResult` as frozen dataclasses;
  - `ChatModel` and `EmbeddingModel` as `Protocol`s.

  Re-export them from `src/tenetrag/protocols/__init__.py`.
- [ ] T046 [P] [US4] Implement `src/tenetrag/llm/capabilities.py`:
  - `Strategy`, `CapabilityProfile` and `capability_profile(provider,
    model, overrides)`;
  - shipped profiles only for documented facts:
    - Databricks endpoints: forbidden `$ref`, `anyOf`, `oneOf`, `allOf`
      and `pattern`, at most 64 properties, strategies `[native_schema,
      tool_call, json_mode, prompt_parse]`;
    - `databricks-claude-sonnet-5`: no temperature or top_p;
    - OpenAI `gpt-4o`, `gpt-4.1` and `gpt-5` families: `native_schema`
      first;
    - the conservative default for unknown models.
  - Each shipped entry gets a comment with its source link from
    `docs/reference/databricks-platform.md`.
  - `databricks-qwen3-embedding-0-6b` is marked unverified until T044
    confirms its dimension.
- [ ] T047 [US4] Implement `src/tenetrag/llm/structured.py`:
  - the schema checks against the profile limits;
  - the request fragments per strategy (research R9);
  - parsing of text, tool-call arguments or JSON;
  - `Draft202012Validator` with `registry=referencing.Registry()`;
  - the re-ask loop up to `parse_retries`;
  - `OutputTruncatedError` on `finish_reason == "length"`.

  Depends on T045 and T046.
- [ ] T048 [P] [US4] Implement `src/tenetrag/llm/fake.py` with
  `FakeChatModel` and `FakeEmbeddingModel`, following data-model §10.
  Fake chat applies the same `structured.py` validation to scripted data.
  Depends on T045 and T047.
- [ ] T049 [US4] Implement `src/tenetrag/llm/openai_compatible.py`:
  - **Classes:** `OpenAICompatibleChatModel` and
    `OpenAICompatibleEmbeddingModel`.
  - **Client construction** (research R9):
    - `openai.OpenAI(api_key=<callable>, base_url=…, max_retries=0,
      timeout=…, http_client=<optional, for tests>)`;
    - `openai` imported lazily, with `MissingExtraError("openai")` when
      it is absent;
    - `api_key="unused"` for `none`.
  - **Calls:** every call goes through `_retry.run_with_retry`, with the
    classification of research R10 and `reauth` wired to the
    credential's `invalidate()`.
  - **Results:** usage maps to `Usage`, with `None` when absent.
    Embeddings send `encoding_format="float"`, are batched by
    `batch_size`, and are reordered by index, with a dimension check.
  - **Warnings:** one per process for a set `OPENAI_ORG_ID`,
    `OPENAI_PROJECT_ID` or `OPENAI_CUSTOM_HEADERS`.
  - **Logging:** prompt and response text are logged only when
    `log_content` is true.

  Depends on T011, T036, T046 and T047.
- [ ] T050 [US4] Implement `src/tenetrag/llm/databricks.py`:
  `DatabricksChatModel` and `DatabricksEmbeddingModel` subclass the
  OpenAI-compatible pair. They set `base_url =
  f"{workspace_url}/serving-endpoints"`, take the host from the
  credential when the source is `cli_profile` or `runtime`, and use the
  Databricks capability profiles. Depends on T049.
- [ ] T051 [US4] Implement `chat_model_from_settings` and
  `embedding_model_from_settings` in `src/tenetrag/llm/__init__.py`. They
  pick the class by `provider`, call `resolve_credential` with the target
  name, and pass the capability profile and settings. Export the classes,
  `Strategy`, `CapabilityProfile` and `capability_profile`. Depends on
  T048 to T050.
- [ ] T052 [US4] Extend `tests/unit/test_secrets_never_leak.py` with part 2:
  - model calls with `PLANTED` keys go through 401, 429 and malformed
    responses on `MockTransport`;
  - check the exceptions, `caplog` and the model `repr`.

  Then run `uv run pytest tests/unit/llm tests/unit/test_secrets_never_leak.py -q`
  and `make check`.

**Checkpoint**: one interface for all three providers, with fail-fast
errors and no silent fallbacks

---

## Phase 7: User Story 5 - Connect to Neo4j and Postgres safely (Priority: P3)

**Goal**: connection wrappers with health floors, whole-unit retry,
per-identity pools, token minting per connection and TLS by default

**Independent Test**: `uv run pytest -m docker -q` passes on the pinned
images. `uv run pytest tests/unit/storage -q` passes without Docker.

### Tests for User Story 5

- [ ] T053 [P] [US5] Write `tests/unit/storage/test_neo4j_unit.py`. It
  patches `neo4j.GraphDatabase.driver` and covers:
  - `test_tls_auto` for Neo4j URIs;
  - `test_telemetry_disabled`;
  - `test_pool_max_age`, which checks `max_connection_lifetime`,
    `max_connection_pool_size`, `connection_acquisition_timeout`,
    `max_transaction_retry_time` and `liveness_check_timeout`;
  - `test_identity_isolation`;
  - `test_health_floor`, with faked `dbms.components()` rows below
    2026.09;
  - `MissingExtraError` when `neo4j` is not importable.
- [ ] T054 [P] [US5] Write `tests/unit/storage/test_postgres_unit.py`. It
  patches `psycopg_pool.ConnectionPool` and covers:
  - every connection parameter is passed explicitly: host, port, dbname,
    user, password and `sslmode` (`require` remote, `disable` local,
    `verify-full` with `tls: verify`);
  - `none` is rejected;
  - the SQLSTATE classification table of research R10;
  - `test_health_floor` with a faked `server_version_num` of 150000 and a
    missing `pg_trgm`;
  - the `connection_class` re-mint, using a fake `connect` that fails
    once with SQLSTATE `28P01`;
  - `test_identity_isolation`.
- [ ] T055 [P] [US5] Write `tests/integration/neo4j/test_neo4j.py`,
  marked `docker`, on `neo4j:2026.09.0-community` through testcontainers
  with the pinned image. It covers `test_health_ok`,
  `test_wrong_password`, `test_database_not_found`,
  `test_restart_recovers` (restart the container inside `write`, and the
  unit replays) and `test_unavailable` (container stopped). Then remove
  the exit-5 allowance from the `integration` target in `Makefile`, so a
  run that collects no docker test fails again.
- [ ] T056 [P] [US5] Write `tests/integration/postgres/test_postgres.py`,
  marked `docker` and parametrized over the pg16 and pg17 images. It
  covers:
  - `test_health_ok`, which includes confirming `pg_trgm` and `vector`
    are available;
  - `test_wrong_password`, `test_restart_recovers` and `test_unavailable`;
  - `test_new_token_per_connection`: a `token_provider` minter that
    returns the role password counts its calls across a forced pool
    refill;
  - `test_token_remint_once`: the minter returns a wrong password first,
    then the right one, and is called exactly twice; an always-wrong
    minter raises `CredentialRejectedError`.

### Implementation for User Story 5

- [ ] T057 [P] [US5] Implement `HealthReport` and `open_connection` in
  `src/tenetrag/storage/__init__.py`. Dispatch by `settings.kind`, resolve
  the credential through `resolve_credential`, and import the drivers
  lazily with `MissingExtraError`.
- [ ] T058 [US5] Implement `Neo4jConnection` in
  `src/tenetrag/storage/neo4j.py`, following research R13:
  - **TLS:** the `auto` check on the URI scheme, where loopback hosts are
    `localhost`, `127.0.0.0/8` and `::1`.
  - **Driver:** `GraphDatabase.driver(uri, auth=basic_auth or None,
    telemetry_disabled=True, max_connection_pool_size,
    max_connection_lifetime, liveness_check_timeout=30,
    connection_acquisition_timeout, max_transaction_retry_time)`.
  - **Units:** `read` and `write` use one session per unit, with
    `execute_read` and `execute_write`.
  - **Health:** `verify_connectivity()`, then `CALL dbms.components()`,
    with the floor check.
  - **Errors:**
    - `neo4j.exceptions.AuthError` maps to `CredentialRejectedError`;
    - `ServiceUnavailable` after retries maps to `StoreUnavailableError`
      (host and port, no secret);
    - `Neo.ClientError.Database.DatabaseNotFound` maps to `QueryError`
      naming the database;
    - other errors map to `QueryError`.

  Depends on T057.
- [ ] T059 [US5] Implement `PostgresConnection` in
  `src/tenetrag/storage/postgres.py`, following research R12:
  - **Parameters:** a kwargs callable returns every parameter explicitly
    on each new connection, with a fresh token for `token_provider`.
  - **Re-mint:** a `connection_class` subclass whose `connect` catches
    SQLSTATE class `28` once for refreshable credentials, calls
    `invalidate()` and retries.
  - **Pool:** `ConnectionPool(…, check=ConnectionPool.check_connection,
    max_lifetime=pool.max_age_seconds, min_size, max_size, open=False)`,
    then `open(wait=True, timeout=acquire_timeout_seconds)`.
  - **Transactions:** `transaction(work, read_only)` runs the whole unit
    under `_retry.run_with_retry` with the SQLSTATE classification.
  - **Health:** `SHOW server_version_num` must be at least 160000, plus
    the `pg_available_extensions` check.
  - **Errors:** failures map to `CredentialRejectedError`,
    `StoreUnavailableError`, `UnsupportedServerError` or `QueryError`.

  Depends on T011, T036 and T057.
- [ ] T060 [US5] Extend `tests/unit/test_secrets_never_leak.py` with part 3:
  - connection failures with `PLANTED` passwords and tokens, on the unit
    fakes;
  - check exceptions, `caplog` and `repr`.

  Then run `uv run pytest tests/unit/storage -q`,
  `uv run pytest -m docker -q` and `make check`.

**Checkpoint**: both stores connect safely, and every story works

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: docs that change with the code, and the final validation

- [ ] T061 [P] Update `ARCHITECTURE.md`:
  - replace the "No code exists yet" banner;
  - mark which modules exist after M0;
  - in the module map, `config` and `auth` may import `protocols`, and
    errors live in `tenetrag.protocols.errors` (research R14);
  - add `_retry` as a private stdlib-only helper of `llm` and `storage`;
  - list the extras `openai`, `databricks`, `neo4j` and `postgres`.
- [ ] T062 [P] Update `README.md`:
  - status: M0 foundation, not released;
  - a "Development" section with the setup and `make check` lines;
  - the two example profiles, linked to
    `specs/001-sdk-foundation/contracts/config.md`.
- [ ] T063 [P] Update `docs/product/engine-brief.md` §6.4:
  - `ChatResult` gains `strategy` and `finish_reason`;
  - `max_input_tokens` must be known when the model is created;
  - a one-line pointer to `src/tenetrag/protocols/models.py`.
- [ ] T064 [P] Update `docs/reference/databricks-platform.md`. Add the
  dated facts from research R11, verified 2026-10-06 at databricks-sdk
  v0.146.0, with source paths:
  - `Config` fills unset attributes from `DATABRICKS_*`, `ARM_*` and
    `GOOGLE_CREDENTIALS`, with no switch;
  - the `/.well-known/databricks-config` probe;
  - `external-browser` blocks with no timeout;
  - `ModelServingUserCredentials` falls back outside Model Serving.

  Add the last one to the "Fail-open traps" table.
- [ ] T065 Run [quickstart.md](quickstart.md) end to end:
  - time a fresh clone to green gates (SC-001);
  - record the unit suite duration (SC-002);
  - run the optional self-hosted check if Ollama is available;
  - run the live Databricks smoke test only if the author asks.

  Record the results at the bottom of `quickstart.md`.
- [ ] T066 Set the status in `specs/001-sdk-foundation/spec.md` to
  "Implemented". Confirm every FR and SC maps to a passing test or a
  recorded check, and list any gaps in the spec's Assumptions or in
  `docs/tech-debt.md`. Create that file only if a gap exists.

---

## Dependencies & Execution Order

### Phase dependencies

- Setup (T001–T005) runs first. T004 needs T001, and T005 needs T001
  and T004.
- Foundational (T006–T011) needs Setup and blocks every story.
- US1 (T012–T018) needs Foundational. It is the MVP.
- US2 (T019–T028) needs Foundational. US3, US4 and US5 use its settings
  models (T024, T025).
- US3 (T029–T037) needs US2's `CredentialSource` and settings.
- US4 (T038–T052) needs US2 (model settings) and US3 (`resolve_credential`).
  The fake models (T045, T047, T048) need only US2.
- US5 (T053–T060) needs US2 (connection settings) and US3. It is
  independent of US4, so US4 and US5 can run in parallel.
- Polish (T061–T066) needs every story it documents.

### Within each story

- Tests are written first and must fail. Then come implementation and
  the story's run task (T018, T028, T037, T052, T060).
- Models and pure modules come before adapters, and adapters before
  factories.

### Parallel opportunities

- Setup: T002 and T003 alongside T001.
- Foundational: T006, T008, T009 and T010 together, then T007 and T011.
- US1: T012, T013, T015 and T016 together.
- US2: T019–T022 together, then T023 and T024 together.
- US3: T029–T033 together.
- US4: T038–T044 together, then T045 and T046 together.
- US5: T053–T056 together. US5 as a whole runs alongside US4.
- Polish: T061–T064 together.

---

## Parallel Example: User Story 4

```bash
# Tests first, all at once (different files):
Task: "Write tests/unit/llm/test_capabilities.py"
Task: "Write tests/unit/llm/test_structured.py"
Task: "Write tests/unit/llm/test_openai_compatible.py"
Task: "Write tests/unit/llm/test_embeddings.py"
Task: "Write tests/unit/llm/test_fake.py"

# Then the two pure modules together:
Task: "Implement src/tenetrag/protocols/models.py"
Task: "Implement src/tenetrag/llm/capabilities.py"
```

---

## Implementation Strategy

### MVP first

1. Setup, then Foundational.
2. US1: the gates are green and enforced.
3. Stop and validate quickstart §1. Every later task lands through these
   gates.

### Incremental delivery

1. US2 (profile). Validate quickstart §2.
2. US3 (credentials). Validate quickstart §3.
3. US4 and US5, in either order or together. Validate quickstart §4
   and §5.
4. Polish: docs, end-to-end quickstart, and the spec marked Implemented.

## Notes

- Commit only when the author asks, on `main`, after the `git status`
  check for adopter material. A natural commit point is each checkpoint.
- Any dependency added beyond research.md goes through the gate of T005
  first.
- A task that changes a module boundary updates `ARCHITECTURE.md` in the
  same change (T061 collects M0's changes).
- Estimate: about 6.5 working days (plan.md).
