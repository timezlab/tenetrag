# Databricks AI integration surfaces + prior art for a GraphRAG SDK

> **Snapshot, 2026-10-02 — not maintained.** Round 1 web research lane on
> models and serving endpoints, embeddings, regions and cross-geo routing,
> document parsing, AI Search, MLflow, serving surfaces and Databricks prior
> art (about 95 searches and fetches). The maintained, re-verified summary is
> in [databricks-platform.md](../reference/databricks-platform.md); where they
> differ, the maintained doc wins. Adopter-specific lines were removed before
> publishing.
>
> **Errata and later resolutions:**
> - The Apps user authorization status conflict (Q5, could-not-verify item 3)
>   was settled as Public Preview by
>   [2026-10-02-factcheck-lakebase-obo.md](2026-10-02-factcheck-lakebase-obo.md).

Research date: 2026-10-02. Read-only web research (about 95 search/fetch calls). Scope: the eight questions in the brief.

Labels: [primary] = Databricks/Microsoft Learn docs, release notes, official blog or press release, PyPI. [secondary] = third party. [inferred] = my reasoning from primary facts. [unverified] = could not confirm or single weak source.
A dagger (†) marks values I read through the fetch tool's page summary rather than seeing verbatim; re-check them before hard-coding anything.

---

## Executive summary: the 5 findings that matter most for the SDK architecture

1. **No mature, supported GraphRAG exists on Databricks; build the SDK rather than extend something.**
   - OntoBricks (Databricks Labs) is ontology/structured-data only, under the Databricks License, and has no SLA. [primary] https://github.com/databrickslabs/ontobricks
   - The official Databricks accelerator and blog use Neo4j (an external graph DB); the repo has about 30 stars and its last push was 2025-04-25. [primary] https://www.databricks.com/blog/building-improving-and-deploying-knowledge-graph-rag-systems-databricks and https://github.com/databricks-industry-solutions/graphrag-demo
   - The only Microsoft-GraphRAG-on-Databricks sample is a single-author MIT repo with 3 commits. It needs a cluster (not serverless), DBR 14.0 ML+, and avoids Volumes/Workspace files because LanceDB rename is unsupported. It also says FMAPI Llama models are incompatible with GraphRAG queries. [secondary] https://github.com/taka-yayoi/graphrag_on_databricks
   - Genie Ontology (Public Preview, announced 2026-06-16) is Databricks' own "knowledge graph"-style context layer over UC semantics. It has no export and is reached through Genie and Genie MCP. [primary] https://docs.databricks.com/aws/en/genie/genie-ontology and https://www.databricks.com/company/newsroom/press-releases/databricks-launches-genie-one-all-new-agentic-coworker-every-team

2. **Embeddings: only one hosted multilingual option, and it is Public Preview.**
   - `databricks-qwen3-embedding-0-6b` (Public Preview): "supports 100+ languages", ~32K-token inputs, dimension configurable up to 1024. [primary] https://learn.microsoft.com/en-us/azure/databricks/machine-learning/foundation-models/supported-models
   - GTE-large-en and BGE-large-en are English-only. [primary] same page.
   - Knowledge Assistant's AI Search source accepts only `databricks-gte-large-en`, `databricks-bge-large-en` or `databricks-qwen3-embedding-0-6b`. [primary] https://learn.microsoft.com/en-us/azure/databricks/agents/agent-bricks/knowledge-assistant
   - Vietnamese is not named in any model card; coverage is [inferred] from "100+ languages". For Vietnamese enterprise text the SDK should allow self-managed embeddings (AI Search accepts up to 4096 dims) and BYO embedding endpoints (external models). [inferred]

3. **Region and cross-geo routing is the biggest deployment risk outside the US and EU.**
   - Asian regions: Azure `southeastasia` (Singapore) and `eastasia` (Hong Kong); AWS `ap-southeast-1` (Singapore); AWS `ap-southeast-3` (Jakarta) is thin. [primary] https://learn.microsoft.com/en-us/azure/databricks/resources/feature-region-support
   - Azure `southeastasia` needs cross-geo routing (marked ⥂) for FMAPI pay-per-token, FMAPI provisioned throughput, `ai_parse_document` v2, `ai_extract`/`ai_classify` v2, `ai_prep_search`, Knowledge Assistant and Supervisor Agent. Natively in-region: AI Search, `ai_query` batch, Custom Agents + Evaluation, MLflow traces in UC, Apps, serverless, Lakebase Autoscaling, Unity Gateway, external models, custom model serving. [primary] same page (ms.date 2026-10-01).
   - Cross-geo is "enabled by default for all workspaces in Geos outside the US and EU that don't have a compliance security profile enabled". Asia Geo = Hong Kong, Indonesia, Japan, South Korea, Singapore; ‡ means Asia-Geo traffic "can be sent for processing within regions in Japan, South Korea, or Singapore". [primary] https://learn.microsoft.com/en-us/azure/databricks/resources/databricks-geos and https://docs.databricks.com/aws/en/resources/feature-region-support
   - Most Gemini 3.x endpoints are "hosted on a global endpoint and require cross geography routing". [primary] supported-models page above.
   - Whether this satisfies local data-residency rules is a legal question I did not research.

4. **Ingestion and batch extraction are well supported; spreadsheets are not.**
   - `ai_parse_document`: GA on DBR 17.3+/Databricks SQL. Formats PDF, JPG/JPEG, PNG, TIFF/TIF, DOC/DOCX, PPT/PPTX. No XLSX/CSV. Max 500 pages and 100 MB. "Non-optimal performance with non-Latin alphabets (Japanese, Korean)". Output is VARIANT with typed elements (text, table, figure, title, caption, section_header, page_header, page_footer, page_number, footnote), each with bbox, confidence and content; optional figure descriptions. [primary] https://docs.databricks.com/aws/en/sql/language-manual/functions/ai_parse_document (†)
   - `ai_extract` (schema-driven) and `ai_classify`; `ai_prep_search` (Beta) makes RAG chunks for AI Search. [primary] https://learn.microsoft.com/en-us/azure/databricks/agents/agent-bricks/intelligent-document-processing (ms.date 2026-09-11)
   - `ai_query(endpoint, request, returnType, failOnError, modelParameters, responseFormat, files)` can drive entity/relation extraction over a chunk table. Needs DBR 15.4+; not on DBSQL Classic. [primary] https://docs.databricks.com/aws/en/sql/language-manual/functions/ai_query (†)
   - GraphRAG extraction as a batch job is therefore feasible: `ai_query` + `responseFormat` writing to Delta, or the engine inside a Lakeflow Job. No doc blesses GraphRAG specifically. [inferred]

5. **Governance, serving and naming.**
   - AI Search: "Row and column level permissions are not supported. However, you can implement your own application level ACLs using the filter API." [primary] https://learn.microsoft.com/en-us/azure/databricks/ai-search/ai-search
   - Apps user authorization (OBO) is Public Preview, with a `vector-search` scope. A release-notes "what's coming" item scheduled auto-enablement for compliance-security-profile workspaces for late September 2026; I could not confirm it shipped. [primary] https://docs.databricks.com/aws/en/release-notes/whats-coming and https://learn.microsoft.com/en-us/azure/databricks/dev-tools/databricks-apps/auth
   - Recommended serving: Databricks Apps + ResponsesAgent + custom MCP. Supervisor Agent can orchestrate Apps agents, MCP servers, UC functions, Genie and KA. [primary] https://docs.databricks.com/aws/en/generative-ai/agent-framework/author-agent and https://learn.microsoft.com/en-us/azure/databricks/agents/agent-bricks/multi-agent-supervisor
   - Renames affect package and doc names: Vector Search to **AI Search** (about 2026-06; `databricks-ai-search`, `databricks.ai_search`, `AISearchClient`), AI Gateway to **Unity AI Gateway**, Asset Bundles to **Declarative Automation Bundles** (release note 2026-03-16, non-breaking), Genie spaces to **Genie Agents** (2026-07-09), Workflows to **Lakeflow Jobs**. [primary] https://docs.databricks.com/aws/en/release-notes/product/2026/march and https://docs.databricks.com/aws/en/dev-tools/bundles/faqs

Cross-cutting model-churn facts for the SDK (all [primary] from the Azure supported-models page, ms.date 2026-09-29):
- Gemini 2.5 Pro retires 2026-10-02 (today); Gemini 2.5 Flash is deprecated with planned retirement 2026-10-02. Model names must be configuration, not code.
- `databricks-claude-sonnet-5` rejects `temperature`, `top_p` and `top_k` with a 400 error. Engines that hard-code `temperature=0` will break on it.
- GPT-6 Sol, GPT-5.5, GPT-5.5 Pro and GPT-5.3 Codex are "not supported in AI Playground. Use the Responses API". Whether Chat Completions rejects them is not stated.
- GPT-5.5 uses extended prompt caching; "cached tensors are stored in GPU-local storage for no more than 24 hours". Relevant to data-retention reviews.
- Claude endpoints are "hosted by Databricks within the Databricks security perimeter".

---

## Q1. Models: FMAPI, Model Serving, external models, AI Gateway, SE Asia

**Catalogue (Azure page, ms.date 2026-09-29)** [primary] https://learn.microsoft.com/en-us/azure/databricks/machine-learning/foundation-models/supported-models
- Endpoint names follow `databricks-<model>`. Examples:
  - OpenAI: `databricks-gpt-6-luna`, `databricks-gpt-5-4-nano` ("high-throughput tasks like ... classification"), `databricks-gpt-5-2` ("excels at structured extraction").
  - Anthropic: `databricks-claude-haiku-4-5`, `databricks-claude-sonnet-5`.
  - Open-weight: `databricks-gpt-oss-120b` and `-20b` (128K context), `databricks-meta-llama-3-3-70b-instruct`, `databricks-llama-4-maverick`, `databricks-qwen3-next-80b-a3b-instruct` (Public Preview), `databricks-qwen35-122b-a10b` (Public Preview).
  - Other: `databricks-gemini-3-5-flash-lite`, `databricks-glm-5-3`, `databricks-kimi-k3`, `databricks-deepseek-v4-1-flash`.
- On Azure, OpenAI, Gemini, GLM, Kimi, Inkling and DeepSeek V4.x are "available through ADI Services, provided by Databricks". Enable via the account-settings toggle "Integration with ADI Services". Pay-per-token; "Standard data residency settings apply". The acronym is not defined in the docs. [primary] https://docs.databricks.com/adi (†)
  - Implication: on Azure these are Databricks-served, not the customer's own Azure OpenAI tenant (that would be an external model). [inferred]
- "Databricks recommends provisioned throughput for production workloads". [primary] same page.

**API surface**
- OpenAI-compatible at `base_url=https://<workspace>/serving-endpoints`: Chat Completions, Responses, Embeddings, Completions. [primary] https://docs.databricks.com/aws/en/machine-learning/foundation-model-apis/api-reference
- Structured outputs via `response_format` (`json_schema` with `strict`, or `json_object`). [primary] https://docs.databricks.com/aws/en/machine-learning/model-serving/structured-outputs (†)
  - Limits: "The maximum number of keys specified in the JSON schema is 64"; unsupported keywords `pattern`, `anyOf`, `oneOf`, `allOf`, `prefixItems`, `$ref`; no enforcement of `maxProperties`, `minProperties`, `maxLength`.
  - Claude: only `json_schema`; `stream` must be false; `response_format` cannot be combined with `tools`/`tool_choice`.
  - Pydantic-generated schemas commonly contain `$ref`/`anyOf`, so the SDK likely needs a schema-flattening shim. [inferred]
- Tool calling is capped at 32 functions. [primary] https://docs.databricks.com/aws/en/machine-learning/model-serving/function-calling
- External models cover OpenAI, Azure OpenAI, Anthropic, Bedrock, Vertex, Cohere, AI21 and custom OpenAI-compatible providers. [primary] https://docs.databricks.com/aws/en/generative-ai/external-models/
- LiteLLM has a `databricks/` provider; Microsoft GraphRAG is LiteLLM-based and uses JSON-schema structured outputs. [primary] https://docs.litellm.ai/docs/providers/databricks and https://microsoft.github.io/graphrag/config/models/. End-to-end GraphRAG through LiteLLM to Databricks was not verified. [unverified]

**Rate limits (sample values, pay-per-token)** [primary] https://docs.databricks.com/aws/en/machine-learning/foundation-model-apis/limits (†)
- Claude Sonnet 5: 1,000,000 ITPM / 100,000 OTPM / 360,000 QPH. Claude Sonnet 4: 200,000 / 20,000 / 360,000. GPT-6 Astra and Llama 3.3 70B: 1,000,000 / 100,000 / 360,000.
- Embeddings (Qwen3-Embedding-0.6B, BGE Large En): 2,160,000 QPH.
- Token-bucket with burst; the most restrictive of ITPM/OTPM/QPH applies; exceeding returns 429.
- Provisioned throughput: 200 QPS per workspace; 597 s per-request execution limit.

**Unity AI Gateway (renamed from AI Gateway)** [primary] https://docs.databricks.com/aws/en/release-notes/unity-gateway/ and https://docs.databricks.com/aws/en/ai-gateway/
- Rate limits, guardrails (PII, Beta), usage table `system.ai_gateway.usage`, payload logging to Delta, unified OTel trace table (Beta), provisioned-throughput governance (GA 2026-08-24), MCP governance (Beta).
- Per-user/group rate-limit granularity was not verified. [unverified]

**Regional notes for Southeast Asia** (Azure table ms.date 2026-10-01) [primary] https://learn.microsoft.com/en-us/azure/databricks/resources/feature-region-support
- Azure `southeastasia`: see finding 3 for the full split.
- Azure `eastasia` (Hong Kong): no GPU custom serving and no Lakebase Autoscaling; provisioned throughput, pay-per-token and the batch AI functions all need ⥂.
- AWS `ap-southeast-1` †: FMAPI provisioned throughput ✓‡; pay-per-token ✓⥂; `ai_query`, `ai_parse_document` v2, `ai_extract` v2 ✓‡; `ai_prep_search` ✓⥂; AI Search ✓; KA and Supervisor ✓⥂; Apps, serverless, Lakebase Autoscaling ✓. https://docs.databricks.com/aws/en/resources/feature-region-support
- AWS `ap-southeast-3` (Jakarta) †: only `ai_query` listed among AI functions; no serverless, Apps or agent features listed. Low confidence. [unverified]
- Model list for AWS `ap-southeast-1` † (pay-per-token): Claude, GPT, Gemini, Qwen, Gemma, Llama 3.3 70B/3.1 8B, Kimi, GLM, DeepSeek and embeddings. Provisioned throughput: GPT OSS 120B/20B, Gemma 3 12B⥂, Llama 4 Maverick⥂ (preview), Llama 3.x, GTE v1.5 (English), BGE v1.5 (English). https://docs.databricks.com/aws/en/unity-gateway/model-region-availability
- Azure `southeastasia` per-model table was truncated in my fetches. [unverified]

---

## Q2. AI Search (formerly Mosaic AI Vector Search)

- Rename: Vector Search became **Databricks AI Search** (about 2026-06; package `databricks-ai-search`, import `databricks.ai_search`, `AISearchClient`). [primary] https://docs.databricks.com/aws/en/ai-search/ai-search
- Index types: Delta Sync (managed or self-managed embeddings), Direct Vector Access, and a full-text BM25 index (Beta). Standard endpoints need Change Data Feed on the source table. [primary] https://learn.microsoft.com/en-us/azure/databricks/ai-search/ai-search (ms.date 2026-09-14)
- Search: HNSW with L2. Hybrid = ANN + BM25 fused by RRF (k=60). Reranker is Beta (read in an earlier fetch). [primary] https://docs.databricks.com/aws/en/ai-search/query-ai-search
- Limits (†) [primary] https://docs.databricks.com/aws/en/ai-search/ai-search
  - Capacity: Standard about 320M vectors at 768 dims (160M at 1536, 80M at 3072); Storage-optimized about 1B at 768 dims.
  - Embedding dimension up to 4096; 50 indexes per endpoint; 500 endpoints per workspace; 50 columns and 50 metadata fields per index.
  - Delta Sync row 100 KB; embedding source column 32,764 bytes; query text 32,764 characters.
  - Max results 10,000 (ANN, full-text) and 200 (hybrid).
- Permissions: no row/column-level security. Use filters on metadata columns for ACLs, for example an `allowed_groups` column. [primary] same page. [inferred] for the pattern.
- Auth: the Azure page documents service principal or PAT and says nothing about OBO. Best practice: service-principal OAuth for production; PATs "add hundreds of milliseconds of latency". [primary] https://docs.databricks.com/aws/en/ai-search/best-practices (†)
  - OBO is reachable through Apps user authorization (`vector-search` scope). Latency with OBO tokens was not documented. [unverified]
- Latency (†) [primary]:
  - Standard: 20-50 ms, 30-200+ QPS for indexes under 320M vectors. Storage-optimized: 300-500 ms, 30-50 QPS up to 1B vectors. https://docs.databricks.com/aws/en/ai-search/best-practices
  - Blog (2026-03-09): about 300 ms at 10M and about 500 ms at 1B vectors; index build under 8 hours at 1B; up to 7x lower cost than Standard; recall above 94% at 10M, above 91% at 100M, 90% at 1B. https://www.databricks.com/blog/decoupled-design-billion-scale-vector-search
  - Hybrid uses "about twice as many resources as ANN"; keep `num_results` at 10-100 ("increasing `num_results` by 10x can double query latency and reduce QPS capacity by 3x"). Managed embeddings add a model-serving call at query time.
- Cost (page undated; fetched 2026-10-02) [primary] https://www.databricks.com/product/pricing/vector-search (†) and https://docs.databricks.com/aws/en/ai-search/cost-management (†)
  - Standard: $0.28/unit-hour (4.00 DBU/hr), 2M vectors/unit at 768 dims. Storage-optimized: $1.28/unit-hour (18.29 DBU/hr), 64M vectors/unit.
  - Minimum one unit per endpoint; billing starts once an index exists and stops 24 h after the last index is deleted. Use Triggered over Continuous sync; share endpoints.
  - One Standard unit running continuously is about $204/month (0.28 x 730 h). [inferred]
- Regions: AI Search ✓ in Azure `southeastasia`, `eastasia` and AWS `ap-southeast-1` (no ⥂). [primary] feature-region-support pages above.

---

## Q3. Batch AI in SQL/Spark

- `ai_parse_document`: see finding 4. Options: `version` ("2.0"), `imageOutputPath` (UC volume), `descriptionElementTypes` ('*', 'figure', ''), `pageRange` ("1,3,5-10"). Signature `ai_parse_document(content[, map('version','2.0')])`. [primary] https://docs.databricks.com/aws/en/sql/language-manual/functions/ai_parse_document (†)
- `ai_extract`: GA; v2 is Public Preview (read in an earlier fetch of the ai_extract page); the Learn sample passes `options => map('version','2.1')`. REST default limit 120 requests/min/workspace. [primary] https://docs.databricks.com/aws/en/sql/language-manual/functions/ai_extract and https://learn.microsoft.com/en-us/azure/databricks/agents/agent-bricks/info-extraction (ms.date 2026-07-09)
- `ai_query`: endpoint types are foundation models, custom serving endpoints and external models. Requires `CAN QUERY`. `files` accepts JPEG/PNG only. `responseFormat` needs DBR 15.4+. [primary] https://docs.databricks.com/aws/en/sql/language-manual/functions/ai_query (†)
- `ai_classify` (500+ labels), `ai_prep_search` (Beta; semantic chunks with titles, section headers, page references, formatted for AI Search indexing). [primary] https://learn.microsoft.com/en-us/azure/databricks/agents/agent-bricks/intelligent-document-processing
- Batch guidance: submit the whole dataset in one query and use `databricks-` pay-per-token models rather than provisioned throughput. [primary] https://docs.databricks.com/aws/en/large-language-models/ai-functions (read in an earlier fetch)
- Region: in Azure `southeastasia`, `ai_query` batch is in-region; `ai_parse_document` v2, `ai_extract`/`ai_classify` v2 and `ai_prep_search` need ⥂. [primary] feature-region-support.
- Documented rows-per-second throughput for AI Functions: not found. [unverified]
- Spreadsheets (XLSX/CSV) need a separate ingestion path. [inferred from the format list]

---

## Q4. MLflow 3

- Latest release 3.16.1 (2026-09-16). [primary] https://pypi.org/project/mlflow/
- Tracing is OpenTelemetry-based. Traces in Unity Catalog need MLflow 3.14+. [primary] https://docs.databricks.com/aws/en/mlflow3/genai/tracing/trace-unity-catalog
- GenAI evaluation: `mlflow.genai.evaluate` with scorers/judges and evaluation datasets. [primary] https://mlflow.org/docs/latest/genai/eval-monitor/
- LoggedModel / app versions: `mlflow.set_active_model`. [primary] https://mlflow.org/docs/latest/genai/version-tracking/
- Prompt Registry on Databricks is **Beta** (UC-backed; needs `mlflow[databricks]>=3.1.0`), even though open-source MLflow offers it broadly. [primary] https://learn.microsoft.com/en-us/azure/databricks/mlflow3/genai/prompt-version-mgmt/prompt-registry/ (ms.date 2026-09-15)
- Region: Custom Agents + Evaluation and MLflow traces in UC are ✓ in Azure `southeastasia` with no cross-geo requirement. [primary] feature-region-support.
- Gateway can write OTel traces to a unified table (Beta). [primary] Unity Gateway release notes.

---

## Q5. Serving: agents, Apps, MCP, UC functions, Genie

- ResponsesAgent is the recommended agent interface; Databricks Apps is the recommended deployment for custom agents. [primary] https://docs.databricks.com/aws/en/generative-ai/agent-framework/author-agent
- Apps: GA. Python (Streamlit, Dash, Gradio) and Node.js (React, Angular, Svelte, Express). [primary] https://docs.databricks.com/aws/en/dev-tools/databricks-apps/ (†)
- Apps authorization: app service principal or user authorization (OBO) via the `x-forwarded-access-token` header. Scopes include `vector-search`, `genie`, `sql`, `model-serving`, `postgres`, `files`. [primary] https://learn.microsoft.com/en-us/azure/databricks/dev-tools/databricks-apps/auth (ms.date 2026-09-28)
  - Status conflict: the Apps auth page shows no preview banner, the agents-on-Apps page says "Public Preview, admin enablement", and release notes say Public Preview. Treat as Public Preview; the late-September-2026 auto-enable for compliance-profile workspaces was scheduled, not confirmed shipped. [primary, conflicting] https://docs.databricks.com/aws/en/release-notes/whats-coming
- Lakebase resource binding creates a Postgres role named after the app service-principal client ID and injects `PG*` environment variables. [primary] https://docs.databricks.com/aws/en/dev-tools/databricks-apps/lakebase
- Managed MCP servers (all Public Preview): Genie, AI Search, DBSQL, UC functions. [primary] https://docs.databricks.com/aws/en/agents/mcp-tools/managed-mcp
- Custom MCP on Apps: streamable HTTP, app name prefix `mcp-`, `/mcp` endpoint. [primary] https://docs.databricks.com/aws/en/generative-ai/mcp/custom-mcp
- UC functions as tools are recommended only for known/fixed queries. [primary] author-agent page above (read in an earlier fetch)
- Genie Agents API (formerly Genie spaces): chat mode and agent mode APIs; OAuth U2M and M2M; needs CAN USE on a Pro/serverless warehouse; data sources are tables and metric views; rate limits not stated in the page I read. [primary] https://docs.databricks.com/aws/en/genie/conversation-api (†)
- Region: Apps, serverless and Lakebase Autoscaling are ✓ in Azure `southeastasia`; Apps ✓ in `eastasia`. [primary] feature-region-support.

---

## Q6. Agent Bricks

- Knowledge Assistant: GA 2026-01-27 ("Instructed Retriever"). Sources are UC volumes and AI Search indexes; indexes must use one of three embedding models (see finding 2). Needs ⥂ in SE Asia. [primary] https://www.databricks.com/en/blog/agent-bricks-knowledge-assistant-now-generally-available-turning-enterprise-knowledge-answers and the KA Learn page (ms.date 2026-09-11)
- Supervisor Agent: orchestrates Genie, KA, UC functions, MCP servers and custom Apps agents. "You cannot use more than 50 agents in a single supervisor system." "AI Search index subagents support only Delta Sync indexes." Has a sandboxed code-execution tool with no egress; SDK management is labelled Beta. [primary] https://learn.microsoft.com/en-us/azure/databricks/agents/agent-bricks/multi-agent-supervisor (ms.date 2026-09-11)
- Information Extraction: Public Preview since 2026-03-27; built on `ai_extract`; precision mode, citations, confidence scores; 128k-token max context; union schema types unsupported; needs serverless, UC and a serverless usage policy with non-zero budget. GA not confirmed. [primary] https://learn.microsoft.com/en-us/azure/databricks/agents/agent-bricks/info-extraction and https://docs.databricks.com/aws/en/release-notes/product/2026/march
- Can a custom GraphRAG retriever plug in?
  - Into Knowledge Assistant: no documented path; sources are volumes and AI Search indexes only. [inferred from the source list]
  - Into Supervisor: yes, exposed as an MCP server, UC function or custom Apps agent. [primary] Supervisor page above.

---

## Q7. Packaging

- Workflows is now **Lakeflow Jobs**. [primary] https://docs.databricks.com/aws/en/jobs/
- Asset Bundles is now **Declarative Automation Bundles**: release note 2026-03-16; CLI and `databricks.yml` unchanged (non-breaking). [primary] https://docs.databricks.com/aws/en/dev-tools/bundles/faqs and https://docs.databricks.com/aws/en/release-notes/product/2026/march
- Serverless environment versions v1-v6; v6 is latest (Python 3.12.3, released 2026-09-03). [primary] https://docs.databricks.com/aws/en/release-notes/serverless/environment-version/
- Wheels from a UC volume install through environment dependencies (`/Volumes/<catalog>/<schema>/<volume>/<path>.whl`). Do not install PySpark. CPU architecture is not guaranteed (aarch64 or x86_64), so native-extension dependencies need multi-arch wheels. [primary] https://docs.databricks.com/aws/en/compute/serverless/dependencies and https://docs.databricks.com/aws/en/dev-tools/bundles/python-wheel
- The Microsoft-GraphRAG sample needed a classic cluster (DBR 14.0 ML+), not serverless. [secondary] taka-yayoi repo above.
- Whether graspologic and similar native engine dependencies install on serverless aarch64 was not checked. [unverified]

---

## Q8. Prior art: GraphRAG and "knowledge graph" on Databricks

| Item | What it is | Storage | Engine | Maturity | License |
|---|---|---|---|---|---|
| Databricks blog "Building, improving, and deploying knowledge graph RAG systems on Databricks" (2025-04-01) | Reference architecture | Neo4j (external) | Neo4j-based | Reference only | n/a |
| databricks-industry-solutions/graphrag-demo | Solution accelerator | Neo4j | Neo4j-based | About 30 stars; last push 2025-04-25 | Not verified |
| databrickslabs/ontobricks | Ontology to knowledge graph over structured data | Lakebase (default), Delta triple tables, Neo4j, or none | n/a (ontology-driven) | Labs; "not formally supported ... with SLAs" | Databricks License (source-available) |
| taka-yayoi/graphrag_on_databricks | Microsoft GraphRAG sample | Delta plus LanceDB | Microsoft GraphRAG | 3 commits, single author | MIT |
| Genie Ontology (2026-06-16) | Databricks' own context/"knowledge graph" layer | Inside Genie/UC | Closed | Public Preview; no export | Proprietary |
| Neo4j + Databricks (partner page 2026-06-12; blog 2026-06-17; webinar 2026-06-23) | Vendor collateral | Neo4j | Neo4j | Marketing/reference | n/a |
| PuppyGraph "Databricks knowledge graph" (2026-05-09) | Vendor blog | Delta queried as a graph | PuppyGraph | Vendor material, not deep-read | Commercial |
| Community "Turning lakehouse into brainhouse via knowledge graphs" (2026-03-25) | Opinion article | n/a | n/a | Opinion | n/a |

Labels and links:
- Blog and accelerator [primary]: https://www.databricks.com/blog/building-improving-and-deploying-knowledge-graph-rag-systems-databricks, https://github.com/databricks-industry-solutions/graphrag-demo
- OntoBricks: "Pluggable graph engine: Pick a backend per domain: Lakebase (Postgres) by default, Lakehouse (governed Delta triple tables, zero extra infra), Neo4j, or No Backend"; "source-available under the Databricks License". [primary] https://github.com/databrickslabs/ontobricks
- taka-yayoi sample [secondary]: https://github.com/taka-yayoi/graphrag_on_databricks
- Neo4j [secondary]: https://neo4j.com/partners/databricks/, https://neo4j.com/blog/developer/graph-and-lakehouse-friends-at-last/, https://neo4j.com/event/graphrag-in-action-building-smarter-ai-agents-with-neo4j-and-databricks/ (Neo4j-hosted webinar, part of MLCon Munich, 2026-06-23; speakers per search snippet only: Lee Razo, Neo4j; Hadi Farhat, Databricks) [single-source]
- PuppyGraph and community [secondary/opinion]: https://puppygraph.com/blog/databricks-knowledge-graph, https://community.databricks.com/t5/community-articles/turning-lakehouse-into-brainhouse-via-knowledge-graphs/m-p/152023
- DAIS: I found no Databricks-authored GraphRAG talk for 2024, 2025 or 2026. Found instead: DAIS 2025 "Building Knowledge Agents to Automate Document Workflows" (speakers not verified) and DAIS 2026 "Open Lineage Meets Graph: Observability for the Agentic Lakehouse" (lineage as a graph queried with Cypher; not GraphRAG). [unverified] https://www.databricks.com/dataaisummit/session/building-knowledge-agents-automate-document-workflows and https://www.databricks.com/dataaisummit/session/open-lineage-meets-graph-observability-agentic-lakehouse
- No native Databricks graph database or GraphRAG product announced as of 2026-10-02 in anything I read. [inferred from absence]
- GitHub searches for `lightrag databricks` and `graphrag lakebase` returned 0 results. [primary: GitHub search; negative evidence]

---

## Could not verify

1. Azure `southeastasia` per-model availability (model table truncated); the AWS `ap-southeast-1` model list was read through a summary.
2. AWS `ap-southeast-3` (Jakarta) feature rows: summary only.
3. Apps OBO preview status conflict (see Q5), and whether the late-September-2026 compliance-profile auto-enable shipped; whether it is enabled in a given workspace is admin-controlled.
4. Information Extraction GA: only Public Preview (2026-03-27) confirmed.
5. Unity AI Gateway rate-limit granularity.
6. AI Functions batch throughput (rows per second).
7. Vietnamese quality for Qwen3-Embedding and `ai_parse_document` (the docs warn only about non-Latin scripts such as Japanese and Korean).
8. Microsoft GraphRAG through LiteLLM to Databricks, end to end.
9. DAIS 2024/2025 Databricks-authored GraphRAG talks (session pages are dynamic; search inconclusive).
10. AI Search latency with OBO tokens, and reranker pricing.
11. Whether GPT-6/5.5 endpoints reject Chat Completions.
12. Local data-residency rules against cross-geo routing (out of scope).
13. License of `graphrag-demo`.

## Leads for other lanes

- Vietnamese retrieval-quality bake-off: Qwen3-Embedding-0.6B vs an external multilingual embedding model.
- Pydantic JSON-schema to Databricks structured-output compatibility shim (flatten `$ref`/`anyOf`; 64-key cap).
- Native-dependency wheels on serverless (aarch64 or x86_64) for GraphRAG engines.
- Local data-residency rules versus cross-geo routing (compliance lane).
- Neo4j-on-Databricks as an optional graph backend.
- A "Lakebase Search" blog (full text and vector search for Postgres) surfaced in results; not read. https://www.databricks.com/blog/lakebase-search-state-art-full-text-and-vector-search-postgres [unverified]

## Method and caveats

- Searches and fetches ran 2026-10-01 to 2026-10-02 against docs.databricks.com, learn.microsoft.com/azure/databricks, databricks.com, mlflow.org, pypi.org, GitHub and vendor sites.
- The fetch tool summarises pages with a small model; numbers marked † came through that summary. Several summaries guessed status labels (for example KA "Beta", Apps "GA") and were cross-checked against dated Learn copies or the GA blog.
- Page dates come from Learn `ms.date` front matter where available; undated pages are stated as such.
- PyPI JSON summaries gave implausible dates, so the MLflow release date was taken from the PyPI project page.

## Sources (dated)

1. Azure supported models, ms.date 2026-09-29 - https://learn.microsoft.com/en-us/azure/databricks/machine-learning/foundation-models/supported-models
2. Azure feature region support, ms.date 2026-10-01 - https://learn.microsoft.com/en-us/azure/databricks/resources/feature-region-support
3. Azure Databricks geos, ms.date 2026-09-11 - https://learn.microsoft.com/en-us/azure/databricks/resources/databricks-geos
4. AWS feature region support (undated) - https://docs.databricks.com/aws/en/resources/feature-region-support
5. Model region availability (undated) - https://docs.databricks.com/aws/en/unity-gateway/model-region-availability
6. ADI Services (undated) - https://docs.databricks.com/adi
7. FMAPI limits (undated) - https://docs.databricks.com/aws/en/machine-learning/foundation-model-apis/limits
8. Structured outputs, last updated 2026-09-11 - https://docs.databricks.com/aws/en/machine-learning/model-serving/structured-outputs
9. Unity Gateway release notes (PT governance GA 2026-08-24) - https://docs.databricks.com/aws/en/release-notes/unity-gateway/
10. Azure AI Search, ms.date 2026-09-14 - https://learn.microsoft.com/en-us/azure/databricks/ai-search/ai-search
11. AI Search best practices (undated) - https://docs.databricks.com/aws/en/ai-search/best-practices
12. Storage-optimized AI Search blog, 2026-03-09 - https://www.databricks.com/blog/decoupled-design-billion-scale-vector-search
13. AI Search pricing (undated) - https://www.databricks.com/product/pricing/vector-search
14. AI Search cost management (undated) - https://docs.databricks.com/aws/en/ai-search/cost-management
15. ai_parse_document (undated) - https://docs.databricks.com/aws/en/sql/language-manual/functions/ai_parse_document
16. ai_query (undated) - https://docs.databricks.com/aws/en/sql/language-manual/functions/ai_query
17. Intelligent document processing, ms.date 2026-09-11 - https://learn.microsoft.com/en-us/azure/databricks/agents/agent-bricks/intelligent-document-processing
18. Information Extraction, ms.date 2026-07-09 - https://learn.microsoft.com/en-us/azure/databricks/agents/agent-bricks/info-extraction
19. Knowledge Assistant (Learn, ms.date 2026-09-11) and GA blog (2026-01-27) - https://learn.microsoft.com/en-us/azure/databricks/agents/agent-bricks/knowledge-assistant
20. Supervisor Agent, ms.date 2026-09-11 - https://learn.microsoft.com/en-us/azure/databricks/agents/agent-bricks/multi-agent-supervisor
21. Prompt Registry (Azure), ms.date 2026-09-15 - https://learn.microsoft.com/en-us/azure/databricks/mlflow3/genai/prompt-version-mgmt/prompt-registry/
22. MLflow on PyPI, 3.16.1 released 2026-09-16 - https://pypi.org/project/mlflow/
23. Apps auth (Azure), ms.date 2026-09-28 - https://learn.microsoft.com/en-us/azure/databricks/dev-tools/databricks-apps/auth
24. What's coming (release notes) - https://docs.databricks.com/aws/en/release-notes/whats-coming
25. Genie Agents API (undated) - https://docs.databricks.com/aws/en/genie/conversation-api
26. Genie Ontology press release, 2026-06-16 - https://www.databricks.com/company/newsroom/press-releases/databricks-launches-genie-one-all-new-agentic-coworker-every-team
27. March 2026 release notes - https://docs.databricks.com/aws/en/release-notes/product/2026/march
28. Serverless environment versions (v6 released 2026-09-03) - https://docs.databricks.com/aws/en/release-notes/serverless/environment-version/
29. Databricks blog on knowledge-graph RAG, 2025-04-01 - https://www.databricks.com/blog/building-improving-and-deploying-knowledge-graph-rag-systems-databricks
30. OntoBricks (GitHub, undated) - https://github.com/databrickslabs/ontobricks
31. graphrag-demo (last push 2025-04-25) - https://github.com/databricks-industry-solutions/graphrag-demo
32. graphrag_on_databricks (GitHub, undated) - https://github.com/taka-yayoi/graphrag_on_databricks
33. Neo4j partner page, 2026-06-12 - https://neo4j.com/partners/databricks/
34. Neo4j blog, 2026-06-17 - https://neo4j.com/blog/developer/graph-and-lakehouse-friends-at-last/
35. Neo4j webinar, 2026-06-23 - https://neo4j.com/event/graphrag-in-action-building-smarter-ai-agents-with-neo4j-and-databricks/
36. PuppyGraph blog (vendor), 2026-05-09 - https://puppygraph.com/blog/databricks-knowledge-graph
37. Community article (opinion), 2026-03-25 - https://community.databricks.com/t5/community-articles/turning-lakehouse-into-brainhouse-via-knowledge-graphs/m-p/152023
38. Microsoft GraphRAG model config (undated) - https://microsoft.github.io/graphrag/config/models/
39. LiteLLM Databricks provider (undated) - https://docs.litellm.ai/docs/providers/databricks
40. ai_extract (undated) - https://docs.databricks.com/aws/en/sql/language-manual/functions/ai_extract
