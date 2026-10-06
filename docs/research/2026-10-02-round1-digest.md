# Research digest — databricks-graphrag brainstorm (2026-10-02)

> **Snapshot, 2026-10-02 — not maintained.** Round 1 synthesis of the storage,
> AI-integration and engine lanes plus the fact-check, written during the
> session to survive context compaction. The maintained, re-verified summary
> is in [databricks-platform.md](../reference/databricks-platform.md) and
> [graphrag-engines.md](../reference/graphrag-engines.md); where they differ,
> the maintained doc wins. Adopter-specific lines were removed before
> publishing.
>
> **Errata:** none found.

Full lane reports: [2026-10-02-databricks-storage-auth.md](2026-10-02-databricks-storage-auth.md), [2026-10-02-databricks-ai-integrations.md](2026-10-02-databricks-ai-integrations.md),
[2026-10-02-core-engines-source.md](2026-10-02-core-engines-source.md) and [2026-10-02-factcheck-lakebase-obo.md](2026-10-02-factcheck-lakebase-obo.md).

## Storage & auth (lane 1)
- Lakebase = one product now (Autoscaling: projects/branches/endpoints, scale-to-zero, read replicas).
  PG 16/17(default)/18. Azure southeastasia GA 2026-03-02; AWS ap-southeast-1 available.
- Extensions: pgvector (HNSW/ivfflat), pg_trgm, unaccent, ltree, pgrouting, PostGIS, pg_graphql. NO Apache AGE.
  lakebase_vector (ANN) + lakebase_text (BM25) GA 2026-09-18. -> graph = node/edge tables + recursive CTE.
- Postgres auth: 1h OAuth token as password, minted per connection:
  w.postgres.generate_database_credential(endpoint=..., ttl 300-3600s). Roles via databricks_create_role.
  Native passwords off by default for new projects since 2026-05-21.
- OBO -> Lakebase ONLY via Databricks Apps user authorization (scope `postgres`; x-forwarded-access-token;
  per-user Postgres role must exist; RLS works; databricks_superuser bypasses RLS).
  Model Serving OBO: does NOT support Lakebase or Volumes (supports AI Search, SQL wh, Genie, UC conn, MCP).
  Databricks recommends Apps for new agents. Apps user-auth status: Preview vs GA unclear.
- Synced tables Delta->Lakebase (snapshot/triggered/continuous, min 15s; RLS not configurable on synced tables).
  Lakebase->Delta CDF: Public Preview.
- Volumes: no append / random writes (write local then copy). Workspace files: 500MB cap, executors can't write,
  code/config only. -> files are snapshot/artifact stores, not live graph stores.
- Recursive CTE GA in DBSQL (DBR 17.0+, default depth 100). GraphFrames classic DBR ML only.
- Compliance: PCI-DSS/HITRUST on Azure + AWS Lakebase regions (compliance security profile workspaces);
  SOC2 T2; CMK all regions.

## AI services & prior art (lane 2)
- No mature Databricks-native GraphRAG: official demo uses external Neo4j (graphrag-demo, stale);
  OntoBricks (Labs, structured-only; backends Lakebase/Delta triples/Neo4j); one 3-commit MS GraphRAG sample
  (notes FMAPI Llama fails GraphRAG queries). Genie Ontology = closed context layer for Genie.
- Embeddings: only databricks-qwen3-embedding-0-6b multilingual (Public Preview); GTE/BGE English-only.
- Cross-geo: Azure southeastasia routes FMAPI, ai_parse_document v2, ai_extract v2, Knowledge Assistant,
  Supervisor cross-geo (Asia geo: JP/KR/SG). In-region: AI Search, ai_query batch, Apps, serverless, Lakebase.
  Cross-geo on by default outside US/EU unless compliance security profile.
- ai_parse_document GA: PDF/images/DOC(X)/PPT(X), NO XLSX; <=500 pages/100MB; "non-optimal" non-Latin.
- Structured outputs: <=64 keys, no $ref/anyOf/oneOf/allOf/pattern -> Pydantic schema flattening shim needed.
- Renames: Vector Search->AI Search (databricks.ai_search); AI Gateway->Unity AI Gateway;
  Asset Bundles->Declarative Automation Bundles; Genie spaces->Genie Agents.
- AI Search: no row/column-level permissions -> filter-based ACLs. Hybrid ANN+BM25, reranker Beta.
- MLflow 3.16.1; UC traces >=3.14; Prompt Registry on Databricks = Beta; mlflow.genai.evaluate.
- Serving: Apps + ResponsesAgent + custom MCP recommended. Agent Bricks Supervisor can call MCP/UC fn/Apps
  agents -> plug-in point for a GraphRAG retriever. Knowledge Assistant GA but sources = Volumes + AI Search only.
- Serverless env v6 Python 3.12.3; wheels from UC Volumes; aarch64 or x86_64.

## Engines (lane 3, pinned tags; verified locally where marked)
- microsoft/graphrag v3.2.0 (2026-09-24, MIT). README: "largely in maintenance mode... won't be accepting new
  PRs or implementing new features" [verified locally]. Storage: Storage/TableProvider/VectorStore ABCs + register_*;
  graph = parquet tables; query API takes DataFrames (storage-decoupled). Prompts = file-path config keys + auto-tune.
  LLM via LiteLLM, static api_key (token refresh needs custom class). Incremental update: merge by exact title,
  NO delete — InputDelta.deleted_inputs never consumed [verified locally]. Only engine with communities/reports/claims
  (claims have start/end dates). Global/DRIFT need JSON output.
- HKUDS/LightRAG v1.5.7 (2026-09-02, MIT, very active). 4 store ABCs (KV/Vector/Graph/DocStatus) chosen by name
  via STORAGES dict. PGTableGraphStorage = plain PG tables, no AGE/pgvector (added 2026-06-22) [verified locally];
  PGGraphStorage needs AGE; PGVectorStorage needs pgvector. Static PG password (asyncpg accepts callable -> small patch).
  Modes: local/global/hybrid/naive/mix/bypass (closed Literal, no custom-mode hook); aquery_data returns context
  without generation; pluggable reranker. Prompts: PROMPTS dict, addon_params, YAML entity profiles, per-query prompt.
  LLM = any async callable (fresh client per call -> token refresh easy). adelete_by_doc_id cascades + rebuilds.
  No communities/reports/claims; edges undirected; created_at only.
- run-llama/llama_index v0.14.25 (MIT). PropertyGraphStore ABC (8 methods). No PG graph store; TiDB store
  (2 SQL tables + recursive CTE) is the template for a Lakebase store. Kuzu store removed. Deletion can't cascade.
  Custom retrievers via CustomPGRetriever. llama-index-llms-databricks static key. Communities only in cookbooks.
- Canonical schema feasible with loss: export cheap, import lossy. Three incompatibilities:
  (1) entity/relation semantics (case rules, directed/typed vs undirected/keywords),
  (2) derived layers & lifecycle (only GR has communities but can't delete; LR rebuilds; LI can't cascade)
      -> SDK-owned chunk->entity/relation evidence table + capability flags,
  (3) storage/query binding differs; retrieval modes not swappable ("global" means different things)
      -> canonical store exposes neutral primitives (vector search, k-hop, reports) + per-engine adapters + LLM-auth shim.
- Secondary: graphiti v0.30.2 (temporal bi-temporal edges; no Postgres driver); KAG slow; fast-graphrag stale;
  HippoRAG 2 alpha; neo4j-graphrag Neo4j-only; cognee v1.6.2 (postgres_demo adapter, provenance arrays model).
  Kuzu archived (fork LadybugDB active). DuckPGQ: no engine backend found.

## Fact-check results (2026-10-02)
1. No AGE / pgvector HNSW: CONFIRMED high (absent from official ext table on Azure/AWS/GCP; superuser features disallowed).
   GCP Lakebase is Beta.
2. OBO -> Lakebase via Apps `postgres` scope, per-user role, RLS: CONFIRMED (mechanism high), DESIGN CAVEATS:
   - Fail-open traps: default SP pool bypasses RLS as table owner; AppKit asUser() dev-mode falls back to SP pool;
     agent get_user_workspace_client() falls back to SP "without raising" -> SDK MUST fail closed.
   - Max 500 Postgres roles per branch -> per-user roles cap ~500 users. Group roles lose per-user current_user.
   - Built-in PgBouncer doesn't support OAuth; per-user pools connect directly (max 3, idle 30s, 1h tokens).
   - `postgres` scope is broad (project/branch/role APIs).
3. Model Serving OBO excludes Lakebase + Volumes: CONFIRMED high (closed resource list; Volumes named explicitly).
   Model Serving OBO = Public Preview, admin-enabled. Databricks recommends Apps for new agents.
4. Apps user authorization: still Public Preview (no GA note Oct 2025-Sep 2026); auto-enable for compliance-profile
   workspaces scheduled "late Sep 2026", still future tense on 2026-10-01.
=> Implication: per-user DB roles don't scale past the 500-role cap; likely need app-level ACL filtering (identity from OBO token
   -> groups -> doc ACL filter / RLS keyed on session setting, run as non-owner SP role), fail-closed.

## Open verification
- Untested end-to-end: LightRAG PGTable on Lakebase; GraphRAG on /Volumes FUSE; LiteLLM databricks provider refresh.
