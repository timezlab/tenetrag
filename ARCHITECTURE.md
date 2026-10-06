# Architecture

> **Intended shape. No code exists yet.** Update this page when the first
> package lands in M0, and from then on in the same PR as any change to
> module boundaries. The scope comes from the
> [SDK platform brief](docs/product/sdk-platform-brief.md). The engine's
> internals are settled in the [engine brief](docs/product/engine-brief.md)
> (reviewed 2026-10-05).

TenetRAG is a Python SDK. It indexes documents into a domain-defined
knowledge graph and serves graph-guided retrieval to user-built agents as a
Python API, tool specs or an MCP server
([ADR 0006](docs/decisions/0006-rename-to-tenetrag-and-run-beyond-databricks.md)).
Two deployment branches are built in parallel: on Databricks, the graph lives
in Lakebase (default) or Delta; elsewhere, in Neo4j (preferred) or Postgres
([ADR 0008](docs/decisions/0008-build-databricks-and-open-branches-in-parallel.md)).

## Module map

| Module | Owns | May import |
|---|---|---|
| `config` | Pydantic profile model (storage, vector, LLM, prompts, domain pack name and version, language, retrievers), loaded from YAML or dict. Every field is tagged index-time or query-time ([ADR 0005](docs/decisions/0005-index-time-vs-query-time-parameters.md)). | stdlib, pydantic |
| `packs` | Domain packs: load YAML, stack `extends`, check conflicts, compile flat structured-output schemas (no `$ref`/`anyOf`/`oneOf`/`allOf`/`pattern`, ≤ 64 keys), coverage check against competency questions; the default packs `core`, `enterprise-docs`, `finance` as package data ([ADR 0007](docs/decisions/0007-define-the-graph-schema-as-layered-domain-packs.md)). | stdlib, pydantic, pyyaml |
| `auth` | `Credentials` types (PAT, OAuth M2M, OAuth U2M, OBO token, runtime); the runtime × identity × backend matrix and its preflight check ([ADR 0003](docs/decisions/0003-caller-supplied-credentials.md)). | `config`; `databricks-sdk` only behind the `databricks` extra |
| protocols | `GraphStore`, `VectorStore` (vectors and chunk full-text search), `ChatModel`, `EmbeddingModel`, optional `Reranker`. Synchronous and batched; graph expansion is one `hop` per call ([ADR 0014](docs/decisions/0014-use-synchronous-protocols-with-one-hop-per-store-call.md)). Methods are defined by what the engine needs, fit both SQL and Cypher backends ([ADR 0008](docs/decisions/0008-build-databricks-and-open-branches-in-parallel.md)), and are listed in [engine brief §6](docs/product/engine-brief.md#6-protocols). | stdlib only |
| `engine` | Chunk → extract → validate → resolve → communities → retrieve; graph-guided retrieval, the opt-in query-strategy stage ([ADR 0010](docs/decisions/0010-offer-query-strategies-as-opt-in-benchmarked-options.md)) and the optional vector/graph router; provenance; text normalization; RRF fusion, final ranking, PageRank, event resolution and supersession ordering for every backend ([ADR 0013](docs/decisions/0013-resolve-events-by-identity-and-version-facts-in-the-engine.md)). | protocols, `config`, `packs` — **nothing else** |
| `ingest` | `scan(path)` → plan, `apply(plan)`; source listing (UC Volume, Workspace folder, local folder); document and chunk hashing; parser registry (`ai_parse_document` is one parser); parser and chunker adapters over permissive libraries ([ADR 0009](docs/decisions/0009-reuse-permissive-libraries-behind-adapters.md)). | `engine`, protocols, `config`, `auth`, parser and chunker libraries behind extras |
| `storage` | `postgres` (local, managed and Lakebase, one code path; Lakebase adds token minting and the connection wrapper), `delta` (UC tables via Spark or SQL warehouse), `neo4j` (graph and vector index, through the driver), `pgvector`, `ai_search` ([ADR 0002](docs/decisions/0002-graph-and-vector-storage-backends.md), [ADR 0008](docs/decisions/0008-build-databricks-and-open-branches-in-parallel.md)). | protocols, `config`, `auth`, backend drivers |
| `llm` | One class per provider (Databricks, OpenAI-compatible, Anthropic, optional LiteLLM), per-model capability profiles, structured-output strategies, fake models for tests. | protocols, `config`, `auth`, provider SDKs |
| `serving` | Public client (`scan`, `apply`, `retrieve`, `retrieve_multi_step`, `retrieve_global`, `answer`, `delete`, `benchmark`, `describe_schema`); builds stores and models from config; `as_tools()` with enums generated from the pack, plus LangChain/LangGraph and LlamaIndex adapters; MCP server (`serve`). | everything above |
| `benchmark` | Golden sets, variants, metrics, MLflow runs ([ADR 0004](docs/decisions/0004-sdk-owned-versioning.md)). Receives the client instance it measures as an argument, so it never imports `serving`. | `engine`, protocols, `config`, mlflow |
| `app` | Databricks App UI (separate brief). | `serving` public API only |

## Dependency direction

```
app ──► serving ──► ingest ──► engine ──► protocols ◄── storage, llm
            │                      ▲
            └──► benchmark ────────┘

config, auth: cross-cutting, imported by any layer except engine (which takes config only)
packs: cross-cutting and pure (stdlib, pydantic, pyyaml); engine may import it
```

- `engine` never imports `storage`, `llm`, `auth`, `databricks-sdk`,
  `pyspark` or any backend driver. Its unit tests run on fake stores and
  fake models.
- `serving` is the only module that wires implementations to protocols.
  Composition from config happens there and nowhere else.
- Optional dependencies stay behind extras (`postgres`, `databricks`,
  `delta`, `ai-search`, `neo4j`, `mcp`, `rerank`, `llamaindex`, `bench`,
  `communities`, `app`). Importing the base package must not require any of them, and in
  particular no Databricks package.
- A third-party library outside `engine` sits behind an adapter and meets
  the six conditions of
  [ADR 0009](docs/decisions/0009-reuse-permissive-libraries-behind-adapters.md):
  permissive license, optional extra, no ambient credentials, no telemetry or
  hidden downloads, no ownership of ids, offsets, hashes, runs or schema,
  and a pinned version.

## Where things run

| Runtime | Typical caller | Notes |
|---|---|---|
| Local machine | contributor, dev | Docker Neo4j (Community, 2026.09 or later) or Docker Postgres + pgvector, LiteLLM proxy or fake models |
| Own infrastructure | team outside Databricks | Neo4j (self-hosted or Aura) or managed Postgres; MCP server or in-process tools |
| Notebook / Lakeflow Job | data engineer | in-process `apply` by default; the job is optional ([brief](docs/product/sdk-platform-brief.md)) |
| Databricks Apps | MCP server, the app | per-request OBO token, or the app's SP |
| Model Serving | user's agent with in-process tools | OBO cannot reach Lakebase ([platform facts](docs/reference/databricks-platform.md#runtime--identity--backend)) |

## Cross-cutting invariants

- Per-domain errors: `ConfigError`, `AuthError`, `StorageError`, `LLMError`,
  `IngestError`.
- Every entity, relation, event and fact links to its chunks and documents, and
  records the domain pack and version that produced it. Relations and facts
  are one row per statement per chunk
  ([ADR 0012](docs/decisions/0012-store-relations-and-facts-as-one-row-per-chunk.md)).
- When one store holds the graph and the vectors, a document's vectors are
  written in its graph transaction
  ([ADR 0015](docs/decisions/0015-write-vectors-with-the-graph-when-one-store-holds-both.md)).
- One writer per index; an index run is the unit of consistency.
