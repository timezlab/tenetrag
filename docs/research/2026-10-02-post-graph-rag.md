# post-graph-rag: code-level report

> **Snapshot, 2026-10-02 — not maintained.** Round 2 code-research lane on
> post-graph-rag v1.15.2 and its storage layer post-graph v1.8.0. The
> maintained, re-verified summary is in
> [graphrag-engines.md](../reference/graphrag-engines.md); where they differ,
> the maintained doc wins. Local paths were removed before publishing.
>
> **Errata:** none found.

Date 2026-10-02. Labels: [source] read in code, [paper] README/CHANGELOG/arXiv abstract only, [inferred] mine.
Read from shallow clones of post-graph-rag and post-graph (not kept). Nothing installed or run.

## Existence/version
- arXiv 2608.24921, "post-graph-rag: A PostgreSQL-Native Bi-Temporal Graph RAG Engine with Temporal Grounding at Synthesis", Chandan Rajah; v1 2026-08-14, v3 2026-09-05 [paper, arXiv abs page]. I did not read the full PDF/HTML body.
- Repo https://github.com/crajah/post-graph-rag, HEAD 50f7478 (2026-09-30), tag v1.15.2 (pyproject 1.15.2). everydev.ai lists 1.13.0, so the listing is stale. [source]
- The storage layer is a separate repo, https://github.com/crajah/post-graph (HEAD b8d67f8, tag v1.8.0), same author, Apache-2.0, 5 stars. All DDL and the recursive CTE live there, not in post-graph-rag. [source]

## Schema
Not "two tables". The engine uses a generic JSONB property-graph layer (post-graph) that creates vertex and edge tables on demand. [source]
- Vertex tables (graph_store.py:23 VERTEX_TABLES): `documents` (actually one row per CHUNK), `entities`, `communities`.
- Edge tables (graph_store.py:101-125): `relations` (entity to entity), `doc_mentions` (chunk to entity), `community_members`, `community_children`. Optional `retrieval_events`.
- Generic vertex DDL, post-graph/post_graph/client_asyncpg.py:~492-549:
  `realm TEXT NOT NULL, id BIGSERIAL, space VARCHAR(255) NOT NULL DEFAULT 'default', uuid UUID DEFAULT gen_random_uuid(), fqid TEXT GENERATED ALWAYS AS (realm||'/'||table||'/'||id) STORED, payload JSONB NOT NULL DEFAULT '{}', created_at, updated_at, PRIMARY KEY (realm,id)`.
  Indexes: (realm,space), UNIQUE(uuid), GIN(payload), HNSW on `embedding vector(dim)` with `vector_cosine_ops` and default m/ef_construction (no params set). Each table also gets an `_audit` shadow table and an append-only `_data` table (data_id, realm, id FK ON DELETE CASCADE, payload, timestamp), which also carries a vector column and HNSW index.
- Edge DDL (client_asyncpg.py:~648-723): same columns plus `from_id BIGINT, to_id BIGINT, relation_type TEXT NOT NULL`, FKs (realm,from_id)/(realm,to_id) ON DELETE CASCADE; index (realm,to_id), GIN(payload); `relations` gets a vector column only if `embed_relations`.
- Fact fields live INSIDE edge `payload` JSON, not columns: description, sources[] (chunk ids), weight, negated, confidence, valid_from, valid_to, t_created, t_expired, superseded_by, dormant_since, dormant_reason (graph_store.py:683-800).
- Extra indexes: expression indexes on payload t_created, t_expired, dormant_since (graph_store.py:149-158); GIN on payload->'sources' (:176); GIN FTS over to_tsvector('english', relation_type||' '||description...) (:838); UNIQUE (realm,space,lower(payload->>'name')) on entities (:227).
- post-graph promotes `valid_from/valid_to` into generated text columns `pt_valid_from/pt_valid_to` (YYYY-MM-DD padded) with indexes (post-graph/promoted.py:37). Dates are text, not DATE or tstzrange. [source]
- Embedding dim default 1536 (config.py:58); the column is fixed at table creation.
- Multi-tenancy by `realm` (schema) and `space`.

## Temporal model
- Valid time: `valid_from`/`valid_to` in relation payload, extracted by the LLM only when the text states a period. The prompt says never default to the document date (extractor.py:390-398). Null/null means "always valid". [source]
- Transaction time: `t_created` (set on first insert, preserved on re-observation) and `t_expired` (set when superseded) (graph_store.py:760-790, :970). [source]
- Supersession is rules first, optional LLM second [source]:
  1. `exclusive_predicate_groups` (config.py:338, default empty): predicates that cannot both hold between the SAME (from,to) pair. A newer edge closes older ones: sets `superseded_by` and `t_expired` (graph_store.py:931-988). "Newer" means document processing order, not valid time or document date (docstring says this explicitly).
  2. `contradiction_detection` (config.py:~195, OFF by default, env RAG_CONTRADICTION_DETECTION). Per new relation, up to N candidate current relations of the same subject (same from_id, newest id first) go to the extraction-role LLM with CONTRADICTION_SYSTEM_PROMPT (extractor.py:164-186). It returns {"contradicted_ids": [...]}. It only runs when the declarative pass found nothing. Failure retracts nothing (extractor.py:704-750). Marked via `mark_superseded` (graph_store.py:1033).
  3. Supersession does not touch `valid_to`. The paper's "supersession closes the fact" is `t_expired` plus `superseded_by`. [inferred from code]
- As-of SQL: in the recursive walk, `((pt_valid_from IS NULL OR pt_valid_from <= $at) AND (pt_valid_to IS NULL OR pt_valid_to >= $at))` plus `superseded_by IS NULL` (post-graph client_asyncpg.py:2930-2957, `_edge_filter_sql`). Belief-time as-of (`as_believed_at`) is NOT in SQL: it is a Python string comparison in `_known_at` (engine.py:~53, applied in `_filter_temporal` :1450-1475). The valid-time as-of (`_valid_at`) also reruns in Python for the non-traversal channels. [source]
- Default query excludes superseded edges (`include_superseded` False, config.py:351). It does NOT return "all versions, flag newest". Only validity is rendered as `[valid X to Y]` / `[from X]` in the synthesis prompt (engine.py:1762-1770), and triples are sorted newest-asserted first within each hop. [source]

## Predicate vocabulary
- `predicate_vocabulary: List[str]` (env RAG_PREDICATE_VOCABULARY, comma list) and `predicate_aliases: Dict` (config.py:284-288). [source]
- It is a SOFT preference: the prompt says "PREFER these predicates ... Only invent a new predicate when none fits" (extractor.py:378-386). Post-hoc `_canonical_predicate` (extractor.py:626-636): normalise (lowercase, underscores, strip tense prefixes like was_/has_), apply alias map, then snap to a vocabulary entry only on prefix match (`p.startswith(c) or c.startswith(p)`). An out-of-vocabulary predicate that does not prefix-match is KEPT as-is. Nothing is rejected for being out of vocabulary. config.py:36 claims "94% predicate-vocabulary adherence" [paper/comment].
- Hard rejections: VAGUE_PREDICATES (relates_to, associated_with, ...), self-loops, pronominal or phrase entities, bare quantities, low confidence (extractor.py:664-690).
- Relation uniqueness is (from, relation_type, to); a repeat adds the chunk to `sources` and raises `weight` (graph_store.py:683).

## Extraction
- One structured-output call per CHUNK (pydantic ExtractionResult: entities with name/type/description/aliases; triples with subject/predicate/object/description/negated/confidence/valid_from/valid_to), plus `gleaning_passes` (default 1) extra "what was missed" call (extractor.py:246, config.py:244). So about 2 extraction calls per chunk, plus embeddings (chunk, entities, relations; batched 64). Optional contradiction call per new relation with candidates, optional keyword/decompose calls at query time. [source]
- Prompt: BASE_SYSTEM_PROMPT (extractor.py ~190-244), tuned for filings and encyclopedias. The LongMemEval README says a separate "conversational" prompt was needed and rewrote the rules (evaluation/longmemeval/README.md). Caller-supplied `extraction_fn` is supported (replace or merge). [source]
- Context: previously discovered canonical entity names (cap 40) are fed back for coreference, at batch granularity. Chunking is 2000 chars with 200 overlap, character-based (config.py:~290).

## Resolution
- Exact case-insensitive name match, then alias match by `jsonb_array_elements_text` scan of the aliases array (graph_store.py:551-577, :579-668). The longer name becomes canonical, the other becomes an alias. LLM-supplied aliases only. No embedding-based merge, no fuzzy match, no transliteration/diacritic folding, no multilingual handling. FTS config is hard-coded 'english'. Prompts are English. Vietnamese support is untested. [source]
- The alias lookup is a seq-scan-style per-entity lookup (no index on aliases). [inferred]
- Entity uniqueness is per (realm, space), so per-company spaces isolate.

## k-hop SQL
- `get_neighborhood` (graph_store.py:1666) calls post-graph `traverse` (client_asyncpg.py:~3053-3110). It is a `WITH RECURSIVE graph_traversal` with columns current_id, depth, path[], edge_path[], edge_ids[]; recursive step is `CROSS JOIN LATERAL (SELECT ... FROM relations WHERE from_id = t.current_id <filters>)`, guard `t.depth < $4 AND NOT (next = ANY(t.path))`. [source]
- Cycle handling: per-path array membership test only. No global visited set, so a node reachable by many paths is re-expanded for each path. [source]
- Fan-out limits: NONE in SQL. `max_hops` default 2, direction hard-coded "out". After the walk, Python sorts by depth and truncates to `max_relation_edges` (default 200) per seed entity (graph_store.py:1716-1732). So the cap bounds output, not work. [source]
- Filters applied inside the walk: relation_types, space, as-of validity, `superseded_by IS NULL`, `dormant_since IS NULL`.
- Seeds: top_k entities by embedding (`<=>`) over `entities`.
- Fusion (engine.py:1034-1215): three channels, (a) graph traversal, (b) relation-embedding ANN search (needs embed_relations), (c) relation FTS (ts_rank, OR-ed terms). Default `merge_strategy="rrf"`, k=60 (engine.py:1513-1520, config.py:140). Optional node-distance rerank and MMR (both default off). Plus chunk vector search and "chunks mentioning matched entities" expansion. Optional LLM subquery decomposition (off by default).

## Provenance and delete
- Chunk vertex (in `documents`) has payload with text, document, source, doc_key, content_hash, paragraph. Entity to chunk via `doc_mentions` edges. Relation to chunk via `payload.sources` = JSON array of chunk ids, with NO FK, so referential integrity is by convention. The chunk to document link is the `doc_key` string; there is no document table. [source]
- Delete (graph_store.py:282-322 `delete_document_chunks`): hard-deletes chunk rows and their mentions, then set-based UPDATE removes chunk ids from relations' `sources` and recomputes weight; relations left with no sources become `dormant_since`/`dormant_reason`, not deleted; entities with no remaining mentions go dormant; orphan sweep and revival exist (graph_store.py:376-481). Dormant rows are filtered from retrieval. [source]
- Edit: `index_text` computes doc_key, compares ordered chunk content hashes, skips if unchanged, else delete-then-reindex all chunks (engine.py:~405-420). No chunk-level diff. [source]
- GAP: if a deleted document had superseded older facts, I found no code that un-supersedes them. `superseded_by` persists and `_revive_orphaned_relations` handles dormancy only. [inferred from reading, not exhaustively verified]

## Output format
`query_data` returns {status, message, data:{entities[{entity_name,entity_type,description}], relationships[{src_id,tgt_id,edge_id,relation_type,description,weight,negated,confidence,valid_from,valid_to,t_created,t_expired,superseded_by,asserted_at,hops}], chunks[{chunk_id,content,metadata}], references[{reference_id,document}], communities[]}, metadata{query_mode,keywords,processing_info}} (engine.py:1034-1272, `_format_triple` :1388). `query()` adds LLM synthesis with a rendered text context ("(A) --[NOT pred (weight=n)]--> (B) [valid X to Y]: desc"). Relations carry chunk ids only indirectly; chunk to document via metadata. [source]

## Benchmarks
- evaluation/ (not in test suite, needs live LLM): longmemeval/{run.py, run_graphiti.py, reader_sweep.py, ablate_retrieval.py, regrade_official.py, fetch.sh}, ectqa/{run.py, baseline_lightrag.py, baseline_graphrag.py, native_score.py, metric.py, fetch.sh, many results_*.json}. [source]
- Baselines that run in-repo: Graphiti (LongMemEval, needs external graphiti with a post-graph driver), LightRAG and GraphRAG (ECT-QA, install separately). I did not run them. README's Zep/Graphiti LongMemEval numbers and TG-RAG 0.599 are PUBLISHED figures from other papers, not reruns. [source+paper]
- Headline claims (README): LongMemEval 94.0% (500 q, gemini-3.6-flash, 3-model judge panel, 1 question excluded); ECT-QA 0.807 on a 78-question, 6-company slice with own re-implemented judge rubric. evaluation/longmemeval/README.md itself reports a 20-instance 75% intermediate result. Self-reported, single author, not independently replicated. [paper]

## Maturity
- License Apache-2.0 (GitHub SPDX, LICENSE file, pyproject). Stars 11, forks 1, contributors 1 (Chandan Rajah), 116 commits, created 2026-07-25, last push 2026-09-30, about 12 tags (v1.15.2). 6 issues/PRs. [source, gh api]
- Tests: 33 test files, about 561 test functions; CI (.github/workflows/ci.yml) runs pgvector/pg16 service, python 3.9 and 3.13 matrix per file (comment says 3.11). Tests hit a real Postgres. [source]
- Status "Beta" classifier. Single-author, 2-month-old research-plus-library artifact with unusually careful docstrings/changelog but no community.

## What we should borrow
| idea | file | why |
|---|---|---|
| Two-axis time on each fact (valid_from/valid_to vs t_created/t_expired), absent validity = always valid | post_graph_rag/graph_store.py:683-800 | maps directly to Delta columns; cheap, auditable |
| Supersession is non-destructive (superseded_by + t_expired); deterministic exclusive-groups first, conservative LLM fallback that fails to "retract nothing" | graph_store.py:931; extractor.py:164-186,704-750 | right fail-closed stance; we should instead key "newer" on document date |
| Provenance as set of chunk ids with weight = distinct chunks; withdraw-on-delete plus dormancy instead of hard delete | graph_store.py:282-481 | gives incremental delete/edit semantics we need |
| Content-hash skip then replace-on-edit | engine.py:405-420 | simple incremental indexing |
| Filter supersession/dormancy/as-of INSIDE the recursive walk, not after | graph_store.py:1666; post-graph _edge_filter_sql | avoids laundering paths through retired edges |
| Three-channel retrieval (graph walk, relation embedding, relation FTS) fused by RRF | engine.py:1115-1200,1513 | rare identifiers and generic-name entities |
| Validity rendered as text in the context | engine.py:1762 | helps the reader order and subtract dates |
| Extraction validation gates (vague predicates, bare quantities, pronouns, 200-char names) | extractor.py:60-110,640-690 | clean graph; the quantity rule is for financial text |
| Promoted generated date columns for the as-of filter | post-graph promoted.py | index the hot temporal predicate |

## Pitfalls / doubts
- "Controlled vocabulary" is soft: out-of-vocabulary predicates survive; only prefix snapping and aliases. Not a closed vocabulary.
- "Conflicting versions returned with dates and flag newest" is NOT implemented. Default drops superseded facts; include_superseded=True returns them unflagged apart from `superseded_by` in the raw payload.
- Supersession keyed to ingestion order, not document date. Out-of-order loading corrupts "newest". Contradiction LLM is off by default, and by the engine's own benchmarks it is an ablation (ablation_contradiction.json), so the headline results likely do not depend on it. I did not check numbers. [inferred]
- Fan-out is capped only after the recursive CTE materializes; cycle check is per-path; dense graphs at 3 hops can blow up. Schema is JSONB-heavy and not portable to Delta as-is. Dates are text.
- No multilingual story: English FTS config, English prompts, alias exact match, no embedding-based entity merge.
- sources[] without FK; deleting a doc that superseded others leaves older facts retired (unverified).
- Paper's own comparisons mix published and re-run numbers, own judge, 78-question slice, one question excluded. Treat 94%/0.807 as self-reported.
- Depends on author's post-graph package (v1.8.0, 5 stars): bus-factor 1 across two repos.

## Verdict
This is a single-author, Apache-2.0, two-month-old Beta library. Its design is the closest analogue to what we need: relational triples with provenance, a bi-temporal pair of time axes, non-destructive supersession, delete-by-withdrawal and RRF over graph, relation-vector and FTS channels. The code is careful and well commented, but several headline claims are softer than the marketing: the predicate vocabulary is a preference rather than a gate, supersession is by ingest order, and "all versions with newest flagged" is not built. Borrow the semantics and the delete/dormancy logic; do not borrow its JSONB-in-one-table layout, its unbounded recursive CTE, or its English-only resolution. Use proper columns (valid_from/valid_to, ingest time, source chunk FK/bridge table) and key supersession on document date.
