# Neo4j — platform facts for the Neo4j backend

**Verified:** 2026-10-04 by reading the Neo4j server source at tag 2026.09.0,
the docs repositories (`dev` branches of 2026-10-01, labelled 2026.10,
which has no release tag yet), driver 6.3.1 and library source at pinned
tags. Nothing was installed or run, so every Cypher shape below is
untested. Neo4j documentation is CC BY-NC-SA, so this page paraphrases and
never copies its text. Decision:
[ADR 0008](../decisions/0008-build-databricks-and-open-branches-in-parallel.md).
Raw report (snapshot, not maintained):
[Neo4j backend](../research/2026-10-04-neo4j-backend.md).

Labels: **[primary]** vendor docs or source · **[source]** library code at a
pinned tag · **[inferred]** our reasoning.

## Editions and licenses

| Item | Fact | Label |
|---|---|---|
| Community Edition | GPLv3. Single instance, ACID, Bolt, vector and full-text indexes, uniqueness constraints. No existence, type or key constraints, no extra user databases, no RBAC, no online backup. | [primary] |
| Enterprise Edition | Commercial. Docker images need `NEO4J_ACCEPT_LICENSE_AGREEMENT=yes`. | [primary] |
| Aura | Free, Professional, Business Critical, Virtual Dedicated Cloud. Always runs the latest server. Offers a subset of APOC core. Tier limits not verified. | [primary] |
| Python driver 6.3.1 | Apache-2.0 and PSF-2.0. Python ≥ 3.10. Retries transient errors for up to 30 s in managed transactions. | [source] |
| Graph Data Science | GPLv3 open part. Separate plugin. On Aura through Graph Analytics sessions or the plugin. | [primary] |

An SDK that talks Bolt to a separate server through the Apache-2.0 driver
does not take on the server's GPL. Shipping a server image or GDS inside
TenetRAG artifacts would [inferred, not legal advice].

CI: testcontainers-python 4.15.0 provides
`testcontainers.community.neo4j.Neo4jContainer`. Its default image is
`neo4j:latest`, so pin the tag. Avoid `NEO4J_PLUGINS`, which downloads at
container start [source].

## Version floors that matter

| Feature | Server version | Label |
|---|---|---|
| Dynamic labels and types `$(...)` without APOC | 5.26 | [primary] |
| Vector index with extra filter properties, in-index filtered `SEARCH ... WHERE` | 2026.01 | [primary] |
| `IN` predicates inside a vector `SEARCH` filter | 2026.06 | [primary] |
| Full-text `SEARCH` clause | 2026.09 (the full-text procedures are deprecated in 2026.10) | [primary] |

The default query language is still Cypher 5, so `SEARCH` needs a
`CYPHER 25` prefix per query [primary].

## Search

- **Vector index:** HNSW, 1–4096 dimensions, cosine or euclidean, scalar or
  binary quantization. Results are approximate. A filter inside `SEARCH`
  allows only an `AND` of property comparisons. A `WHERE` outside `SEARCH`
  filters after the search, so older servers must over-fetch [primary].
- **Full-text index:** Lucene. No Vietnamese analyzer. `standard-folding`
  folds Vietnamese letters and `đ` to ASCII and applies an English stop
  list [primary]. Plan: do not use it, since folding merges `lãi`, `lại`
  and `lai`. Index the engine's own normalized property, which keeps
  diacritics, with `standard-no-stop-words`, the same normalized text
  Postgres uses [plan inferred].
- **Scoring:** Lucene relevance, probably BM25 [inferred]. Scores are
  comparable only within one query, never with Postgres `ts_rank`.
- **Fuzzy matching:** Lucene `term~` is edit distance, not trigram
  similarity [inferred]. This is the largest parity gap with `pg_trgm`.
- **Fusion:** no Cypher RRF exists. Fuse in the engine (Graphiti does it in
  Python).

## Writes and consistency

- Idempotent batch writes: `UNWIND $rows` with `MERGE` on a key backed by a
  uniqueness constraint. `MERGE` alone does not guarantee uniqueness under
  concurrent load [primary].
- Relationship `MERGE` locks both end nodes, so hub entities can deadlock.
  Driver retries make idempotent writes safe [primary; source].
- `CALL { } IN TRANSACTIONS` runs only in implicit transactions, and
  committed batches stay committed after a later failure [primary].
- Transaction memory: unlimited per transaction by default, 70 % of heap in
  total [primary].
- No advisory locks. "One writer per index" needs a lease node taken with
  `MERGE` and a conditional `SET` [inferred].
- Practical run model: one write transaction per document, plus a run
  record with a status [inferred].

## Modelling and traversal

- Indexes and constraints on relationship properties are per relationship
  type [primary]. With pack-defined relation types, either run DDL per
  type when a pack version syncs, or use one edge type with a type
  property (Graphiti uses `RELATES_TO` with a `name`) [source]. Chosen:
  typed edges ([ADR 0008](../decisions/0008-build-databricks-and-open-branches-in-parallel.md)).
- Quantified path patterns take inline filters but cannot cap fan-out per
  hop. For ≤ 2 hops, use one scoped `CALL (n) { … ORDER BY … LIMIT k }` per
  hop [primary; plan inferred].
- Ranking chunks by the query vector on a small candidate set can use
  `vector.similarity.cosine`, which is exact [source].

## Reusable code (patterns only, at pinned tags)

| Library | License | Use |
|---|---|---|
| neo4j-graphrag 1.22.0 | Apache-2.0 | `CYPHER 25` prefix helper and the filtered vector `SEARCH` builder. Its writer uses `CREATE` (not idempotent) and APOC, and its hybrid search uses max-normalization, not RRF. |
| Graphiti v0.30.2 | Apache-2.0 | Temporal edge model on one edge type, Lucene query building with a tenant filter, Python RRF, index DDL. |
| llama-index-graph-stores-neo4j 0.8.0 | MIT | `MERGE` upsert patterns. Pins `neo4j<6` and needs APOC. |
| langchain-neo4j 0.10.0 | MIT | Import patterns through APOC. |

None fits as a dependency of the backend [inferred].

## Not verified
- Aura tier matrix and Free-tier limits.
- BM25 as the full-text similarity.
- The default `db.transaction.timeout`.
- Any performance figure.
