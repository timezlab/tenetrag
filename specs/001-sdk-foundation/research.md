# Research: SDK foundation (M0)

Checked on 2026-10-06. Four lanes read source code at pinned tags, PyPI
metadata and Docker Hub, and queried OSV
(`https://api.osv.dev/v1/querybatch`). Nothing was installed or run.
Labels: **[source]** read in code, **[pypi]** package metadata, **[osv]**
advisory database, **[inferred]** our reasoning. Decisions R9, R11 and
R12 were taken by the author on 2026-10-06.

## Versions and the dependency gate

Each version is older than 24 hours, and every pinned version has zero
OSV advisories, including `MAL-` [osv]. Every package ships wheels for
CPython 3.11–3.14, so no build script runs on install [pypi].

| Package | Version | License | Use |
|---|---|---|---|
| uv | 0.12.23 | MIT OR Apache-2.0 | package manager, lockfile (dev) |
| hatchling | 1.32.4 | MIT | build backend (dev) |
| ruff | 0.16.10 | MIT | formatter and linter (dev) |
| mypy | 2.4.0 | MIT | type checker (dev) |
| pytest | 9.1.1 | MIT | tests (dev) |
| pytest-socket | 0.8.1 | MIT | blocks network in unit tests (dev) |
| types-PyYAML | 6.0.12.20260906 | Apache-2.0 | PyYAML stubs for mypy (dev); uploaded 2026-09-06, added at lock time |
| import-linter | 2.15 | BSD-2-Clause | import rules (dev) |
| testcontainers | 4.15.0 | Apache-2.0 | Docker in integration tests (dev only: its Ryuk reaper pulls an image) |
| pydantic | 2.13.5 | MIT | profile model (base) |
| PyYAML | 6.0.3 | MIT | profile YAML (base) |
| jsonschema | 4.26.0 | MIT | validates structured output (base) |
| openai | 3.24.0 | Apache-2.0 | chat and embedding clients (extras `openai`, `databricks`) |
| databricks-sdk | 0.146.0 | Apache-2.0 | Databricks OAuth, CLI profile, runtime (extra `databricks`) |
| neo4j | ≥ 6.3.1 | Apache-2.0 AND Python-2.0 | Neo4j driver (extra `neo4j`); 6.4.0 was uploaded 2026-10-05 15:37 UTC, too new to lock today |
| psycopg[binary], psycopg-pool | 3.3.6, 3.3.3 | LGPL-3.0-only | Postgres driver and pool (extra `postgres`, under ADR 0017) |

`openai` 3.x brings `httpx2` (Pydantic's fork of httpx, BSD-3-Clause).
Its old advisories are fixed in 2.12.0. The latest, 2.13.1, has none
[osv].

**Lock check (T005, 2026-10-06 09:15 UTC).** `uv lock` with uv 0.12.23
resolved 65 packages and recorded `exclude-newer-span = "PT24H"`. Every
direct dependency locked at the version in the table above (`neo4j`
6.3.1, `httpx2` 2.13.1). The newest upload in the lock is `rpds-py`
2026.9.1, 40.7 hours old, and every package has wheels. An OSV querybatch
for all 64 third-party packages in `uv.lock` returned 0 advisories and no
`MAL-` entry [osv].

Runtime licenses of the transitive dependencies (base and all extras) are
MIT, BSD, Apache-2.0, PSF-2.0, MIT-0 or Python-2.0, except:
- `psycopg`, `psycopg-binary` and `psycopg-pool`: LGPL-3.0-only, allowed
  by ADR 0017;
- `certifi` 2026.7.22: MPL-2.0, pulled in by `requests` through
  `databricks-sdk` (the `databricks` extra) and through `docker` (dev,
  via testcontainers). MPL-2.0 is file-level copyleft
  that applies only to modified certifi files; TenetRAG uses it
  unmodified [inferred, not legal advice]. The author accepted it as
  "equivalent" on 2026-10-06, recorded in ADR 0009 condition 1.

## R1. Package manager and build

- **Decision:** uv with a committed `uv.lock`, and hatchling as the build
  backend. `[tool.uv] exclude-newer = "24 hours"` makes every resolution
  skip versions younger than a day, which enforces the gate at lock time.
  CI runs `uv sync --locked`, which fails when the lock is stale.
- **Rationale:** one tool covers environments, locking and running the
  gates. The relative `exclude-newer` is documented and recorded in the
  lock [primary: docs.astral.sh/uv/concepts/resolution].
- **Alternatives:** `uv_build` is stable but pure-Python only and pinned
  to uv's 0.x line, so hatchling is less coupled. Poetry and pip-tools
  were not considered further.

## R2. Formatter and linter

- **Decision:** ruff 0.16, both `ruff format` and `ruff check`, with rule
  sets `E F W I B UP S SIM RUF ANN PT TID BLE N`.
  - `tests/` ignores `S101` and `ANN`.
  - `COM812` and `ISC001` stay off, since they conflict with the
    formatter.
- **Rationale:** one fast tool replaces black, isort and flake8 with
  plugins. `TID` bans relative imports and complements import-linter.
- **Scope:** ruff 0.16 also formats Python code blocks inside Markdown
  [observed at T005]. `pyproject.toml` excludes `*.md`, because the code
  in docs and specs is design sketches, and excludes `.agents` and
  `.claude`, the agent harness scripts.

## R3. Type checker

- **Decision:** mypy 2.4 with `strict = true` and the `pydantic.mypy`
  plugin (`init_forbid_extra`, `init_typed`,
  `warn_required_dynamic_aliases`).
- **Alternatives:**
  - basedpyright works, but it brings Node through `nodejs-wheel-binaries`.
  - The `pyright` wrapper downloads Node at run time.
  - `ty` is still beta (0.0.84).

## R4. Tests

**Unit tests**
- They run with `--disable-socket`, so any network call fails the test
  (FR-002, SC-002).
- They use the fake models (§R9) and `MockTransport` from `httpx2`, which
  the OpenAI client accepts as `http_client`.

**Integration tests**
- They are marked `docker` and use testcontainers. Images are pinned by
  digest at implementation time:
  - `neo4j:2026.09.0-community`;
  - `pgvector/pgvector:0.8.7-pg16`, the floor;
  - `pgvector/pgvector:0.8.7-pg17`, the Lakebase default.
- `pg_trgm` ships in the official Postgres contrib, which the pgvector
  image extends [inferred]. A test confirms it.
- When Docker is absent, they skip with that reason. CI always has Docker.

**Live tests**
- They are marked `live` and run only when a contributor exports the
  variables the test names (`TENETRAG_LIVE_DATABRICKS_HOST` and similar).
- CI runs none.

## R5. Import rules

**Decision:** import-linter contracts in `pyproject.toml`:
1. `tenetrag.protocols` imports no other `tenetrag` module.
2. `tenetrag.config` imports only `tenetrag.protocols`.
3. `tenetrag.auth` imports only `config` and `protocols`.
4. `tenetrag.llm` and `tenetrag.storage` are independent of each other.
5. Nothing imports `tenetrag.llm` or `tenetrag.storage` except the
   package itself. `serving` arrives in M1.

The engine contract arrives with `tenetrag.engine` in M1.

**Base import test:** a fresh subprocess imports `tenetrag` and asserts
that none of `openai`, `httpx2`, `databricks`, `neo4j`, `psycopg`,
`psycopg_pool` is in `sys.modules` (SC-008).

## R6. CI

- **Decision:** GitHub Actions, with one workflow, two jobs and a Python
  matrix of 3.11 and 3.14.
  - The `gates` job runs format check, lint, type check, import check and
    unit tests.
  - The `integration` job runs the Docker tests.
- **Pins:**
  - `astral-sh/setup-uv` at commit
    `c18668ad3cf93ea998bef934396af7bb5c839dc7` (v10.2.0, an immutable
    release).
  - `actions/checkout` at v7.0.1, pinned by its full SHA, resolved with
    `git ls-remote` when the workflow is written.
- **Python 3.15:** final is due 2026-10-09. It joins the matrix after
  release.
- **Python 3.11:** in security support only, so the floor is revisited
  in 2027.

## R7. Profile loading

- **Decision:** Pydantic 2.13 models with `extra="forbid"` and
  `frozen=True`. YAML loads through a `yaml.SafeLoader` subclass whose
  `construct_mapping` rejects duplicate keys. Phase markers are classes
  placed in `Annotated` metadata (data model §8).
- **Rationale:** PyYAML's safe loader keeps the last duplicate silently,
  which breaks the fail-closed rule, and the subclass is a few lines.
  ruamel.yaml would add a dependency to fix one behaviour.

## R8. Stage hashes

- **Decision:** SHA-256 over canonical JSON, as in data model §8, in
  `tenetrag/config/hashing.py` only.
- **Rationale:**
  - `json.dumps` with sorted keys and compact separators is stable across
    platforms and Python versions.
  - Floats use the shortest repr.
  - Golden values in the tests catch any drift.

## R9. Model clients (author's decision)

**Decision:** thin `ChatModel` and `EmbeddingModel` classes over the
`openai` SDK, as ADR 0009's starting choice says. One class pair serves
every OpenAI-compatible server. The Databricks pair sets `base_url` to
`{workspace_url}/serving-endpoints` and uses the Databricks capability
profiles.

**Construction** [source: openai v3.24.0 `src/openai/_client.py`]:
- `api_key=<callable>` returns the current token from our token source,
  so a refreshed OAuth token is used on the next request. A non-`None`
  `api_key` stops the read of `OPENAI_API_KEY` (lines 252–259).
- An explicit `base_url` stops the read of `OPENAI_BASE_URL`
  (lines 303–306).
- `max_retries=0` turns off the SDK's retries, so R10's policy is the
  only one (`_base_client.py:851-859`).
- An explicit `timeout`.
- For the `none` credential, `api_key="unused"`: the SDK refuses an empty
  key, and local servers ignore the header.

**Accepted environment reads** (ADR 0018):
- `OPENAI_ORG_ID` and `OPENAI_PROJECT_ID` (lines 277–283).
- `OPENAI_CUSTOM_HEADERS`, read whenever no provider runtime is set
  (line 315).
- `OPENAI_LOG`.
- The client warns once per process when the first three are set.

**Request shapes:**

| Strategy | Request |
|---|---|
| `native_schema` | `response_format={"type": "json_schema", "json_schema": {"name": …, "schema": …, "strict": true}}` |
| `tool_call` | one function tool with the schema, forced through `tool_choice` |
| `json_mode` | `response_format={"type": "json_object"}`, schema in the system message |
| `prompt_parse` | schema and instructions in the system message |

**Results and validation:**
- `finish_reason == "length"` raises `OutputTruncatedError`.
- Usage comes from `usage.prompt_tokens`, `usage.completion_tokens` and
  `usage.prompt_tokens_details.cached_tokens`, each `None` when absent.
- Embeddings pass `encoding_format="float"`, so servers that do not
  return base64 work and numpy is not needed.
- Parsed output is validated with `jsonschema.Draft202012Validator`
  against an empty `referencing.Registry()`, so a schema can never fetch
  a remote `$ref` [source: jsonschema v4.26.0 `validators.py:131-132`].

**Alternative rejected:** our own HTTP client. It would close the three
`OPENAI_*` reads, but the author judged it not worth 150–250 lines to
maintain.

## R10. Retry policy

**Decision:** one small module, `tenetrag/_retry.py` (stdlib only), used
by model calls and Postgres units of work. It implements data model §6:
- attempts and a total-time budget;
- exponential backoff with full jitter;
- `Retry-After` and `retry-after-ms` hints;
- the one `reauth` retry.

**Classification:**

| Failure | Models (`openai` exceptions) | Postgres (SQLSTATE) |
|---|---|---|
| retry | `RateLimitError`, `APITimeoutError`, `APIConnectionError`, `InternalServerError` | class `08`, `57P01`–`57P03`, `53300`, `40001`, `40P01` |
| reauth (refreshable credential only) | `AuthenticationError` | class `28` with a `token_provider` |
| fail | `BadRequestError`, `PermissionDeniedError`, `NotFoundError`, others | everything else |

**Libraries considered** (read in source on 2026-10-06, at the author's
request to prefer a library where one fits):
- **tenacity 9.1.4** (Apache-2.0, 2026-02-07). It has full jitter
  (`wait_random_exponential`), an injectable `sleep` and
  `stop_before_delay`. But `RetryCallState` calls `time.monotonic()`
  directly, so the clock cannot be injected, and every attempt counts
  toward `stop_after_attempt`. The `reauth` rule (one retry that uses no
  attempt, and a second rejection that fails) would need a custom `stop`,
  `retry`, `wait` and `before_sleep` sharing mutable state, which is more
  code than the loop it replaces.
- **stamina 26.1.0** (MIT, over tenacity). A backoff hook can return a
  float, which covers `Retry-After`. But its jitter is additive, not full
  jitter, its test mode is global, and it has no `reauth` notion.
- **backoff 2.2.1** (MIT). Its last release was in 2022-10.

Rejected: the own module is about 80 lines of stdlib code and keeps the
policy in one place.

**Neo4j:** uses the driver's own managed-transaction retry instead.
`max_transaction_retry_time` is set to the store retry budget. The driver
retries `TransientError`, `SessionExpired` and `ServiceUnavailable`, and
never auth errors [source: neo4j-python-driver `exceptions.py`,
`session.py`].

## R11. Databricks credentials (author's decision)

| Kind | Implementation |
|---|---|
| `pat`, `obo` | a static bearer token. No Databricks SDK. Never `ModelServingUserCredentials`, which falls back to the default chain outside Model Serving [source: `credentials_provider.py:1522-1553`] |
| `oauth_m2m` | `Config(host=…, client_id=…, client_secret=…, auth_type="oauth-m2m")` |
| `oauth_u2m` | `Config(host=…, auth_type="external-browser")`, only when stdin and stdout are terminals. The SDK's browser flow blocks with no timeout [source: `oauth.py:677-692`], so in a run with no user present it raises `CredentialSourceError` that points to `cli_profile` |
| `cli_profile` | `Config(profile=name)`. The SDK runs `databricks auth token --profile <name>` and reads `access_token`, `token_type` and `expiry` [source: `credentials_provider.py:959-1010`] |
| `runtime` | when `DATABRICKS_RUNTIME_VERSION` is present, `Config(auth_type="runtime")`. Otherwise `CredentialSourceError`, with no network |
| `workspace_client` | the caller's client, used as given |

Each request takes its token from `config.authenticate()`, which
refreshes under a lock [source: `oauth.py:279`, `327-332`]. The SDK's
`ValueError`s map to `CredentialSourceError`, and a 401 maps to `reauth`.

**Accepted (ADR 0018):**
- `Config` loads every `DATABRICKS_*`, `ARM_*` and `GOOGLE_CREDENTIALS`
  variable for attributes left unset, before reading the named profile,
  and there is no switch to turn this off [source: `config.py:725-743`,
  `808-811`].
- An explicit `auth_type` keeps the auth family fixed
  (`credentials_provider.py:1484-1488`).
- The resolver logs one warning that names the variables that are set.

**Also noted:**
- `Config()` probes `{host}/.well-known/databricks-config` when a host is
  set (best effort).
- The user agent names a detected coding agent [source: `config.py:632-684`,
  `useragent.py:242-315`].

**Alternative rejected:** blocking each variable by passing `""` for every
unused attribute, plus a custom credentials strategy. It is undocumented
behaviour, and the author chose the simpler path.

## R12. Postgres driver (author's decision)

**Decision:** psycopg 3.3 with the `binary` extra, and psycopg-pool 3.3,
in the `postgres` extra, under ADR 0017.

**Pool:**
- `ConnectionPool(kwargs=<callable>, check=ConnectionPool.check_connection,
  max_lifetime=pool.max_age_seconds, min_size, max_size, open=False)`,
  then `open(wait=True, timeout=…)`, so a startup failure surfaces at
  once.
- `kwargs` may be a callable, called for every new physical connection,
  so each connection gets a freshly minted token [source: psycopg_pool
  `pool.py:646-661`, since 3.3].
- The re-mint after a rejected token is done by a `connection_class`
  subclass whose `connect` invalidates the token and retries once on
  SQLSTATE class `28`. The pool calls `connection_class.connect(conninfo,
  **kwargs)` [source: `pool.py:614-624`].

**Explicit parameters:** host, port, dbname, user, password and `sslmode`
are always passed. `auto` gives `require` (or `verify-full` with `tls:
verify`) for a non-local host, and `disable` for a local one. libpq
defaults to `sslmode=prefer` and reads `PG*` variables for anything left
unset [inferred from libpq behaviour], so nothing is left unset that
matters for identity.

**Health:**
- `SHOW server_version_num` must be at least 160000.
- `SELECT name FROM pg_available_extensions WHERE name IN ('vector',
  'pg_trgm')`.

**Alternative:** pg8000 (BSD-3) plus our own pool. The author chose
psycopg. pg8000 also defaults to unverified TLS that falls back to
plaintext [source: pg8000 `core.py:218-240`].

## R13. Neo4j driver

**Decision:** `GraphDatabase.driver(uri, auth=…)` with these settings:
- `telemetry_disabled=True` [source: `_sync/config.py:111-112`];
- `max_connection_pool_size=pool.max_size`;
- `max_connection_lifetime=pool.max_age_seconds`;
- `liveness_check_timeout=30`;
- `connection_acquisition_timeout=pool.acquire_timeout_seconds`;
- `max_transaction_retry_time=retry.max_total_seconds`.

**Use:**
- One session per unit of work, since sessions are not thread-safe and
  the driver is.
- `auto` TLS rejects `neo4j://` and `bolt://` for a non-local host, with
  a `ConfigError` that suggests `neo4j+s://`.

**Health:**
- `verify_connectivity()`, then `CALL dbms.components()` for the version
  and edition.
- `Neo.ClientError.Database.DatabaseNotFound` maps to a `QueryError` that
  names the database.
- `neo4j.exceptions.AuthError` maps to `CredentialRejectedError`.

**Environment:** the driver reads only `PYTHONNEO4JDEBUG` and
`SSLKEYLOGFILE`, neither a credential [source].

## R14. Where errors live

- **Decision:** `tenetrag.protocols.errors`, re-exported from
  `tenetrag.protocols` and from `tenetrag`.
- **Rationale:** constitution principle III lets the engine import only
  protocols, `config` and `packs`, and the engine must raise and catch
  these errors. A separate `tenetrag.errors` would need an amendment.
  Errors that cross a protocol boundary are part of the protocol
  contract.
- **Consequence:** `config` and `auth` import `protocols`.
  `ARCHITECTURE.md` changes to say so.

## R15. Logging and secrets

- **Decision:**
  - Module loggers, and no `print`.
  - Model settings carry `log_content: false` (operational). Only when it
    is true are prompt and response text logged, at DEBUG.
  - `Secret` masks itself in `repr` and `str`.
  - `test_secrets_never_leak` plants known values in every credential
    kind, drives success and failure paths, and scans `caplog`, `repr`,
    `str` and the full exception chains (SC-006).
