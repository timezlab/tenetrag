# GraphRAG engines — reference architectures

**Verified:** 2026-10-02 by reading source at pinned tags or commits; nothing
was installed or run. These engines are references we borrow algorithms and
prompts from; none is a runtime dependency — see
[ADR 0001](../decisions/0001-build-own-graphrag-core.md). Port code only from
MIT or Apache-2.0 sources, with an attribution comment. What papers show
about these methods: [graphrag-research.md](graphrag-research.md). Licenses
of supporting libraries: [supporting-libraries.md](supporting-libraries.md).
Labels: **[source]** read in code · **[docs]** README/docs · **[inferred]**.
Raw lane reports (snapshots, not maintained):
[core engines](../research/2026-10-02-core-engines-source.md),
[RAGFlow](../research/2026-10-02-ragflow.md), [post-graph-rag](../research/2026-10-02-post-graph-rag.md),
[KG construction](../research/2026-10-02-kg-construction-libs.md),
[retrieval algorithms](../research/2026-10-02-retrieval-algorithm-libs.md),
[landscape](../research/2026-10-02-landscape.md),
[AWS graphrag-toolkit and a retrieval-flow review](../research/2026-10-02-aws-graphrag-toolkit.md).

Citation roots:

| Key | Root |
|---|---|
| GR | `github.com/microsoft/graphrag/blob/v3.2.0/packages/` |
| LR | `github.com/HKUDS/LightRAG/blob/v1.5.7/lightrag/` |
| LI | `github.com/run-llama/llama_index/blob/v0.14.25/llama-index-core/llama_index/core/` |
| RF | `github.com/infiniflow/ragflow/blob/v0.27.2/` — last Python release with `rag/graphrag/` |
| RC | `github.com/infiniflow/ragflow/blob/v1.0.0-rc1/` — Go rewrite; `K/` = `internal/ingestion/component/knowledge_compiler/` |
| PG | `github.com/crajah/post-graph-rag/blob/v1.15.2/post_graph_rag/`; storage layer in `github.com/crajah/post-graph` v1.8.0 |
| GI | `github.com/getzep/graphiti/blob/v0.30.2/graphiti_core/` |
| CO | `github.com/topoteretes/cognee/blob/v1.6.2/cognee/` |
| HR | `github.com/OSU-NLP-Group/HippoRAG/blob/2bfd831/src/hipporag/` |
| SAG | PyPI sdist `zleap-sag` 0.13.0, `src/zleap/sag/` (the engine has no public repo) |
| N4 | `github.com/neo4j/neo4j-graphrag-python/blob/1.22.0/src/neo4j_graphrag/` |
| AW | `github.com/awslabs/graphrag-toolkit/blob/graphrag-lexical-graph/v3.19.1/`; `L/` = `lexical-graph/src/graphrag_toolkit/lexical_graph/`, `D/` = `docs-site/src/content/docs/lexical-graph/` |

## Core references

| | Microsoft GraphRAG | LightRAG | LlamaIndex PropertyGraphIndex |
|---|---|---|---|
| Version | v3.2.0 (2026-09-24); README: "largely in maintenance mode … won't be accepting new PRs or implementing new features" [docs] | v1.5.7 (2026-09-02); ~8 releases since 2026-06 | v0.14.25 (2026-09-21); store ABC untouched since 2025-05 |
| Graph data | Parquet tables: documents, text_units, entities, relationships, communities, community_reports, covariates (claims) | KV, vector, graph and doc-status stores; nodes `entity_id, entity_type, description, source_id, file_path, created_at`; undirected edges with keywords, weight | `EntityNode` (id = name), `Relation(label, source_id, target_id, properties)`, `ChunkNode` |
| Storage seam | `Storage`, `TableProvider`, `VectorStore` ABCs + `register_*` factories | 4 ABCs picked by name via `STORAGES` dict (`kg/__init__.py`); no plugin API | `PropertyGraphStore` ABC, 8 abstract methods (`graph_stores/types.py#L276`) |
| Postgres | none built in | `PGTableGraphStorage` = plain tables, no AGE (`kg/pgtable_impl.py#L267`, added 2026-06-22); `PGGraphStorage` needs AGE; `PGVectorStorage` needs pgvector | no PG graph store; TiDB store (2 SQL tables + recursive CTE) is the closest template |
| Retrieval | local, global (community map-reduce), DRIFT, basic; query API takes DataFrames | naive, local, global (relationship keywords), hybrid, mix, bypass — closed `Literal`, no custom-mode hook; `aquery_data` returns context without generation | LLM-synonym, vector, text-to-Cypher, Cypher-template, `CustomPGRetriever` |
| Prompts | file-path config keys; `generate_indexing_prompts` auto-tune | mutable `PROMPTS` dict, `addon_params`, YAML entity profiles, per-query prompt | extractor prompt + `parse_fn`; schema extractor |
| LLM auth | LiteLLM, static `api_key` (refresh needs a custom class) | any async callable; fresh `AsyncOpenAI` per call (refresh is easy) | static key; injectable `http_client` |
| Incremental / delete | update merges by exact title; **no delete** (`InputDelta.deleted_inputs` defined, never consumed) | `adelete_by_doc_id` cascades and rebuilds shared entities from cached extractions | node-level delete only; no cascade |
| Time / claims | claims with `start_date`/`end_date`; claim extraction **off by default** (`ExtractClaimsDefaults.enabled = False`) | `created_at` only | none |

## Other engines read in source

| Engine | Pin · license · status | Study it for | Gap for us |
|---|---|---|---|
| RAGFlow classic GraphRAG | v0.27.2 (2026-09-10) · Apache-2.0 · **deprecated** in v0.27.0 in favour of Knowledge Compilation; Python source removed in v1.0.0-rc1 (RF `docs/release_notes.md`) | Ports of the GR and LR prompts; entity-resolution blocking; per-document subgraph checkpoints | Chunks batched to ~4096 tokens, so provenance is the document id only; contradictions summarized away; any insert regenerates every community |
| RAGFlow Knowledge Compilation | v1.0.0-rc1 (2026-09-29) · Apache-2.0 · ~6 weeks old, no published quality data | YAML extraction templates; claims carrying a verbatim quote verified against the cited chunk; document-level plus dataset-level rows with `source_doc_ids`; hash-keyed per-chunk cache (wiki kind) | No date type or validity field (timeline dates are free text); conflicting values concatenated or resolved to the "more recent-looking" one |
| post-graph-rag | v1.15.2 (2026-09-30) · Apache-2.0 · one author, 11 stars, ~561 tests against real pgvector | Closest analogue: Postgres only, valid time plus transaction time, non-destructive supersession, `sources[]` with dormancy on delete, as-of filter inside the recursive walk, RRF over three channels | JSONB payload with text dates; supersession by document processing order (`graph_store.py#L947`); superseded facts hidden; English only; CTE fan-out capped after materialization |
| Graphiti | v0.30.2 (2026-09-08) · Apache-2.0 · active, 31k stars | Bi-temporal edges with deterministic interval resolution; staged entity resolution; temporal search filters | Graph DB only (Neo4j, FalkorDB, Neptune; Kuzu deprecated); no alias field; episode-level provenance; `remove_episode` does not restore facts it expired |
| cognee | v1.6.2 (2026-09-29) · Apache-2.0 · active, 31k stars | `text[]` provenance columns with refcount delete; opt-in supersession for relations declared functional | Postgres adapter is "DEMO … not production-ready"; entity id = hash of the lowercased name, type ignored; recency by ingest time |
| SAG (Zleap-AI) | `zleap-sag` 0.13.0 (2026-09-17) · MIT · app repo active, 2.5k stars | Our storage model: events with `start_time`/`end_time`, entities with typed values and `value_raw`, expansion by SQL join, time-range search scope, per-source generations | Engine only as a PyPI sdist (declared repo returns 404); prompts zh/en only; benchmarks self-reported |
| HippoRAG 2 | main `2bfd831` (2026-10-01; PyPI 2.0.0a4) · MIT · research code | Personalized PageRank (PPR) over an entity + passage graph; exact delete through per-chunk source counts; recognition-memory fact filter | Entity keys casefolded to alphanumerics (figures lost); ASCII-only synonym guard; returns passages, not entity profiles |
| neo4j-graphrag-python | 1.22.0 (2026-10-01) · Apache-2.0, parts PSF-2.0 · active | Lexical graph (Document, Chunk, `FROM_CHUNK`); schema pruning with a report; seed-then-expand retrievers; retrievers as LLM tools | Neo4j and APOC only; global O(n²) resolvers; no time |
| AWS graphrag-toolkit `lexical-graph` | v3.19.1 (2026-08-26) · Apache-2.0 · active, 445 stars, 30 contributors | Three-tier lexical graph: chunk → topic → statement, with facts (SPO, and SPC for attributes) linking statements across sources to entities; statements as the unit of context; a subgraph turned into vector queries without an LLM (`EntityNetworkSearch`); hub pruning by a degree band; chunk-first entity seeding by default | Graph stores are Neptune, Neo4j and FalkorDB only (Postgres only as a vector store); statements are LLM rewrites (acronyms expanded), not verbatim quotes; relation names unguided and English uppercase; attributes stored as fact nodes; versions per document by extraction time, not per fact |
| fast-graphrag | `23b3a1b` (2025-11-01) · MIT · dormant | Scores flow entity → relation → chunk through scipy sparse matrices after PPR | Insert only |
| nano-graphrag | `acb35c0` (0.0.8) · MIT · dormant | Hash-keyed incremental insert | No delete; regenerates every community report on insert |
| NodeRAG | `f77dd6a` (0.1.0) · MIT · dormant | Pure scipy PPR; per-node-type quotas in the output | No document delete found |
| R2R | v3.6.5 (2025-06-06) · MIT · stale since 2025-11 | Entities, relationships and communities as Postgres tables with `chunk_ids uuid[]` | Exact-name dedupe within one document only |
| KAG | v0.8.0 (main 2026-01-28) · Apache-2.0 · slowing | A `source` edge from every node to its chunk; typed logical-form query plans | Schema requires an OpenSPG server |
| Mem0 | v2.2.1 (2026-09-25) · Apache-2.0 · active | Cautionary only | Graph memory removed on main; v1 hard-deleted contradicted relations by LLM decision |
| iText2KG (ATOM) | v1.1.0 (2026-09-04) · Apache-2.0 · active | Observation time kept apart from valid start/end; relative dates resolved against the observation date | No invalidation; in-memory graph |
| GR "fast" indexing | GR v3.2.0 · MIT | Zero-LLM noun-phrase co-occurrence graph with PMI weights | English-only extractors (TextBlob/NLTK, spaCy `en_core_web_md`) |
| LazyGraphRAG | no public code; a GR docstring says the regex extractor was used "in the first benchmarking of LazyGraphRAG" | Idea only: defer summarization to query time | — |
| benchmark-qed | v0.4.0 · MIT · Microsoft | AutoQ question generation (includes temporal); AutoE assertion and retrieval metrics | Temporal and conflicting-version questions for our corpus must still be hand-written |

## What no engine provides

These are ours to build, which is why
[ADR 0001](../decisions/0001-build-own-graphrag-core.md) holds:

- **All versions of a fact, dated and sourced, with the newest flagged.**
  Graphiti and post-graph-rag supersede and then hide older facts; RAGFlow
  merges conflicts into one text; cognee and post-graph-rag decide "newer" by
  ingest or processing order, not by the date in the document.
- **Correct state after a delete.** Graphiti does not restore facts that a
  deleted episode expired, and post-graph-rag has no un-supersede path
  [inferred, not exhaustive]. RAGFlow (classic and rc1) keeps a deleted
  document's text inside merged descriptions; only LightRAG rebuilds them
  from cached extractions.
- **Vietnamese.** Prompts are English or zh/en (SAG, NodeRAG, RAGFlow);
  guards are ASCII-only (HippoRAG); NLP models are English (GR fast,
  E2GraphRAG, KET-RAG); full-text search uses the `english` config
  (post-graph-rag).
- **Verbatim figures.** Only RAGFlow rc1's evidence quotes and SAG's
  `value_raw` preserve them; HippoRAG strips them from entity keys.
- **Identity beyond the name.** No engine read keeps two same-named
  entities of different owners apart by their attributes. They key on the
  name, or the name and type, or they partition hard by tenant (Graphiti
  `group_id`, mem0 `user_id`, LightRAG `workspace`). Graphiti merges a
  single exact-name hit without an LLM call. Record-linkage tools weigh
  attributes, but none declares per-type scope and vetoes. Ours:
  [ADR 0016](../decisions/0016-identify-entities-by-scope-keys-and-vetoes.md);
  evidence in the
  [homonyms](../research/2026-10-05-entity-homonyms.md#2-engines-and-record-linkage-libraries-code-lane)
  and [identity criteria](../research/2026-10-05-entity-identity-criteria.md#3-what-matching-systems-do)
  snapshots.
- **A schema lifecycle.** Many engines enforce a schema, and neo4j-graphrag
  reports every pruned item with a reason, but none records a schema version
  on extracted items, re-extracts selectively after a schema change, or
  designs a schema from target questions. Per-engine table:
  [graph-schema-design.md](graph-schema-design.md#what-engines-offer).

## Retriever flows compared

Engines compared step by step with the candidate retrieval flow in
[graphrag-research.md](graphrag-research.md#inputs-for-the-engine-brief-inferred)
(item 10; diagram in the
[snapshot](../research/2026-10-02-aws-graphrag-toolkit.md#95-proposed-flow)).
Steps: **1** entity linking from the query · **2** chunk hits seed entities ·
**3** expansion filtered by type, time and hubs · **4** subgraph → chunks ·
**5** chunks ranked by the query vector · **6** output.
✓ yes · ◐ partly · ✗ no. All [source] unless marked.

| Engine | 1 Entry | 2 Chunks seed entities | 3 Filtered expansion | 4 Subgraph → chunks | 5 Rank by query vector | 6 Output | Where |
|---|---|---|---|---|---|---|---|
| AWS graphrag-toolkit | One LLM call picks entities from the question and the top chunks; exact name match is optional | ✓ default | ◐ hub band by fact count (0.1×–10× the top entity); no type or time filter | ✓ subgraph rendered as text and used as a vector query | ◐ statement rerank, tf-idf by default | Statements (LLM rewrites), not chunks | AW `L/retrieval/query_context/keyword_vss_provider.py`, `entity_vss_provider.py`, `entity_context_provider.py`; `L/retrieval/retrievers/entity_network_search.py` |
| SAG | LLM NER of the query | ✓ vector + BM25 seed both events and entities | ✓ `event_entity` relation vectors scored against the query; per-entity quotas; time-range scope | ✓ hydration to source chunks | ◐ LLM or reranker | Events, entities, chunks | SAG `modules/search/production.py` |
| LightRAG (`mix`) | LLM keywords → entity vector search | ✗ `mix` adds vector chunks, but they do not seed entities | ✗ one hop; edges sorted by degree, then weight, descending, so hubs come first | ✓ through `source_id` | ✓ `VECTOR` is the default | Entities, relations, chunks | LR `operate.py#L4844` (keywords), `#L6020` (entities), `#L6129` (edge sort), `#L6136` (chunks), `#L5280` (`mix`) |
| post-graph-rag | Entity vector search | ✗ chunk vector search runs alongside, not as seeds | ◐ relation-type and as-of filters inside the recursive walk; no fan-out cap | ◐ chunks mentioning matched entities | Not read | Relations and chunks; RRF over graph walk, relation ANN and relation full-text | PG `graph_store.py#L1666`, `engine.py#L1034-L1215` |
| HippoRAG 2 | Query → fact embeddings; an LLM keeps ≤ 4 of the top 5 facts | ✓ passage scores enter the PPR reset vector | ◐ PPR; phrase seeds divided by the number of chunks containing them, which damps hubs | ✓ PPR ranks passages | ✗ the graph decides the order | Passages only | HR `HippoRAG.py#L1892`, `rerank.py`, `HippoRAG.py#L2008-L2115`, `#L2211` |
| fast-graphrag | LLM NER → entity vector match | ✗ | ◐ PPR | ✓ scores propagate entity → relation → chunk through sparse matrices | ✗ | Entities, relations, chunks with scores | `fast_graphrag/_services/_state_manager.py#L185`, `#L296-L310` |
| neo4j-graphrag `HybridCypherRetriever` | — | ✓ vector + full-text hit, then a user-written `retrieval_query` | User-written Cypher | User-written | User-written | Whatever the Cypher returns; Neo4j only | N4 `retrievers/hybrid.py#L286` |
| Graphiti | BM25, cosine and BFS over edges and nodes | ◐ episodes, not chunks | ◐ temporal `SearchFilters`; `node_distance` reranker around a centre node | ◐ to episodes | ✗ | Facts (edges), nodes, episodes | GI `search/search_config.py`, `search/search_config_recipes.py`, `search/search_filters.py` |

**Reading the table** [inferred]:
- No engine runs the whole flow. Every step has a working implementation,
  so the risk is in composing them, not in inventing them.
- **Closest overall: SAG.** It has event nodes with time, BM25 + vector
  seeding, query-scored edges, a time scope and hydration to chunks. But it
  has no entity–entity relations, its prompts are zh/en only, and the engine
  ships only as a PyPI sdist.
- **Closest per step:** AWS for steps 1–4, LightRAG for steps 4–6.
- **Step 4 without an LLM has three shipped variants:** provenance plus
  query vector (LightRAG), PPR (HippoRAG 2), and score propagation
  (fast-graphrag). Make step 4 a swappable stage and benchmark all three.
- **An LLM in the loop belongs to the agentic family:** GR DRIFT (LLM
  follow-up queries), KAG's planner, RC's agent runtime. Our flow leaves that
  loop to the calling agent.
- **No engine does these:**
  - keep only the edges whose evidence lies in the returned chunks;
  - return verbatim facts with every dated version;
  - link entities through an alias table and trigrams for Vietnamese;
  - apply type, time and hub filters in one expansion step.
- **Benchmark idea:** use LightRAG `mix` as a reference engine baseline. It
  runs on Postgres through `PGTableGraphStorage`. Keep it in the `bench`
  extra only, after the dependency gate.

## Microsoft GraphRAG communities

Read in source at v3.2.0 on 2026-10-05
([snapshot](../research/2026-10-05-graphrag-communities.md), with file and
line for each claim). Nothing from GraphRAG was run.

- **Build.** Hierarchical Leiden (`graspologic_native.hierarchical_leiden`)
  runs over the relationship edges, undirected, weighted by the summed LLM
  `relationship_strength`. Level 0 is the coarsest, and any community that
  reaches `max_cluster_size` (10) is split into the next level. With
  `use_lcc` (on by default), nodes outside the largest connected component
  get no community. The seed is fixed (0xDEADBEEF).
- **Membership.** A relationship belongs to a community only when both
  endpoints are in it, so edges between communities appear in no report.
- **Reports.** One LLM call per community per level, finest level first.
  The context lists edges by combined endpoint degree, with their entities
  and claims, trimmed at 8000 tokens. Each node keeps only one edge per
  direction (`agg("first")`). The code that would substitute
  sub-community reports appears unreachable. The output has title,
  summary, findings, rating (0–10) and rating_explanation.
- **Global search.** It uses the reports at level ≤ N (CLI default 2),
  taking each entity's deepest community. Map calls read full report text
  in batches of up to 12000 tokens and score points from 0 to 100; reduce
  drops zero scores and writes the answer. Dynamic selection, off by
  default, rates level-0 reports from 0 to 5 and descends into relevant
  children.
- **Local and DRIFT.** Local search gives 15 % of its context budget to
  the reports of the communities that hold the most matched entities. DRIFT
  primes with a HyDE answer against the 20 most similar reports, then runs
  local search for 3 rounds.
- **Update.** Only the delta is clustered; its communities and reports are
  appended with offset ids, and old communities are never re-clustered.
  There is no delete path.

## What we borrow

### Data model and provenance

| Idea | From | Where |
|---|---|---|
| Claim rows carrying a verbatim quote that is verified as a substring of the cited chunk, with offsets; soft gate by default because dropping facts hurts enumeration questions | RC | `K/structure/evidence.go`, `K/tree/claims.go` |
| Chunk-id-labelled batches so the model cites chunk ids in one pass | RC | `K/structure/prompt.go` (`PackBatch`) |
| Two-stage extraction: entities first, then relations restricted to them | RC | `K/structure/compile.go` |
| Extraction templates as data: entity types, relation types, rules, output fields | RC | `api/db/init_data/compilation_templates/*.yaml` |
| Typed values with a verbatim `value_raw` beside int, float, datetime and unit columns | SAG | `db/models.py` |
| Lexical graph: Document → Chunk (`NEXT_CHUNK`) ← entity (`FROM_CHUNK`) | N4 | `components/lexical_graph.py` |
| Provenance as chunk-id arrays with GIN indexes; refcount delete; orphaned rows go dormant | CO, PG | CO `infrastructure/databases/graph/postgres_demo/tables.py`, `infrastructure/databases/provenance/source_ref_state.py`; PG `graph_store.py#L282-L481` |
| Schema pruning that reports what it dropped and why | N4 | `components/graph_pruning.py` |
| Extraction rule: numbers, dates, measurements and attributes are never entities; attributes come out as `entity\|ATTRIBUTE\|value` (store them as columns or claims, not as the toolkit's fact nodes) | AW | `L/indexing/prompts.py` (`EXTRACT_TOPICS_PROMPT`) |
| Delimiter-text entity/relation extraction; description summarization | GR | `graphrag/index/operations/extract_graph/graph_extractor.py` |
| Claims (covariates) with subject, object, start/end dates | GR | `graphrag/data_model/schemas.py` (`COVARIATES_FINAL_COLUMNS`) |
| Plain-table graph on Postgres | LR, LI-TiDB | `kg/pgtable_impl.py`; TiDB `property_graph.py#L76` |

### Time and versions

| Idea | From | Where |
|---|---|---|
| Valid time only when the text states it (null = always valid), plus transaction time; never use the document date as valid time | PG | `graph_store.py#L683-L800`, `extractor.py#L390-L398` |
| The LLM nominates duplicates and contradictions as separate lists; code applies the interval rules and handles out-of-order ingestion | GI | `utils/maintenance/edge_operations.py#L538-L573`; `prompts/dedupe_edges.py` |
| "Never mark facts with key differences as duplicates" — numbers, dates, qualifiers | GI | `prompts/dedupe_edges.py` |
| Supersede only relations the profile declares functional | CO | `tasks/graph/resolve_temporal_contradictions.py` |
| As-of, superseded and dormant filters applied inside the recursive walk | PG | `graph_store.py#L1666`; post-graph `client_asyncpg.py` (`_edge_filter_sql`) |
| Relative dates resolved against a reference time (episode or observation date) | GI, iText2KG | GI `prompts/extract_edges.py`; iText2KG `itext2kg/atom/models/schemas.py` (`AuvaLab/itext2kg` v1.1.0) |
| Validity rendered into the context (`[valid X to Y]`) | PG | `engine.py#L1762` |

### Entity resolution

| Idea | From | Where |
|---|---|---|
| Staged: exact normalized name → MinHash/LSH over 3-gram shingles (Jaccard ≥ 0.9) with a low-entropy guard → LLM only on the residue, answering -1 when unsure | GI | `utils/maintenance/dedup_helpers.py`, `utils/maintenance/node_operations.py` |
| Block by type and new-vs-all pairs; reject a pair whose 2-gram difference contains a digit ("Q3" ≠ "Q4"); batched yes/no LLM confirmation | RF | `rag/graphrag/entity_resolution.py#L228-L289` |
| Synonym edges by embedding kNN instead of merging nodes | HR | `HippoRAG.py#L1278` |
| Alias sets as first-class output of cluster-then-LLM dedupe | KGGen — idea only, no LICENSE file | `stair-lab/kg-gen` `src/kg_gen/utils/llm_deduplicate.py` |
| Several same-named candidates go to the LLM instead of one being picked; the prompt has a same-name, different-thing example and answers "no match" when unsure | GI | `prompts/dedupe_nodes.py` |
| Two same-name entities in one chunk re-keyed by name, chunk id and ordinal, so they stay apart | CO | `cognee/modules/graph/utils/expand_with_nodes_and_edges.py` |
| Per-attribute behaviour (how many share a value, one value at a time, lasting); a disagreeing exclusive attribute disqualifies a match; a missing value scores nothing | Senzing config template, idea only (a matcher, not an engine) | `g2config_template.json` (third-party copy) |
| Qualifiers such as country or birth date lower a score but never create a match | nomenklatura logic-v2 (OpenSanctions matcher) | `nomenklatura/matching/logic_v2/model.py` |
| Term-frequency adjustment, so a common value counts less | Splink 5.0.0 | `splink/internals/comparison_level.py` |

### Retrieval

| Idea | From | Where |
|---|---|---|
| Dual-level keyword retrieval; mix mode; context-only retrieval | LR | `operate.py`, `lightrag.py#L3998` (`aquery_data`) |
| Communities + community reports; local/global/DRIFT search; bring-your-own-graph | GR | `graphrag/api/query.py`, `docs/index/byog.md` |
| Seed by vector + BM25, expand by SQL join, per-entity quotas, hydrate to source chunks, time-range scope | SAG | `modules/search/production.py` |
| RRF over graph walk, relation-embedding ANN and relation full-text (k = 60) | PG | `engine.py#L1115-L1200`, `engine.py#L1513` |
| PPR seeds: phrase score ÷ number of chunks containing the phrase, passage score × 0.05, damping 0.5 | HR | `HippoRAG.py#L2008-L2115` |
| Pure scipy sparse PPR (no igraph) | NodeRAG | `NodeRAG/utils/PPR.py` |
| Recognition-memory filter: a small LLM keeps ≤ 4 of the top-5 facts; dense fallback when none survive | HR | `rerank.py` |
| Entity → relation → chunk score propagation with sparse matrices | fast-graphrag | `fast_graphrag/_services/_state_manager.py#L296-L310` |
| Compiled rows resolved back to source chunks; claim recall renders the verbatim quote | RC | `internal/rag/agentic-rag/runtime/tool_compiled_expansion.go`, `tool_claims.go` |
| Edges and nodes reranked by graph distance from a centre entity, for "everything about A" questions | GI | `search/search_config_recipes.py` (`EDGE_HYBRID_SEARCH_NODE_DISTANCE`) |
| Graph and structure navigation exposed as agent tools | RC, N4 | RC `internal/rag/agentic-rag/runtime/tool_executor.go`; N4 `ToolsRetriever` |
| Query rewrite into expected answer types plus entities | RF | `rag/graphrag/search.py#L38-L60` |
| Parent/child: match small chunks, return the parent | RF | `rag/nlp/search.py#L968-L1010` |
| Related chunks of the matched entities and relations ranked by cosine to the query (`KG_CHUNK_PICK_METHOD=VECTOR`, the default); `WEIGHT` polls by occurrence count | LR | `operate.py#L6136` (`_find_related_text_unit_from_entities`), `utils.py#L5965` (`pick_by_vector_similarity`) |
| Entity-network paths rendered as text and used as vector queries, to reach chunks unlike the question but linked to it — no LLM in the step | AW | `L/retrieval/retrievers/entity_network_search.py` |
| Chunk-first entity seeding: vector search over chunks or topics (top 3), then the entities their statements mention, scored by fact count | AW | `L/retrieval/query_context/entity_vss_provider.py`, `keyword_vss_provider.py` |
| Hub pruning: keep entities whose fact count is within 0.1×–10× of the top matched entity's; paths of ≤ 3 entities; top 3 paths | AW | `L/retrieval/query_context/entity_context_provider.py` (`filter_entities`) |
| Results grouped source → topic → statements, each with its facts, chunk id, score and the retrievers that found it — a model for the app's retriever view | AW | `D/traversal-based-search.mdx` |

### Incremental indexing and operations

| Idea | From | Where |
|---|---|---|
| Delete-by-document with rebuild from cached extractions | LR | `lightrag.py#L5718`, `operate.py#L1101` |
| Per-source generations: write new rows, switch the active generation, clean up the old | SAG | `db/models.py` (`SAGSourceManifest`) |
| Content-hash-keyed per-chunk extraction cache plus a per-document contribution diff | RC | `K/wiki/wiki_map_cache.go`, `K/wiki/wiki_incremental_state.go` |
| Backlog table with last-event-wins and claim-token fencing | RC | `internal/ingestion/knowledge_compile/consumer.go` |
| Hash-keyed checkpoints for the expensive phases (resolution, communities) | RF | `rag/graphrag/checkpoints.py` |
| Index manifest binding stored embeddings to the model identity | HR | `HippoRAG.py#L317` |
| Document versions: stable identity from caller-chosen metadata fields, `valid_from`/`valid_to` per version; delete removes orphaned facts and entities | AW | `L/versioning.py`, `D/versioned-updates.mdx` |
| Prompt auto-tuning | GR | `graphrag/api/prompt_tune.py#L52` |

## Pitfalls to avoid

| Pitfall | Seen in | Our rule |
|---|---|---|
| Entity identity by exact name with engine-specific casing | GR upper-cases; LR keeps case; LI capitalizes; CO hashes the lowercased name and ignores type | Normalize names (Unicode NFC, tone-mark placement; diacritics kept) and keep aliases in a table; identify by type, scope, keys and vetoes, never by the name alone ([ADR 0016](../decisions/0016-identify-entities-by-scope-keys-and-vetoes.md)) |
| A single exact-name hit merged with no further check, so two companies' "Finance Department" become one | GI `dedup_helpers.py` (`_resolve_with_similarity`) | A name counts only within a compatible scope and after the vetoes; a name many share, such as a person's, is only evidence ([engine brief §2.6](../product/engine-brief.md#26-resolve-entities-e8)) |
| A wrong merge drops the other node's properties | N4 (`apoc.refactor.mergeNodes`, `properties:'discard'`) | Keep each attribute value per source with its quote; merges stay reversible from the cache |
| Numbers only inside LLM-merged descriptions | GR, LR, LI, RF | Keep figures verbatim with time and source; always return source chunks |
| Contradictions summarized away or merged to the "more recent-looking" value | RF summarize prompt; RC `K/structure/merge.go` | One fact row per statement with its date and source; never merge conflicting facts |
| Older facts hidden once superseded | PG (default config), GI (`expired_at`) | Return every version with dates and sources; flag the newest |
| "Newer" decided by ingest order | PG, CO | Order by the date stated in the text, then the document date; re-indexing an old document must not make it newest |
| A deleted document's text survives in merged rows | RF, RC (`StripMergedSources` strips ids only) | Derive descriptions from fact rows, or rebuild affected rows on delete |
| Deleting a document leaves the facts it superseded hidden | GI `remove_episode`; PG | Recompute supersession for affected keys on delete |
| Derived layers that cannot be deleted | GR | Provenance tables drive delete and re-index |
| Document id as the only provenance | RF (`general/index.py#L63`) | Extract per chunk and keep chunk ids |
| First-chunk-wins provenance | LI (`_insert_nodes`) | Many-to-many entity ↔ chunk provenance |
| Invalid chunk citations widened to the whole batch | RC `K/structure/compile.go` (`payloadChunkIDs`) | Reject the item |
| Evidence matching by exact substring after whitespace collapse only | RC `evidence.go` | NFC + whitespace normalization, character offsets; a diacritic-insensitive match only as a flagged fallback |
| Entity keys stripped to ASCII alphanumerics | HR `utils/misc_utils.py#L91`, `HippoRAG.py#L1333` | Keep the raw surface form; normalize in a separate column; Unicode-aware checks |
| Any insert regenerates every community | RF `general/index.py#L526-L530`; nano-graphrag `graphrag.py#L319` | Regenerate only touched communities ([ADR 0011](../decisions/0011-cluster-by-default-and-make-community-reports-opt-in.md)) |
| Updates cluster only the new documents and append their communities, so an entity can sit in an old and a new community | GR `index/update/communities.py:44-84` | Re-cluster the whole graph (no LLM), then rewrite only the reports whose membership changed |
| Edges between communities and nodes outside the largest component appear in no report | GR `create_communities.py:113-127`, `graphs/stable_lcc.py` | Communities never replace entity-led retrieval; keep every component |
| Undirected edges | RF, LR | Keep direction and predicate |
| Neighbour edges ranked by degree, so hubs come first | LR `operate.py#L6129` | Penalize hubs; rank edges by relevance to the query |
| KG context returned as CSV text in a fake chunk | RF `rag/graphrag/search.py` | Structured records with chunk id, document id and date |
| Recursive CTE capped only after it materializes; per-path cycle check | PG / post-graph `traverse` | Cap fan-out per hop inside the query; depth ≤ 2 by default |
| Contradicted facts deleted on LLM judgment | Mem0 v1 | Never delete on LLM judgment; supersede and keep |
| Global post-hoc O(n²) entity resolution | N4 `components/resolver.py` | Blocked, incremental resolution per new entity |
| Runaway indexing cost ($200 and 36 h reported) | RF issue #7957 | Cost estimate in the plan before anything runs; actual calls and tokens beside the estimate in the run record; no automatic stop ([engine brief](../product/engine-brief.md#213-cost-e10-decided), E10) |
| Static API keys | GR, LI | Token providers with refresh in the `llm` layer |
| Statements and attribute facts as graph nodes: one piece of knowledge shows up as several near-identical nodes | AW (seen in one demo graph) | Entities and typed events are nodes; statements are fact rows; attributes are columns |
| Relation names unguided ("currently unguided") and forced to English uppercase | AW `D/graph-model.mdx`, `L/indexing/prompts.py` | Relation types come from the profile; labels in the graph language |
| Acronyms expanded by the LLM during extraction | AW `EXTRACT_PROPOSITIONS_PROMPT` | Keep the source acronym verbatim; expansions go to the alias table [inferred: domain acronyms are often ambiguous] |
| Every statement embedded as a vector entry point: "High storage costs", "queries often taking minutes", deprecated | AW `D/traversal-based-search.mdx` | Embed chunks and entity names; reach facts through the graph |

## Not portable

- **License:** Youtu-GraphRAG (academic use only), PathRAG and ArchRAG (no
  LICENSE file), KGGen (no LICENSE file, although `pyproject.toml` says MIT).
- **Infrastructure we do not have:** KAG schema (OpenSPG server), GFM-RAG
  (GPU GNN with English-trained weights), ArchRAG (custom Faiss build).
- **Wrong shape:** E2GraphRAG (single long document, `en_core_web_lg`),
  PathRAG (rebuilds the whole networkx graph per query), Kotaemon (UI over
  other engines), RAG-Anything (parser layer; pins `lightrag-hku<1.5`).
