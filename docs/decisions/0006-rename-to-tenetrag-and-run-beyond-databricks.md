# Rename the project to TenetRAG and make Databricks one deployment target

**Status:** accepted; amended by
[ADR 0008](0008-build-databricks-and-open-branches-in-parallel.md) (2026-10-04),
which puts Neo4j in v1, built in parallel with the Databricks backends,
and makes it the preferred backend outside Databricks.
**Date:** 2026-10-03
**Deciders:** Liam Lee (brainstorm session, 2026-10-02 to 2026-10-03)

## Context
The project started as `databricks-graphrag`, a GraphRAG SDK for Databricks
only. [ADR 0002](0002-graph-and-vector-storage-backends.md) rejected
external graph databases because the goal was Databricks-native storage.

The author then widened the target. Teams outside Databricks should be able
to run the SDK, including on graph databases such as Neo4j, and Databricks
should stay a first-class option. The Postgres family already runs anywhere,
since local Postgres and Lakebase share one code path, so the change costs
little in storage code.

Source comparisons in
[graphrag-engines.md](../reference/graphrag-engines.md) found that no engine
does all of the following:
- keeps dated versions of facts;
- keeps every fact traced to its evidence;
- lets the user define and version the graph schema;
- runs the graph-first retrieval flow end to end.

Research in [graphrag-research.md](../reference/graphrag-research.md) shows
that plain vector RAG matches graph methods on single-fact questions.

The old name no longer describes the scope, and it carries a vendor's
registered trademark. We did not find a published policy on whether third
parties may use that trademark in project names.

## Decision
1. **Name.**
   - The project is **TenetRAG**: "Temporal Entity Network with Evidence
     Trails for Retrieval-Augmented Generation".
   - The repository, package and import name is `tenetrag`.
2. **Positioning.** A GraphRAG SDK for agents. It builds a domain-defined
   knowledge graph of dated, evidence-backed facts from an organisation's
   documents, uses that graph to find the right chunks, and returns both.
3. **Deployment.**
   - Storage stays behind the `GraphStore` and `VectorStore` protocols.
   - The Postgres family is the default backend that runs anywhere: local
     Postgres, any managed Postgres, and Lakebase.
   - The Databricks backends stay first-class: Lakebase, Delta with AI
     Search, OBO, MLflow and Apps.
   - Graph databases such as Neo4j are in scope as further `GraphStore`
     implementations. When they land is an open question in the
     [brief](../product/sdk-platform-brief.md).
4. **The graph is always built.** Every index run extracts entities,
   relations, events and facts under the domain profile. The graph is not an
   optional tier.
5. **Retrieval is graph-guided.** The graph finds entities and facts. Vector
   search then finds the chunks they rest on, using provenance plus a vector
   query, ranked by the query vector. The engine brief settles the exact
   flow.
6. **Optional router.**
   - A router can send a query to plain vector RAG instead of the graph path.
   - It is off unless the user enables it.

## Alternatives considered
- **Keep the Databricks-only scope and the `databricks-graphrag` name.**
  Rejected: the author wants the SDK usable outside Databricks. The old name
  would misdescribe the project and keep a vendor trademark in it.
- **Make the graph an optional tier** (lexical and vector search first,
  graph extraction later or only for part of the corpus). Rejected by the
  author: the graph is the product. Simple questions reach plain vector RAG
  through the router instead.
- **Other names.** Names were checked on 2026-10-03 against PyPI, GitHub
  repository names and arXiv titles.
  - Factpath, Hoso, DossierRAG, ProvRAG and SegueRAG were clean but fit
    worse: no time or evidence in the name, unclear meaning, long, or hard to
    pronounce.
  - GRACE, LEDGER, GRAFT, TROVE, CAIRN, CREDO, EviRAG and others collide with
    2025–2026 RAG, graph or agent papers or repositories.
  - LEGEND collides with FINOS Legend, a data-modelling platform used in
    finance.
- **"Evidence Tracing" for the final T.** Rejected: in LLM tooling
  "tracing" reads as observability (MLflow Tracing).

## Consequences

**Better:**
- One codebase serves Databricks and non-Databricks users. The Postgres path
  needs no new work to run outside Databricks.
- The name states the two strongest differentiators, time and evidence, and
  carries no vendor trademark.
- With the router enabled, single-fact questions can skip the graph path,
  where research shows no gain.

**Worse:**
- Every index run pays for LLM extraction, so these become mandatory:
  - the cost estimate in the plan;
  - extraction caching;
  - batching chunks per call;
  - trying schema changes on a sample first.
- Each extra graph backend adds an implementation and a contract-suite run.
- On Neo4j we compete directly with neo4j-graphrag, Graphiti and LightRAG,
  and the Databricks-native advantage does not apply there.
- The router can misroute, so the benchmark must report results per
  question type.

**Must now be true:**
- Docs call the project TenetRAG. The repository, package and import name is
  `tenetrag`.
- Importing `tenetrag` requires no Databricks package:
  - `databricks-sdk`, `pyspark`, `databricks-sql-connector` and the AI
    Search client live behind extras;
  - Databricks credential types load only with the `databricks` extra.
- `GraphStore` methods are engine operations, not SQL, so a Cypher backend
  can implement them.
- The plain vector path the router selects returns the same result shape as
  the graph path: chunks with provenance.
- ADR 0002's rejection of external graph databases no longer holds. That
  ADR carries an amendment note pointing here.

## Revisit if
- A trademark claim arrives.
- A same-domain project takes the name before we reserve it.
- The benchmark shows the graph path does not beat the plain vector path on
  the target question types. In that case, revisit
  [ADR 0001](0001-build-own-graphrag-core.md) too.
