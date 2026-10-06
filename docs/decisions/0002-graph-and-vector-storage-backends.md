# Store the graph in Delta or Postgres and vectors in pgvector or AI Search

**Status:** accepted; amended by
[ADR 0006](0006-rename-to-tenetrag-and-run-beyond-databricks.md)
(2026-10-03). Graph databases such as Neo4j are now in scope as further
`GraphStore` backends, and the Postgres family is the default that runs
anywhere. Amended again by
[ADR 0008](0008-build-databricks-and-open-branches-in-parallel.md)
(2026-10-04): Lakebase is the default on Databricks, Delta stays as an
alternative, Neo4j is in v1, and pgvector is the default vector store.
**Date:** 2026-10-02
**Deciders:** Liam Lee (brainstorm session, 2026-10-02)

## Context
Databricks has no graph store. Lakebase is managed Postgres with pgvector but
no Apache AGE. Databricks SQL supports recursive CTEs. UC Volumes allow no
append or random writes, and Workspace files are capped at 500 MB and meant
for code. Agents reach these backends under different identities, and only
the SQL warehouse is reachable with OBO from both Apps and Model Serving
([databricks-platform.md](../reference/databricks-platform.md)). Contributors
must be able to run every test without a Databricks workspace.

## Decision
The graph lives in relational tables in one of two backend families. The
**Delta** family uses UC tables through Spark or a SQL warehouse. The
**Postgres** family covers Lakebase and local Postgres, which share one code
path; Lakebase adds OAuth token minting. Vectors live in **pgvector** or
**Databricks AI Search**. Graph and vector stores are chosen independently.
Presets cover the expected pairs: UC tables + AI Search, Lakebase + pgvector,
local Postgres + pgvector. The engine sees only `GraphStore` and
`VectorStore` protocols.

## Alternatives considered
- **UC Volumes or Workspace files (Parquet, like Microsoft GraphRAG)** —
  rejected: no transactions, every update rewrites whole files, and
  concurrent writers silently overwrite each other (last writer wins).
- **SQLite for local development** — rejected: it would be a third code path
  that diverges from Lakebase's, and a SQLite file cannot be written in place
  on a Volume. Local Postgres replaces it.
- **External graph database (Neo4j, as in the official demo)** — rejected:
  the goal is Databricks-native storage under Unity Catalog and platform
  permissions.
- **Apache AGE on Postgres** — not available on Lakebase. Would revisit if
  Lakebase adds it, as an optional query path.

## Consequences

**Better:**
- Unit and contract tests run on Docker Postgres alone: no workspace, no keys.
- Delta tables are governed by Unity Catalog and reachable under OBO from both
  Apps and Model Serving.
- Users can mix stores, for example a graph in UC tables with vectors in
  pgvector.

**Worse:**
- Two graph backends to maintain, each with its own contract-suite run.
- Delta has no faithful local equivalent (Spark needs a JVM; delta-rs is a
  different code path), so Delta contract tests need a workspace.
- Graph traversal is SQL (recursive CTEs or iterative joins), not a graph
  query language.
- Delta has no multi-table transaction we rely on yet, so a run needs a
  commit marker (open question 2 in the
  [brief](../product/sdk-platform-brief.md)).
- Lakebase is not reachable from Model Serving under OBO.
- AI Search adds sync lag between a Delta write and query visibility.

**Must now be true:**
- Every backend implements the same protocol and passes the same contract
  suite.
- Postgres-family code never requires superuser (Lakebase has none), so local
  Postgres and Lakebase stay on one code path.
- `engine/` imports no backend driver (`psycopg`, `pyspark`,
  `databricks.sql`, `databricks.ai_search`).
- The SDK computes embeddings itself, so pgvector and AI Search (Delta Sync
  index with self-managed embeddings) hold vectors from the same model.
- Writes are batched and idempotent, keyed by content hashes. Deletes cascade
  by document through provenance.

## Revisit if
Databricks ships a native graph store or Lakebase adds AGE, or the Delta
backend cannot meet the per-run consistency guarantee after the open
question 2 spike.
