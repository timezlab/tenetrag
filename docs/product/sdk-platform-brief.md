# TenetRAG — SDK design brief (2026-10-02, repositioned 2026-10-03)

Status: reviewed by the author on 2026-10-04. The questions still open are
listed at the end. Decisions taken here are recorded in
[ADRs 0001–0011](../decisions/). On 2026-10-03,
[ADR 0006](../decisions/0006-rename-to-tenetrag-and-run-beyond-databricks.md)
renamed the project from `databricks-graphrag` to TenetRAG and made Databricks
one deployment target among others. On 2026-10-04, three more decisions
were added:
- the Databricks and open branches are built in parallel, with Neo4j in
  v1 ([ADR 0008](../decisions/0008-build-databricks-and-open-branches-in-parallel.md));
- permissive libraries may be reused behind adapters
  ([ADR 0009](../decisions/0009-reuse-permissive-libraries-behind-adapters.md));
- query strategies are opt-in and benchmarked
  ([ADR 0010](../decisions/0010-offer-query-strategies-as-opt-in-benchmarked-options.md)).

On 2026-10-05, communities were decided: the graph is clustered by
default, and community reports and global search are opt-in
([ADR 0011](../decisions/0011-cluster-by-default-and-make-community-reports-opt-in.md)).

The author's review answers of 2026-10-04 are recorded in place: Neo4j is
preferred outside Databricks and starts in M1, every backend shares a
per-document consistency floor, AI Search pairs only with a Delta graph,
and the benchmark quality rule is fixed.

Scope: the platform around the core
engine. The core engine (parse → chunk → extract → resolve → communities →
retrieval, exact schema) gets its own brief; so does the app UI. The graph
schema users define, and the default packs, are in the
[domain packs brief](domain-packs.md).

**Goal** — Developers who build their own agents, on Databricks or
elsewhere, can index an organisation's documents into a domain-defined
knowledge graph of dated, evidence-backed facts, and attach it to those agents
as a tool or MCP server. Retrieval uses the graph to find the right chunks and
returns both. Agents get sourced business context (definitions, decisions,
events, formulas, historical figures) that table-oriented tools such as Genie
do not provide. Two deployment branches are built in parallel: on
Databricks, Lakebase (default) or Delta; elsewhere, Neo4j (preferred) or
Postgres.

**Users & pain**
- Users: developers/AI engineers building custom agents, on Databricks
  (Apps, Model Serving, notebooks, jobs) or on their own infrastructure. Two
  audiences at once: the open-source community, with Databricks users first,
  and the author's team at their employer, the first internal adopter.
- Retrieval consumers are those agents (tool calls, MCP), not people; a
  convenience `answer()` exists, but retrieval is the product.
- Pain on Databricks: it has no graph store, so GraphRAG there means an external
  graph DB (the official demo uses Neo4j) or a non-native sample. Existing
  engines fit badly: Microsoft GraphRAG is in maintenance mode and cannot
  delete or update documents incrementally; LightRAG's storage pattern is many
  small writes and it has no claim/temporal layer; LlamaIndex has no Postgres
  graph store and cannot cascade deletes.
- Typical question: "what decisions and definitions exist about campaign A,
  from which meeting, when, according to which document?"
- Not quantified. The first adopter's corpus is a few hundred documents,
  expected to grow to thousands, with periodic additions, edits and deletions.

**Constraints**
- Discovered (repo): greenfield; Python rule pack (Pydantic at boundaries,
  `Protocol` seams, per-domain exceptions, fail-closed on auth/validation);
  Spec Kit 0.13.4 initialized, constitution still a template; dependency-gate
  security hook.
- Discovered (platform research, verified 2026-10-02; facts and sources in
  [databricks-platform.md](../reference/databricks-platform.md)): no graph
  store or AGE, so the graph is relational tables plus recursive CTEs;
  Lakebase uses per-connection OAuth tokens and cannot use its PgBouncer;
  what OBO reaches differs by runtime, and only the SQL warehouse is reachable
  under OBO from both Apps and Model Serving; Volumes and Workspace files are
  unsuitable for in-place writes; no mature Databricks-native GraphRAG exists.
- Supplied (author):
  - Open-source code under Apache-2.0 with a NOTICE file; wheels on GitHub
    Releases. On PyPI, only a 0.0.0 placeholder reserves the name
    `tenetrag`. No employer IP approval is needed (author, 2026-10-04).
  - Python 3.11 or later.
  - Generic defaults; domain specifics only through configuration. Nothing
    adopter-specific in the public repo (adopter notes live in gitignored
    `docs/private/`).
  - Own core engine; Microsoft GraphRAG and LightRAG are architecture
    references, not dependencies. Permissive libraries, LlamaIndex
    included, may be reused outside the engine behind adapters
    ([ADR 0009](../decisions/0009-reuse-permissive-libraries-behind-adapters.md)).
  - Two deployment branches, developed in parallel
    ([ADR 0008](../decisions/0008-build-databricks-and-open-branches-in-parallel.md)):
    - Databricks: graph in Lakebase (default) or UC tables (Delta);
      vectors in pgvector (default) or AI Search (optional).
    - Open: graph and vectors in Neo4j with its vector index (preferred),
      or in Postgres with pgvector (fallback).

    Graph and vector stores are chosen independently, so users may mix.
  - The caller chooses and supplies credentials (PAT, service principal, OBO,
    …); the SDK passes them through.
  - LLMs: Databricks serving endpoints / AI Gateway on Databricks; other
    providers (Anthropic, Qwen, OpenAI-compatible such as a LiteLLM proxy)
    anywhere.
  - Formats: PDF, DOCX, PPTX, XLSX, MD, TXT and more; Vietnamese and English.
  - Indexing runs in-process by default; a Lakeflow Job is optional because
    some users lack job permissions.
  - v1 includes everything in this brief, the benchmark, and the app (app
    after the SDK). Solo developer with AI agents, no deadline. The early
    one-week estimate predates Neo4j and the Databricks branch, so each
    milestone's spec now carries its own estimate.

**Chosen approach — "own core, borrowed algorithms"**

Design principles:
1. The engine depends only on protocols (`GraphStore`, `VectorStore`,
   `ChatModel`, `EmbeddingModel`) and never imports a backend, Spark or
   databricks-sdk. Protocol methods are defined by engine needs (engine brief)
   and fit both SQL and Cypher backends. The engine keeps normalization,
   fusion, ranking and PageRank, so backends stay thin.
   [ADR 0001](../decisions/0001-build-own-graphrag-core.md),
   [ADR 0002](../decisions/0002-graph-and-vector-storage-backends.md),
   [ADR 0008](../decisions/0008-build-databricks-and-open-branches-in-parallel.md).
2. Every parameter is classified as index-time (changes the graph: chunking,
   embedding model, extraction prompt/model) or query-time (retriever, top-k,
   answer model). This one classification drives re-index detection,
   benchmark cost and versioning.
   [ADR 0005](../decisions/0005-index-time-vs-query-time-parameters.md).
3. Provenance is mandatory: every entity, relation, event and fact traces to chunks
   and documents. It powers citations and keeps document-level ACLs possible
   later without re-indexing.
4. No implicit identity: credentials are explicit objects. A missing requested
   credential, or a runtime × backend combination that cannot work, fails
   before any query with the reason; the SDK never falls back to another
   identity. [ADR 0003](../decisions/0003-caller-supplied-credentials.md).
5. Source text is never translated; figures stay verbatim with time and
   source. Text is normalized only where no meaning is lost (Unicode NFC,
   Vietnamese tone-mark placement); diacritics are kept, so matching tells
   `lãi`, `lại` and `lai` apart. The extraction model normalizes numbers
   and units into typed values, and code checks them against the quote;
   entities get a canonical name in a configurable graph language plus
   aliases; entity resolution is pluggable (multilingual embeddings propose,
   LLM confirms). A name alone never identifies an entity: each type
   declares whose thing it is, which attributes prove two mentions the
   same and which prove them different, and every identity value carries
   a checked quote
   ([ADR 0016](../decisions/0016-identify-entities-by-scope-keys-and-vetoes.md)).
6. The graph is always built, and retrieval is graph-guided. The graph finds
   entities and facts. Vector search then finds the chunks they rest on.
   Results carry chunks, facts and evidence. An optional router, off unless
   the user enables it, sends a query to plain vector RAG instead.
   Each run clusters the graph into communities without an LLM. Community
   reports and global search are opt-in and never the default path.
   [ADR 0006](../decisions/0006-rename-to-tenetrag-and-run-beyond-databricks.md),
   [ADR 0011](../decisions/0011-cluster-by-default-and-make-community-reports-opt-in.md).
7. The graph schema is a versioned, layered domain pack (`core` → domain
   pack → user pack) that drives extraction, validation, entity resolution
   and retrieval. v1 ships `core`, `enterprise-docs` and `finance`.
   [ADR 0007](../decisions/0007-define-the-graph-schema-as-layered-domain-packs.md),
   [domain-packs.md](domain-packs.md).
8. Query strategies (temporal parsing, entity extraction, bilingual and
   multi-query variants, HyDE, Query2doc, questions per chunk) are opt-in
   options. Multi-step decomposition is a separate method,
   `retrieve_multi_step()`. Each one is a benchmark variant reported per
   question type. The no-LLM pipeline stays the default, and rewriting a
   query from chat history is the calling agent's job.
   [ADR 0010](../decisions/0010-offer-query-strategies-as-opt-in-benchmarked-options.md).
9. Agents can read the schema. Tool specs carry the pack's type names as
   enums, and a `describe_schema` tool returns a compact summary of the
   merged pack
   ([domain-packs.md](domain-packs.md#how-the-pack-is-used)).

Layers (`app` → `serving` → `engine` → protocols ← implementations;
`config` and `auth` are cross-cutting):

| Component | Responsibility |
|---|---|
| `config` | One Pydantic profile model (storage, vector, LLM, prompts, domain pack name and version, language, retrievers), loaded from YAML or dict. |
| `packs` | Load, stack and check domain packs; compile them into flat structured-output schemas; ship the default packs `core`, `enterprise-docs` and `finance` ([domain-packs.md](domain-packs.md)). |
| `auth` | `Credentials` (PAT, OAuth M2M, OAuth U2M, OBO token, Databricks runtime), per client with per-request override; runtime × backend capability matrix with a preflight check. |
| `llm` | One class per provider (Databricks, OpenAI-compatible, Anthropic, optional LiteLLM) with a per-model capability profile that picks the structured-output strategy (native schema → tool call → JSON mode → parse + validate + retry), user-overridable; Databricks token refresh; chat and embedding configured separately; fake models for tests. |
| `storage` | Graph stores: `postgres` (local, managed and Lakebase share code; Lakebase adds token minting), `delta` (UC tables via Spark or SQL warehouse) and `neo4j` (self-hosted or Aura, through the driver). Vector stores: `pgvector`, `ai_search` and the Neo4j vector index ([ADR 0008](../decisions/0008-build-databricks-and-open-branches-in-parallel.md)). |
| `ingest` | `scan(path)` over a UC Volume, Workspace folder or local folder returns a plan; `apply(plan)` executes it. Pluggable parser registry (`ai_parse_document` is one parser); parsers and the chunker wrap permissive libraries behind adapters ([ADR 0009](../decisions/0009-reuse-permissive-libraries-behind-adapters.md)). |
| `engine` | Core GraphRAG pipeline and retrieval methods, including the opt-in query-strategy stage ([ADR 0010](../decisions/0010-offer-query-strategies-as-opt-in-benchmarked-options.md)) and the optional vector/graph router — engine brief. |
| `serving` | Python API (`scan`, `apply`, `retrieve`, `retrieve_multi_step`, `retrieve_global`, `answer`, `delete`, `benchmark`, `describe_schema`); `as_tools()` (JSON-schema tool specs with enums generated from the pack, plus LangChain/LangGraph and LlamaIndex adapters); MCP server (`serve`) with a Databricks Apps template. |
| `benchmark` | Golden sets, configuration variants, metrics, MLflow runs. |
| `app` | Databricks App over the public SDK API only — separate brief. Folder browser and plan review, apply, graph view, chat over `answer()`, a retrieval inspector that shows the raw `retrieve()` output for a typed query, and benchmark runs. |

Storage guarantees:
- Batch, idempotent writes keyed by content hashes. Delete by document
  cascades through provenance.
- Every backend meets one consistency floor
  ([ADR 0008](../decisions/0008-build-databricks-and-open-branches-in-parallel.md)):
  each document is atomic, and a run record marks when a run completes.
  After a crash, some documents have their new version and the rest keep
  the old one; running `apply` again skips the finished documents by hash.
  Postgres and Neo4j commit one transaction per document; Delta exposes
  batches through a `run_id` commit marker (open question 2).
- Query-time Delta reads go through an in-process cache refreshed when the
  table version changes, avoiding SQL-warehouse latency on every query.
- The SDK computes embeddings itself, so pgvector, AI Search and the Neo4j
  vector index use the same model. With a Delta graph, AI Search reads them
  through a Delta Sync index with self-managed embeddings, and the SDK
  reports or waits for sync lag. AI Search pairs only with a Delta graph:
  a Lakebase graph always uses pgvector, and config loading rejects other
  pairings with a `ConfigError`.
- Connection wrapper (Lakebase and local Postgres): pool with a credential
  callback, pre-ping, recycling before the 3-day connection limit, retry with
  backoff on transient errors (dropped connection, restart, scale-to-zero
  wake-up, too many connections), one re-mint on token expiry, immediate
  failure on other auth errors, errors mapped to `StorageError` subclasses.
  Retries replay whole transactions only.

Ingest and change detection:
- Two-level hashing: a document hash classifies documents as new, changed,
  unchanged or missing; chunk hashes reuse cached extraction for unchanged
  chunks of changed documents. A pipeline version (parser, index-time
  parameters, prompt versions) flags documents for re-index when the pipeline
  changes.
- A plan lists file counts and sizes per format, skipped files with reasons,
  new/changed/unchanged/deleted documents, and estimated pages, tokens and
  cost. Nothing indexes without a plan.
- Deleting documents that vanished from the source is opt-in and shown in the
  plan; deletions above a threshold need an explicit flag.
- Indexing runs in-process by default or as a configured Lakeflow Job (entry
  point plus bundle template). The app follows the same rule: in-process by
  default, a job when the user opts in. One writer per index: a concurrent
  `apply` fails fast.

Benchmark:
- Golden set as JSONL, CSV or a Delta table: question, optional expected
  answer, expected sources, tags.
- Two baselines: naive vector retrieval, and hybrid retrieval (BM25 plus
  dense, fused with RRF). A vector RAG suite also benchmarks these
  pipelines on their own, end to end, beside the full graph flow.
- Quality rule: graph-guided retrieval must beat the hybrid baseline on
  most target question types (everything about an entity, as-of-date,
  decisions) and lose no more than a small margin on single-fact lookups.
  The margins and thresholds are set from the first realistic golden set.
- Variants over index-time and query-time parameters (for example embedding
  model A vs B, chunk size X vs Y, naive vector vs graph retrieval, each
  query strategy against the no-LLM baseline, one backend against another,
  `retrieve_global()` against the baselines on global questions).
  Query-strategy variants also report extra LLM calls, p50 and p95 latency
  and the worst per-type loss
  ([ADR 0010](../decisions/0010-offer-query-strategies-as-opt-in-benchmarked-options.md)). Indexes are
  reused when index-time configuration hashes match, and chunks and
  extractions are reused when only the embedding model differs; a plan with
  estimated cost precedes the run.
- Metrics: deterministic retrieval metrics (hit@k, recall@k, MRR, RAGAS
  non-LLM context metrics), latency and token usage, plus RAGAS/DeepEval
  scorers through `mlflow.genai.evaluate` with a configurable judge model;
  each failure is categorized (source missed, noisy context, wrong answer
  despite right context, unfaithful answer) and broken down by tag. One MLflow
  run per variant. Docs advise spot-checking LLM judges against human labels
  for Vietnamese.

Versioning (owned by the SDK; the app is a UI over it;
[ADR 0004](../decisions/0004-sdk-owned-versioning.md)): prompts resolve from
MLflow Prompt Registry (Databricks UC or local MLflow server) by alias such as
`@production`, with inline profile prompts as fallback. Every index run
records prompt versions, configuration hash and pipeline version.

Errors: per-domain exceptions (`ConfigError`, `AuthError`, `StorageError`,
`LLMError`, `IngestError`). Auth fails closed. Per-file ingest failures are
skipped and reported while the rest of the run commits.

Testing: unit tests run on fake models and local Neo4j and Postgres in
Docker (no workspace, no API keys); one parametrized contract suite per store protocol
runs on Postgres and Neo4j (pinned Community image) in CI and on Delta, AI
Search and Lakebase in a workspace; workspace integration tests cover the
auth matrix and the MCP server on Apps; golden sets double as quality
regression tests. Test data comes in three tiers: a synthetic bilingual
corpus with planted ground truth in the repo, public proxy corpora
downloaded locally, and the adopter's real corpus run in place
([test-corpora.md](../reference/test-corpora.md)).

Packaging: one package, `tenetrag`, with extras (`postgres`, `databricks`,
`delta`, `ai-search`, `neo4j`, `mcp`, `rerank`, `llamaindex`, `bench`,
`communities`, `app`). The `app` extra includes `communities`
([ADR 0011](../decisions/0011-cluster-by-default-and-make-community-reports-opt-in.md)).
Importing the base package needs
no Databricks dependency; CI builds wheels and attaches them to GitHub Releases;
Databricks installs them from a UC Volume; bundle templates for the indexing
job and the MCP app.

Milestones (all of them belong to v1, Neo4j included):

| | Content | Depends on |
|---|---|---|
| M0 | Repo gates (formatter, linter, type-checker, pytest), config, credentials, LLM classes (Databricks, OpenAI-compatible, fake), Neo4j and Postgres connection wrappers | this brief |
| M1 | End-to-end on local Neo4j and local Postgres + LiteLLM: scan → apply → retrieve → answer, edit/delete, core retrieval metrics; the parametrized contract suite on both; the synthetic test corpus; packs `core` and `enterprise-docs` | engine brief, Neo4j backend spec |
| M2 | Databricks branch: Lakebase, Delta + AI Search, auth-matrix preflight, indexing job | M1 |
| M3 | Tool adapters (pack-generated enums, `describe_schema`) and MCP server on Apps (OBO) | M2 |
| M4 | Full benchmark (RAGAS/DeepEval, both baselines, the vector RAG suite, variants, failure categories, query-strategy variants), prompt versioning, the `finance` pack | M1 |
| M5 | `retrieve_multi_step()`; communities, with clustering on by default and community reports and `retrieve_global()` opt-in ([ADR 0011](../decisions/0011-cluster-by-default-and-make-community-reports-opt-in.md)); advanced retrievers | engine brief, M4 |
| M6 | App UI, full scope as listed under `app` | app brief, stable API |

**Alternatives considered** (full reasoning in the linked ADRs)
- *LightRAG core + Databricks shell*: storage pattern unsuited to Delta,
  closed query modes, no temporal claims ([ADR 0001](../decisions/0001-build-own-graphrag-core.md)).
- *Wrap several engines* (the original idea): lossy shared schema, retrieval
  modes not interchangeable ([ADR 0001](../decisions/0001-build-own-graphrag-core.md)).
- *No graph* (Knowledge Assistant, or AI Search over entity-tagged chunks):
  retrieval not customizable; naive vector stays as the benchmark baseline
  ([ADR 0001](../decisions/0001-build-own-graphrag-core.md)).
- *SQLite for local work*, *Volumes or Workspace files as the graph store*
  ([ADR 0002](../decisions/0002-graph-and-vector-storage-backends.md)).
- *Versioning in the app* ([ADR 0004](../decisions/0004-sdk-owned-versioning.md)).
- *Databricks-only scope under the name `databricks-graphrag`*, *the graph as
  an optional tier* ([ADR 0006](../decisions/0006-rename-to-tenetrag-and-run-beyond-databricks.md)).
- *A type list injected into the prompt*, *LinkML as the runtime pack
  format*, *many default packs in v1*
  ([ADR 0007](../decisions/0007-define-the-graph-schema-as-layered-domain-packs.md)).
- *Lakebase only on Databricks*, *Neo4j after v1*, *neo4j-graphrag's writer*
  ([ADR 0008](../decisions/0008-build-databricks-and-open-branches-in-parallel.md)).
- *Keep the library ban*, *LlamaIndex as the framework*
  ([ADR 0009](../decisions/0009-reuse-permissive-libraries-behind-adapters.md)).
- *Postgres as the default outside Databricks*, *whole-run atomicity on
  every backend*, *AI Search over a Lakebase graph*
  ([ADR 0008](../decisions/0008-build-databricks-and-open-branches-in-parallel.md)).
- *HyDE on by default*, *all query rewriting left to the agent*,
  *conversational rewriting in the SDK*
  ([ADR 0010](../decisions/0010-offer-query-strategies-as-opt-in-benchmarked-options.md)).
- *Community reports always built, as in Microsoft GraphRAG*, *no
  communities in v1*, *clustering only the new documents*
  ([ADR 0011](../decisions/0011-cluster-by-default-and-make-community-reports-opt-in.md)).
- *A narrow app (schema design and retrieval inspection only)*: rejected by
  the author on 2026-10-04; the app keeps its full scope.

**Out of scope (v1)**
- Content authorization (document-level ACLs, RLS); platform permissions
  apply, and provenance keeps the door open.
- Text-to-SQL and numeric analytics (Genie's job).
- Knowledge Assistant / Agent Bricks integration.
- PyPI publishing, apart from the 0.0.0 placeholder that reserves the name.
- Data connectors (SharePoint, Confluence, Drive and similar); users copy
  files to a folder or Volume.
- Conversational agent memory, and rewriting queries from chat history.
- Community summaries as the default retrieval path.
- An own OCR or layout parser; parsers are wrapped behind adapters.
- Running Microsoft GraphRAG, LightRAG or LlamaIndex as engines. Reusing
  LlamaIndex or other permissive components behind adapters is allowed
  ([ADR 0009](../decisions/0009-reuse-permissive-libraries-behind-adapters.md)).
- An agent framework or chat product; agents belong to users, and the app's
  chat and retrieval inspector are test surfaces over `answer()` and
  `retrieve()`.
- Volumes/Workspace files as graph stores or snapshot targets; SQLite.
- Synthetic golden-set generation as an SDK feature. The repository's own
  test-corpus generator is a development tool, not part of the SDK.

**Success criteria (v1)**
1. From a fresh clone, a contributor runs the unit and contract suites with
   Docker Postgres, Docker Neo4j and fake models — no workspace, no API keys.
2. On a real corpus, `scan` of a Volume path reports counts, sizes, skipped
   files and an estimate; `apply` indexes it; editing one document re-indexes
   only that document and reuses extraction of its unchanged chunks; deleting
   a document removes everything derived only from it.
3. A custom agent on Databricks retrieves context through the MCP server on
   Apps under OBO and through in-process tools under SP or PAT; every
   returned fact names its source document and chunk.
4. Every credential × runtime × backend combination in the matrix either
   works or fails before querying with an error naming the reason, as
   exercised by integration tests.
5. A benchmark over a golden set yields one MLflow run per variant with
   retrieval metrics, RAGAS/DeepEval scores and failure categories, including
   naive vector and hybrid baselines vs graph. Graph-guided retrieval meets
   the quality rule under Benchmark on the first realistic golden set.
6. Changing an index-time parameter (such as the extraction prompt version)
   marks the affected documents for re-index in the next plan; changing a
   query-time parameter does not.
7. Wheels from a GitHub Release install on Databricks serverless from a UC
   Volume.
8. Through the app, a user selects a folder, reviews the plan, applies it,
   views the graph, chats, types a query and inspects exactly what `retrieve()`
   returns (entities, relations, events, facts, chunks, sources), and runs a
   benchmark, using only the public SDK API.
9. A user picks `core` with `enterprise-docs` or `finance`, adds a type in
   their own pack, runs the coverage check and a trial on sample documents,
   and gets a drop report with a reason for every dropped item
   ([domain-packs.md](domain-packs.md#success-criteria-v1)).
10. The same contract suite passes on Postgres, Lakebase, Delta and Neo4j,
    and the same agent session runs unchanged against the Postgres and the
    Neo4j backend.
11. An agent calls `describe_schema`, receives the merged pack's summary
    with its name, version and hash, and its tool calls use only the type
    names the generated enums allow.
12. Each v1 query strategy, and `retrieve_multi_step()`, runs as a
    benchmark variant with per-type retrieval metrics, extra LLM calls and
    latency beside the no-LLM baseline.
13. Every index run stores community membership when the `communities`
    extra is installed. With reports on, editing one document rewrites
    only the reports of the communities it changed, and every point of a
    `retrieve_global()` answer cites chunks.

**Open questions**
1. Resolved on 2026-10-05: core engine design and the exact
   store-protocol methods, in [engine-brief.md](engine-brief.md). The
   author answered its questions E1–E14, and ADRs 0012–0015 record the
   decisions behind E1, E2–E3, E13–E14 and the vector write path. Inputs:
   [graphrag-research.md](../reference/graphrag-research.md#inputs-for-the-engine-brief-inferred),
   including the node-model and retrieval-flow review (item 10), the
   query-strategy stage (item 11), one `GraphStore` for SQL and Cypher
   (item 12) and Vietnamese–English handling (item 13). Settled on 2026-10-04 and to be designed in: the
   per-document consistency floor, `one_at_a_time` supersession with
   conflict flags ([domain-packs.md](domain-packs.md#how-the-pack-is-used)),
   category endpoint constraints, `TEXT_IN` links to documents, and
   `retrieve_multi_step()`. Settled on 2026-10-05: the two community
   layers of
   [ADR 0011](../decisions/0011-cluster-by-default-and-make-community-reports-opt-in.md).
2. Delta multi-table consistency: `run_id` commit marker vs Databricks
   multi-statement transactions — spike before the Delta store (agent, on
   the author's workspace); blocks M2's Delta backend.
3. Whether an OBO token survives agent → MCP server on Apps → Lakebase.
   The author has a workspace with Apps user authorization and has run an
   agent there with OBO and a Lakebase checkpointer. The spike still runs
   before M3; it blocks M3's OBO-on-Lakebase path.
4. Resolved on 2026-10-04: open-sourcing needs no employer IP approval.
5. Resolved on 2026-10-05: a first realistic golden set of 31 questions
   over a public web corpus close to the use case, covering the question
   types in [test-corpora.md](../reference/test-corpora.md), drafted by
   the agent and approved by the author. Corpus and questions stay outside
   git.
   The internal-corpus set is built and run inside the adopter's workspace
   later.
6. Resolved on 2026-10-04: Neo4j lands in v1
   ([ADR 0008](../decisions/0008-build-databricks-and-open-branches-in-parallel.md)).
   Later that day it became the preferred backend outside Databricks,
   built from M1.
7. Resolved on 2026-10-04: the four non-goals under Out of scope are
   accepted, and the app keeps its full scope.
8. Resolved on 2026-10-04: reserve `tenetrag` on PyPI with a 0.0.0
   placeholder before the first public push (author).
9. Resolved on 2026-10-04: each document is atomic and a run record marks
   completion, on every backend
   ([ADR 0008](../decisions/0008-build-databricks-and-open-branches-in-parallel.md)).
10. Resolved on 2026-10-05: Neo4j 2026.09 or later; typed relation edges
    with per-type DDL; self-hosted Docker by default, with Aura supported
    and smoke-tested on Aura Free before each release
    ([ADR 0008](../decisions/0008-build-databricks-and-open-branches-in-parallel.md)).
11. Resolved on 2026-10-04: AI Search pairs only with a Delta graph; a
    Lakebase graph always uses pgvector.
12. Resolved on 2026-10-04: agents see a minimal set of pack fields by
    default, and a load-time lint checks the rest
    ([domain-packs.md](domain-packs.md#how-the-pack-is-used)).
13. Resolved on 2026-10-05: the graph is clustered by default with no
    LLM, and community reports and `retrieve_global()` are opt-in. When
    reports are on, a run rewrites only the reports of communities that
    changed
    ([ADR 0011](../decisions/0011-cluster-by-default-and-make-community-reports-opt-in.md)).
    Global questions are being added to the golden set.
