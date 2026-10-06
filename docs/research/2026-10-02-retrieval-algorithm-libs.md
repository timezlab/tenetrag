# Retrieval/indexing algorithms beyond MS GraphRAG and LightRAG: code-level report

> **Snapshot, 2026-10-02 — not maintained.** Round 2 code-research lane on
> retrieval and indexing algorithms beyond Microsoft GraphRAG and LightRAG:
> HippoRAG 2, SAG, fast-graphrag, NodeRAG, KAG, PathRAG and others. The
> maintained, re-verified summary is in
> [graphrag-engines.md](../reference/graphrag-engines.md) and
> [graphrag-research.md](../reference/graphrag-research.md); where they
> differ, the maintained doc wins. Local paths were removed before publishing.
>
> **Errata:** none found.

*2026-10-02. Read via shallow clones (not installed or run). Labels: **[source]** read in code, **[docs]** README/docs only, **[inferred]** my reasoning. Each repo is pinned to a commit or tag.*

## Executive summary
- **Offer PPR (personalized PageRank) over an entity+passage graph as a retriever, with scipy sparse.** HippoRAG 2 (`2bfd831`, MIT) is the reference. NodeRAG's `utils/PPR.py` is a ready-made scipy power iteration. Both need only an edge list, so SQL is enough. The caveat is that HippoRAG returns passages ranked, not entity profiles.
- **SQL-join expansion is the best fit for our storage model.** SAG (`zleap-sag` 0.13.0, MIT) puts chunk, event, entity, event_entity and typed entity values in relational tables. It builds "hyperedges" at query time with joins. fast-graphrag's entity→relation→chunk sparse-matrix chain is the same idea in numpy.
- **Cheap indexing is real.** The `graphrag` v3.2.0 "fast" method uses spaCy/regex noun-phrase co-occurrence and PMI weights, with LLM calls only for community reports. KET-RAG spends LLM calls on only a budgeted PageRank-selected fraction of chunks.
- **LazyGraphRAG has no public code.** Only the regex NP extractor's docstring says it was used "in the first benchmarking of LazyGraphRAG".
- **Hype or blocked for us:**
  - Youtu-GraphRAG: academic-only license.
  - PathRAG and ArchRAG: no LICENSE file.
  - KAG: needs the OpenSPG server for schema.
  - GFM-RAG: GPU GNN.
  - E2GraphRAG: English-only spaCy, single long document.
- **Gap shared by all repos:** none supports validity time, conflicting versions, or verbatim figures in its graph keys. We must build C2 and the figure handling ourselves. SAG is the only one with event `start_time`/`end_time` columns and a time-scoped search.

## 1. HippoRAG 2 (OSU-NLP-Group/HippoRAG)
- **Version:** main `2bfd831` (2026-10-01). `pyproject.toml` says 2.0.0a5. PyPI latest is 2.0.0a4 (2025-06-24). The only GitHub tag is v1.0.0. **[source]**
- **License:** MIT. **Activity:** 4.0k stars, pushed 2026-10-01 (MCP server, index manifest, fail-closed state checks). **[source]**
- **Graph** (`src/hipporag/HippoRAG.py`):
  - Phrase nodes are entity strings. Passage nodes are chunks, keyed by a content hash.
  - Fact edges: `add_fact_edges` (L1179) adds one undirected edge per triple, with weight = triple count and per-chunk `fact_source_counts`.
  - Context edges: `add_passage_edges` (L1230) adds an edge from the passage to every phrase in it, weight 1.0.
  - Synonym edges: `add_synonymy_edges` (L1278) links entity embeddings with kNN. Defaults are `synonymy_edge_topk=2047`, `sim_threshold=0.8`, at most 100 per node (`utils/config_utils.py` L160–175).
  - The edge weight is `max(fact count, synonym score)`.
- **OpenIE:** two LLM calls per chunk. NER (`prompts/templates/ner.py`) returns `{"named_entities": [...]}`. Triples are then extracted conditioned on those entities (`triple_extraction.py`, "construct an RDF graph… resolve pronouns"). Both prompts are one-shot, English, Radio City example. **[source]**
- **Query:**
  1. Embed the query against fact embeddings (`get_fact_scores`, L1892).
  2. Recognition memory: an LLM filter (`rerank.py`, `DSPyFilter`) picks up to 4 of the top `linking_top_k=5` facts.
  3. If no facts survive, fall back to dense passage retrieval (`retrieve`, L763).
  4. Otherwise `graph_search_with_fact_entities` (L2008) seeds PPR.
- **Seeds:**
  - Phrase weight = fact score, divided by the number of chunks the phrase appears in (an IDF-like term), averaged over facts.
  - Passage nodes get min-max-normalized dense-retrieval score × `passage_node_weight=0.05`.
  - The two vectors are summed into one reset vector.
- **PPR:** `graph.personalized_pagerank(... damping=0.5, directed=False, weights='weight', reset=..., implementation='prpack')` (L2211). `damping=0.5` means 50% reset. Scores are read off the passage nodes only. **[source]**
- **Incremental:**
  - `index()` reuses persisted OpenIE per chunk hash and runs synonymy only for new entities versus all (L1316).
  - `delete()` (L595) removes chunks, subtracts the chunk from `fact_source_counts`, and drops unreferenced entities, facts and edges. It is exact because edges are source-aware.
  - An edit is delete-old-text plus insert-new-text, since the key is the text hash. **[source]**
- **Graph size, from the shipped `outputs/musique/openie_results_ner_gpt-4o-mini.json`, my count:**
  - 11,656 chunks gave 101,544 entities, 127,640 triples, 120,702 distinct fact-edges and 146,301 passage-edges.
  - That is about 8.7 entities and 11 triples per ~100-word chunk, plus up to 100 synonym edges per entity. **[source, computed]**
- **Cost:** index = 2 LLM calls per chunk plus embeddings of chunks, entities and facts. Query = 1 embedding, 1 small LLM filter call, and PPR on the full graph (fast with prpack). **[source]**
- **Relational fit:** yes, **[inferred]**.
  - The tables would be `entity`, `chunk`, and `edge(src, dst, weight, source_chunk_ids)`.
  - Load the edges into `scipy.sparse.csr_matrix`, build the reset vector from pgvector top-k, iterate or call `scipy.sparse.linalg`.
  - Synonym edges come from a pgvector kNN self-join, per new entity only.
  - A few hundred thousand edges loads in seconds; cache the CSR per index version.
- **Fit pitfalls:**
  - `text_processing` (`utils/misc_utils.py` L91) casefolds and replaces every non-alphanumeric character with a space. Entity keys therefore lose figures ("3.5%" becomes "3 5"). The raw triples stay in the OpenIE JSON, so verbatim figures need our own column.
  - The synonym guard `len(re.sub('[^A-Za-z0-9]','',entity)) > 2` (L1333) counts only ASCII, so short Vietnamese entities with diacritics get no synonym edges. **[source]**
  - The output is passages only. No time model.

## 2. LazyGraphRAG, graphrag "fast" indexing, benchmark-qed
- **LazyGraphRAG code:** not public. I found no "lazy" implementation in `microsoft/graphrag` v3.2.0 (`769542f`, MIT), none in benchmark-qed, and `gh search` returned no Microsoft repo. The only references are `docs/blog_posts.md` L41, a docstring, and a config example name. **[source]**
  - The `regex_extractor.py` docstring says it is "the extractor used in the first benchmarking of LazyGraphRAG but it only works for English".
- **Fast index:**
  - `IndexingMethod.Fast` (`config/enums.py` L48) runs `create_base_text_units, create_final_documents, extract_graph_nlp, prune_graph, finalize_graph, create_communities, create_final_text_units, create_community_reports_text, generate_text_embeddings` (`index/workflows/factory.py` L63).
  - `build_noun_graph.py`: nodes are noun phrases mapped to the text-unit ids that contain them. Edges connect all pairs of phrases in a text unit, with weight = number of co-occurring text units.
  - Weights are optionally converted to PMI (`graphs/edge_weights.py`).
  - Extractors (`NounPhraseExtractorType`):
    - `regex_english`: TextBlob/NLTK, English only.
    - `syntactic_parser`: spaCy dependency parse plus NER, default model `en_core_web_md`.
    - `cfg`: grammar-based noun chunks plus NER.
  - spaCy 3.8, TextBlob 0.20 and NLTK 3.9 are declared in `pyproject.toml`.
  - **LLM use: only community-report summaries.** No entity or relation descriptions. **[source]**
  - `fast-update` is the incremental variant.
- **benchmark-qed** (MIT, release v0.4.0 on 2026-09; the `gh` releases listing shows v0.3.0, but the changelog and tags show 0.4.0): **[source]**
  - AutoQ: synthetic local, global and data-linked questions. Linked types are bridge, comparison, intersection and temporal (`autoq/config.py` L126, L545–570).
  - AutoE: pairwise LLM-judge on relevance, comprehensiveness, diversity and empowerment. 0.4.0 added assertion scoring, retrieval metrics (TVD) and significance tests.
  - AutoD: dataset sampling and summarization.
  - LazyGraphRAG appears only as a sample method name for answer folders.
- **Usable for our benchmark:** partly **[inferred]**. The temporal question type and the assertion/retrieval-metric evaluation are reusable ideas. Prompts and datasets are English; Vietnamese needs prompt overrides (supported per the 0.2.0 prompt-customization changelog entry). Golden questions for "state at past date" and "conflicting definitions" must be hand-made.

## 3. KAG (OpenSPG/KAG)
- **Version:** v0.8.0 tag (2025-06-28); main `fdab15b` (2026-01-28). **License:** Apache-2.0. **Activity:** 9.1k stars, last push 2026-01-28. **[source]**
- **Mutual indexing:**
  - Extractors (`builder/component/extractor/schema_constraint_extractor.py`, `knowledge_unit_extractor.py`) emit a `SubGraph`.
  - `add_chunk_to_graph` (L417) adds a Chunk node and a `source` edge from every extracted node to the chunk. Chunk text is stored as `name\ncontent`. This is the provenance link.
  - Entity linking and standardization LLM steps feed it. The prompts include NER, std, relation and event steps, so about 3–4 LLM calls per chunk **[source, by method names]**.
- **Schema:** a `.schema` file (`examples/riskmining/schema/RiskMining.schema`) declares EntityType/ConceptType, typed properties, relations, `constraint: MultiValue`, and `rule:` blocks in a Datalog-like DSL.
  - The constraint extractor loads the schema via `SchemaClient(host_addr=…, project_id=…)` (L64). That needs an OpenSPG server. **[source]**
- **Logical-form solver:**
  - `solver/prompt/logic_form_plan.py` defines operators `Retrieval(s=s1:Type[name], p=p1:edge, o=o1)`, `Math(...)`, `Deduce(op=judgement|entailment|extract|choice|multiChoice)` and `Output(...)`.
  - The planner (`planner/lf_kag_static_planner.py`) has the LLM emit steps with variable aliases and rewrites sub-queries with the upstream answers.
  - Executors are `kag_hybrid_executor` (graph and chunk retrieval), math and deduce.
  - LLM calls per query: 1 plan, plus per step 1 rewrite, 1 retrieval and 1 deduce. **[inferred]**
- **Without the server:**
  - A `memory_graph` backend exists (`common/graphstore/memory_graph.py`): igraph plus torch, with `ppr_chunk_retrieval` using damping 0.1 and a seed reset of 1 per start node.
  - But the extractors still construct `SchemaClient` with a host address, so I could not find a path that avoids the server. Treat the schema-constrained build as server-bound. **[source for memory_graph and SchemaClient; inference for "no server path"]**
- **Fit:** the idea is valuable. A typed-slot query plan (`Retrieval(s=Campaign[A], p=hasDecision)`) maps cleanly onto SQL over typed tables. The code is Chinese-first, needs the server, and is heavy. Port the idea only.

## 4. fast-graphrag and nano-graphrag
- **fast-graphrag** (circlemind-ai): `23b3a1b` (2025-11-01), version 0.0.5, MIT, no release tags, 4.0k stars. Idle for 11 months. **[source]**
  - Query path (`_services/_state_manager.py` `get_context`, L185):
    1. One LLM call extracts `named` and `generic` entities from the query (`_information_extraction.py` L41).
    2. Vector-match them to entities (top-1 for named, top-20 at threshold 0.5 for generic). Entity score is the max across channels.
    3. `personalized_pagerank(damping=0.85, directed=False, reset=...)` in igraph (`_storage/_gdb_igraph.py` L172).
    4. Entity ranking policy (threshold 0.05), then `scores.dot(e2r)` for relations, then `.dot(c2r)` for chunks. Both matrices are `scipy.sparse.csr_matrix` (L296–310).
  - Output is `TContext(entities, relations, chunks)`, each with scores. This is the closest to our "context-only structured retrieval" shape.
  - Indexing: LLM entity/relation extraction per chunk with gleaning steps (`max_gleaning_steps`), plus an LLM merge of duplicate descriptions (`_merge`).
  - Incremental: insert only. No `delete` at the graph or service level. Edge merge uses `edge_merge_threshold=5` (`_policies/_graph_upsert.py` L222).
  - Relational fit: **yes**. Two sparse incidence matrices plus PPR are trivially loaded from `entity`, `relation`, `relation_chunk` tables. **[inferred]**
- **nano-graphrag** (gusye1234): `acb35c0` (2026-01-27), v0.0.8 (2024-10-01), MIT, 4.0k stars, 83 open issues. **[source]**
  - It reimplements MS GraphRAG (~1100 lines) with swappable storage (nano-vectordb, hnswlib, networkx, neo4j) and a DSPy entity-extraction variant (`nano_graphrag/entity_extraction/`).
  - Additions: hash-keyed incremental insert (docs and chunks), `enable_naive_rag` chunk mode.
  - Limits: no delete, and `ainsert` does `await self.community_reports.drop()` then regenerates all community reports on every insert (`graphrag.py` L319, with an inline TODO above it). That makes edits and deletes expensive (C4).
  - Effectively in maintenance only.

## 5. Newer code-backed variants
| Repo | Pin | License | Activity | Core mechanism | Verdict for us |
|---|---|---|---|---|---|
| NodeRAG (Terry-Xu-666) | `f77dd6a`, v0.1.0 (2025-03-18) | MIT | Dormant 18 months | Heterogeneous graph: text, semantic-unit, entity, relationship, attribute, high-level (community) nodes. Query: HNSW seeds plus regex phrase match on entities, then scipy sparse PPR with `alpha=0.5, max_iter=2` (`utils/PPR.py`, `search/search.py` L78) | Borrow the sparse PPR and node-type quotas (`post_process_top_k`). Prompts are English/Chinese, other languages by LLM-translating the prompt (`utils/prompt/prompt_manager.py`). No document delete found. |
| PathRAG (BUPT-GAMMA) | `32567bf` (2025-12-17) | README says MIT, **no LICENSE file** (GitHub: none) | 377 stars | LightRAG fork. For each pair of seed entities, DFS to depth 3, then flow-decayed weights (threshold 0.3, alpha 0.8) over a rebuilt `networkx` graph (`PathRAG/operate.py` L1054–1180) | Hype for us. Rebuilds the whole graph from storage per query. Licensing unclear. Returns path text, which is the one useful idea. |
| Youtu-GraphRAG (Tencent) | v0.2.1 (2026-02-26) | **Custom: academic use only, no commercial or production use** (`LICENSE`) | 1.3k stars | Schema-guided 4-level knowledge tree, agentic decomposer, FAISS node/relation retrieval, IRCoT | Blocked by license. Do not port. |
| RAG-Anything (HKUDS) | v1.4.1 (2026-09-02) | MIT | 23k stars, active | Parser layer (MinerU, Docling, PaddleOCR) plus Image/Table/Equation processors that LLM-describe each item and insert an entity plus a chunk into LightRAG. `pyproject.toml` pins `lightrag-hku<1.5` | Not a retrieval algorithm. Borrow table-as-chunk, and the idea of keeping tables verbatim. |
| E2GraphRAG (YiboZhao624) | `f598d4f` (2025-09-22) | MIT | 161 stars | No LLM entity extraction: spaCy sentence-level co-occurrence graph (`extract_graph.py`), plus an LLM summary tree over chunks, plus shortest-path chunk retrieval (`query.py`) | `en_core_web_lg` hard-coded; built for single long documents (novels). Hype for a multi-document corpus. |
| ArchRAG (sam234990) | `a219fef` (2025-11-27) | **No LICENSE** | 42 stars | MS GraphRAG extraction, then Leiden attributed communities, hierarchical C-HNSW (custom Faiss build), PPR entity search | Blocked by license and custom Faiss. |
| KET-RAG (waetr) | `c632ff4` (2025-02-18), Apache-2.0 | Apache-2.0 | 204 stars; last push 2025-06-02 | MS GraphRAG fork. `indexing_sket/filter_chunks.py`: pick `budget` fraction of chunks (default 0.8 in `config/defaults.py`; paper reports lower values) by `nx.pagerank(alpha=0.85)` on a chunk-kNN graph, then LLM-extract only those. Rest indexed in a keyword–chunk bipartite graph (NLTK English stopwords) (`create_final_keyword_index.py`) | Borrow the budget idea; but PageRank centrality favors typical chunks and would deprioritize unique decisions. English-only tokenizer. |
| GFM-RAG (RManLuo) | v2.0.0 (2026-04-19) | Apache-2.0 | 300 stars, active (2026-09) | HippoRAG-style OpenIE graph index, then a pretrained GNN (8M or 34M "G-reasoner") scores nodes conditioned on the query (`gfmrag_retriever.py` `retrieve(query, top_k, target_types)`), torch-geometric | Needs GPU and torch-geometric; English-trained weights; opaque scoring. Not a fit for SQL. |
| **SAG (Zleap-AI/SAG)** | repo v1.8.11 (`f80ee6c`, 2026-10-02); engine `zleap-sag==0.13.0` (PyPI, 2026-09-17) | MIT | 2.5k stars, very active | See below | **Closest to our storage model.** |

**SAG details** **[source: sdist `zleap_sag-0.13.0`, read not run]**
- **Source-availability caveat:** the GitHub repo is the app. The engine is the PyPI package `zleap-sag`; its declared repo `Zleap-AI/zleap` returns 404. I read the sdist.
- **Tables** (`src/zleap/sag/db/models.py`): `data_source`, `kb_document`, `source_chunk`, `source_event`, `entity_type`, `entity`, `event_entity`, plus `sag_source_manifest` (active_generation_id, chunk/extract versions).
  - `source_event` has `title, summary, content, start_time, end_time, parent_id, level, keywords, generation_id`.
  - `entity` has typed values: `value_raw` (verbatim text), `int_value`, `float_value`, `datetime_value`, `value_unit`.
  - `event_entity` has weight and description.
- **Index:** one event per chunk plus several entities per chunk. One extraction pass per chunk, no relation extraction.
- **Retrieval** (`modules/search/production.py`): LLM NER of the query, vector and BM25 seed events and entities, hop expansion by scoring `event_entity` relation vectors (`score_relations_by_event_ids`), per-entity quotas, then LLM or rerank precision ranking and hydration to source chunks. `RepositorySearchScope` carries `start_time`/`end_time`, data-source and source filters.
- **Incremental:** per-source generations with cleanup (`pending_cleanup_generations`), so edit or delete replaces one source's rows.
- **Limits:** extraction prompts only support `zh` and `en`; "Extract never cross-language-falls back" (`modules/extract/prompts.py` L51–57). Vietnamese would need new prompt files. Benchmark claims (HotpotQA/2Wiki/MuSiQue) are **[docs]**, self-reported. Not checked against the paper.

**Other high-adoption repos found** (not read, listed by `gh search --topic graphrag`): `neo4j-labs/llm-graph-builder`, `neo4j/neo4j-graphrag-python` (need Neo4j), `trustgraph-ai/trustgraph`, `pingcap/autoflow` (TiDB), `Graphify-Labs/graphify` (123k stars, appears to be code-graph tooling; not verified). Cognee, Graphiti and RAGFlow are in the shared repos directory and I assume another lane covers them.

## 6. txtai graph and Kotaemon
- **txtai** (v9.13.0, 2026-08-27, Apache-2.0, 13k stars): **[source]**
  - `graph/base.py` makes documents the nodes. `inferedges` links each node to its top `limit=15` neighbours with `minscore=0.1` from the embedding index.
  - No LLM at index time.
  - Topics come from Louvain/greedy-modularity communities (`topics.py`), named by top terms.
  - `graph/rdbms.py` stores nodes and edges in a SQL database via the `grand` library with SQLAlchemy; the code special-cases PostgreSQL schemas. Query is openCypher-like (`graph/query.py`).
  - There is no entity extraction in the graph. Multilingual depends only on the embedding model. A useful low-cost "related documents" layer, not an entity-centric one.
- **Kotaemon** (v0.12.0, 2026-05-31, Apache-2.0, 25.8k stars): a UI app whose graph features wrap MS GraphRAG, LightRAG and nano-graphrag (`libs/ktem/ktem/index/file/graph/*.py`). It has no algorithm of its own. Notable only for the Vietnamese entry in `ktem/utils/lang.py` (the answer-language map), which controls the answer language and does not make extraction multilingual. **[source]**

## Comparison against C1–C10
| Mechanism | C1 entity aggregation | C2 time/versions | C3 provenance | C4 incr. add/edit/delete | C5 index LLM / query | C6 relational fit | C7 multilingual / ER | C8 context-only output | C9 license / maintenance | C10 vs naive RAG |
|---|---|---|---|---|---|---|---|---|---|---|
| HippoRAG 2 | partial (passages) | none | chunk via `source_id` | good, exact delete | 2 calls/chunk; 1 filter call/query | yes (SQL edges + scipy) | embeddings model-agnostic; ASCII quirks; ER by embedding kNN | passages plus seed facts | MIT / active | [docs] only |
| fast-graphrag | yes (entities, relations, chunks) | none | chunk | insert only | extraction + gleaning + merge; 1 NER call/query | yes (2 sparse matrices) | prompt English | entities/relations/chunks with scores | MIT / idle | [docs] only |
| SAG | yes (event-entity joins) | event start/end, query time scope | chunk and source | good (generations) | 1 pass/chunk; NER + rerank calls | native SQL | zh/en prompts only | yes | MIT / very active; engine closed in repo | [docs] only |
| graphrag fast | weak (NP co-occurrence) | none | text unit | `fast-update` | LLM only for reports | tables already (parquet) | English regex; spaCy needs per-language model | via MS search | MIT / active | covered elsewhere |
| NodeRAG | yes (typed nodes) | none | via nodes | insert, no delete found | several calls/chunk | scipy yes | prompt translation | node-type quotas | MIT / dormant | [docs] only |
| KAG | schema-typed slots | not built in | chunk `source` edges | server-bound | 3–4 calls/chunk; planner calls | memory_graph only | Chinese-first | mixed | Apache / 8 months idle | [docs] only |
| KET-RAG | partial | none | chunk | none | budgeted extraction | tables | English tokenizer | MS-style | Apache / idle | [docs] only |
| nano-graphrag | MS-style | none | chunk | no delete; reports regenerated | MS-style | no | prompt English | MS-style | MIT / maintenance | [docs] only |

C10 note: I did not run benchmarks. Every "beats naive RAG" figure in these repos is README or paper self-reporting. The papers lane should cover it.

## What we should borrow
| Idea | Repo | File path | Why |
|---|---|---|---|
| Fact-edge weight = triple count, with per-chunk source counts | HippoRAG | `src/hipporag/HippoRAG.py` L1179, L684 | Exact delete of one chunk's contribution; maps to an edge table with a `source_chunk_ids` column |
| Seed weight divided by number of chunks containing the phrase | HippoRAG | `HippoRAG.py` L2065 | IDF-like seed weighting, one line in SQL |
| Passage seeds × 0.05 plus phrase seeds, PPR reset 0.5 | HippoRAG | `HippoRAG.py` L2008–2115, config L91, L192 | Tested constants |
| Recognition-memory triple filter | HippoRAG | `rerank.py`, `prompts/filter_default_prompt.py` | Cheap precision step; rewrite the prompt for Vietnamese |
| Pure scipy sparse PPR | NodeRAG | `NodeRAG/utils/PPR.py` | Drop-in numpy/scipy implementation, no igraph |
| Node-type quotas on ranked output | NodeRAG | `NodeRAG/search/search.py` `post_process_top_k` | Maps to per-type limits in the context output |
| Entity → relation → chunk sparse matrices | fast-graphrag | `fast_graphrag/_services/_state_manager.py` L296–310 | Gives structured context with scores |
| One event per chunk with entity links, expansion by SQL join, time-scoped search | SAG | `zleap_sag/db/models.py`, `modules/search/production.py` | Same storage model as ours |
| Typed value columns with `value_raw` | SAG | `db/models.py` L780–800 | Keeps figures verbatim and queryable |
| Per-source generation and cleanup | SAG | `db/models.py` `SAGSourceManifest` | Edit = new generation, swap, then cleanup |
| Provenance as a `source` edge from every node to its chunk | KAG | `schema_constraint_extractor.py` L417 | Same shape as our C3 requirement |
| Typed-slot plan operators | KAG | `solver/prompt/logic_form_plan.py` | Query plan to SQL |
| PMI-weighted co-occurrence graph | graphrag | `graphs/edge_weights.py` | Zero-LLM edge weights for a candidate graph |
| Extraction budget | KET-RAG | `indexing_sket/filter_chunks.py` | Cost control for large corpora, with a different selection rule |
| Table/figure kept as its own chunk | RAG-Anything | `modalprocessors.py` `TableModalProcessor` | Tables in product docs |
| Index manifest binding embeddings to model identity | HippoRAG | `HippoRAG.py` L317 | Prevents mixing embedding models |

## Pitfalls
| Pitfall | Where | Consequence |
|---|---|---|
| Entity keys are casefolded alnum-only | HippoRAG `text_processing` | Verbatim figures and symbols lost in graph keys; store raw separately |
| ASCII-only synonym guard | HippoRAG L1333 | Short Vietnamese entities get no synonym edges |
| Hard-coded English models | graphrag regex NP, E2GraphRAG `en_core_web_lg`, KET-RAG NLTK stopwords | Do not work for Vietnamese without replacement |
| Prompts support only `zh`/`en` | SAG, NodeRAG (translates prompt by LLM) | Vietnamese prompt files must be written and tested |
| No delete | fast-graphrag, nano-graphrag, NodeRAG (not found) | Incompatible with C4 |
| Full community-report regeneration per insert | nano-graphrag L319 | Cost grows with every edit |
| Central-chunk selection | KET-RAG | Unique one-off decisions are the least central |
| Per-query full-graph rebuild | PathRAG | Latency grows with corpus |
| Missing or restrictive licenses | PathRAG, ArchRAG (none), Youtu (academic-only) | Cannot port |
| Core engine not in public repo | SAG (PyPI sdist only) | Attribution and maintenance risk; pin a version |
| Schema needs a server | KAG | Not usable offline |
| Retrieval returns passages, not entities | HippoRAG | Need our own entity aggregation join |
| No validity time or version conflicts in any graph | all | Must model `valid_from/valid_to`, `supersedes` ourselves |

## Ranked verdict
1. **Entity-seeded SQL expansion with typed context output** (SAG model plus fast-graphrag matrices). Highest fit for C1, C3, C6, C8. Our own tables carry time and versions (C2). Query cost: 1 NER call plus joins.
2. **HippoRAG-style PPR over entity+passage graph, scipy sparse.** Worth offering as the "associative / multi-hop" retriever. Index = 2 calls per chunk, exact delete. Needs Vietnamese-aware normalization and verbatim-figure columns. NodeRAG's PPR code is the port target.
3. **Recognition-memory filter** as an optional precision step (one small LLM call).
4. **Cheap NLP co-occurrence graph (graphrag fast style)** as a zero-LLM candidate generator or low-budget tier; needs Vietnamese NER/tokenizer. Optionally add KET-RAG-style budgeting with a coverage-based selection.
5. **KAG-style typed plan:** adopt as a query-planner idea over our schema, not the code.
6. **txtai-style document-similarity graph:** optional "related documents" layer.

**Hype or blocked:** PathRAG (licensing plus per-query graph rebuild), Youtu-GraphRAG (license), ArchRAG (license, custom Faiss), GFM-RAG (GPU GNN), E2GraphRAG (single-document, English), RAG-Anything (parser value only), Kotaemon (wrapper). Evidence for C10 is untested in this report.

## Gaps
- LazyGraphRAG query path: not public, so untested.
- KAG online retrieval (`kag_hybrid_executor`, `kg_cs`) read only at the interface level; LLM call counts there are inferred.
- NodeRAG per-chunk LLM call count not traced (only pipeline file names).
- SAG paper (arXiv 2606.15971) not read; benchmark numbers unverified.
- Cognee, Graphiti, RAGFlow, LightRAG variants not covered (assumed other lanes).
- Not verified: Graphify's category and other topic-search hits.

## Sources (all pinned above)
HippoRAG `2bfd831`; graphrag v3.2.0 `769542f`; benchmark-qed `10e8dbe` (v0.4.0 changelog); KAG `fdab15b`; fast-graphrag `23b3a1b`; nano-graphrag `acb35c0`; PathRAG `32567bf`; NodeRAG `f77dd6a`; youtu-graphrag `d982b5a`; RAG-Anything `1f73f01`; E-2GraphRAG `f598d4f`; ArchRAG `a219fef`; KET-RAG `c632ff4`; gfm-rag `b3e4321`; txtai `20c9b8e`; kotaemon `9ad3e4e`; SAG `f80ee6c`; PyPI sdist zleap-sag 0.13.0. Clones were not kept.
