# TenetRAG

TenetRAG (Temporal Entity Network with Evidence Trails for Retrieval-Augmented
Generation) is a Python SDK for GraphRAG. It indexes documents into a
domain-defined knowledge graph of dated, evidence-backed facts, and serves
graph-guided retrieval to user-built agents as a Python API, tool specs or an
MCP server. Two deployment branches are built in parallel: Databricks
(Lakebase by default, Delta, pgvector or AI Search) and elsewhere (Neo4j
preferred, or Postgres) ([ADR 0008](docs/decisions/0008-build-databricks-and-open-branches-in-parallel.md)).

**Status:** design phase, no code yet. The design is settled through
ADR 0019, and the constitution is at v1.1.0. M0 is planned in
[specs/001-sdk-foundation](specs/001-sdk-foundation/plan.md); next is its
task list.

## Stack
Python · Postgres/pgvector (local, managed, Lakebase) · Neo4j · Delta via
Spark or SQL warehouse · Databricks AI Search · MLflow · Spec Kit for feature
work.

## Key rules
The full set is the [constitution](.specify/memory/constitution.md);
these are the rules most often broken.
- **No adopter data in git.** Anything specific to an adopting organization
  (use case, documents, prompts, golden sets, examples) goes only in
  `docs/private/`, which is gitignored. Public fixtures and examples are
  synthetic or public. Check `git status` before every commit.
- **Fail closed on identity.** Credentials are always passed explicitly, and
  a missing credential raises `AuthError`. Never fall back to another
  identity ([ADR 0003](docs/decisions/0003-caller-supplied-credentials.md)).
  The profile may name a source, never a secret; the OpenAI and Databricks
  SDKs' own env reads are the one accepted exception ([ADR 0018](docs/decisions/0018-name-credential-sources-in-the-profile.md)).
- **`engine` depends only on protocols** and the pure `config` and `packs`
  modules. It never imports storage, llm, `databricks-sdk` or `pyspark`
  ([ARCHITECTURE.md](ARCHITECTURE.md)).
- **Provenance and fidelity.** Every entity, relation, event and fact links to its
  chunks and documents, with a quote checked against its chunk. Source text
  is never translated, and figures stay verbatim with their time and source.
- **A name is not identity.** Entities merge by the scope, keys and vetoes
  their pack declares, and CI requires zero wrong merges on identity cases
  ([ADR 0016](docs/decisions/0016-identify-entities-by-scope-keys-and-vetoes.md)).
- **Tests ship with behaviour.** A bug fix comes with a regression test that
  fails first. Engine tests run on the reference store with fake models.
- **Platform facts are dated.** Before relying on Databricks or Neo4j
  behavior, read its reference doc below and re-verify Preview/Beta items
  against the linked source.

## Commands
Not set up yet. M0 adds the formatter, linter, type-checker and pytest; list
the exact commands here when it does.

## Docs map

| When you need to... | Read |
|---|---|
| Know what v1 is, its milestones and open questions | [docs/product/sdk-platform-brief.md](docs/product/sdk-platform-brief.md) |
| Change the engine: pipeline, entity resolution, versions, retrieval, store protocols | [docs/product/engine-brief.md](docs/product/engine-brief.md) |
| Define or change the graph schema, or a default pack | [docs/product/domain-packs.md](docs/product/domain-packs.md) (format), [docs/product/v1-packs.md](docs/product/v1-packs.md) (default packs), then [docs/reference/graph-schema-design.md](docs/reference/graph-schema-design.md) |
| Understand module boundaries and import rules | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Know why a decision was made | [docs/decisions/](docs/decisions/) via [docs/index.md](docs/index.md) |
| Check Lakebase, OBO, AI Search, MLflow or model limits | [docs/reference/databricks-platform.md](docs/reference/databricks-platform.md) |
| Check Neo4j versions, search and transaction limits | [docs/reference/neo4j-platform.md](docs/reference/neo4j-platform.md) |
| Pick test data (no adopter data locally) | [docs/reference/test-corpora.md](docs/reference/test-corpora.md) |
| Port an algorithm or prompt from a reference engine | [docs/reference/graphrag-engines.md](docs/reference/graphrag-engines.md) |
| Know what papers show about a GraphRAG method | [docs/reference/graphrag-research.md](docs/reference/graphrag-research.md) |
| Pick or reuse a library (license, Vietnamese support, reuse rule) | [docs/reference/supporting-libraries.md](docs/reference/supporting-libraries.md), [ADR 0009](docs/decisions/0009-reuse-permissive-libraries-behind-adapters.md) |
| See the raw research behind a reference doc | [docs/research/](docs/research/) snapshots (not maintained) via [docs/index.md](docs/index.md#research-snapshots) |
| Start a feature (3+ tasks or 2+ days; smaller changes go straight in) | Spec Kit `speckit-specify` → `specs/NNN-<name>/` (first: [001-sdk-foundation](specs/001-sdk-foundation/spec.md)) |
| Follow coding and security rules | `.agents/rules/` (auto-loaded through `.claude/rules`) |
| Read standing principles, or check a plan against them | [.specify/memory/constitution.md](.specify/memory/constitution.md) |
