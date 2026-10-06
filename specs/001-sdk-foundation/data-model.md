# Data model: SDK foundation (M0)

The shapes M0 defines, with their validation rules. Names here are the
public names unless marked private (`_name`). Library choices are in
[research.md](research.md), and call signatures are in
[contracts/](contracts/).

## 1. Errors

All live in `tenetrag.protocols.errors`, which imports only the standard
library, so every module may import it, the engine included. They are
re-exported from `tenetrag.protocols` and from the top-level `tenetrag`
package.

```
TenetRAGError(Exception)
├── ConfigError(TenetRAGError, ValueError)
│   └── MissingExtraError          extra not installed; names the extra
├── AuthError(TenetRAGError)
│   ├── MissingCredentialError     target needs one, none given; names target and accepted kinds
│   ├── CredentialSourceError      named env var unset or empty, CLI profile missing or expired,
│   │                              no runtime identity; names the source, never a value
│   ├── CredentialMismatchError    kind the target cannot use; names kind and target
│   └── CredentialRejectedError    the server refused the credential (after the one allowed refresh)
├── StorageError(TenetRAGError)
│   ├── StoreUnavailableError      unreachable, or the retry budget ran out; names host and port
│   ├── UnsupportedServerError     version, edition or extension below the floor; names found and required
│   └── QueryError                 a non-transient failure of a unit of work
└── LLMError(TenetRAGError)
    ├── ModelUnavailableError      rate limit, timeout or server error after the retry budget
    ├── StructuredOutputError      parse or validation failed; carries strategy and attempts
    ├── OutputTruncatedError       the output hit the output-token limit
    ├── UnsupportedRequestError    schema construct, empty text or over-long text rejected before any call
    └── ResponseError              malformed provider response, such as a wrong vector dimension
```

Rules:
- Every message says what failed and what to do next (FR-009).
- A third-party exception is caught at the module boundary and re-raised
  as one of these, with `raise … from exc`.
- No message, attribute or cause the SDK builds holds a secret. The planted
  secret test (SC-006) checks messages, `repr`, `__cause__` chains and
  captured logs.

## 2. Profile

`tenetrag.config.Profile` is a Pydantic model, loaded by `load_profile`
from a YAML file, a YAML string or a dict.

### Fields in M0

| Path | Type | Default | Phase |
|---|---|---|---|
| `connections` | map of name → `Neo4jSettings` or `PostgresSettings` (by `kind`) | empty | operational |
| `models.extraction` | `ChatModelSettings` or none | none | index-time, stage `extract` |
| `models.answer` | `ChatModelSettings` or none | none | query-time |
| `models.embedding` | `EmbeddingModelSettings` or none | none | index-time, stage `embed` |
| `language` | language code, `^[a-z]{2,3}(-[A-Z]{2})?$` | `en` | index-time, stage `extract` |

**`ChatModelSettings`** (one discriminated model, by `provider`):

| Field | Applies to | Default | Marker |
|---|---|---|---|
| `provider` | all: `databricks`, `openai_compatible`, `fake` | required | content |
| `model` | all; the endpoint name on Databricks | required | content |
| `base_url` | `openai_compatible`, required | — | operational |
| `workspace_url` | `databricks`; required unless the credential carries the host (CLI profile, runtime) | — | operational |
| `temperature` | all | 0.0 | content |
| `max_output_tokens` | all | none | content |
| `capabilities` | all; overrides of §5 | none | content |
| `credential` | all except `fake`; a `CredentialSource` (§3) | none | operational |
| `timeout_seconds` | all | 120 | operational |
| `retry` | all; `RetrySettings` | §6 | operational |
| `log_content` | all; log prompt and response text at DEBUG | false | operational |

**`EmbeddingModelSettings`**: `provider`, `model`, `base_url` or
`workspace_url`, `dimensions` (content; required unless the shipped
capability profile gives it), `capabilities` (content), `batch_size`
(operational, default 64), `credential`, `timeout_seconds` (60),
`retry` and `log_content` (operational).

**`Neo4jSettings`** (`kind: neo4j`), all operational: `uri`
(`neo4j://`, `neo4j+s://`, `bolt://`, `bolt+s://`), `database`
(default `neo4j`), `credential`, `tls` (§7), `pool` (§7),
`connect_timeout_seconds` (15), `retry` (§6).

**`PostgresSettings`** (`kind: postgres`), all operational: `host`,
`port` (5432), `database`, `credential`, `tls`, `pool`,
`connect_timeout_seconds` (15), `retry`.

### Loading rules

- YAML goes through a safe loader that also rejects duplicate keys in a
  mapping. Tags that build objects are rejected.
- Unknown fields are rejected (`extra="forbid"` on every model). The error
  for a key named like a secret (`password`, `token`, `api_key`, `secret`)
  adds: "credentials are passed in code, or named as a source under
  `credential`".
- All problems are reported in one `ConfigError`, one line per problem,
  each with its dotted path.
- An empty document is a `ConfigError`.
- The loaded `Profile` is frozen.

## 3. Credential sources (in the profile)

`CredentialSource` is a discriminated union on `kind`. It names where a
secret comes from, never the secret.

| `kind` | Fields | Accepted by |
|---|---|---|
| `none` | — | `openai_compatible`, Neo4j |
| `api_key` | `env` | `openai_compatible` |
| `basic` | `user`, `password_env` | Neo4j, Postgres |
| `pat` | `token_env` | `databricks` |
| `oauth_m2m` | `client_id`, `client_secret_env` | `databricks` |
| `oauth_u2m` | — (uses `workspace_url`) | `databricks` |
| `cli_profile` | `name` | `databricks` |
| `runtime` | — | `databricks` |

Environment variable names match `^[A-Za-z_][A-Za-z0-9_]*$`. Three kinds
exist only in code, since they come from a request or from the caller's
program: `obo`, `token_provider` and `workspace_client` (§4).

Postgres takes no `none`. libpq reads `PGPASSWORD` and `~/.pgpass` when no
password is passed, so the wrapper always passes one: a `basic` password
or a minted token.

Databricks `oauth_m2m`, `oauth_u2m`, `cli_profile`, `runtime` and
`workspace_client` delegate to the Databricks SDK. That SDK fills
settings left unset from `DATABRICKS_*` variables (ADR 0018). The resolver
passes `auth_type` explicitly, and logs a warning naming any such
variables that are set. `pat` and `obo` are plain bearer tokens and need
no Databricks SDK.

## 4. Credentials (in code)

`tenetrag.auth.Credentials` builds `Credential` objects. Each is frozen
and has:
- `kind`: one of the kinds of §3, plus `obo`, `token_provider` and
  `workspace_client`;
- `identity`: a non-secret label, such as `basic:neo4j`,
  `cli_profile:dev` or `pat:adb-123.azuredatabricks.net`. Pools are keyed
  by it, and errors name it;
- `source`: `code`, `env:NAME`, `cli_profile:NAME` or `runtime`;
- `refreshable`: whether a new token can be obtained for the same
  identity. True for `oauth_m2m`, `oauth_u2m`, `cli_profile`, `runtime`,
  `workspace_client` and `token_provider`. False for `pat`, `obo`,
  `api_key` and `basic`.

**`Secret`** wraps a string. Its `repr` and `str` are `Secret('***')`, and
`reveal()` returns the value. Only the code that builds an HTTP header or
a driver argument calls it.

**Token flow.** Bearer kinds hand out an `AccessToken(value: Secret,
expires_at: datetime | None)` through a private `_TokenSource`.
- It is cached until shortly before `expires_at`. A lock makes the refresh
  happen once across threads.
- `invalidate()` is called once after the server rejects the token as
  expired. The next call refreshes it for the same identity. A second
  rejection raises `CredentialRejectedError`.

**Resolution** (`resolve_credential(target, source, override)`):
1. A credential passed in code (`override`) wins.
2. Otherwise the profile's `source` is resolved: the named variable is
   read, the CLI profile is opened, or the runtime identity is requested.
3. With neither, `MissingCredentialError` names the target and the kinds
   it accepts.
4. A kind outside the target's accepted set raises
   `CredentialMismatchError`.

No step reads a variable, file or runtime the caller did not name.

## 5. Capability profile

`tenetrag.llm.CapabilityProfile` (frozen):

| Field | Meaning |
|---|---|
| `strategies` | supported structured-output strategies. The class uses the first in the fixed order `native_schema`, `tool_call`, `json_mode`, `prompt_parse` that the profile lists |
| `accepts_temperature`, `accepts_top_p` | when false, the class drops that parameter |
| `forbidden_schema_keywords` | such as `$ref`, `anyOf`, `oneOf`, `allOf`, `pattern` on Databricks |
| `max_schema_properties` | 64 on Databricks |
| `max_input_tokens`, `max_output_tokens` | none when unknown |
| `embedding_dimensions` | for embedding models |
| `query_prefix`, `passage_prefix` | empty by default |
| `parse_retries` | re-asks after a parse or validation failure, default 2 |

- **Lookup:** shipped profiles match the model name by prefix.
  `capabilities` in the profile overrides individual fields.
- **Unknown models:** `strategies = [prompt_parse]` and no schema limits.
  This works on every server. The caller widens it in the profile once
  the server is known to support more.
- **No guessing at run time:** the class never switches strategy after
  seeing an error, so a run is reproducible.

## 6. Retry settings

`RetrySettings` (operational):

| Field | Models | Stores |
|---|---|---|
| `max_attempts` | 5 | 5 |
| `max_total_seconds` | 60 | 30 |
| `initial_backoff_seconds` | 0.5 | 0.2 |
| `max_backoff_seconds` | 8 | 4 |

- Backoff is exponential with full jitter. A `Retry-After` or
  `retry-after-ms` hint replaces the computed delay when it fits the
  remaining budget.
- Each failure is classified as `retry`, `reauth` or `fail`.
  - `reauth` means a rejected token on a refreshable credential: the token
    is invalidated once and the call is retried once, without using up a
    retry attempt.
  - Store retries replay the whole unit of work.

## 7. Connections

**TLS** (`tls`):
- `auto` (the default) requires encryption unless the host is a loopback
  address or `localhost`.
- `require` encrypts, and `verify` also checks the certificate and host
  name.
- `off` must be set explicitly for a non-local host.

**Pool** (`pool`):
- `max_size` (8), `max_age_seconds` (43200, that is 12 hours, below
  Lakebase's 3-day limit) and `acquire_timeout_seconds` (30).
- Postgres also has `min_size` (1), and a liveness check before each
  checkout.
- A pool belongs to one `Credential.identity`. Work under another identity
  opens another pool.

**`HealthReport`** (frozen):
- `backend`: `neo4j` or `postgres`;
- `server_version`;
- `edition`: Neo4j only;
- `extensions`: Postgres only, as name → available;
- `identity`, `encrypted`.

**Floors:**
- Neo4j 2026.09.
- Postgres 16, with `vector` and `pg_trgm` available (installed, or
  installable).

## 8. Phases and stage hashes

**Markers.** Each leaf field of `Profile` carries exactly one marker in
its `Annotated` metadata:
- `IndexTime(stage)`: index-time, in that stage;
- `QueryTime()`: query-time;
- `Content()`: takes the phase and stage of the nearest ancestor field
  that has `IndexTime` or `QueryTime`;
- `Operational()`: always query-time, even under an index-time ancestor
  (FR-012).

A `Content()` leaf with no phased ancestor, or a leaf with no marker,
fails `tests/unit/config/test_phases.py`, and the failure names the
dotted path (SC-003).

**Stages:** `chunk`, `extract`, `resolve`, `embed`, `cluster`, `reports`,
from engine brief §9. A field the brief lists under "card" belongs to
`extract`. M0 has fields only in `extract` and `embed`. The other stages
hash an empty field set until M1 adds fields.

**Hash** (`tenetrag.config.hashing.stage_hashes(profile)`, the one module
of ADR 0005) returns `{stage: "sha256:<hex>"}`. The input is canonical
JSON of `{"format": 1, "stage": <name>, "fields": {<dotted path>:
<value>}}`:
- the index-time leaves of that stage only, after defaults are filled in;
- strings in NFC;
- keys sorted, compact separators, `ensure_ascii=False`.

Golden hashes for two fixture profiles are pinned in the tests, so a
change of format or field set is a visible test change.

## 9. Model results

From [engine brief §6.4](../../docs/product/engine-brief.md#64-model-protocols),
with two additive fields:
- `Message(role: "system" | "user" | "assistant", content: str)`.
- `Usage(input_tokens, cached_input_tokens, output_tokens)`: each
  `int | None`, and `None` when the provider does not report it.
- `ChatResult`:
  - `text`;
  - `data`: parsed JSON, or `None` without a schema;
  - `usage`, `model_id`;
  - `strategy`: a `Strategy` or `None` (added);
  - `finish_reason` (added).

## 10. Fake models

**`FakeChatModel(responses=…, model_id="fake-chat")`**
- It takes a sequence of scripted items, each a text, a dict (returned as
  `data` and as JSON text) or an exception to raise. A callable
  `(messages, schema) -> item` can be passed instead.
- It records each call as `(messages, schema, params)`.
- It raises `AssertionError` when the script runs out, so a test never
  passes on a default.

**`FakeEmbeddingModel(dimensions=8)`**
- It returns a unit vector derived from SHA-256 of the prefixed text, so
  the same text always gives the same vector, and the query and passage
  prefixes differ.
- It records each call.

Both report usage as `None` counts unless the script sets them.
