# Quickstart: validate the SDK foundation (M0)

A run guide that proves each user story works. Shapes are in
[data-model.md](data-model.md), and signatures in [contracts/](contracts/).
The exact gate commands are copied into `AGENTS.md` when they land.

## Prerequisites

- Python 3.11 or later, and uv 0.12 or later. Install uv from its
  release page or a package manager, never with `curl | sh`.
- Docker, for the integration tests only.
- No Databricks account, no API key and no network beyond package
  downloads.

## 1. Gates from a fresh clone (Story 1, SC-001, SC-002, SC-008)

```sh
git clone <repo> tenetrag && cd tenetrag
uv sync --locked --all-extras        # fails if uv.lock is stale
make check                           # every gate below, in order
```

`make check` runs these. Each one can also be run alone:

| Gate | Command |
|---|---|
| format | `uv run ruff format --check .` |
| lint | `uv run ruff check .` |
| types | `uv run mypy` |
| imports | `uv run lint-imports` |
| unit tests | `uv run pytest -m "not docker and not live"` (network blocked) |
| integration | `uv run pytest -m docker` (needs Docker) |

**Expected:**
- every gate passes;
- the unit run finishes in under 60 seconds;
- `tests/unit/test_base_import.py` shows that a bare `import tenetrag`
  loads no optional package.

**Negative check:** add `import neo4j` to `src/tenetrag/protocols/models.py`,
and `lint-imports` fails, naming both modules. Revert it.

## 2. Profile and stage hashes (Story 2, SC-003, SC-004)

```python
from tenetrag.config import profile_from_yaml
from tenetrag.config.hashing import stage_hashes

base = """
models:
  extraction: {provider: fake, model: fake-chat}
  answer:     {provider: fake, model: fake-chat}
  embedding:  {provider: fake, model: fake-embed, dimensions: 8}
"""
a = stage_hashes(profile_from_yaml(base))
b = stage_hashes(profile_from_yaml(base.replace("answer:     {provider: fake, model: fake-chat}",
                                                "answer:     {provider: fake, model: other}")))
assert a == b                                  # answer model is query-time
```

**Expected:**
- Changing only `embedding.model` changes `a[Stage.EMBED]` alone.
- A misspelled key raises `ConfigError` that lists its path.

## 3. Credentials fail closed (Story 3, SC-005, SC-006)

```sh
export DATABRICKS_TOKEN=dummy OPENAI_API_KEY=dummy   # ambient values the SDK must ignore
uv run pytest tests/unit/auth -q
```

**Expected:**
- `test_ambient_vars_never_read` passes: no credential is taken from
  these variables when no source is named.
- `test_secrets_never_leak` passes.
- `unset DATABRICKS_TOKEN OPENAI_API_KEY` afterwards.

## 4. Models through one interface (Story 4, SC-009)

The unit tests cover all three providers with mocked HTTP:
`uv run pytest tests/unit/llm -q`.

**Self-hosted check (optional, SC-010).** With Ollama serving `qwen3`
and `bge-m3` locally, and only `pip install "tenetrag[openai,neo4j]"`
(no Databricks package):
1. Load the self-hosted profile of
   [contracts/config.md](contracts/config.md#example-profile-self-hosted).
2. Call `generate()` with a small schema, and `embed_documents()`.

The expected result is valid `data` and 1024-dimension vectors.

**Databricks live smoke (optional).** After `databricks auth login
--profile dev`:

```sh
TENETRAG_LIVE_DATABRICKS_PROFILE=dev uv run pytest -m live -q
```

**Expected:**
- A chat call with a schema succeeds.
- The embedding endpoint returns the dimension that its shipped profile
  states. If not, fix the profile.
- With `DATABRICKS_HOST` set (the test sets it to the profile's own
  host), one warning names it.

## 5. Store connections (Story 5)

```sh
uv run pytest -m docker -q
```

This starts the pinned `neo4j:2026.09.0-community` and
`pgvector/pgvector:0.8.7-pg16` and `-pg17` images through testcontainers.

**Expected:**
- the health reports pass the floors;
- a wrong password fails at once with `CredentialRejectedError`;
- a container restart during a unit of work recovers within the budget;
- the Postgres token minter is called once per new connection, and twice
  after a rejected token.

For a manual check, the local stack runs the same Neo4j image and the
pg17 image: `make dev-up`, then call `health()` as
[docs/guides/local-stack.md](../../docs/guides/local-stack.md) shows.

## Done when

- `make check` and `uv run pytest -m docker` pass locally and in CI on
  Python 3.11 and 3.14.
- `ARCHITECTURE.md`, the Commands section of `AGENTS.md` and `README.md`
  reflect what landed (FR-030).
