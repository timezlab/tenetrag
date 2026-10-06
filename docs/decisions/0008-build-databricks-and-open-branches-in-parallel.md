# Build the Databricks and open deployment branches in parallel, with Neo4j in v1

**Status:** accepted
**Date:** 2026-10-04
**Deciders:** Liam Lee (session 2026-10-04)

## Context
[ADR 0002](0002-graph-and-vector-storage-backends.md) put the graph in
Delta or the Postgres family and the vectors in pgvector or AI Search.
[ADR 0006](0006-rename-to-tenetrag-and-run-beyond-databricks.md) made
Postgres the default that runs anywhere and Databricks a first-class
target. It left open when graph databases such as Neo4j would land
(open question 6 in the [brief](../product/sdk-platform-brief.md)).

On 2026-10-04 the author set two deployment branches, developed in
parallel:
- **Databricks:** Lakebase is the default graph store. Delta stays in v1 as
  an alternative. pgvector is the default vector store, and AI Search is
  optional.
- **Outside Databricks:** Postgres or Neo4j.

Later the same day, reviewing open questions, the author made Neo4j the
preferred backend outside Databricks, built from M1 together with
Postgres. They expect faster search on Neo4j. Postgres stays the fallback
outside Databricks and the default on Databricks, through Lakebase.

A Neo4j study on 2026-10-04
([snapshot](../research/2026-10-04-neo4j-backend.md); facts in
[neo4j-platform.md](../reference/neo4j-platform.md)) found:
- Neo4j can carry our model. Entities, events and facts become nodes, roles
  become one edge type with a name, and writes use `UNWIND` with `MERGE` on
  a uniquely constrained hash key.
- The Python driver is Apache-2.0. The Community server and Graph Data
  Science (GDS) are GPLv3.
- In-index filtered vector search needs server 2026.01 or later.
  Full-text `SEARCH` needs 2026.09.
- Batched transactions run only in implicit transactions, so "one index
  run is one transaction" cannot hold on Neo4j.
- Relationship indexes are per relationship type, and our types come from
  the pack at runtime.
- No existing library fits as our writer.
- The estimated extra effort is 5 to 7 engineer-weeks. It falls towards 4
  if the engine owns normalization, fusion, PageRank and tie-breaks.

## Decision
1. **Two deployment branches, both in v1:**

   | Branch | Graph store | Vector store | Text search |
   |---|---|---|---|
   | Databricks | Lakebase (default), or Delta UC tables through Spark or a SQL warehouse | pgvector in Lakebase (default), or AI Search | Postgres full text, or AI Search hybrid |
   | Open (preferred) | Neo4j, self-hosted or Aura | Neo4j vector index (default), or pgvector | Neo4j full-text index |
   | Open (fallback) | Postgres, local or managed | pgvector | Postgres full text |

   AI Search pairs only with a Delta graph. A Lakebase graph always uses
   pgvector. Config loading rejects any other pairing with a `ConfigError`
   that names the valid pairs.

2. **Neo4j is the preferred backend outside Databricks.** Postgres is the
   fallback there and the default on Databricks. Neo4j and Postgres are
   both built from M1, so the protocol and the contract suite meet SQL and
   Cypher from the start. The benchmark's backend variant tests the
   expected search speed gain; no figure exists yet.
3. **Three graph backends in v1:** the Postgres family (one code path for
   local, managed and Lakebase), Delta, and Neo4j. Each implements
   `GraphStore` and passes the same contract suite.
4. **The engine brief designs `GraphStore` for SQL and Cypher together.**
   Store methods return candidate ids and records. The engine owns:
   - text normalization;
   - RRF fusion, final ranking and tie-breaks;
   - Personalized PageRank;
   - supersession ordering.

   The backends stay thin, and their results stay comparable.
5. **One parametrized contract suite.**
   - These must match on every backend:
     - counts after a batch write and after a replay;
     - the end state after a delete by document;
     - supersession flags;
     - provenance reachability;
     - type, time and status filters;
     - expansion membership within the hop limit;
     - the fan-out cap and hub penalty as invariants;
     - text matching after NFC and tone-mark normalization (`hoà` matches
       `hòa`) that keeps diacritics (`lãi`, `lại` and `lai` stay
       distinct).
   - These may differ: absolute scores, order among ties, ANN recall (the
     suite asserts a floor) and fuzzy-match scores (it asserts set
     membership).
   - The suite also tests the one-writer rule and recovery after a run is
     killed mid-way.
6. **Neo4j specifics.**
   - The SDK talks to a server the user supplies, through the driver, behind
     a `neo4j` extra. It never ships a Neo4j server image or GDS.
   - The minimum server version is 2026.09. Vector and full-text search
     then share one code path, the `SEARCH` clause behind a `CYPHER 25`
     prefix.
   - CI uses a pinned Community image through testcontainers.
   - APOC and GDS are not required. PageRank runs in the engine.
   - Relations are typed edges such as `OWNER_OF`, written with dynamic
     types and given per-type DDL when a pack version syncs (author,
     2026-10-05). An expansion filtered by type then reads only edges of
     that type, and Neo4j Browser shows real relation names. Roles stay
     one `ROLE` edge type with a name, because retrieval usually needs all
     roles of a fact. If `MERGE` with a dynamic type proves slow, the
     writer groups rows by type and runs one query per type, with type
     names checked against the pack.
   - The default deployment is a self-hosted Neo4j server in Docker. Aura
     (Neo4j's managed cloud) is supported: every CI run uses the pinned
     Docker image, and a smoke test runs on an Aura Free instance before
     each release (author, 2026-10-05).
7. **One consistency floor for every backend.**
   - Each document is atomic: a reader sees a document's old version or
     its new one, never a mix.
   - A run record marks when a run completes. After a crash, some
     documents have their new version and the rest keep their old one.
     Running `apply` again skips the finished documents by hash and indexes
     the rest.
   - Postgres and Neo4j commit one transaction per document. Delta writes
     in batches and exposes them through a `run_id` commit marker (open
     question 2), which meets the floor.
   - One writer per index: an advisory lock on Postgres, a lease node on
     Neo4j.

## Alternatives considered
- **Lakebase only on Databricks, without Delta.** Considered. The author
  kept Delta in v1: UC tables are reachable under OBO from both Apps and
  Model Serving, and Lakebase is not reachable from Model Serving under
  OBO ([databricks-platform.md](../reference/databricks-platform.md#runtime--identity--backend)).
- **Postgres as the default outside Databricks.** Rejected by the author,
  who expects faster search on Neo4j. The benchmark checks this.
- **One `REL` edge type with a `type` property on Neo4j.** Rejected on
  2026-10-05: it eases parity with Postgres, but every expansion would read
  all edges of a node and filter on a property, which gives up the search
  speed the author chose Neo4j for.
- **Neo4j from a later milestone (M2b), after Postgres.** Rejected for the
  same reason. Neo4j starts in M1.
- **Whole-run atomicity for readers on every backend.** Rejected: on Neo4j
  every read would filter on a run record. Each document stays atomic.
- **AI Search over a Lakebase graph,** through a Direct Vector Access index
  or a Delta copy of the embeddings. Rejected: a second write path and a
  sync lag for a pairing that pgvector already covers.
- **Neo4j after v1, on demand.** Rejected: the author wants the open branch
  to offer a graph database from the start. A protocol designed for SQL
  first would also risk leaking SQL shapes that Cypher cannot match.
- **Neo4j graph with pgvector only.** Rejected as the default, because users
  outside Databricks would then run two servers. The pairing stays possible,
  since graph and vector stores are chosen independently.
- **neo4j-graphrag's writer.** Rejected: it writes with `CREATE`, which is
  not idempotent, and it needs APOC.
- **AI Search as the default vector store on Databricks.** Rejected by the
  author: pgvector keeps graph and vectors in one database and one
  transaction.

## Consequences

**Better:**
- Teams outside Databricks get Neo4j by default and Postgres as the
  fallback. Teams on Databricks choose Lakebase or Delta.
- Designing the protocol for SQL and Cypher together keeps SQL out of the
  engine.
- Agents on Model Serving under OBO keep a path through Delta and the SQL
  warehouse.

**Worse:**
- Three graph backends and three contract-suite runs. Delta, Lakebase and
  AI Search runs need a workspace.
- About 4 to 7 extra engineer-weeks for Neo4j, now on M1's critical path,
  plus two query sets to update on every engine change.
- Users on Neo4j servers older than 2026.09, including 5.26 LTS, cannot use
  the Neo4j backend.
- The default local setup needs a Neo4j server, usually in Docker.
- Parity risks:
  - run atomicity;
  - fuzzy entity linking (`pg_trgm` similarity against Lucene edit
    distance);
  - Neo4j server version floors;
  - Aura's APOC subset and its always-latest server version.
- Scores differ across backends, so the benchmark compares backends by
  retrieval metrics, never by raw scores.
- On Neo4j we compete directly with neo4j-graphrag and Graphiti.

**Must now be true:**
- Every graph backend passes the same contract suite. Postgres and Neo4j
  run in Docker in CI. Delta, Lakebase and AI Search run in a workspace.
- `GraphStore` methods are engine operations. The engine contains no SQL
  and no Cypher.
- Normalization, RRF, tie-breaks, PageRank and supersession ordering live in
  the engine.
- TenetRAG artifacts contain no GPL component. The Neo4j driver loads only
  with the `neo4j` extra. The CI image tag is pinned.
- pgvector is the default vector store on Databricks. AI Search is opt-in,
  and only with a Delta graph.
- Every backend meets the per-document consistency floor, and the
  contract suite tests it with a run killed mid-way.

## Revisit if
- The benchmark shows Neo4j no faster and no better than Postgres on the
  default retrieval path. Postgres could then become the default
  everywhere.
- The Neo4j backend cannot meet the contract's consistency guarantee.
- Delta fails the open question 2 spike. Delta would then move after v1.
- Keeping three backends in step slows the engine more than the milestones
  allow.
