# Neo4j GraphStore backend for TenetRAG — research report

> **Snapshot, 2026-10-04 — not maintained.** Code lane; nothing executed, all Cypher untested. The maintained,
> re-verified summary is in [neo4j-platform.md](../reference/neo4j-platform.md); where they differ, the maintained doc
> wins. Local paths were removed before publishing.
*2026-10-04 · confidence: medium-high on facts (read from docs source and code), medium on estimates · labels: [primary] vendor docs/source, [source] code at pinned tag, [secondary], [inferred] my reasoning*

## Summary (10 lines)
1. Server: Community (GPLv3) is enough for a backend, but it only has *uniqueness* constraints (no existence, type or node-key), one user database, no RBAC and no online backup [primary]. Enterprise is commercial. Aura always runs the latest server [primary].
2. Licence: the Python driver (6.3.1) is Apache-2.0 (+PSF-2.0 parts) and neo4j-graphrag 1.22.0 is Apache-2.0, so an MIT/Apache SDK that talks Bolt to a separate server has no GPL linkage [primary/source]. GPL applies if we *ship* a CE image or GDS [inferred, not legal advice].
3. Vector: native HNSW index, 1–4096 dims, cosine/euclidean, scalar/binary quantization, in-index filtered search via `SEARCH ... WHERE` (server 2026.01+, `IN` from 2026.06, HFQ from 2026.07) [primary]. Neo4j can be the VectorStore for chunks and entities.
4. Full text: Lucene index; `standard-folding` (ASCIIFoldingFilter, folds `đ`) exists in source, but it uses an English stop list; scoring is Lucene's (BM25 by default, [inferred]); `SEARCH` for full-text only from 2026.09 [primary]. Safest for Vietnamese: index our own normalized column with `standard-no-stop-words`, same as Postgres.
5. Writes: `UNWIND` + `MERGE` on a uniqueness-constrained hash key is idempotent; dynamic labels/types via `$()` work in Cypher 5.26+ and Cypher 25 without APOC [primary]. `CALL {} IN TRANSACTIONS` cannot run inside an explicit transaction, so "one run = one transaction" and "batched big deletes" conflict [primary].
6. Atomicity: no multi-statement commit marker for free. Use one transaction per document plus a run record (`run_id`, status) and a lease node for "one writer" [inferred].
7. Modelling trap: indexes and constraints on *relationship* properties are per relationship type, and our types come from the pack at runtime. Either create DDL per type at pack sync, or use one static edge type with a `rtype` property (Graphiti does the latter) [primary/source].
8. Traversal: quantified path patterns take inline predicates, but cannot cap fan-out per hop; do 2 unrolled `CALL (n) { ... ORDER BY ... LIMIT k }` hops instead [inferred]. PPR: compute client-side on the small expanded subgraph; GDS is GPLv3 and extra to install, available on Aura only through Graph Analytics sessions/plugin [primary].
9. Reuse: little is reusable as-is. neo4j-graphrag's writer uses `CREATE` (not idempotent) and APOC; Graphiti and LlamaIndex show patterns (RRF in Python, group_id tenancy, `MERGE` + unique id). Hybrid search in neo4j-graphrag is max-normalised, not RRF.
10. Parity risk is highest for fuzzy entity linking, ranking scores and atomic runs. Estimate +5 to 7 engineer-weeks over the Postgres backend [inferred]; contract suite compares sets and invariants, not scores or tie order.

---

## Version baseline (all claims pinned)
- Server: latest git tag `2026.09.0` (neo4j/neo4j); docs `dev` branches (docs-cypher @ea9b47a, docs-operations @e16efb0, both 2026-10-01) are labelled 2026.10, which has no tag yet. Anything marked "2026.10" below is unreleased as of today. 5.26 is the last SemVer LTS; "next LTS in 2026" is mentioned but not yet identified [primary: docs-operations `introduction.adoc`, `deprecations.adoc`].
- Default query language is still `CYPHER_5` (`db.query.default_language`), so Cypher 25 features (`SEARCH`, `FILTER`, `LET`) need a `CYPHER 25` prefix per query. neo4j-graphrag does exactly this (`neo4j_queries.py:30-35`) [primary/source].
- Driver: neo4j-python-driver 6.3.1, `requires-python >=3.10` [source: pyproject.toml @6.3.1].

## Q1. Editions and licences
| Item | Finding | Label |
|---|---|---|
| Community (CE) | GPLv3; single instance; ACID, Cypher, Bolt, APOC core, GDS Community support, range/composite/full-text/vector indexes, **uniqueness constraints** | [primary] docs-operations `introduction.adoc` (feature table) |
| CE gaps that matter | no property existence / type / node-or-relationship **key** constraints; no multiple databases beyond `system` + default; no RBAC; no online backup; no parallel/pipelined runtime | [primary] same table |
| Enterprise (EE) | adds the above plus clustering; commercial licence; Docker image needs `NEO4J_ACCEPT_LICENSE_AGREEMENT=yes`; tags have `-enterprise` suffix, CE tags have none | [primary] `docker/introduction.adoc`, `docker/configuration.adoc` |
| Aura | tiers Free, Professional, Business Critical, Virtual Dedicated Cloud; always latest server; supports a curated APOC *core* subset (incl. `apoc.merge`, `apoc.periodic`, `apoc.path`, `apoc.text`) | [primary] docs-aura `apoc.adoc`, `partials/apoc-procedures.adoc` |
| Aura feature matrix per tier (vector index, Free limits) | **not verified**: the pricing page fetch gave no numbers | gap |
| Python driver | Apache-2.0 AND PSF-2.0 (`license = "Apache-2.0 AND Python-2.0"`) | [source] pyproject.toml @6.3.1 |
| neo4j-graphrag | Apache-2.0 (GitHub shows NOASSERTION only because of the dual licence files) | [source] LICENSE.txt @1.22.0 |
| APOC core | Apache-2.0 (GitHub API) | [secondary] |
| GDS | GPLv3 for the open part; Enterprise needs a licence key; Community caps concurrency at 4 cores | [source] NOTICE.txt @2026.09.0; [primary] GDS intro page |
| Aura docs text | CC BY-NC-SA 4.0: do not paste Neo4j doc text into our docs | [primary] docs-aura `license.adoc` |

Implications for an MIT/Apache SDK [inferred]:
- A pure client using the Apache-2.0 driver over Bolt is not a derivative of the GPL server. Safe path: declare `neo4j>=6` as an optional extra, document that users bring their own server.
- If TenetRAG ships a docker-compose that pulls `neo4j:<ver>` this is the user's pull, not our redistribution. Bundling an image or GDS jar in our own artifacts would trigger GPLv3 duties. Ask counsel before shipping any bundle.
- ADR 0006 already flags vendor-trademark caution; the module name `storage.neo4j` is descriptive use, but we found no published third-party policy (not searched here) -> lead.
- CI: CE image `neo4j:<ver>` needs no licence acceptance. testcontainers-python 4.15.0 has `testcontainers.community.neo4j.Neo4jContainer` (default image `neo4j:latest`, sets `NEO4J_AUTH`, `get_driver()`); `testcontainers.neo4j` is a deprecated shim [source: `src/testcontainers/neo4j.py`, `src/testcontainers/community/neo4j/__init__.py` @testcontainers-v4.15.0]. Pin the image tag explicitly. Avoid `NEO4J_PLUGINS=["apoc"]` in CI: it downloads at container start [primary: `docker/plugins.adoc`]; our design needs no APOC (see Q4).

## Q2. Vector and full-text search
Vector index [primary: docs-cypher `indexes/semantic-indexes/vector-indexes.adoc`, `clauses/search.adoc`]:
- GA 5.13; `VECTOR` value type 2025.10; multi-label/multi-type indexes with extra filter properties 2026.01; High Fidelity Quantized search 2026.07.
- Dimensions 1–4096; similarity `cosine` (default) or `euclidean`; quantization scalar or binary (binary is the default type); `vector.hnsw.m`, `ef_construction`, `default_search_expansion_factor` are tunable. One vector property per node or relationship per index.
- Query: `MATCH (n:Chunk) SEARCH n IN (VECTOR INDEX name FOR $v [WHERE ...] LIMIT k) SCORE AS s` (Cypher 25). Without a filter in `SEARCH`, `WHERE` after `MATCH` is a **post-filter**; with `WHERE` inside `SEARCH` it is **in-index filtering** and the search "continues until it has found the requested number of results" that match.
- Filter limits: only `AND` of property predicates; no `OR`, `NOT` (except booleans), `<>`, string ops, type predicates; `IN` only from 2026.06; no two predicates on the same property in the same direction. Index name cannot be a parameter. The `MATCH` pattern may contain only the bound node (no hops).
- Result is ANN: "may not be the exact k nearest".
- Pre-2026.01 servers: only post-filtering, so over-fetch (neo4j-graphrag does `top_k * effective_search_ratio`, `neo4j_queries.py:38-43`) [source].
- Relationship vector indexes exist (same syntax).

Full text [primary: `full-text-indexes.adoc`; source: neo4j/neo4j @2026.09.0]:
- Lucene-backed; per-index analyzer via `fulltext.analyzer`; `fulltext.eventually_consistent` available. `SEARCH ... FULLTEXT INDEX` is new in 2026.09; the procedures `db.index.fulltext.queryNodes/queryRelationships` are deprecated in 2026.10.
- Analyzers shipped (provider classes in `community/lucene-index/.../fulltext/analyzer/providers/`): standard, standard-no-stop-words (default), standard-folding, simple, whitespace, keyword, classic, stop, unicode-whitespace, url-or-email, cjk, thai, plus ~30 language analyzers (no Vietnamese). `standard-folding` = `StandardTokenizer` + `ASCIIFoldingFilter` + lowercase + stop filter; its description warns of odd behaviour for non-ASCII digits and symbols [source: `StandardFolding.java`, `StandardFoldingAnalyzer.java`].
- Lucene's `ASCIIFoldingFilter` maps precomposed Vietnamese letters (e.g. U+1EA1, U+1EBF) and `đ`/`Đ` (U+0111/U+0110) to ASCII [source: apache/lucene `ASCIIFoldingFilter.java`, main branch, not pinned]. It does not strip standalone combining marks, so text must be NFC [inferred].
- Fuzzy `term~` and boolean operators come from Lucene classic query syntax, which the docs link to (Lucene 10.5.1) but do not demonstrate [primary link]; behaviour is edit distance, not trigram similarity [inferred].
- BM25: docs only say "Lucene relevance score" and that scores are comparable only within one query. A code search for `BM25Similarity`/`setSimilarity` in neo4j/neo4j returned nothing, so Lucene's default (BM25 since Lucene 6) probably applies [inferred; GitHub code search may be incomplete]. Index-wide IDF statistics make scores differ from Postgres `ts_rank`.
- No per-query property filter: the usual trick is to index a tenant/index id property and add `group_id:"x" AND (...)` to the query text (Graphiti: `driver/neo4j/operations/search_ops.py:54-76`, with `lucene_sanitize`) [source].

Vietnamese recommendation [inferred]: store `name_norm`/`text_norm` produced by the engine's pure-Python normalizer (NFKD strip, `đ`->`d`, lowercase) and keep the original in separate properties; build full-text indexes on the `*_norm` properties with `standard-no-stop-words` (no English stop-word loss, no stemming). The same normalizer feeds Postgres, so analyzer differences disappear.

Could Neo4j be the VectorStore? Yes for chunks and entity-name embeddings: one multi-label vector index with `index_id` as filter property (`=` predicate, 2026.01+). Risks: server-version floor, ANN recall differences, 4096-dim cap, memory use of HNSW inside the DB heap/page cache. Keep the `VectorStore` protocol separate so users can still pair Neo4j graph with pgvector [inferred]. Hybrid chunk search needs RRF: do fusion in the engine from two ranked lists (Graphiti does RRF in Python, `search_utils.py:1775-1790`; neo4j-graphrag only has max-normalised "naive" and linear fusion, `neo4j_queries.py:197-262`) [source].

## Q3. Writes and consistency
- Batch idempotent upsert: `UNWIND $rows AS row MERGE (e:Entity {key: row.key}) ON CREATE SET ... ON MATCH SET ...`, backed by `CREATE CONSTRAINT ... REQUIRE e.key IS UNIQUE`. Docs: constraints "provide index-backed performance" and "protect against duplicate creation under concurrent loads, where MERGE alone only guarantees the existence of the pattern, not its uniqueness" [primary: `clauses/merge.adoc:609`]. Uniqueness constraints exist for nodes and relationships (also composite), and are available in CE.
- Relationship MERGE: `MERGE (a)-[r:T {key:row.key}]->(b)` takes exclusive locks on both end nodes when no match is found, then re-matches [primary: `merge.adoc` "Concurrent relationship merges"]. Hot nodes (hub entities) become lock points -> deadlocks possible; the driver's managed transactions retry transient errors until `max_transaction_retry_time = 30 s` [source: `_conf.py:360`, `_async/work/session.py:594-603` @6.3.1]. Idempotent writes make retries safe.
- Dynamic labels/types: `MERGE (n:$($labels) {...})`, `MERGE ()-[r:$($type)]->()` [primary: `merge.adoc`, `create.adoc`]. Available since 5.26. Performance: 5.26 to 2025.07 no index use; 2025.08 to 2025.10 token-lookup only; 2025.11+ exact seeks on range indexes (no full-text, order not used). A relationship type must be a single string. Alternative without dynamic syntax: group rows by type in Python and send one static query per type (labels and types come from the validated pack, so safe to interpolate after allow-list check) [inferred].
- Transaction memory: `db.memory.transaction.max` default 0 (unlimited per transaction), `dbms.memory.transaction.total.max` defaults to 70% of heap [primary: `configuration-settings.adoc:3266-3346`]. Whole-run transactions risk exhausting heap for big documents; user-side `db.transaction.timeout` also applies (default not checked).
- `CALL { } IN TRANSACTIONS [OF n ROWS] [CONCURRENT] [ON ERROR CONTINUE|BREAK|FAIL|RETRY]` is "only allowed in implicit transactions"; committed inner batches stay committed on later failure [primary: `subqueries/subqueries-in-transactions.adoc:15,346`]. With the Python driver that means `session.run` (as neo4j-graphrag does for cleanup, `kg_writer.py:289-295`), not `execute_query` or `execute_write` [source/inferred].
- Atomic or recoverable run [inferred, design options]:
  1. *One explicit transaction per document* (`execute_write`): atomic per document, bounded memory, idempotent re-run. Closest to the Postgres "unit".
  2. *Run record*: `(:Run {id, index_id, status: 'open'|'committed'|'failed'})`; every written node/edge stores `run_id`; readers ignore items whose run is not committed (adds a join/filter to every query) or a recovery job deletes items of failed runs. Needed only if a run must be all-or-nothing for readers.
  3. Single giant transaction: strongest parity, bounded by heap; only for small runs.
- One writer per index: Neo4j has no advisory locks. Options: a `(:IndexLease {index_id, owner, expires_at})` node taken with `MERGE` + conditional `SET` in a transaction (exclusive node write lock serialises takers) with heartbeat; or APOC `apoc.lock.nodes` (APOC core is on Aura's list; not needed otherwise) [primary: Aura APOC list; design inferred]. Postgres equivalent is `pg_advisory_lock`.

## Q4. Modelling
Proposed shape [inferred], mirroring `domain-packs.md` "What the graph contains":
- Nodes: `Document`, `Chunk`, `Entity` (+ pack type label via `$()`), `Event`, `Fact` (+ type label). Properties: `key` (content hash, unique), `index_id`, `pack`, `pack_version`, `name`, `name_norm`, `aliases`, embeddings as `VECTOR`/list.
- Roles: n-ary events/facts as nodes with `(:Fact)-[:ROLE {name:'buyer'}]->(:Entity|:Event)`. Role names are pack data, so keep one static type `ROLE` with a `name` property (indexable once) instead of one type per role.
- Provenance: `(:Entity)-[:MENTIONED_IN {surface}]->(:Chunk)`, `(:Fact|:Event)-[:SUPPORTED_BY {quote}]->(:Chunk)`, `(:Chunk)-[:PART_OF {position}]->(:Document)`. Matches neo4j-graphrag's lexical graph (`FROM_DOCUMENT`, `NEXT_CHUNK`, `FROM_CHUNK`, config in `components/types.py:247-262` @1.22.0) in spirit; names differ [source].
- Relations (entity->entity): native edge carrying value, `valid_from/valid_to`, `observed_at`, `recorded_at`, `status`, `quote`, `doc_id`, `chunk_id`, pack name and version. Their provenance is on the edge itself (cheaper than reifying), which only works if each (relation, chunk) is its own edge keyed by hash, as the "one row per statement per chunk" input implies.
- **Relationship indexes are per type**: range indexes on relationship properties exist (`create-indexes.adoc`: "only relationships with the specified type ... are added"), as do relationship uniqueness constraints. With pack-defined types, either (A) run DDL per relation type when a pack version is synced (needs schema privileges; idempotent `IF NOT EXISTS`), or (B) one static type `REL` + property `rtype`, one index and one constraint for all types, type filter as a property predicate. Graphiti chose (B): `RELATES_TO` with a `name` property and indexes on `uuid, group_id, name, created_at, expired_at, valid_at, invalid_at` (`graph_queries.py:55-64`, `models/edges/edge_db_queries.py:69,132` @v0.30.2) [source]. LlamaIndex and LangChain choose (A)-style dynamic types via `apoc.merge.relationship` [source]. Recommendation: (B) for parity with Postgres (`relation` table with a `type` column), unless benchmark shows a need for native typed expansion [inferred].
- Reified edge nodes are the fallback if edges need their own edges (Graphiti's Kuzu path uses `RelatesToNode_`, `edge_db_queries.py:88`) [source].
- Constraint gap in CE: no existence/type constraints, so required-property validation stays in the engine (it already validates in code) [inferred].

## Q5. Traversal
- Quantified path patterns: `((a)-[r:REL WHERE r.status = 'current' AND r.valid_to IS NULL]->(b)){1,2}` with inline `WHERE`; docs say inline predicates prune during traversal [primary: `patterns/variable-length-paths.adoc:364-562`]. `WHERE` on the quantified *relationship* shorthand is not allowed, QPP form is needed.
- Per-hop fan-out cap is not expressible inside a QPP. Use a scoped `CALL (frontier) { MATCH (frontier)-[r:REL]-(m) WHERE <type/time filter> RETURN m, r ORDER BY <rank> LIMIT $k }` per hop, unrolled twice for the <=2-hop limit [inferred; `CALL (var) {}` syntax is documented in `subqueries/call-subquery.adoc:167`]. LlamaIndex's `get_rel_map` only applies one global `LIMIT` after `*1..depth`, so it is not a fan-out cap (`neo4j_property_graph.py:559-600` @v0.14.25) [source].
- Hub penalty: degree via `COUNT { (m)--() }`, or a maintained `degree` property recomputed for touched nodes at end of the run (a write on hubs inside the run would add lock contention) [inferred, untested].
- Subgraph -> chunks: `MATCH (x)-[:MENTIONED_IN|SUPPORTED_BY]->(c:Chunk)`, then score `vector.similarity.cosine(c.embedding, $q)` exactly on the small candidate set (same as ranking by query vector in Postgres; exact scores, no ANN) [inferred; function used by neo4j-graphrag `neo4j_queries.py:52-56`].
- APOC: core subset on Aura includes `apoc.path`, `apoc.periodic`, `apoc.merge`, `apoc.text`, `apoc.lock` [primary]. We do not need it.
- PPR: GDS `gds.pageRank` accepts `sourceNodes` for personalised runs and has no edition note on that page [primary]. But GDS needs an in-memory projection, a separate plugin (GPLv3; CE capped at 4 cores) and on Aura Aura Graph Analytics sessions (Free/Pro/BC/VDC, need Aura API credentials, Arrow port) or the plugin on AuraDB Professional [primary: docs-aura `graph-analytics/index.adoc`, `alternative-deployments.adoc`]. Recommend client-side PPR (power iteration) on the <=2-hop expanded subgraph returned by the store; it is identical for both backends and keeps `engine` pure [inferred].

## Q6. Delete by document
Sketch [inferred, untested; shows shape not final Cypher]:
```
-- 1. chunks of the document
MATCH (:Document {key:$doc})<-[:PART_OF]-(c:Chunk)
-- 2. provenance-owned items
MATCH (x)-[s:SUPPORTED_BY]->(c)           // relation/event/fact -> chunk
-- delete SUPPORTED_BY edges, then Fact/Event nodes with no remaining SUPPORTED_BY
-- delete relation edges where r.doc_id = $doc (needs the per-type or rtype index from Q4)
-- 3. entities: delete MENTIONED_IN to c; DETACH DELETE entities with no MENTIONED_IN left
-- 4. DETACH DELETE chunks, then the document
-- 5. recompute supersession for touched (subject, relation type) groups
```
- Large deletes: docs have a "Deleting a large volume of data" pattern with `CALL { ... DETACH DELETE ... } IN TRANSACTIONS OF n ROWS` [primary: `subqueries-in-transactions.adoc:76`], which needs implicit transactions and is not atomic. Per-document deletes are small, so one `execute_write` is fine; stage large ones in batches by chunk.
- Cost drivers: `DETACH DELETE` of a hub entity touches all its edges; deleting by `doc_id` on edges needs the index (Q4) or it scans all edges. Also drop `NEXT_CHUNK` neighbours carefully (neo4j-graphrag has them).
- Supersession recompute is plain Cypher over (subject, type) groups ordered by `valid_from`, `observed_at`; or do it in the engine from a fetched group and write back flags (portable, same code as Postgres) [inferred].
- Reusable? No library gives provenance cascade: LlamaIndex `delete()` is by id/name/property with `DETACH DELETE` (`neo4j_property_graph.py:738-770`) [source].

## Q7. Reusable code (all at pinned tags)
| Library @ tag | Licence | Piece | Fit |
|---|---|---|---|
| neo4j-graphrag @1.22.0 | Apache-2.0 | `neo4j_queries.py:30-35` `CYPHER 25` prefix helper; `:306-350` `SEARCH ... WHERE` vector builder; `:38-62` legacy procedure queries; `:85-115` upsert nodes with `SET n:$(row.labels)` (5.24+) | Copy the idea. **Writer uses `CREATE (n:__KGBuilder__ {__tmp_internal_id})`, not `MERGE`: not idempotent**; relationships via `apoc.merge.relationship`; `components/kg_writer.py:185-330` |
| same | | `components/lexical_graph.py` (Document/Chunk/next-chunk) | Shape matches `PART_OF`/chunk order; trivial to rewrite |
| same | | `components/resolver.py:73-165` exact-match merge with `apoc.refactor.mergeNodes` | Does not fit: our resolution is staged, per type, reversible, with alias table |
| same | | `retrievers/hybrid.py`, `neo4j_queries.py:197-262` | Max-normalised/linear fusion, not RRF; fulltext still via procedure at 1.22.0 (comment `:363` says SEARCH supports vector only; contradicted by 2026.09 docs, so update) |
| same | | `components/schema.py` (2105 lines), `graph_pruning.py` | Own schema model; do not adopt, our pack compiler is richer |
| Graphiti @v0.30.2 | Apache-2.0 | `driver/neo4j/operations/search_ops.py` (Lucene query build, group_id filter), `search/search_utils.py:1775` `rrf`, `graph_queries.py:55-140` index DDL, `models/edges/edge_db_queries.py` `MERGE ... {uuid}` + `SET r = edge` | Best reference for a temporal Neo4j layer: one edge type + `valid_at/invalid_at/expired_at`; note vector search there is brute force, no vector index (not fully verified) |
| LlamaIndex `llama-index-graph-stores-neo4j` 0.8.0 @v0.14.25 | MIT | `neo4j_property_graph.py:196-216` constraints, `:345-420` MERGE upserts, `:559-600` rel map | Pins `neo4j>=5.16,<6`, so conflicts with driver 6.x; patterns only. Needs APOC (`apoc.meta.data`, `apoc.merge.relationship`) |
| langchain-neo4j `libs/neo4j/v0.10.0` | MIT | `graphs/neo4j_graph.py:25-70` import queries (`apoc.merge.node/relationship`) | Patterns only; depends on neo4j-graphrag |
Verdict: no library can be a dependency of the backend; copy-with-attribution small query ideas, license permitting (all permissive) [inferred].

## Q8. Parity matrix
Rating: L low, M medium, H high.
| Requirement | Postgres way | Neo4j way | Risk |
|---|---|---|---|
| Batch idempotent writes | `INSERT ... ON CONFLICT (hash) DO UPDATE` | `UNWIND` + `MERGE` on uniquely constrained key | L |
| Run = unit of consistency | one transaction | per-document transaction + run record; `IN TRANSACTIONS` unusable inside tx | **H** |
| One writer per index | advisory lock | lease node (or APOC lock) | M |
| Runtime type names | rows with `type` column | `$()` labels/types, or static type + property | M (L with static type) |
| Delete cascade + supersession | FK `ON DELETE CASCADE` or CTE | explicit multi-step Cypher; per-type index on `doc_id` | M |
| Entity linking: alias table | table + index | `Alias` nodes or list property + range index | L |
| Entity linking: trigram/fuzzy | `pg_trgm` `similarity`, `%` | Lucene `~` edit distance, or `apoc.text` (no index) | **H** (different semantics) |
| Name embedding | pgvector | vector index (ANN) | M |
| Hybrid chunk search BM25 + vector | `ts_rank`/tsvector + pgvector, RRF | Lucene full text + vector index, RRF in engine | M |
| Accent-insensitive | `unaccent` on normalized column | same normalized column, `standard-no-stop-words` | L |
| Expansion <=2 hops, type/time filter | recursive CTE / iterative joins, `LATERAL ... LIMIT` per hop | QPP or scoped `CALL` per hop | M |
| Fan-out cap, hub penalty | `LATERAL` + `ORDER BY ... LIMIT`; degree column | scoped `CALL ... LIMIT`; `COUNT {}` or property | M |
| Subgraph -> chunks ranked by query vector | join + `<=>` | match + `vector.similarity.cosine` | L |
| PPR | client-side | client-side (GDS optional) | L |
| Tests in Docker CI | `pgvector/pgvector` image | `neo4j:<ver>` CE image via testcontainers community module | L |
| Server-feature floor | PG 15+ extensions | 2026.01+ for filtered vector, 2026.09 for full-text `SEARCH` | M |
| Managed variants | Lakebase (no superuser) | Aura (APOC subset, latest version, no filesystem) | M |

Effort [inferred]: +5 to 7 engineer-weeks over the Postgres backend (schema/DDL and writes 1.5; retrieval queries 2; delete and supersession 1; contract-suite harness and CI 1; Aura and version-gating 1) plus ongoing cost of two query sets per engine change. If both branches share the pure-Python parts (normalizer, RRF, PPR, supersession ordering, tie-breaks) the figure drops toward 4 weeks.

Contract suite design [inferred]:
- One parametrised pytest fixture `graph_store` over [postgres, neo4j] (and a fake for engine unit tests), seeded from the same synthetic fixtures (no adopter data), containers via testcontainers.
- **Must be identical**: counts after batch upsert and after replay (idempotency); end state after delete by document (no orphan entity, relation, event, fact, chunk) and after re-ingest; supersession flags; provenance reachable from every item; filter semantics (type, `as_of` time, status); expansion membership within hop limit; fan-out cap as an invariant (each node contributes <= k per hop, which k chosen may differ on ties); hub penalty monotonicity (a penalised hub never outranks an otherwise equal non-hub); accent-insensitive match (`Nguyen`, `Nguyễn`, `Đức`/`Duc`) and original text round-trip.
- **May differ**: absolute scores and score scale (BM25 vs `ts_rank`, ANN vs exact), order among ties (engine breaks ties by `(score desc, id asc)` after the store returns raw lists), ANN recall (assert recall >= threshold on a tiny corpus, or force exact mode), fuzzy-match similarity numbers (assert the expected candidates are inside the returned set, not their order), concurrency error types (assert a generic `StorageError`).
- Put fusion (RRF), final ranking, PPR and normalization in the engine so backend differences stay inside "return the top-N candidate ids".
- Add a one-writer test (second writer is rejected or waits) and a kill-mid-run test (restart converges to the same end state).

## Key takeaways
1. Neo4j is feasible and CE is enough for CI and self-hosted use; require server >=2026.01 if you want in-index filtering, and gate full-text `SEARCH` on 2026.09 with a procedure fallback for earlier servers.
2. Decide the relation model first (typed edges + per-type DDL vs one `REL` type + `rtype`); it drives indexes, delete cost and parity.
3. Decide the run-consistency semantics for non-Postgres backends (per-document atomic + run record) and write it into the protocol contract, because "one transaction" cannot be promised.
4. Keep APOC and GDS out of the required path; compute PPR, RRF and normalisation in the engine.
5. Do not depend on any existing library for writes; borrow patterns from Graphiti and neo4j-graphrag.

## Gaps and caveats
- Not verified: AuraDB tier matrix and Free limits; whether Aura Free supports 2026 vector features; exact Neo4j EE licence terms for dev/test; whether `standard-folding` English stop words hurt Vietnamese (list not read); BM25 is inferred; default `db.transaction.timeout`; performance numbers for any query (nothing was executed; all Cypher is untested).
- Docs 2026.10 content comes from `dev` branches, not a release tag.
- Postgres-side statements in Q8 are from the project's ADRs and my knowledge, not re-verified.
- Not read: Graphiti's `graphiti.py` bulk path, neo4j-graphrag `retrievers/vector.py` filter classifier (`classify_filter_for_search`), LangChain vector stores.
- Leads: trademark policy for "Neo4j" in a module name; Memgraph/FalkorDB/Kuzu as alternative Cypher backends (Graphiti has drivers); whether Lakebase-branch tests can share the Postgres container image.

## Sources (pinned)
1. neo4j/docs-cypher `dev` @ea9b47a (2026-10-01): `indexes/semantic-indexes/vector-indexes.adoc`, `full-text-indexes.adoc`, `clauses/search.adoc`, `clauses/merge.adoc`, `clauses/create.adoc`, `subqueries/subqueries-in-transactions.adoc`, `patterns/variable-length-paths.adoc`, `indexes/search-performance-indexes/create-indexes.adoc`.
2. neo4j/docs-operations `dev` @e16efb0 (2026-10-01): `introduction.adoc`, `configuration/configuration-settings.adoc`, `docker/*.adoc`.
3. neo4j/docs-aura (cloned 2026-10-04): `apoc.adoc`, `partials/apoc-procedures.adoc`, `graph-analytics/*.adoc`, `license.adoc`.
4. neo4j/neo4j tag 2026.09.0: `community/lucene-index/.../fulltext/analyzer/providers/*.java`, `StandardFoldingAnalyzer.java`.
5. apache/lucene main: `ASCIIFoldingFilter.java` (unpinned).
6. neo4j/neo4j-python-driver tag 6.3.1: `pyproject.toml`, `LICENSE.txt`, `src/neo4j/_conf.py`, `_async/work/session.py`.
7. neo4j/neo4j-graphrag-python tag 1.22.0 (690a0e8): `neo4j_queries.py`, `components/kg_writer.py`, `lexical_graph.py`, `resolver.py`, `types.py`.
8. getzep/graphiti tag v0.30.2 (eaa4128): `graphiti_core/driver/neo4j/operations/search_ops.py`, `search/search_utils.py`, `graph_queries.py`, `models/edges/edge_db_queries.py`.
9. run-llama/llama_index tag v0.14.25: `llama-index-integrations/graph_stores/llama-index-graph-stores-neo4j/.../neo4j_property_graph.py`.
10. langchain-ai/langchain-neo4j tag libs/neo4j/v0.10.0: `libs/neo4j/langchain_neo4j/graphs/neo4j_graph.py`.
11. testcontainers/testcontainers-python tag testcontainers-v4.15.0: `src/testcontainers/community/neo4j/__init__.py`.
12. neo4j.com GDS docs (introduction, page-rank) and pricing page, fetched via a summarising tool 2026-10-04 [secondary quality]; neo4j.com/licensing.
13. Project: ARCHITECTURE.md, ADR 0002, ADR 0006, domain-packs.md, graphrag-research.md (read).
