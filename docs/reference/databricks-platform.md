# Databricks platform facts this project depends on

**Verified:** 2026-10-02 against official docs (sources inline). Preview/Beta
items change fast — re-check the linked page before building on one, and
update this file in the same PR when a fact changes.
Raw lane reports (snapshots, not maintained):
[storage and auth](../research/2026-10-02-databricks-storage-auth.md),
[AI integrations](../research/2026-10-02-databricks-ai-integrations.md),
[fact-check](../research/2026-10-02-factcheck-lakebase-obo.md),
[round 1 digest](../research/2026-10-02-round1-digest.md).

Labels: **[primary]** official doc or release note · **[inferred]** our
reasoning from primary facts · **[unverified]** could not confirm.

## Lakebase (managed Postgres)

| Fact | Detail | Source |
|---|---|---|
| Product shape | One product, "Autoscaling": projects → branches → endpoints; scale-to-zero, read replicas, branching. Provisioned instances closed to new databases since 2026-03-12. | [primary] [release notes](https://learn.microsoft.com/en-us/azure/databricks/release-notes/lakebase/) |
| Postgres versions | 16, 17 (default), 18 | [primary] [manage projects](https://docs.databricks.com/aws/en/oltp/projects/manage-projects) |
| Extensions | `vector` (pgvector, ivfflat + hnsw), `pg_trgm`, `unaccent`, `ltree`, `pgrouting`, PostGIS, `pg_graphql`; `lakebase_vector` / `lakebase_text` (Lakebase Search, GA 2026-09-18, cannot be disabled once enabled). **No Apache AGE** — absent from the official table on Azure, AWS and GCP. | [primary] [extensions](https://learn.microsoft.com/en-us/azure/databricks/oltp/projects/extensions) |
| No superuser | "Any functionality that requires superuser privileges … is not allowed." | [primary] [compatibility](https://docs.databricks.com/aws/en/oltp/projects/compatibility) |
| Password | OAuth token, TTL 300–3600 s, minted per new connection: `w.postgres.generate_database_credential(endpoint="projects/<p>/branches/<b>/endpoints/<e>")` → `.token`. `sslmode=require`. Native passwords off by default for new projects since 2026-05-21. | [primary] [REST](https://docs.databricks.com/api/postgres/v1/generate-database-credential.md), [external apps](https://learn.microsoft.com/en-us/azure/databricks/oltp/projects/external-apps-connect) |
| Roles | Each Databricks identity needs a Postgres role (`databricks_create_role(id, 'USER'\|'SERVICE_PRINCIPAL'\|'GROUP')` or UI/REST). UI-created roles get `databricks_superuser`, which bypasses RLS. **Max 500 roles per branch.** Group-role logins make `current_user` the group. | [primary] [roles](https://docs.databricks.com/aws/en/oltp/projects/postgres-roles), [limits](https://docs.databricks.com/aws/en/oltp/projects/limitations) |
| Connections | Built-in PgBouncer does not support OAuth → connect directly. 24 h idle timeout, 3-day max connection life. Private Link workspaces need an extra port-5432 endpoint for external clients. | [primary] [authentication](https://learn.microsoft.com/en-us/azure/databricks/oltp/projects/authentication), [private link](https://learn.microsoft.com/en-us/azure/databricks/oltp/projects/private-link) |
| Delta → Lakebase | Synced tables: Snapshot / Triggered / Continuous (min 15 s; CDF required for the latter two); RLS cannot be set on synced tables. | [primary] [synced tables](https://learn.microsoft.com/en-us/azure/databricks/oltp/projects/sync-tables) |
| Lakebase → Delta | Lakebase Change Data Feed, Public Preview. | [primary] [Lakebase CDF](https://learn.microsoft.com/en-us/azure/databricks/oltp/projects/lakebase-cdf) |
| Regions | Azure `southeastasia` (GA 2026-03-02), AWS `ap-southeast-1`, others; GCP is Beta in three regions. | [primary] manage projects ([AWS](https://docs.databricks.com/aws/en/oltp/projects/manage-projects), [GCP](https://docs.databricks.com/gcp/en/oltp/projects/manage-projects)) |
| Compliance | SOC 2 Type 2; CMK in all AWS/Azure regions; PCI-DSS/HITRUST in Lakebase regions for compliance-security-profile workspaces. | [primary] [data protection](https://learn.microsoft.com/en-us/azure/databricks/oltp/projects/data-protection) |

## Identity and OBO

- Unified auth (`databricks-sdk`) `auth_type`s include `pat`, `oauth-m2m`,
  `runtime`, `external-browser`, `databricks-cli`, `azure-*`, `google-*`, OIDC
  variants, `model-serving`. [primary]
  [unified auth](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/auth/unified-auth)
- **Apps user authorization (OBO)** — Public Preview, a workspace admin must
  enable it. User token arrives in `x-forwarded-access-token`; scopes include
  `sql`, `vector-search`, `model-serving`, `postgres`, `files`, `genie`,
  `catalog.*:read`. [primary] [Apps auth](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/auth),
  [scopes](https://docs.databricks.com/api/workspace/api/scopes),
  [agents on Apps](https://learn.microsoft.com/en-us/azure/databricks/agents/custom-agents/agent-authentication)
- **Model Serving OBO** — Public Preview, admin-enabled;
  `WorkspaceClient(credentials_strategy=ModelServingUserCredentials())`
  created inside `predict`. Reaches only: AI Search, serving endpoints, SQL
  warehouses, UC connections, UC tables/functions (Statement Execution),
  Genie, MCP. "Resources not listed here, such as Unity Catalog Volumes … are
  not supported"; Lakebase is not listed. Databricks recommends Apps for new
  agents. [primary]
  [Model Serving auth](https://learn.microsoft.com/en-us/azure/databricks/generative-ai/agent-framework/agent-authentication-model-serving)

### Runtime × identity × backend

| Runtime | Identity | UC tables (SQL warehouse) | AI Search | Lakebase / pgvector | Serving endpoints |
|---|---|---|---|---|---|
| Local machine | PAT, OAuth U2M, SP | yes | yes | yes, with a Postgres role | yes |
| Notebook / Job | user or run-as SP | yes (+ Spark) | yes | yes, with a Postgres role [inferred] | yes |
| Databricks Apps | app SP | yes | yes | yes | yes |
| Databricks Apps | OBO | yes | yes | yes — one Postgres role per user, ≤500 per branch | yes |
| Model Serving | OBO | yes | yes | **no** | yes |
| Model Serving | SP | yes | yes | yes, via SP secrets or passthrough (shared identity) | yes |

### Fail-open traps (the SDK must fail closed instead)

| Symptom | Cause | SDK behaviour |
|---|---|---|
| Queries succeed but RLS is ignored | App's default SP pool connects as table owner | Never route an OBO-mode request to the SP pool |
| OBO silently becomes app identity in dev | AppKit `asUser(req)` falls back to the SP pool without a token | Missing token → `AuthError` |
| Agent runs as SP although OBO was configured | `get_user_workspace_client()` falls back to SP "without raising" | Do not call fallback helpers; check identity explicitly |

## Files

- **UC Volumes** — POSIX `/Volumes/...` on clusters/serverless, Files API
  elsewhere; **no append or random writes** (write locally, then copy); not
  reachable through Model Serving OBO. [primary]
  [volume files](https://learn.microsoft.com/en-us/azure/databricks/volumes/volume-files)
- **Workspace files** — 500 MB cap, executors cannot write, meant for code
  and config. [primary]
  [workspace files](https://learn.microsoft.com/en-us/azure/databricks/files/workspace)

## Databricks SQL

- Recursive CTEs (`WITH RECURSIVE`) are GA: DBSQL 2025.25, DBR 17.0+,
  `UNION ALL` only, default depth 100, 1M-row cap. [primary]
  [CTE](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-qry-select-cte)
- No native graph store or graph query language; GraphFrames runs on classic
  DBR ML only. [primary]
  [GraphFrames](https://learn.microsoft.com/en-us/azure/databricks/integrations/graphframes/)

## AI Search (formerly Mosaic AI Vector Search)

- Python module `databricks.ai_search`. Delta Sync index (managed or
  self-managed embeddings) or Direct Vector Access; hybrid ANN + BM25 via RRF;
  reranker Beta. No row/column-level permissions — filter-based ACLs only.
  Standard endpoint 20–50 ms; PAT adds latency, SP OAuth recommended.
  [primary] [AI Search](https://docs.databricks.com/aws/en/ai-search/ai-search),
  [best practices](https://docs.databricks.com/aws/en/ai-search/best-practices)

## Models (Foundation Model APIs / serving endpoints)

- OpenAI-compatible at `https://<workspace>/serving-endpoints` (chat,
  responses, embeddings, completions); endpoint names `databricks-<model>`.
  [primary] [API reference](https://docs.databricks.com/aws/en/machine-learning/foundation-model-apis/api-reference)
- Multilingual embedding: only `databricks-qwen3-embedding-0-6b` (Public
  Preview); GTE/BGE are English-only. [primary]
  [supported models](https://learn.microsoft.com/en-us/azure/databricks/machine-learning/foundation-models/supported-models)
- Structured outputs: no `$ref`/`anyOf`/`oneOf`/`allOf`/`pattern`, ≤64 keys;
  Claude cannot combine `response_format` with tools; `claude-sonnet-5`
  rejects `temperature`/`top_p`/`top_k` with HTTP 400; tool calling ≤32
  functions. [primary]
  [structured outputs](https://docs.databricks.com/aws/en/machine-learning/model-serving/structured-outputs),
  [function calling](https://docs.databricks.com/aws/en/machine-learning/model-serving/function-calling)
- External models (OpenAI, Azure OpenAI, Anthropic, Bedrock, Vertex, …) go
  through Unity AI Gateway (rate limits, usage tables, payload logging).
  [primary] [external models](https://docs.databricks.com/aws/en/generative-ai/external-models/)

## Document parsing

- `ai_parse_document` — GA; PDF, images, DOC(X), PPT(X); **no XLSX**; ≤500
  pages / 100 MB; typed elements with bounding boxes; "non-optimal" for
  non-Latin scripts. [primary]
  [ai_parse_document](https://docs.databricks.com/aws/en/sql/language-manual/functions/ai_parse_document)
- `ai_query` with `responseFormat` runs structured LLM extraction as a batch
  SQL/Spark job. [primary] [ai_query](https://docs.databricks.com/aws/en/sql/language-manual/functions/ai_query)

## MLflow

- `mlflow.genai.evaluate` accepts RAGAS, DeepEval and Phoenix scorers
  (e.g. RAGAS `ContextRecall`, `ContextEntityRecall`, `Faithfulness`,
  `NonLLMContextRecall`); LLM scorers take `model="databricks:/<endpoint>"`.
  [primary] [third-party scorers](https://docs.databricks.com/aws/en/mlflow3/genai/eval-monitor/third-party-scorers/ragas)
- Prompt Registry on Databricks is **Beta**. UC-stored traces need MLflow
  ≥ 3.14. [primary]
  [prompt registry](https://learn.microsoft.com/en-us/azure/databricks/mlflow3/genai/prompt-version-mgmt/prompt-registry/)

## Serving and packaging

- Custom MCP servers on Apps: streamable HTTP at `/mcp`, app name prefixed
  `mcp-`. [primary] [custom MCP](https://docs.databricks.com/aws/en/generative-ai/mcp/custom-mcp)
- Serverless environment v6: Python 3.12.3; wheels install from UC Volumes;
  CPU may be aarch64 or x86_64. Asset Bundles are now "Declarative Automation
  Bundles" (non-breaking rename). [primary]
  [serverless dependencies](https://docs.databricks.com/aws/en/compute/serverless/dependencies)

## Regions and cross-geo processing

- Some AI features run outside the workspace's region. Example, Azure
  `southeastasia`: Foundation Model APIs,
  `ai_parse_document` v2, `ai_extract` v2, Knowledge Assistant and Supervisor
  run cross-geo; AI Search, `ai_query` batch, Apps, serverless and Lakebase are
  in-region. Cross-geo is on by default outside US/EU unless the compliance
  security profile is enabled; Asia traffic may be processed in Japan, Korea
  or Singapore. [primary]
  [feature regions](https://learn.microsoft.com/en-us/azure/databricks/resources/feature-region-support),
  [geos](https://learn.microsoft.com/en-us/azure/databricks/resources/databricks-geos)

## Prior art (why we build)

- Official demo uses external Neo4j, last push 2025-04
  ([graphrag-demo](https://github.com/databricks-industry-solutions/graphrag-demo)),
  as does the only first-party GraphRAG blog (2025-04-01,
  [knowledge graph RAG on Databricks](https://databricks.com/blog/building-improving-and-deploying-knowledge-graph-rag-systems-databricks));
  OntoBricks (Databricks Labs) is structured-data only
  ([ontobricks](https://github.com/databrickslabs/ontobricks)); Genie Ontology
  is a closed context layer for Genie. [primary]

## Not verified

Lakebase AGE roadmap · whether an OBO token survives agent → MCP on Apps →
Lakebase · Apps user-authorization GA date · enforcement of
`generate_database_credential(claims=...)` · Lakebase cold-start latency ·
Vietnamese quality of embeddings and parsing.
