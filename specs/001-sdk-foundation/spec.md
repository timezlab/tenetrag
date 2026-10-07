# Feature Specification: SDK foundation (M0)

**Feature Branch**: none; solo development on `main`, and Spec Kit finds
this feature through `.specify/feature.json`

**Created**: 2026-10-06

**Status**: Implemented (2026-10-07). Gaps are listed under Assumptions
and in [docs/tech-debt.md](../../docs/tech-debt.md).

**Input**: User description: "M0 foundation for TenetRAG, per the SDK platform brief milestones: repo quality gates (formatter, linter, type-checker, pytest), the `tenetrag` package skeleton with optional extras and per-domain errors, the config profile model (YAML or dict, every field tagged index-time or query-time, ADR 0005), caller-supplied credentials that fail closed (ADR 0003), LLM classes (Databricks, OpenAI-compatible, fake) behind the ChatModel and EmbeddingModel protocols, and Neo4j and Postgres connection wrappers. No engine, ingest or retrieval yet."

M0 is the first milestone of the
[SDK platform brief](../../docs/product/sdk-platform-brief.md). It builds
what every later milestone stands on, and nothing that indexes or
retrieves. Two kinds of people use it:
- **Contributors** work on the SDK itself: the author and AI agents.
- **Callers** are developers who build agents and pipelines on the SDK.
  In M0 they load a profile, create credentials, call models and open
  store connections. M1's engine is the first internal caller.

TenetRAG has two first-class deployment paths, and M0 serves both
([ADR 0008](../../docs/decisions/0008-build-databricks-and-open-branches-in-parallel.md)):
- **Self-hosted**: Neo4j or Postgres, with any OpenAI-compatible model
  server, such as Ollama, vLLM, a LiteLLM proxy or OpenAI. It needs no
  Databricks account, package or credential.
- **Databricks**: serving endpoints called from a laptop, a notebook, a
  job or an app. Lakebase, Delta and AI Search follow in M2.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Green gates from a fresh clone (Priority: P1)

A contributor clones the repository, follows the documented setup, and
runs the formatter check, the linter, the type checker and the tests. All
of them pass without a Databricks workspace, an API key, or network access
beyond installing packages. The same gates run in CI. Importing the base
package needs no optional extra, and the module import rules of
[ARCHITECTURE.md](../../ARCHITECTURE.md) are checked by a tool, not by
review.

**Why this priority**: every later story lands through these gates, and
the constitution requires them before any change is called done. The
import check also guards principle III from the first module on.

**Independent Test**: on a clean machine with only Python and Docker,
follow the documented steps, then run the gates. Then add one deliberate
fault at a time (bad formatting, a type error, a forbidden import, a
failing test) and confirm that the matching gate fails.

**Acceptance Scenarios**:

1. **Given** a fresh clone and Python 3.11 or later, **When** the
   contributor runs the documented setup and the single command that runs
   every gate, **Then** all gates pass, and the unit tests use no network,
   no Docker, no workspace and no credential.
2. **Given** a module that imports a module the architecture forbids (for
   example, the protocols module importing a database driver), **When**
   the gates run, **Then** the import check fails and names both modules.
3. **Given** an environment where only the base package is installed,
   **When** the package is imported, **Then** the import succeeds and loads
   no optional dependency.
4. **Given** a push to the hosted repository, **When** CI runs, **Then** it
   runs the same gates on the lowest and the newest supported Python, plus
   the integration tests against pinned Neo4j and Postgres containers.

---

### User Story 2 - Load and validate a profile (Priority: P1)

A caller writes a profile in YAML, or passes the same content as a dict.
It names the store connections, the chat model for extraction, the chat
model for answers, the embedding model, and the graph language. Loading
validates everything and reports every problem at once, each with its
field path. Each field is declared index-time or query-time
([ADR 0005](../../docs/decisions/0005-index-time-vs-query-time-parameters.md)).
The profile yields one hash per pipeline stage, computed from index-time
fields only.

**Why this priority**: every component is built from the profile. Stage
hashes later drive re-index detection, benchmark index reuse and run
records, so the phase of each field has to be right from the first field
on, not retrofitted.

**Independent Test**: load valid, invalid and varied sample profiles and
compare the errors and the stage hashes. No store, model or network is
needed.

**Acceptance Scenarios**:

1. **Given** a valid YAML profile, **When** it is loaded, **Then** the
   caller gets a validated profile with the file's values, and with the
   documented defaults for fields the file leaves out.
2. **Given** the same profile once as YAML and once as a dict with its
   keys in another order, **When** both are loaded, **Then** their stage
   hashes are identical.
3. **Given** a profile with a misspelled field name and, elsewhere, a
   negative timeout, **When** it is loaded, **Then** a `ConfigError` lists
   both problems with their field paths, and nothing is built.
4. **Given** two profiles that differ only in the answer model, **When**
   their stage hashes are computed, **Then** every hash is equal.
5. **Given** two profiles that differ only in the embedding model, **When**
   their stage hashes are computed, **Then** only the embedding stage hash
   differs.
6. **Given** two profiles that differ only in the extraction model,
   **When** their stage hashes are computed, **Then** only the extraction
   stage hash differs.
7. **Given** a contributor adds a profile field without declaring its
   phase, **When** the gates run, **Then** a test fails and names the
   field.

---

### User Story 3 - Supply credentials that fail closed (Priority: P2)

A caller gives an explicit credential to each target that needs one
([ADR 0003](../../docs/decisions/0003-caller-supplied-credentials.md)):
- Neo4j or Postgres: a user name and password, or, for Postgres, a
  callback that mints a token (Lakebase uses it in M2);
- an OpenAI-compatible endpoint: an API key, or an explicit "no
  credential" for a local server without one;
- a Databricks workspace: a personal access token, OAuth machine-to-machine
  (a service principal), OAuth user-to-machine (a browser login the caller
  asks for, or a Databricks CLI profile the caller names, such as one made
  by `databricks auth login`), an on-behalf-of (OBO) user token, the
  runtime identity of a Databricks notebook or job, or a workspace client
  the caller built.

A credential comes from code or from the profile. The profile names where
a credential comes from (an environment variable, a Databricks CLI
profile, the runtime identity, or none), never the secret itself. So a
CLI, an MCP server or a job can run from a profile file alone. A
credential passed in code overrides the profile's source for the same
target.

A target that needs a credential and gets none fails with the reason. The
SDK reads only the sources the caller named, and never switches to
another identity. Secrets never appear in printed objects, logs or error
messages.

Two third-party clients still read some environment variables on their
own once the SDK uses them. The OpenAI SDK reads `OPENAI_ORG_ID`,
`OPENAI_PROJECT_ID` and `OPENAI_CUSTOM_HEADERS`. The Databricks SDK fills
settings the SDK left unset from `DATABRICKS_*` variables. The author
accepted both (ADR 0018), so the SDK warns about them instead of
blocking them.

**Why this priority**: every real model call and store connection needs
it, and a silent fallback can read data as the wrong user. Profile loading
and fake models work without it, so it ranks after Stories 1 and 2.

**Independent Test**: create, print, refresh and reject credentials with
fake token sources and fake targets. No workspace is needed.

**Acceptance Scenarios**:

1. **Given** a target that requires a credential and none was supplied,
   **When** a model or connection for it is created, **Then** an
   `AuthError` names the target and the credential kinds it accepts, and
   no network call is made.
2. **Given** the process environment holds variables that Databricks or
   OpenAI tooling would read (such as `DATABRICKS_TOKEN` or
   `OPENAI_API_KEY`), **When** neither the code nor the profile names a
   credential source, **Then** the SDK still raises `AuthError` and never
   reads those variables.
3. **Given** the code or the profile names an environment variable as a
   secret's source, **When** the credential is created, **Then** the
   secret is read from that variable alone. If the variable is unset or
   empty, an `AuthError` names the variable, never a value.
4. **Given** any credential, **When** it is printed, logged or included in
   an error, **Then** its secret is masked.
5. **Given** an OAuth machine-to-machine credential whose access token
   expires, **When** the next call needs a token, **Then** a new token is
   obtained for the same identity. If that fails, an `AuthError` is
   raised.
6. **Given** an OBO token that the service rejects as expired, **When** a
   call is made, **Then** an `AuthError` is raised, and no other identity
   is tried.
7. **Given** a credential kind the target cannot use (for example, an OBO
   token for a Neo4j connection), **When** the model or connection is
   created, **Then** an `AuthError` names the kind and the target.
8. **Given** the runtime identity is requested outside a Databricks
   runtime, **When** the credential is created, **Then** an `AuthError`
   says that no runtime identity is available.
9. **Given** a Databricks CLI profile name, **When** a Databricks model is
   created, **Then** it authenticates through that profile. If
   `DATABRICKS_*` variables are also set, which the Databricks SDK may
   apply, a warning names them. A profile that does not exist, or whose
   login has expired, raises an `AuthError` that names the profile and
   says to log in again.
10. **Given** a credential passed in code and a source named in the
    profile for the same target, **When** the target is created, **Then**
    the code's credential is used.
11. **Given** a self-hosted profile (Neo4j, and a local OpenAI-compatible
    server with "no credential"), **When** its models and connection are
    created with only the base package and the `neo4j` extra installed,
    **Then** no Databricks package or credential is needed or loaded.

---

### User Story 4 - Call chat and embedding models through one interface (Priority: P2)

A caller configures a chat model and an embedding model. Each is a
Databricks serving endpoint, an OpenAI-compatible endpoint (such as
Ollama, vLLM, a LiteLLM proxy or OpenAI) or a fake model. All three answer through the same two
interfaces, `ChatModel` and `EmbeddingModel`, as listed in
[engine brief §6.4](../../docs/product/engine-brief.md#64-model-protocols).
A request for structured output returns parsed data. Each model has a
capability profile, which the caller can override, so the SDK adapts to
what each model accepts.

**Why this priority**: M1's extraction and embedding depend on it, and
the fake models are what every engine unit test runs on.

**Independent Test**: run the fake models in unit tests, and the Databricks
and OpenAI-compatible classes against recorded or simulated HTTP
responses. A live smoke test runs only when a contributor supplies
credentials explicitly.

**Acceptance Scenarios**:

1. **Given** a chat model of any of the three kinds and a JSON schema,
   **When** the caller asks for structured output, **Then** the result
   holds the text, the parsed data, the strategy used, and the token usage
   (input, cached input, output). A count the provider does not report is
   marked unknown, never zero.
2. **Given** a model whose profile does not support native schema output,
   **When** structured output is requested, **Then** the class uses the
   next strategy in the order native schema, tool call, JSON mode, then
   parse, validate and retry.
3. **Given** output that still fails to parse or validate after the
   allowed retries, **When** the call ends, **Then** an `LLMError` names
   the strategy and the number of attempts, and no partial or guessed data
   is returned.
4. **Given** output cut off at the output-token limit, **When** the call
   ends, **Then** the error says that the output was truncated, not that
   it failed to parse.
5. **Given** the provider answers with a rate limit or a temporary server
   error, **When** a call is made, **Then** it is retried with backoff,
   honouring the provider's retry-after hint, up to a bounded number of
   attempts and total time, and then fails with an `LLMError`.
6. **Given** the provider rejects the credential, **When** a call is made,
   **Then** an `AuthError` is raised at once, apart from the single token
   refresh of Story 3 for refreshable credentials.
7. **Given** a model whose profile says it rejects a sampling parameter,
   such as temperature, **When** a call passes that parameter, **Then** the
   class leaves it out instead of failing.
8. **Given** a schema with a construct the model's profile cannot accept,
   **When** structured output is requested, **Then** the request is
   rejected before any call, and the error names the construct.
9. **Given** a list of texts, **When** documents are embedded, **Then**
   there is one vector per text, in input order, each with the configured
   dimension. A vector of another dimension raises an `LLMError`. An empty
   list returns an empty result without a call.
10. **Given** a model that expects different prefixes for queries and
    passages, **When** queries and documents are embedded, **Then** each
    gets its own prefix.
11. **Given** the fake models and the same inputs, **When** a test runs
    twice, **Then** the outputs are identical. The fake chat model can be
    scripted with responses and failures, and both fake models record
    their calls.

---

### User Story 5 - Connect to Neo4j and Postgres safely (Priority: P3)

A caller opens a connection to Neo4j (self-hosted 2026.09 or later, or
Aura) or to Postgres with pgvector (local or managed). A health check
confirms that the server can host TenetRAG. The caller then runs units of
work in transactions. Transient failures are retried, connections are
kept healthy, token credentials are refreshed for the same identity, and
an authentication failure stops at once.

**Why this priority**: M1's stores build on these wrappers. Nothing in M0
writes graph data yet, so the wrappers can land last.

**Independent Test**: integration tests against pinned Docker images,
with injected faults: a server restart, a wrong password, and an expired
token from a fake token source.

**Acceptance Scenarios**:

1. **Given** a reachable server that meets the requirements, **When** the
   health check runs, **Then** it reports the server version and, for
   Neo4j, the edition. For Postgres, it confirms that the `vector` and
   `pg_trgm` extensions are available.
2. **Given** Neo4j older than 2026.09, or Postgres older than 16 or without
   a required extension, **When** the health check runs, **Then** a
   `StorageError` names what was found and what is required.
3. **Given** a unit of work that hits a transient error (a dropped
   connection, a server restart, too many connections, a database waking
   up), **When** it runs, **Then** the whole unit is retried with backoff
   within a bounded time, never just part of it. When the budget runs out,
   a `StorageError` says the store is unavailable.
4. **Given** a wrong password, **When** a connection is opened, **Then** an
   `AuthError` is raised at once, with no retry and no other identity.
5. **Given** a Postgres token credential whose token has expired, **When**
   a connection is opened, **Then** the wrapper mints one new token for
   the same identity and retries once. A second failure raises an
   `AuthError`.
6. **Given** an open pool, **When** connections are handed out, **Then**
   each is checked before use and replaced before a configurable maximum
   age.
7. **Given** a pool opened for one identity, **When** work arrives for
   another identity, **Then** that pool never serves it. The other
   identity gets its own pool.
8. **Given** a query and its values, **When** it runs, **Then** the values
   travel as parameters. The wrappers offer no way to splice values into
   query text.
9. **Given** a server that is not on the local machine, **When** a
   connection is opened, **Then** an encrypted connection is required
   unless the caller turns that off explicitly.

---

### Edge Cases

**Profile**
- YAML that tries to build arbitrary objects through tags is rejected,
  since profiles are loaded safely.
- A key that appears twice in one YAML mapping raises `ConfigError`, not
  "last one wins".
- An empty profile file raises `ConfigError`.
- A secret-looking key (`password`, `token`, `api_key`) is rejected as an
  unknown field, with a hint that credentials are passed in code.
- Setting a field to its default value gives the same stage hashes as
  leaving it out.

**Credentials**
- A token callback that raises, or returns an empty token, raises
  `AuthError` with the original error kept as its cause.
- An OAuth token that expires during a long call is refreshed once for
  the same identity on the next call, never mid-request under another
  identity.
- A browser login starts only when the caller asks for one. In a run with
  no user present, an expired login raises `AuthError` instead of waiting
  for a browser.
- A profile copied to another machine names the same sources, and each
  machine supplies its own values.

**Models**
- An empty text, or a text longer than the model's input limit, is
  rejected before any call and named by its position. Nothing is
  truncated silently.
- Embeddings the provider returns out of order are put back in input
  order.
- A model with no shipped capability profile gets a documented
  conservative default, which the caller can override.
- Prompt and response text are not logged unless the caller turns on
  content logging explicitly, since documents can be confidential.

**Connections**
- A Neo4j database name that does not exist raises `StorageError` naming
  the database.
- A server unreachable at startup is retried within the budget, then
  reported as unavailable with its host and port and no secret.

**Packaging**
- Building a Neo4j or Postgres connection without its extra installed
  raises `ConfigError` naming the extra to install.
- Installing on Python older than 3.11 is refused.

## Requirements *(mandatory)*

### Functional Requirements

**Repository and gates**

- **FR-001**: The repository MUST provide one documented command per gate
  (format check, lint, type check, tests) and one command that runs them
  all. `AGENTS.md` lists them.
- **FR-002**: Unit tests MUST run with network access blocked, and without
  Docker, a workspace or any credential. Integration tests that need
  Docker are marked. Locally they skip with a stated reason when Docker is
  absent, and CI always runs them.
- **FR-003**: Every public function and class MUST be type-annotated, and
  the type checker MUST pass. Each suppression comment states its reason.
- **FR-004**: The import rules of `ARCHITECTURE.md` MUST be checked by a
  tool for every module that exists. A test MUST confirm that importing
  the base package loads no optional dependency.
- **FR-005**: CI MUST run all gates and the integration tests on every
  push and pull request, on Python 3.11 and the newest stable Python, with
  pinned Neo4j Community and Postgres-with-pgvector images.
- **FR-006**: Every dependency MUST pass the dependency gate of
  constitution principle IX before it is added, and MUST be locked in a
  committed lockfile. CI fails when the lockfile is out of date. A library
  outside the engine meets the six conditions of
  [ADR 0009](../../docs/decisions/0009-reuse-permissive-libraries-behind-adapters.md).
- **FR-007**: The package MUST be named `tenetrag`, require Python 3.11 or
  later, and ship under Apache-2.0 with `LICENSE` and `NOTICE` files.
  Drivers and Databricks packages sit behind extras. M0 declares only the
  extras its own code uses. The self-hosted path MUST work with no
  Databricks package installed and no Databricks credential.

**Errors**

- **FR-008**: Every error the SDK raises MUST share one base class and
  belong to `ConfigError`, `AuthError`, `StorageError` or `LLMError`.
  `IngestError` arrives with ingest in M1.
- **FR-009**: Error messages MUST say what failed and what to do next, and
  MUST NOT contain secrets. No third-party exception escapes the public
  surface untranslated. The original is kept as the cause.

**Profile**

- **FR-010**: A profile MUST load from a YAML file or a dict, through safe
  YAML loading. Duplicate keys and unknown fields are rejected, and all
  problems are reported at once with their field paths.
- **FR-011**: The M0 profile MUST cover named store connections (Neo4j
  and Postgres settings, without secrets), the extraction chat model, the
  answer chat model, the embedding model, and the graph language, which
  defaults to `en`. Each connection and model can name its credential
  source.
- **FR-012**: Every profile field MUST declare its phase. Operational
  fields (addresses, timeouts, retry budgets, pool sizes, concurrency) are
  query-time, even inside an index-time section. Every index-time field
  names its stage, from the stages of
  [engine brief §9](../../docs/product/engine-brief.md#9-configuration-added).
- **FR-013**: Stage hashes MUST be computed in exactly one module, from
  index-time field values only. They MUST be identical across input form
  (YAML or dict), key order, operating system and supported Python
  version.
- **FR-014**: The profile MUST have no field that holds a secret value.
  It may name a credential source (FR-016).

**Credentials**

- **FR-015**: Credentials MUST be explicit objects of the kinds listed in
  Story 3, plus an explicit "no credential" for targets that accept
  anonymous access, such as a local proxy. A target that requires a
  credential and gets none raises `AuthError`.
- **FR-016**: The SDK MUST NOT discover credentials from the environment,
  configuration files or the runtime on its own. It reads a source only
  when the caller's code or profile names it: an environment variable by
  name, a Databricks CLI profile by name, the runtime identity, or an
  explicit "no credential". A credential passed in code overrides the
  profile's source for the same target. A named source that is missing,
  empty or expired raises `AuthError` naming the source. The environment
  variables that the OpenAI and Databricks SDKs read on their own are an
  accepted exception (ADR 0018). When the SDK uses one of those clients
  and sees such a variable set, it logs a warning that names the
  variable, never its value.
- **FR-017**: A credential that can refresh MUST refresh only for the same
  identity, and a named Databricks CLI profile MUST be passed to the
  Databricks SDK by name. The SDK never retries under another identity,
  and never calls helpers that fall back to a service principal.
- **FR-018**: A credential kind that a target cannot use MUST be rejected
  when the model or connection is created, naming the kind and the target.
- **FR-019**: Secrets MUST be masked in printed objects, logs, errors and
  exception causes the SDK creates.

**Models**

- **FR-020**: The SDK MUST define the `ChatModel` and `EmbeddingModel`
  protocols of engine brief §6.4 and provide Databricks, OpenAI-compatible
  and fake implementations of both.
- **FR-021**: Each model MUST have a capability profile: its structured
  output strategies, accepted sampling parameters, schema limits, input
  token limit, embedding dimension, and query and passage prefixes. The
  SDK ships profiles for the model families the plan lists, starting with
  the Databricks foundation models, and the caller can override any value
  in the profile.
- **FR-022**: Structured output MUST follow the strategy order of Story 4
  and validate the parsed data against the given schema. Failure raises
  `LLMError`, never partial data.
- **FR-023**: Every model call MUST have a configurable timeout and a
  bounded retry budget for transient errors (rate limits, timeouts, server
  errors, dropped connections), with backoff that honours retry-after
  hints. Other errors fail at once.
- **FR-024**: Model clients MUST be safe to share across threads, MUST NOT
  send telemetry, and MUST NOT download anything at run time, such as a
  tokenizer. `count_tokens` returns unknown when no local count exists.
- **FR-025**: The fake models MUST ship in the package. They are
  deterministic, scriptable with responses and failures, record their
  calls and use no network.

**Connections**

- **FR-026**: The Neo4j wrapper MUST accept a connection address, a
  database name and a credential. It runs read and write units of work
  with whole-unit retry on transient errors, and its health check enforces
  server 2026.09 or later.
- **FR-027**: The Postgres wrapper MUST accept the connection settings and
  either a password or a token callback. It pools connections with a
  check before use and a configurable maximum age, whose default stays
  below the three-day connection limit of managed Postgres. It mints
  a new token for each new connection when given a callback, re-mints once
  on token expiry, retries whole units on transient errors, and checks
  server 16 or later with `vector` and `pg_trgm` available.
- **FR-028**: Both wrappers MUST bind each pool to one identity, require
  encryption for hosts that are not local unless the caller turns it off,
  pass all values as query parameters, and map failures to `AuthError` or
  to distinct `StorageError` kinds: unavailable, unsupported server, and
  failed query.
- **FR-029**: M0 MUST NOT create schemas, indexes or data in either store.
  That starts in M1.

**Docs**

- **FR-030**: The same change set MUST update `ARCHITECTURE.md` (the banner
  and which modules exist), the Commands section of `AGENTS.md`, and the
  `README.md` status and contributor setup.
- **FR-031**: Choices that later work depends on, such as the package
  manager, the gate tools and the HTTP client, MUST be recorded as ADRs.

### Key Entities

- **Profile**: the validated configuration a caller loads. In M0 it holds
  store connections, three model roles (extraction, answer, embedding),
  their credential sources and the graph language. Every field has a
  phase, and every index-time field has a stage.
- **Stage hash**: a deterministic digest of one stage's index-time values.
  Later milestones store it in run records and extraction cache keys.
- **Credential**: an explicit identity for one target. It has a kind, a
  source (code, a named environment variable, a named Databricks CLI
  profile, the runtime, or none), a masked secret, and a rule for
  refreshing for the same identity, or for never refreshing.
- **Capability profile**: what one model accepts and returns. The
  structured-output strategy and the request shape come from it.
- **Chat result**: the text, parsed data, strategy used and token usage of
  one chat call.
- **Connection**: a store's settings, a credential, a pool bound to that
  credential's identity, and a health report.
- **Error families**: `ConfigError`, `AuthError`, `StorageError` and
  `LLMError` under one base, each with subclasses that tell callers what
  to do next.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: From a fresh clone, on a machine with only Python and
  Docker, a contributor reaches green gates in 10 minutes or less by
  following the documented steps, with no account and no key.
- **SC-002**: The unit test suite finishes in under 60 seconds on a CI
  runner and makes zero network calls.
- **SC-003**: Every profile field declares a phase, and a field without
  one fails the gates.
- **SC-004**: For one profile, stage hashes match across both input forms
  and every Python version in CI. Changing any query-time field changes
  no hash. Changing only the embedding model changes exactly one.
- **SC-005**: In the credential failure suite, every missing, rejected or
  mismatched credential raises `AuthError` before any query or model call,
  and no source that TenetRAG resolves itself falls back to another
  identity.
- **SC-006**: A test plants known secret values, then scans all captured
  logs, printed objects and error texts. It finds none of them.
- **SC-007**: When an injected transient fault (server restart, dropped
  connection, rate limit) clears inside the retry budget, every case
  recovers. When it does not clear, every case fails with the documented
  error.
- **SC-008**: Importing the base package with no extras succeeds and loads
  no optional dependency, and the import check reports zero violations.
- **SC-009**: The same calling code runs against the Databricks,
  OpenAI-compatible and fake models, with only the profile changed.
- **SC-010**: A self-hosted setup (Neo4j or Postgres, and a local
  OpenAI-compatible server) starts from a profile file alone, with no
  credential code, no Databricks account and no Databricks package
  installed.

## Assumptions

- The repository is hosted on GitHub, since the brief ships wheels on
  GitHub Releases. CI runs on every push.
- Floors: Neo4j 2026.09, from the constitution. Postgres 16, the lowest
  version Lakebase offers.
- Exact names (credential constructors, classes, commands) are fixed in
  the plan and its contracts, since ADR 0003 left the constructor names to
  M0.
- Credentials are bound when a model or connection is created.
  Per-request override arrives with the serving client.
- Naming credential sources in the profile refines ADR 0003 without
  contradicting it: the caller still names the identity, and the SDK
  discovers nothing itself (ADR 0018).
- Planning read the source of both SDKs. The Databricks SDK fills unset
  settings from `DATABRICKS_*` variables, even for a named profile, and
  the OpenAI SDK reads three `OPENAI_*` variables that no argument turns
  off. The author accepted both on 2026-10-06 (ADR 0018), so the SDK
  warns about them.
- Stage hashes are not stored until M1 writes the first run record, so
  their format may still change until then. Whether a stage's hash covers
  the stages before it is decided with the engine in M1. In M0, each hash
  covers only its own stage's fields.
- Live tests against a real Databricks workspace or model endpoint are
  opt-in. They run only when a contributor supplies credentials through
  variables the test names. CI holds no secrets in M0 and runs none of
  them.
- All fixtures are synthetic (constitution principle I).
- Stage hashes across operating systems (FR-013): CI runs on Linux only.
  `test_hash_golden` pins the digests, so any system that runs the suite
  checks them, but no other system has run it yet.
- SC-010 was checked with a local stub server in place of Ollama, which
  was not installed (quickstart results). The stub proves the wiring and
  the missing Databricks package, not model quality.
- Gaps found when checking each requirement against its test (T066), with
  the reason each waits: the CI integration job on Python 3.11 (FR-005),
  a concurrency test for model clients (FR-024), the live Databricks
  smoke test (FR-021), and a pool rejection reported as unavailable
  (FR-028). See [docs/tech-debt.md](../../docs/tech-debt.md).
- Out of scope for M0:
  - the Anthropic and LiteLLM-native model classes and the reranker
    (later milestones);
  - Lakebase token minting, the runtime × identity × backend preflight,
    Delta and AI Search (M2; the Postgres token callback is where Lakebase
    plugs in);
  - the `GraphStore` and `VectorStore` protocols, store schemas, domain
    packs, ingest and the engine (M1);
  - prompt versioning (M4);
  - the PyPI placeholder, which the author reserves.
- Estimate: about six and a half working days for one developer with
  agents. Gates and skeleton take one day, the profile one, credentials
  one and a half (with sources named in the profile), models one and a
  half, and connections one and a half.
