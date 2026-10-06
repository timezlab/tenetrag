# Core engines in source: Microsoft GraphRAG, LightRAG, LlamaIndex

> **Snapshot, 2026-10-02 — not maintained.** Round 1 code-research lane on
> Microsoft GraphRAG v3.2.0, LightRAG v1.5.7 and LlamaIndex v0.14.25 at pinned
> tags: storage pluggability, data model, customization. Recovered from the
> session transcript. The maintained, re-verified summary is in
> [graphrag-engines.md](../reference/graphrag-engines.md); where they differ,
> the maintained doc wins. Local paths were removed before publishing.
>
> **Errata:** none found.

## GraphRAG engines: storage pluggability, data model, customization - findings
Pinned 2026-10-02. Cites are path#Lline under: GR = github.com/microsoft/graphrag/blob/v3.2.0/packages/; LR = github.com/HKUDS/LightRAG/blob/v1.5.7/lightrag/; LI = github.com/run-llama/llama_index/blob/v0.14.25/llama-index-core/llama_index/core/; LI-int = same tag, llama-index-integrations/; docs/ cites are repo-root. Labels: [source] verified in code, [docs] README/docs, [inferred]; table cells are [source] unless marked.

### Comparison

| Engine | Version / license | Storage interface | Postgres needs | Query modes | Prompt override | OpenAI-compatible LLM | Incremental / delete | Tables / time |
|---|---|---|---|---|---|---|---|---|
| microsoft/graphrag | v3.2.0 (2026-09-24), MIT; README: "largely in maintenance mode" [docs] | 3 ABCs + factories: Storage (KV files), TableProvider (DataFrames), VectorStore; no graph DB, graph = parquet tables | None built in (no pgvector store); custom TableProvider/VectorStore via register_* [source, inferred] | local, global, drift, basic (+stream); take DataFrames | ~12 prompt-file config keys, entity_types list, auto-tune API | LiteLLM 1.100.1; api_key required and static; refresh needs custom LLMCompletion | Update merges by exact title, no re-cluster; no delete | Claims with start/end dates; documents.raw_data; no numerics |
| HKUDS/LightRAG | v1.5.7 (2026-09-02), MIT; 8 stable + 3 rc since 2026-06 | 4 ABCs (KV, Vector, Graph, DocStatus) picked by string name via STORAGES dict; no plugin API | KV/DocStatus plain PG; PGTableGraphStorage plain tables (no AGE/pgvector); PGGraphStorage needs AGE; PGVectorStorage needs pgvector | local, global, hybrid, naive, mix, bypass | Mutable PROMPTS dict, addon_params, YAML entity profiles, per-query prompt | Any async callable; native OpenAI SDK, fresh client per call | Incremental; adelete_by_doc_id cascades, rebuilds shared entities | v1.5 table/image parsing; created_at only [source, docs] |
| run-llama/llama_index | v0.14.25 (2026-09-21), MIT; store ABC untouched since 2025-05 | PropertyGraphStore ABC (8 abstract methods) plus optional vector store; instance passed in, no registry | No PG graph store; PGVectorStore needs pgvector [source, pyproject] | LLM-synonym, vector, text-to-Cypher, Cypher-template, custom | Extractor prompt and parse_fn; schema extractor; no auto-tune | Databricks(OpenAILike); static api_key; http_client injectable | Upsert; ref-doc delete unusable; node-level delete only | None; free-form properties |

### microsoft/graphrag v3.2.0 (769542f)
- Storage: Storage ABC (graphrag-storage/graphrag_storage/storage.py#L13), TableProvider (.../tables/table_provider.py#L14), VectorStore (graphrag-vectors/graphrag_vectors/vector_store.py#L56; lancedb default with local db_uri, azure_ai_search, cosmosdb); registered via register_storage/register_table_provider/register_vector_store; Cosmos (3.1.0) is the non-file precedent [source].
- Model: documents, text_units, entities, relationships, communities, community_reports, covariates (graphrag/graphrag/data_model/schemas.py); titles upper-cased (graphrag/graphrag/index/operations/extract_graph/graph_extractor.py#L146); embeddings only for text-unit text, entity description, community full_content [source].
- Query is storage-decoupled: graphrag/graphrag/api/query.py takes DataFrames. Custom retriever = BaseSearch plus context-builder ABC (graphrag/graphrag/query/structured_search/base.py, .../context_builder/builders.py); no registry [source]. Bring-your-own-graph: supply entities/relationships parquet, then run create_communities, create_community_reports, generate_text_embeddings [docs/index/byog.md].
- Prompts: config keys are file paths (extract_graph.prompt, entity_types, summarize, claims, community reports, 4 search modes); graphrag/graphrag/api/prompt_tune.py#L52 generate_indexing_prompts returns 3 tuned prompts [source].
- LLM: graphrag-llm/graphrag_llm/config/model_config.py#L102 "api_key must be set when auth_method=api_key"; .../completion/lite_llm_completion.py#L240-243 binds it once, then **call_args. Refresh path: register_completion/register_embedding with custom classes [source, inferred]. LiteLLM v1.100.1's databricks provider (llms/databricks/common_utils.py#L258-287) uses refreshing SDK auth only when api_key is None, so a call_args api_key-null override is plausible but untested [inferred]. Extraction is delimiter text (errors yield empty frames); global/DRIFT search need JSON-object output (graphrag/graphrag/query/structured_search/global_search/search.py#L97) [source].
- Incremental: InputDelta.deleted_inputs is computed (graphrag/graphrag/index/update/incremental_index.py#L26) but never consumed: no delete or edit of existing documents; delta communities only get ID offsets [source].
- Execution: concurrent_requests=25, threaded (graphrag/graphrag/config/defaults.py#L189); sliding-window rate_limit; no Spark [source].

### HKUDS/LightRAG v1.5.7 (28ff1b0)
- Registry: kg/__init__.py#L1,#L122,#L153 (STORAGE_IMPLEMENTATIONS, STORAGES, verify_storage_implementation) plus kg/factory.py get_storage_class (4 defaults hard-wired, rest importlib via STORAGES[name]); a custom backend means mutating both dicts first [source, inferred]. ABCs: base.py#L252 (Vector), #L418 (KV), #L519 (Graph), #L1269 (DocStatus).
- Postgres: kg/pgtable_impl.py#L267 PGTableGraphStorage, tables lightrag_graph_nodes/edges (JSONB properties), added 2026-06-22; docs/LightRAG-API-Server.md#L917-919 recommends it over AGE-based PGGraphStorage on managed PG [source, docs]. pgvector only when vector_storage == "PGVectorStorage" (kg/postgres_impl.py#L2950). Password is a static string (#L424,#L704), but asyncpg accepts callable/awaitable passwords (asyncpg connect_utils.py#L1071), so token rotation needs a small patch [source, inferred]. working_dir is created even for remote backends [source].
- Model: node entity_id, entity_type, description, source_id (chunk ids joined by <SEP>), file_path, created_at; edges are undirected pairs with keywords, weight; no communities, reports, claims [source].
- Retrieval and prompts: mode is a closed Literal (base.py#L93, default "mix"), so no custom-mode hook; aquery_data (lightrag.py#L3998) returns entities/relationships/chunks without generation; rerank_model_func (lightrag.py#L755) is the pluggable stage. Prompts: mutable PROMPTS dict (prompt.py#L11), addon_params, YAML entity-type profiles, per-query user_prompt (base.py#L149); no auto-tune [source].
- LLM: llm/openai.py#L177,#L305 build a fresh AsyncOpenAI per call and pass api_key through unchanged [source], so a wrapper can supply a fresh token per call; openai-python >=1.106 also accepts an async-callable api_key (CHANGELOG) [inferred]. Extraction JSON is opt-in (lightrag.py#L743); query keyword extraction always requests json_object (operate.py#L5047) [source].
- Delete: lightrag.py#L5718 adelete_by_doc_id plus operate.py#L1101 rebuild_knowledge_from_chunks re-derive shared entities from cached extractions; ainsert_custom_kg (lightrag.py#L3484) imports caller graphs outside the crash-recovery guarantee [source].
- Execution: MAX_ASYNC_LLM 4, parallel insert 3, embedding 8 (constants.py#L96,#L97,#L708); no Spark [source].

### run-llama/llama_index v0.14.25 (f12d46a)
- graph_stores/types.py#L276 PropertyGraphStore: abstract get, get_triplets, get_rel_map, upsert_nodes, upsert_relations, delete, structured_query, vector_query (client is a plain property); supports_structured_queries/supports_vector_queries default False. EntityNode id = name; Relation(label, source_id, target_id, properties) [source].
- Integrations at tag: neo4j, falkordb, memgraph, nebula, neptune, tidb, ApertureDB; Kuzu removed 2025-10-28 (commit 52c42d5d) [source]. TiDBPropertyGraphStore (LI-int graph_stores/llama-index-graph-stores-tidb/.../tidb/property_graph.py#L76): two SQL tables plus recursive-CTE get_rel_map, the template for a Lakebase store [source, inferred]. SimplePropertyGraphStore persists one JSON via fsspec [source].
- indices/property_graph/base.py#L195 _insert_nodes drops KG nodes already in the store (first chunk wins), so triplet_source_id is single-valued. _delete_node (#L396) is store.delete(ids); ref_doc_info raises NotImplementedError and BaseIndex.delete_ref_doc (indices/base.py#L317) needs docstore entries PropertyGraphIndex never writes; delete_llama_nodes (types.py#L383) has no shared-entity check or re-summarization [source].
- Retrieval: PGRetriever merges sub-retrievers; subclass CustomPGRetriever (indices/property_graph/sub_retrievers/custom.py#L13). Prompts: SimpleLLMPathExtractor(extract_prompt, parse_fn); schema extractor (indices/property_graph/transformations/schema_llm.py#L368) needs astructured_predict, and get_program_for_llm (program/utils.py#L58) uses function calling only if is_function_calling_model, default False in OpenAILike (LI-int llms/llama-index-llms-openai-like/.../openai_like/base.py#L104) [source].
- Databricks: llama-index-llms-databricks 0.6.1 and embeddings-databricks 0.6.0 read DATABRICKS_TOKEN/DATABRICKS_SERVING_ENDPOINT; static key; http_client or reuse_client=False allow refresh injection [source, inferred].
- Execution: num_workers=4 (async_utils.py#L139); BaseLLM/BaseEmbedding rate_limiter since 2026-02/03. Communities only in docs cookbooks (GraphRAG_v2.ipynb) [docs].

### Canonical-schema assessment (inferred from the notes above)
Yes, with loss: export to canonical is cheap, import is lossy. Coverage: documents (GR native, LR full_docs, LI synthesized from chunk properties); chunks (all); entities (all; LI lacks a description field); relations (all, differing); communities/reports/claims (GR only); embeddings (GR 3 kinds, LR entities/relations/chunks, LI chunks and KG nodes, no relation vectors); provenance (GR id lists, LR <SEP> string plus entity_chunks/relation_chunks KV stores at lightrag.py#L1461-1467, LI one source id).
- Export: lossless from GR; LR/LI give empty community/claim layers; LR edges lose direction; LI relations lack description and weight.
- Import: GR via DataFrames or BYOG (communities regenerable); LR via ainsert_custom_kg (normalizes names, undirected); LI via upsert_nodes/relations (descriptions only in free-form properties).
Three incompatibilities:
1. Entity/relation semantics: name-keyed identity with different case rules (GR upper-case, LR cleaned and case-kept, LI default parser capitalizes); relations are described/weighted/untyped (GR), undirected with keywords (LR), directed/typed (LI).
2. Derived layers and lifecycle: GR alone derives communities/reports/claims yet cannot delete; LR rebuilds on delete; LI cannot cascade. Needs capability flags plus an SDK-owned chunk-to-entity/relation evidence table to implement delete itself.
3. Storage and query binding: tables+vector store (GR), four-store engine (LR), graph store+retrievers (LI). Retrieval is not swappable ("global" is community map-reduce in GR, relationship-keyword retrieval in LR), so the canonical store should expose neutral primitives (vector search, k-hop neighborhoods, reports) behind per-engine adapters, each with its own LLM-auth shim.

### Secondary engines
- getzep/graphiti v0.30.2 (2026-09-08), Apache-2.0: temporal graph; edges carry valid_at/invalid_at/expired_at/reference_time and episodes (graphiti_core/edges.py#L263-281); drivers Neo4j, FalkorDB (+falkordblite extra), Neptune+OpenSearch, Kuzu (deprecated); no Postgres; very active [source, docs].
- OpenSPG/KAG v0.8.0 (2025-06-28), Apache-2.0: schema-constrained, logical-form reasoning on the OpenSPG server (compose: server, MySQL, Neo4j, MinIO); last commits KAG 2026-01-28, OpenSPG 2025-06-29: slow [source, docs].
- circlemind-ai/fast-graphrag: pyproject 0.0.5, no releases, MIT, last code change 2025-06-21: igraph, hnswlib, pickles under working_dir; personalized PageRank; stale [source].
- OSU-NLP-Group/HippoRAG: README 2.0.0a5 (alpha), MIT, commits through 2026-10-01: PPR over igraph pickle (HippoRAG.py#L451) and parquet embedding stores; index/retrieve/delete; llm_base_url for OpenAI-compatible, key read from an env-var name [source, docs].
- neo4j/neo4j-graphrag-python 1.22.0 (2026-10-01): Neo4j-only; Apache-2.0 per pyproject (GitHub shows NOASSERTION); vector, hybrid, text2cypher retrievers; active [source].
- topoteretes/cognee v1.6.2 (2026-09-29), Apache-2.0: graph adapters ladybug (default), kuzu, neo4j, neptune, turso, postgres_demo (graph_node/graph_edge tables, text[] provenance arrays, source-ref attach/remove interface; code says demo, not production); vectors LanceDB, pgvector; weekly releases [source].

### Kuzu and embedded stores
- Kuzu maintained? No: kuzudb/kuzu is archived, last release v0.11.3 (2025-10-10) [docs: README]; LlamaIndex removed its store, graphiti deprecated it. Active fork LadybugDB/ladybug: MIT, v0.21.2 (2026-10-01), cognee's default [source]. RyuGraph fork: last push 2026-01-20.
- FalkorDBLite (v0.10.0, Python >=3.12) embeds Redis + FalkorDB, which is SSPLv1 (FalkorDB LICENSE); its own license not determined [source].
- DuckDB+DuckPGQ (cwida/duckpgq-extension, MIT, pushed 2026-09-17): no backend found in any engine above (GitHub code search; weak absence evidence).
- File-backed: LightRAG NetworkXStorage/NanoVectorDB/Faiss, LlamaIndex JSON, HippoRAG and fast-graphrag pickles. LightRAG branches dev-lancedb and dev-nebula-graph are absent from v1.5.7's registry [source].

gaps: untested: GraphRAG LanceDB/FileStorage on /Volumes FUSE, LightRAG PGTable on Lakebase, Lakebase extensions. Unread: LlamaIndex PG vector store code, non-TiDB graph stores, LightRAG community branches, GraphRAG query internals. Nothing executed.
leads: LiteLLM databricks provider as shared auth layer; cognee provenance arrays as canonical provenance model; llama-index-vector-stores-databricks 0.7.0.

### Sources
Tags/commits in headings; other engines at versions named; litellm v1.100.1, openai-python CHANGELOG 1.106.0, asyncpg main, LadybugDB v0.21.2; fast-graphrag and HippoRAG main as of 2026-10-02. Clones were not kept.
