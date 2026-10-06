# KG construction and agent-memory libraries: source-level report

> **Snapshot, 2026-10-02 — not maintained.** Round 2 code-research lane on
> knowledge-graph construction and agent-memory libraries: Graphiti, cognee,
> neo4j-graphrag, R2R, Mem0, iText2KG, AutoSchemaKG, KGGen. The maintained,
> re-verified summary is in
> [graphrag-engines.md](../reference/graphrag-engines.md); where they differ,
> the maintained doc wins. Local paths were removed before publishing.
>
> **Errata and later resolutions:**
> - The header says paths are relative to each repo root, but KGGen paths are
>   relative to `src/kg_gen/` (for example
>   `src/kg_gen/utils/llm_deduplicate.py`) and iText2KG `atom/...` paths are
>   relative to `itext2kg/` (for example `itext2kg/atom/models/schemas.py`).

*2026-10-02. Code read from shallow clones at the pinned tags. Labels: [source] = read in code, [docs] = README or docs text, [inferred] = my reasoning. Paths are relative to each repo root.*

## Executive summary
- **Graphiti v0.30.2** has the best temporal and invalidation design. Edges carry `valid_at/invalid_at/expired_at`. Contradiction is decided by the LLM, but the timestamp arithmetic is deterministic code. Nothing is deleted. The mechanism ports to plain tables.
- **Graphiti has no SQL driver and no alias model.** Its provenance is episode-level only, and `remove_episode` is lossy (see pitfalls).
- **cognee v1.6.2** has the most useful relational artifacts. Its `postgres_demo` schema carries four `text[]` provenance columns for refcount-style delete and re-ingest. It also has an opt-in "supersede functional relationships" pass. Its Postgres adapter is labelled demo-only and cannot run its temporal retriever.
- **neo4j-graphrag 1.22.0** contributes the lexical-graph pattern (Document, Chunk, `FROM_CHUNK`) and the schema-pruning idea. It has no temporal model, and its resolvers are post-hoc batch merges.
- **R2R v3.6.5** is the only reference whose entities, relationships and communities are Postgres tables. It is stale (last commit 2025-11-07), and its dedupe is name-exact per document.
- **Mem0 v2.2.1** has dropped graph memory and the LLM ADD/UPDATE/DELETE/NONE step from the default path.
- **iText2KG, AutoSchemaKG and kg-gen** are batch-oriented. Only iText2KG's ATOM models incremental merge with timestamps (`t_obs/t_start/t_end`).
- **Recommended design:** Graphiti-style bi-temporal claim rows, plus cognee-style array provenance on every row, plus a Graphiti-style staged entity resolution (deterministic first, LLM only for the residue). Details are in the verdict.

---

## 1. Graphiti (getzep/graphiti)
**Tag/date:** v0.30.2, released 2026-09-08 (commit eaa4128). **License:** Apache-2.0. **Activity:** last push 2026-09-30, about 31k stars, very active [source: GitHub API].

### Edge invalidation algorithm (`graphiti_core/utils/maintenance/edge_operations.py`)
1. `resolve_extracted_edges` (l.325) first dedupes exact `(src, dst, normalized fact)` within the batch. It then embeds the facts and runs two hybrid searches per edge with `EDGE_HYBRID_SEARCH_RRF` [source]:
   - **Duplicate candidates:** restricted to edges between the same two nodes (`EntityEdge.get_between_nodes`).
   - **Invalidation candidates:** unrestricted, across the whole group.
2. `resolve_extracted_edge` (l.623) has a verbatim fast path: same endpoints and same normalized fact. In that case it just appends `episode.uuid` to `edge.episodes`, with no LLM call.
3. Otherwise there is one LLM call (`ModelSize.small`), prompt `prompts/dedupe_edges.py::resolve_edge`. It returns `EdgeDuplicate{duplicate_facts:[idx], contradicted_facts:[idx]}`, with indices continuous across both lists [source]. The system message says "NEVER mark facts with key differences as duplicates", particularly numeric values, dates and qualifiers. The few-shot example treats "software engineer" to "senior engineer" as a contradiction, not a duplicate.
4. Dates are deterministic code (`resolve_edge_contradictions`, l.538) [source]:
   - Skip a candidate if its `invalid_at <= new.valid_at`, or if `new.invalid_at <= candidate.valid_at`. These are disjoint intervals.
   - Otherwise, if `candidate.valid_at < new.valid_at`, set `candidate.invalid_at = new.valid_at` and `candidate.expired_at = now` (first expiry only).
   - If a contradicted candidate has a later `valid_at` than the new edge, the new edge is itself expired (`invalid_at = candidate.valid_at`, `expired_at = now`). Out-of-order ingestion is therefore handled.
5. Invalidated edges are saved, never deleted (`entity_edges = resolved + invalidated` in `graphiti.py::add_episode`) [source].

### How `valid_at` and `invalid_at` are extracted
- **Prompts:** `prompts/extract_edges.py` (l.40-66 fields, l.127-172 rules), and `extract_nodes_and_edges.py` for the combined path.
- **Reference time:** `REFERENCE_TIME` is the episode's `valid_at`, an ISO-8601 UTC string supplied by the caller. The prompt says "Use REFERENCE_TIME to resolve vague or relative temporal expressions (e.g., 'last week')". For present-tense facts, `valid_at` is set to the episode timestamp. For a termination, `invalid_at` is set to the relevant time [source].
- **Fallback:** if the edge has no timestamps, a separate small-model call (`_extract_edge_timestamps`, l.576, prompt `extract_timestamps`) runs. Parse errors are logged and the timestamp is left null [source].
- **Language:** the temporal prompts are English instructions. I found no Vietnamese-specific handling [source, absence].

### Entity resolution (`node_operations.py`, `dedup_helpers.py`, `prompts/dedupe_nodes.py`)
- **Candidate search:** cosine over name embeddings. `NODE_DEDUP_CANDIDATE_LIMIT=15`, `NODE_DEDUP_COSINE_MIN_SCORE=0.6` (l.64-65), scoped by `group_id` [source].
- **Deterministic pass:** `_resolve_with_similarity`:
  - exact match on a normalized name;
  - fuzzy match by MinHash/LSH over 3-gram shingles, with Jaccard >= 0.9 (`_FUZZY_JACCARD_THRESHOLD`);
  - a low-entropy or very short name guard (`_NAME_ENTROPY_THRESHOLD=1.5`) that defers to the LLM [source].
- **LLM pass:** only for unresolved nodes, batched in flights of `MAX_NODES=30`. Prompt `dedupe_nodes.nodes` returns `{id, name, duplicate_candidate_id | -1}`. It explicitly says "return -1 when unsure" and gives the Java-the-island vs Java-the-language example [source].
- **Aliases:** the code has no alias field. Resolution keeps one node and may update `name` to "the most complete" form; the other surface forms are lost. `grep alias` finds only helper comments [source, absence].

### Episodes as provenance
`EpisodicNode` holds `source`, `source_description`, `content`, `valid_at` and `entity_edges`. `EntityEdge.episodes` is a list of episode UUIDs, and Entity-MENTIONS edges link episodes to nodes. `store_raw_episode_content=False` blanks `content` [source]. An episode is whatever text you pass in, so there is no chunk-level pointer unless you make each chunk an episode.

### Community building (`community_operations.py`)
- **Algorithm:** a custom `label_propagation` over entity neighbours (l.93).
- **Summaries:** pairwise-merged by `summarize_pair` (an LLM call per merge), then a name is generated. `update_community` assigns new nodes incrementally, and `remove_communities` wipes them [source].
- **Cost:** O(communities) LLM calls to build.

### Search (`search/search_config_recipes.py`, `search_utils.py`)
- **Retrieval methods:** edges and nodes can use `bm25`, `cosine_similarity` and `bfs`.
- **Rerankers:** `rrf`, `node_distance`, `episode_mentions`, `mmr`, `cross_encoder`.
- **Recipes:** `COMBINED_HYBRID_SEARCH_RRF`, `..._MMR`, and others.
- **Temporal filters:** `SearchFilters` accepts DNF lists of `DateFilter` on `valid_at`, `invalid_at`, `created_at` and `expired_at` (`search_filters.py:55-65`) [source]. A point-in-time query is therefore a filter, not a traversal.

### Drivers
`GraphProvider = {NEO4J, FALKORDB, KUZU, NEPTUNE}` (`driver/driver.py:59`). The Kuzu extra is marked deprecated ("upstream Kuzu project is unmaintained", `pyproject.toml:31`). `grep -i postgres|psycopg|asyncpg` finds no driver code. The only hits are a sagas prompt and an LLM cache. Per-driver operation ABCs exist (`driver/operations/*_ops.py`), so a SQL backend is conceivable [inferred].

### Ingestion cost per episode
The default `add_episode` path is sequential [source, `graphiti.py:~1175-1230`]:
1. `extract_nodes`: 1 LLM call.
2. Node dedupe: 0 to ceil(unresolved/30) calls.
3. `extract_edges`: 1 call.
4. Per new edge: 1 `resolve_edge` call (skipped on the verbatim fast path), plus 0 or 1 timestamp call, plus 1 per edge with a custom attribute schema.
5. Node summary and attribute calls, batched.
6. Optional community update, per node.

That is roughly 4 + (number of extracted edges) calls per episode. The same-pair search limits the candidate set, but both searches run per edge [inferred from the code]. A combined single-call extraction path exists (`combined_extraction.py`, used on the bulk path) [source]. I did not measure cost.

### Delete (`graphiti.py:1824 remove_episode`)
It deletes only edges whose `episodes[0] == episode.uuid`, and nodes mentioned in exactly one episode. It does not restore edges this episode had invalidated, and it does not remove the episode UUID from edges created by an earlier episode [source].

**Fit:** C2 strong. C3 episode-level only. C4 delete is weak. C5 heavy: about one LLM call per edge. C6 needs a rewrite of the Cypher. C7 has no aliases.

---

## 2. cognee (topoteretes/cognee)
**Tag/date:** v1.6.2, 2026-09-29 (ba3631f). **License:** Apache-2.0. **Activity:** pushed 2026-10-02, about 31k stars, very active.

### Cognify pipeline (`cognee/api/v1/cognify/cognify.py` ~l.592-640) [source]
`classify_documents`, then `extract_chunks_from_documents`, then `extract_graph_and_summarize` (LLM graph extraction plus chunk summary), then `add_data_points` (graph plus vector), then optional `record_provenance`, `detect_contradictions` and `resolve_temporal_contradictions`.

### Entity identity and resolution
- **Deterministic ids:** `Entity.id_for(name)` is `uuid5(OID, "Entity:(name,)")` over `generate_node_name` (lowercase, apostrophes stripped) (`modules/graph/utils/expand_with_nodes_and_edges.py:72-113`, `infrastructure/engine/models/DataPoint.py:177`). The same name across documents is the same node; the id ignores entity type.
- **Same-name conflicts in one chunk** get ordinal ids.
- **Memify consolidation** (`memify_pipelines/consolidate_entities.py`): `detect_entity_duplicates` plus `merge_entity_duplicates`. Parameters: `similarity_threshold=0.85` on name-embedding cosine, `name_match`, `top_k`, `protect_node_types`, `allow_cross_type=False`, `dry_run` [source].
- **Aliases:** no alias model found.

### Temporal
- **Temporal cognify** (`cognify(temporal_cognify=True)`, `tasks/temporal_graph/`): extracts `Event{name, time_from, time_to, location}` with a `Timestamp` model (year required; month, day, hour default to 1 or 0), then builds a graph from the events.
- **Temporal retrieval** (`modules/retrieval/temporal_retriever.py`): an LLM extracts a `QueryInterval` from the question, then `graph_engine.collect_time_ids/collect_events` are called. These exist only in the Neo4j and Ladybug adapters. `postgres_demo/adapter.py` has no `collect_time_ids` [source, absence].
- **Supersession** (`tasks/graph/resolve_temporal_contradictions.py`, `modules/graph/utils/temporal_conflict_resolver.py`): opt-in, only for relationships the caller declares functional (single-valued). The "latest" fact wins by the edge's `updated_at` (ingestion time, not valid time). Losers are tagged `superseded`, `superseded_by`, `supersession_reason`, never deleted [source].
- **LLM contradiction detection** (`tasks/graph/detect_contradictions.py`): writes `contradicts` edges, non-destructive, off by default [source].

### Postgres graph adapter
- **Status:** the module docstring says "DEMO ... not production-ready" and points to Kuzu or Neo4j for production (`infrastructure/databases/graph/postgres_demo/adapter.py:1-9`). It rejects raw Cypher (l.329-336).
- **Schema** (`postgres_demo/tables.py`) [source]:
  - `graph_node(id text PK, name, type, properties jsonb, source_ref_keys text[], source_dataset_ids text[], source_run_ids text[], source_run_refs text[], created_at, updated_at)`.
  - `graph_edge(source_id, target_id, relationship_name)` as the composite PK, with `properties jsonb`, the same four `text[]` columns, and FKs `ON DELETE CASCADE`.
  - `graph_metadata`.
  - Covering indexes on `(source_id) INCLUDE (target_id, relationship_name)` and the reverse, and GIN indexes on the provenance arrays.
- **Traversal:** `get_neighborhood` is a bounded-depth method with chunked ids (`bounded_neighborhood.py`), not a recursive CTE as far as I read [inferred].

### Provenance and delete
- **Chunk link:** chunks link to entities via a `contains` edge with `edge_text` "Document chunk mentions X: desc" (`expand_with_nodes_and_edges.py:115-135`) [source].
- **Delete:** `try_delete_data_by_graph_provenance` calls `unified.delete_by_document`. Source refs are removed with `provenance_after_remove` (pure functions in `provenance/source_ref_state.py`). An artifact is hard-deleted only when no refs remain. This is refcount-by-array-membership [source].
- **Concurrency caveat:** the module docstring says the read-modify-write is not atomic across concurrent stamping [source].

**Fit:** C3 strong. C4 the best delete model found. C6 the schema is a direct template. C2 weak: time lives in event nodes, and supersession is declared and ingestion-time based.

---

## 3. neo4j-graphrag-python
**Tag/date:** 1.22.0, 2026-10-01. **License:** Apache-2.0 for most files, with some PSF-2.0 parts (`LICENSE.txt`; GitHub reports NOASSERTION). **Activity:** pushed 2026-10-01. Neo4j only, by design.

Paths are under `src/neo4j_graphrag/`.
- **`SimpleKGPipeline`** (`experimental/pipeline/kg_builder.py`): loader, splitter, chunk embedder, `LLMEntityRelationExtractor`, `GraphPruning`, `KGWriter`, `EntityResolver`. Defaults: `on_error="IGNORE"` (a failed chunk is skipped), `perform_entity_resolution=True` [source].
- **Schema enforcement:** `components/schema.py` (`GraphSchema`, `NodeType`, `RelationshipType`, `additional_properties`, `Pattern`, `ConstraintType`) plus `components/graph_pruning.py`. The pruner records `PrunedItem(reason)` for removed nodes, relationships and properties. There is also `graph_schema_extraction.py` for LLM schema induction [source].
- **Lexical graph** (`components/lexical_graph.py`, `components/types.py:236-256`): `Document`, `Chunk`, `FROM_DOCUMENT`, `NEXT_CHUNK`, and `FROM_CHUNK` from each entity to its chunk [source].
- **Resolvers** (`components/resolver.py`) [source]:
  - `SinglePropertyExactMatchResolver`: same label plus same property, merged via `apoc.refactor.mergeNodes`.
  - `FuzzyMatchResolver`: rapidfuzz.
  - `SpaCySemanticMatchResolver`: spaCy vectors, default `en_core_web_lg`, threshold 0.8.
  - All are global post-hoc batch jobs over `__Entity__` nodes. The similarity resolvers compare pairs within a label via `combinations` (O(n^2)) and rely on APOC. The spaCy default model is English.
- **Retrievers** (`retrievers/`): `VectorCypherRetriever` and `HybridCypherRetriever` take a user-supplied `retrieval_query` appended after the vector or fulltext hit (`node` is the bound variable). `Text2CypherRetriever` generates Cypher. `ToolsRetriever` lets an LLM choose among retrievers as tools [source].
- **Storage-agnostic ideas:** the chunk-to-entity link, the pruning report, the "retrieval query after seed hit" pattern, and tool-wrapped retrievers.
- **No time model:** no temporal fields anywhere in the resolver or extractor [source, absence].

---

## 4. R2R (SciPhi-AI/R2R)
**Tag/date:** v3.6.5, 2025-06-06. Last commit 2025-11-07 (1915011 is the tag commit). **License:** MIT. **Activity:** stale. About 11 months with no release as of today, 129 open issues [source: GitHub API].

**Postgres schema** (`py/core/providers/database/graphs.py`, `create_tables`) [source]:
- `documents_entities` and `graphs_entities`: `id uuid, name, category, description, parent_id uuid FK, description_embedding vector, chunk_ids uuid[], metadata jsonb, created_at, updated_at`, with indexes on name, parent_id and category.
- `documents_relationships` and `graphs_relationships`: `subject, predicate, object` (text), `subject_id, object_id` (uuid), `weight, description, description_embedding, chunk_ids uuid[], parent_id, metadata`.
- `graphs_communities`: `collection_id, community_id, level, name, summary, findings text[], rating, rating_explanation, description_embedding, UNIQUE(community_id, level, collection_id)`.
- `graphs` holds `collection_id`, `status`, `document_ids uuid[]`.

**Dedupe:** `graph_service.deduplicate_document_entities` (l.1303) calls `merge_duplicate_name_blocks` per document. That is exact-name merging, then one LLM call to rewrite the merged description and re-embed it [source]. There is no cross-document or alias resolution in what I read.

**Communities:** Leiden is done by an external Graspologic HTTP service (`CLUSTERING_SERVICE_URL`, `_call_clustering_service`, graphs.py:2404-2430). A graph is built from relationship rows and clustered outside Postgres [source].

**Fit:** C6 is the closest to our target storage (plain tables with `chunk_ids uuid[]`). C2 has no time model. C9 is poor.

---

## 5. Mem0
**Tag/date:** v2.2.1 (Python), 2026-09-25. Main read at abb81c8 (2026-10-01). **License:** Apache-2.0. **Activity:** very active, about 66k stars.

- **Graph memory is gone on main.** There is no `mem0/graphs` directory. `skills/mem0/references/features.md:54` says "v3 replaces graph memory with built-in entity linking", with entities stored in a parallel `{collection}_entities` vector collection and used as a retrieval boost [docs, but consistent with the missing directory]. Two stale mentions remain (`mem0/AGENTS.md:41,54` and `LLM.md:329` list Neo4j, Memgraph, Kuzu and AGE), which contradict the code layout, so treat them as outdated [source].
- **ADD/UPDATE/DELETE/NONE:** `DEFAULT_UPDATE_MEMORY_PROMPT` (`mem0/configs/prompts.py:176`) still defines the four operations. The default extraction is now `ADDITIVE_EXTRACTION_PROMPT` ("Your sole operation is ADD", l.468). `get_update_memory_messages` is not referenced from `mem0/memory/main.py` [source, grep]. Dedupe on the add path is an MD5 hash of the text (`main.py:1008-1034`) [source].
- **Old graph memory** (v1.0.0, `mem0/memory/graph_memory.py`, fetched from GitHub at that tag): entity nodes matched by embedding cosine >= 0.9 (`_search_source_node`, threshold 0.9), and an LLM `DELETE_RELATIONS_SYSTEM_PROMPT` step that hard-deletes (`DELETE r`) relationships judged contradicted. There are no timestamps, so no history. Stores were Neo4j, Memgraph, Kuzu and Neptune/AGE variants [source].

**Fit:** little for us. The old "LLM decides delete" step loses history, which is wrong for our "return all versions" requirement.

---

## 6. iText2KG / ATLAS (AutoSchemaKG) / KGGen
| | Tag/date | License | Activity |
|---|---|---|---|
| iText2KG (AuvaLab) | v1.1.0, 2026-09-04 | Apache-2.0 | active |
| AutoSchemaKG (HKUST-KnowComp), PyPI `atlas-rag` | 0.0.5.post1, 2026-01-14 (default-branch last commit; GitHub pushed_at 2026-04-29 reflects another ref) | MIT | slowing |
| KGGen (stair-lab) | PyPI 0.4.0 (2025-09-30); last commit 2026-03-24 | `license = "MIT"` in `pyproject.toml`, **no LICENSE file in repo, and GitHub reports none** | slowing |

- **iText2KG ATOM** (`itext2kg/atom/`):
  - Flow: extract atomic facts, then extract relationship quintuples (`t_obs/t_start/t_end` as lists of float epochs, `atomic_facts`, `embeddings`), then merge KGs (`Atom.merge_two_kgs`, `parallel_atomic_merge`, `build_graph_from_different_obs_times`).
  - The relative-time prompt resolves against `observation_date` (`atom/models/schemas.py:180-216`).
  - Merge (`atom/graph_matching/matcher.py`): exact name+label first, then cosine against the global KG (default entity threshold 0.8, relationship 0.7 in `build_graph`). Matching relations are forced to adopt the best-matching name, and matched relations simply extend the timestamp and fact lists. There is **no invalidation**; "newest" is derived from the lists [source].
  - Entity resolution needs no LLM (embeddings only). The graph is held in memory and persisted as JSON/NPZ (`kg_store_dir`) or Neo4j [source].
- **AutoSchemaKG:** three-stage extraction (entity-relation, event-entity, event-relation; `triple_extraction.py:205-207`), then LLM "conceptualization" of nodes, events and relations in batches (`concept_generation.py`). Schema is induced after the fact; a language filter exists (`filter_language_content`). Built for Neo4j/HippoRAG-style retrieval. No temporal or incremental update model found [source, absence].
- **KGGen:** `generate` then `cluster`/`deduplicate`. `steps/_3_deduplicate.py` has `SEMHASH`, `LM_BASED` and `FULL`. `FULL` is SemHash at 0.95, then KNN clustering and a DSPy LLM call per cluster returning `duplicates` plus an `alias` (`utils/llm_deduplicate.py`). `Graph.entity_clusters` and `edge_clusters` retain the alias sets, which is the only first-class alias output among these libraries. The `Graph` model is sets of strings and triples, with no provenance or time, and `aggregate(graphs)` merges whole graphs [source].

---

## Comparison against C1-C10
(S = strong, P = partial, W = weak, - = none; all [source] unless noted)

| | Graphiti 0.30.2 | cognee 1.6.2 | neo4j-graphrag 1.22.0 | R2R 3.6.5 | Mem0 2.2.1 | iText2KG 1.1.0 | AutoSchemaKG | KGGen 0.4.0 |
|---|---|---|---|---|---|---|---|---|
| C1 entity aggregation | S (edges per entity, summaries) | P (entity to chunk edges) | P (Cypher after seed) | P | W | P | P | W |
| C2 time, validity, conflicts | S (bi-temporal, invalidate) | P (events; opt-in supersede, ingestion-time) | - | - | - | P (t_start/t_end lists, no invalidation) | - | - |
| C3 provenance | P (episode list) | S (arrays, run refs, chunk edge) | S (FROM_CHUNK, FROM_DOCUMENT) | P (`chunk_ids[]`) | W | P (atomic_facts) | W | - |
| C4 incremental add/edit/delete | P add; W delete | S delete by source ref | W (global resolver reruns) | W | W | P merge only | W | W |
| C5 LLM cost / latency | W (about 1 call per edge) | P | P | P | S (cheap) | P | W (3 stages plus concepts) | P |
| C6 relational fit | W (Cypher; no SQL driver) | S (demo schema exists) | W | S (Postgres tables) | n/a | W | W | W |
| C7 multilingual / aliases | W (English prompts, no alias field) | W (no alias model) | W (spaCy English default) | W | W | P (embedding match; model-dependent [inferred]) | P (language filter) | P (alias output) |
| C8 context-only retrieval | S (`search_` returns edges, nodes, episodes) | P (completion-oriented; triplet context) | S (retrievers return context) | P | P | - | - | P |
| C9 license / maintenance | Apache, active | Apache, active | Apache plus PSF, active | MIT, stale | Apache, active | Apache, active | MIT, slowing | MIT declared, no LICENSE file |
| C10 vs vector RAG | no benchmark in repo read [docs claim only] | not evaluated here | not evaluated here | - | - | - | - | - |

C10: I read no benchmark data in these repos, so I make no claim.

## What we should borrow
| Idea | Library | File path | Why |
|---|---|---|---|
| Bi-temporal claim columns (`valid_at`, `invalid_at`, `expired_at`, `created_at`) | Graphiti | `graphiti_core/edges.py` (EntityEdge), `search/search_filters.py:55-65` | Maps to plain columns. Point-in-time and "all versions" are `WHERE` clauses. |
| Deterministic interval-contradiction rule after the LLM picks candidates | Graphiti | `edge_operations.py:538-573, 780-800` | Date logic stays testable code. It also handles out-of-order ingestion by expiring the new edge. |
| "Never mark as duplicate if numbers, dates or qualifiers differ" resolve prompt, plus duplicate vs contradicted as two separate outputs | Graphiti | `prompts/dedupe_edges.py` | Fits "figures stay verbatim". Needs adapting: our versions of a definition are meant to be kept, not expired. |
| Staged entity resolution: embedding candidates, then exact, then MinHash/Jaccard 0.9 with an entropy guard, then LLM only for the residue; return -1 when unsure | Graphiti | `dedup_helpers.py`, `node_operations.py:627-710` | Cuts LLM calls. The entropy guard avoids merging short names. Needs a Vietnamese check (diacritics folding) [inferred]. |
| Array provenance columns plus delete by array-membership, hard-delete when the array empties | cognee | `postgres_demo/tables.py`, `provenance/source_ref_state.py` | Direct answer to document edit and delete. Needs an atomic upsert (their docstring admits the race). |
| Opt-in "functional relationship" declaration before superseding | cognee | `tasks/graph/resolve_temporal_contradictions.py` | Avoids collapsing many-valued relations. Rank by valid time, not `updated_at`. |
| Lexical graph: Document, Chunk, `FROM_CHUNK`, `NEXT_CHUNK` | neo4j-graphrag | `components/lexical_graph.py` | Three plain tables. |
| Prune extraction against a schema and keep a pruned-items report | neo4j-graphrag | `components/graph_pruning.py` | Audit trail for dropped items. |
| Retrieval as a seed hit followed by a parameterized expansion | neo4j-graphrag | `retrievers/vector.py` (VectorCypher) | Re-implement as seed query plus a recursive CTE. |
| Relational layout with `chunk_ids uuid[]` on entities and relationships | R2R | `core/providers/database/graphs.py` | Compact, indexed schema. Add provenance and validity columns. |
| Cluster-then-LLM alias output (`duplicates`, `alias`) | KGGen | `utils/llm_deduplicate.py` | Gives an alias table for free. |
| Observation time kept separate from valid-from and valid-to | iText2KG | `atom/models/relationship.py` | Matches "state at a past date" plus "when we learned it". |

## Pitfalls
| Pitfall | Where | Consequence |
|---|---|---|
| `remove_episode` ignores edges this episode invalidated, and removes only `episodes[0]` creations | Graphiti `graphiti.py:1824` | After a document edit or delete, old facts stay expired and stale episode ids remain. Our design needs a recompute or restore step. [source] |
| An invalidation decision depends on LLM recall over the top-K hybrid candidates | Graphiti `resolve_extracted_edge` | A missed contradiction leaves two "current" facts. Cap and log it. [inferred] |
| Graphiti expires older facts. We must keep all versions and flag the newest | Graphiti vs our C2 | Use "superseded_by" and a validity interval rather than hiding. Do not copy `expired_at` semantics blindly. [inferred] |
| Entity id = hash of lowercased name, type ignored | cognee `DataPoint.id_for` | Homonyms across documents merge silently; different spellings do not. [source] |
| Supersession ranked by `updated_at` (ingestion time) | cognee `temporal_conflict_resolver.py` | A re-ingested old document looks "newest". [source] |
| Postgres adapter is demo-only and lacks the temporal retriever | cognee | Do not depend on it as a design proof. [source] |
| Post-hoc, global, O(n^2) resolvers needing APOC | neo4j-graphrag `resolver.py` | Rerun cost grows with the whole graph, and merges are irreversible. [source] |
| Relations merged by embedding to best-match name | iText2KG `matcher.py` | Can fuse distinct relations ("owns" vs "approves"). [source / inferred] |
| LLM `DELETE` of contradicted relations | Mem0 v1.0.0 graph | Destroys history. [source] |
| Stale repo docs vs code | Mem0 `AGENTS.md` vs tree | Trust code. [source] |
| Stale project | R2R (no release since 2025-06) | Treat as design reference only. [source] |
| License ambiguity | KGGen (no LICENSE file) | Do not port code. [source] |
| English-centric prompts and spaCy default | Graphiti, neo4j-graphrag | Vietnamese needs our own prompts and an embedding model tested on Vietnamese. [inferred] |

## Ranked verdict for relational-table storage
1. **Bi-temporal claim table with deterministic interval resolution (Graphiti pattern), adapted to keep all versions.** Rows carry `valid_from`, `valid_to`, `recorded_at`, `superseded_by`. An LLM only nominates candidates and flags conflicts; code sets the intervals. This answers C2 and the "flag the newest" question. It is portable because it uses only columns and range predicates.
2. **Array-valued provenance on every row, with refcount-style delete (cognee pattern).** Claims, entities and relations hold source-ref arrays (`chunk_id`, `document_id`, `run_id`) with GIN indexes. Editing a document removes its refs and hard-deletes only orphaned rows. This is the only evidence-backed answer to C4 in these libraries. Make the update atomic, since cognee documents a race. On Delta, the equivalent is MERGE-based ref arrays or a separate link table [inferred].
3. **Staged entity resolution with an alias table (Graphiti staging plus KGGen alias output).** Normalize, then run candidate retrieval, then deterministic similarity, then LLM for the residue only, and persist `entity_alias(entity_id, surface_form, source_ref)` instead of overwriting names. Prefer reversible merges (a `merged_into` pointer) over Neo4j-style `mergeNodes`.
4. **Lexical graph (Document, Chunk, entity-to-chunk links) as the backbone of provenance (neo4j-graphrag pattern).** It is the same idea as ranking 2 and costs little.
5. **Do not adopt:** LLM-decided delete (Mem0), name-hash identity (cognee), ingestion-time recency (cognee), and global post-hoc merges.

## Gaps
- No LLM-call counts were measured. Cost figures are from reading the call graph.
- Not read: Graphiti `driver/*/operations` bodies, `bulk_utils.py`, cognee `delete_by_document` planner internals, and neo4j-graphrag `KGWriter` and `Text2CypherRetriever` internals. R2R extraction prompts and the AutoSchemaKG concept prompt text were also not read.
- I did not verify claimed benchmark results (C10) for any library.
- The session's clone directory included pre-existing clones (for example `mem0` at main, no tags); the Mem0 version pin relies on the GitHub release list (v2.2.1) plus main at abb81c8.
- AutoSchemaKG: GitHub `pushed_at` (2026-04-29) is later than the default-branch last commit (2026-01-14); I did not identify the newer ref.

## Sources (all read this session)
- getzep/graphiti @ v0.30.2 (eaa4128, 2026-09-08)
- topoteretes/cognee @ v1.6.2 (ba3631f, 2026-09-29)
- neo4j/neo4j-graphrag-python @ 1.22.0
- SciPhi-AI/R2R @ v3.6.5 (1915011); GitHub API for the last commit
- mem0ai/mem0 @ main abb81c8 (release list v2.2.1); `mem0/memory/graph_memory.py` and `mem0/graphs/utils.py` at tag v1.0.0 via the GitHub API
- AuvaLab/itext2kg @ v1.1.0 (840aba2)
- HKUST-KnowComp/AutoSchemaKG @ default branch d0a1666; PyPI `atlas-rag` 0.0.5.post1
- stair-lab/kg-gen @ default branch 6259b4c; PyPI `kg-gen` 0.4.0
