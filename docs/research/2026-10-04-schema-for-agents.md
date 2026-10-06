# Exposing the graph schema to LLM agents — research report

> **Snapshot, 2026-10-04 — not maintained.** Web lane; medium confidence, several rows from search summaries. The maintained,
> re-verified summary is in the "Expose to agents" step in [domain-packs.md](../product/domain-packs.md#how-the-pack-is-used); where they differ, the maintained doc
> wins. Local paths were removed before publishing.
*2026-10-04 · ~30 sources read or searched · confidence: medium (precedents high; "schema tool helps" evidence indirect)*

## Summary (10 lines)
1. Every mainstream data-agent precedent ships a schema-discovery tool: Neo4j (`get_neo4j_schema`, official `get-schema`), LangChain SQL (`sql_db_list_tables`, `sql_db_schema`), GraphQL MCP (`introspect-schema`), dbt MCP (`get_all_models`, `get_model_details`, `list_metrics`).
2. Graphiti's MCP server is the counter-example: it takes entity types from server config but (as far as I verified) has no schema-read tool. Not verified for LightRAG.
3. MCP spec: tools are model-controlled; resources are application-driven. Clients mostly do not let the model read resources by itself (Claude Code, Cursor, Claude Desktop, OpenAI Agents SDK are all manual or tools-only; client behaviour moves fast, so re-check).
4. So a schema exposed ONLY as a resource is likely invisible to the agent. Expose a tool; optionally mirror as a resource.
5. Anthropic and OpenAI both say: detailed descriptions matter most, use enums, keep the tool count small (OpenAI under 20; Anthropic selection degrades past 30-50 tools). With 5 tools you are far below the limits.
6. Evidence: a perfect or filtered schema is an upper bound for text-to-SQL; "full schema" is fine when it fits and the model is strong. Weaker or smaller models and large schemas benefit from pruning. 40-50 types is a SMALL schema (a few thousand tokens), so full-schema injection is cheap.
7. The strongest signal for TenetRAG: KG agents hallucinate entity IDs and relation names (Graph Explorer, ACL 2026 Findings). Enums in tool params plus a clear error message that lists valid values attack this directly.
8. Tool-description enrichment is not free: +5.85 points median success, but +67% steps and 16.7% regressions (preprint). Keep it compact and test.
9. No study found that tests "schema-read tool vs no schema tool" on a pack-like ontology. That is a gap; the SDK should run its own eval from the competency questions.
10. Recommendation (end): enums in tool specs + a compact `describe_schema` tool with optional per-type detail + `pack_id`/`version`/`hash` in responses + a resource mirror; sanitize descriptions.

## 1. Precedents
| Precedent | Exact names | What it returns | Source |
|---|---|---|---|
| mcp-neo4j-cypher | `get_neo4j_schema`, `read_neo4j_cypher`, `write_neo4j_cypher` | JSON list of node labels with an attribute dict and a relationship dict. Needs APOC; samples 1,000 nodes/label by default (`NEO4J_SCHEMA_SAMPLE_SIZE`, per-call `sample_param`, `-1` = full scan). README advises 100-500 for large DBs. | [README](https://github.com/neo4j-contrib/mcp-neo4j/blob/main/servers/mcp-neo4j-cypher/README.md) |
| Official Neo4j MCP | `get-schema`, `read-cypher`, `write-cypher`, `list-gds-procedures` | Introspects labels, relationship types, property keys | [neo4j/mcp](https://github.com/neo4j/mcp) |
| neo4j-graphrag Text2CypherRetriever | params `neo4j_schema`, `examples`, `custom_prompt` | Schema and few-shot question/Cypher pairs are put in the generation prompt (not a tool) | [source](https://neo4j.com/docs/neo4j-graphrag-python/current/_modules/neo4j_graphrag/retrievers/text2cypher.html) |
| Graphiti MCP server | `add_memory`, `add_triplet`, `search_nodes`, `search_memory_facts`, `get_episode_entities`, `get_entity_edge`, `get_episodes`, `get_status`, others | No schema-read tool found. 10 built-in entity types (Preference, Requirement, Procedure, Location, Event, Person, Organization, Document, Topic, Object) come from `config.yaml`, used at ingestion. | [README](https://github.com/getzep/graphiti/blob/main/mcp_server/README.md) |
| LightRAG / other GraphRAG MCP | not verified | - | - |
| LangChain SQL toolkit | `sql_db_list_tables`, `sql_db_schema`, `sql_db_query`, `sql_db_query_checker` | List-then-describe-on-demand: schema fetched per table, with sample rows | [LangChain SQL agent docs](https://docs.langchain.com/oss/python/langchain/sql-agent/index.html) |
| Databricks Genie | no agent tool; Unity Catalog metadata | Genie uses table and column descriptions, PK/FK, sample values, column synonyms, example SQL; says description quality is critical; advises hiding unneeded columns | [Genie best practices](https://docs.databricks.com/gcp/en/genie/best-practices) |
| GraphQL MCP (blurrah/mcp-graphql) | `introspect-schema`, `query-graphql` | Description says: use introspect first "if you don't have access to the schema as a resource". Another server splits list-types and describe-type. | [repo](https://github.com/blurrah/mcp-graphql) (via search snippet; tool names not deep-read) |
| dbt MCP | `get_all_models`, `get_model_details`, `list_metrics`, `get_dimensions`, `get_entities`, `query_metrics` | Semantic layer: list, then detail, then query | [dbt docs](https://docs.getdbt.com/docs/dbt-ai/mcp-available-tools) |
| Vanna | not verified | - | - |

Pattern (inference): two shapes. (a) one blob schema tool (Neo4j, GraphQL); (b) list-then-describe (LangChain SQL, dbt). Shape (b) wins as schemas grow.

## 2. MCP: resource vs tool vs prompt
- Spec (revision 2026-07-28 shown as "latest"; 2025-06-18 resource page read): tools are "model-controlled"; resources are "application-driven", where the host decides how to include context; "database schemas" is a named resource example. Resources have `audience` and `priority` annotations. [Tools](https://modelcontextprotocol.io/specification/latest/server/tools), [Resources](https://modelcontextprotocol.io/specification/2025-06-18/server/resources).
- Tools spec (latest): servers SHOULD return tools in deterministic order (helps client and LLM prompt-cache hits); `tools/list` carries `ttlMs` and `cacheScope`; `outputSchema` is optional; tool annotations are untrusted unless the server is trusted.
- Client reality (mixed quality; re-verify before relying):
  - OpenAI Agents SDK: docs surface tools and prompts to the agent; resources are programmatic (`list_resources()`) only. [docs](https://openai.github.io/openai-agents-python/mcp/) `single-source`
  - langchain-mcp-adapters: `load_mcp_resources` returns LangChain Blob objects, so the developer loads them; not auto-exposed to the model. [reference](https://reference.langchain.com/python/langchain_mcp_adapters) (search snippet only)
  - Claude Code: as of 2025-10, a community report says resources are listed for @-mention but not auto-read; built-in `ListMcpResourcesTool` / `ReadMcpResourceTool` exist, with open bugs for HTTP servers. [report](https://glama.ai/mcp/servers/@DollhouseMCP/DollhouseMCP/blob/62c9b46e851b3753b28f2b916e6379c465abb9d3/docs/development/MCP_RESOURCES_SUPPORT_RESEARCH_2025-10-16.md), [bug](https://claudeissues.com/issue/11292-bug-mcp-http-server-resources-not-accessible-via-listmcpresourcestool-and-readmc). The official Claude Code MCP page I fetched does not describe resources. `single-source`, 12 months old.
  - Cursor: forum threads say resources unsupported or not read. [thread](https://forum.cursor.com/t/mcp-resources-support/151758) `single-source`
- Claude Code does lazy-load MCP tool definitions through ToolSearch by default and warns when a tool result exceeds 10,000 tokens (default max 25,000; per-tool override `_meta."anthropic/maxResultSizeChars"`, whose example is a `get_schema` tool). [Claude Code MCP docs](https://code.claude.com/docs/en/mcp). Consequence: a schema tool result must stay well under 10k tokens.
- Conclusion (inference): tool = what the agent reliably uses; resource = convenience for human attach/hosts that support it. Do both, one source of truth.

## 3. Dynamic tool specs (enums etc.)
- Anthropic: "Provide extremely detailed descriptions... by far the most important factor"; at least 3-4 sentences per tool; `input_examples` optional (~20-50 tokens simple, 100-200 complex); consolidate related operations; namespace names. [Define tools](https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools)
- Anthropic: tool-selection accuracy degrades past 30-50 tools; typical multi-server setup ~55k tokens of definitions; tool search recommended at 10+ tools or >10k tokens of definitions; <10 tools or <100 tokens total, standard calling is fine. [Tool search](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-search-tool)
- Anthropic engineering: namespacing and response format have non-trivial effect on evals and vary by model; evaluate yourself. [Writing tools for agents](https://www.anthropic.com/engineering/writing-tools-for-agents) (via secondary summary; not deep-read)
- OpenAI: "fewer than 20 functions" at the start of a turn; use enums and object structures to prevent invalid states; definitions count against context; `strict: true` needs `additionalProperties:false` and all properties required. [Function calling](https://developers.openai.com/api/docs/guides/function-calling)
- Enum size limits: NOT verified (the OpenAI structured-outputs page I fetched truncated before listing limits; I recall a total-enum-values cap in strict mode but did not confirm). Check before generating a 50-value enum.
- Inference: 40-50 types split over 3 params (entity types ~15, relation types ~20, fact types ~10) is small. Per-param enum text costs roughly one short line per type. Stacked packs change enums, so the tool spec must be generated from the merged pack and re-generated when the pack changes (and the generated spec hashed).
- Caveat: an enum on `find_entity(type)` can hide a good fallback (e.g. user typo). Return errors that list valid values.

## 4. Evidence on schema in context
| Finding | Label | Source |
|---|---|---|
| With strong reasoning models, schema linking (filtering) can be skipped when the full schema fits; filtering can drop needed columns. A perfect schema is still an upper bound; full schema costs tokens. 71.83% BIRD. Maamari et al. 2024. | [preprint] (NeurIPS 2024 workshop listing) | [arXiv 2408.07702](https://arxiv.org/abs/2408.07702) |
| Text2Cypher schema filtering (Ozsoy 2025): exact-match pruned schema best for Llama-3.1-8B; small models do better with shorter prompts; Gemini-1.5-Flash better with longer; pruning helps cost for all. Numeric table not extracted. | [peer-reviewed workshop paper (LLM-TEXT2KG 2025)] | [arXiv 2505.05118](https://arxiv.org/pdf/2505.05118v1) (details via search summary) |
| Spider 2.0 style enterprise schemas (1,000+ columns, up to ~2.6M tokens) break full-schema prompting; retrieval/pruning required. Benchmarks like Spider/BIRD have small schemas. | [preprint/benchmark], summary only | [BEAVER](https://arxiv.org/html/2409.02038v1) |
| Schema-agnostic graph agent discovering structure at runtime: 88.4% vs 83.3% for full-context baseline on 258 questions, under 1/3 input tokens; needs a model that drives tools reliably. | [preprint], single benchmark | [arXiv 2608.15834](https://arxiv.org/abs/2608.15834) |
| KG agents often hallucinate entity IDs and relation names in tool-call arguments. | [peer-reviewed] (ACL 2026 Findings, abstract only) | [Graph Explorer](https://preview.aclanthology.org/ingest-acl/2026.findings-acl.387/) |
| MCP tool descriptions: 97.1% of 856 tools have at least one smell; augmenting all components: median +5.85 pts success, +67.46% steps, regressions in 16.67% of cases; removing Examples does not significantly hurt; no component combo wins everywhere. | [preprint] | [arXiv 2602.14878](https://arxiv.org/html/2602.14878v1) |
| Genie: description quality "critical", hide irrelevant columns. | [vendor] | [Genie best practices](https://docs.databricks.com/gcp/en/genie/best-practices) |

Reading (inference): (1) giving the agent the schema helps; evidence is strongest for generation tasks (SQL/Cypher) where wrong names are fatal. (2) Length hurts mainly small models and huge schemas. (3) A 40-50 type pack is closer to Spider/BIRD than to enterprise-scale, so full injection is affordable; compactness is for cost and focus, not necessity. (4) Disconfirming: Maamari shows modern models handle noise, so a schema tool's value is smaller for strong models; and the 2602.14878 result shows more text can cause more steps and regressions.

## 5. Design options [inferred]
**A. Full YAML.** Faithful but verbose, includes authoring metadata (competency questions, internal notes, extraction hints). Not agent-oriented. Use only for human/debug.
**B. Compact agent summary (default).** Per type: name, one-line description, for relations the allowed endpoint types and time kind, for fact types the typed roles, enum values inline, 1-2 example queries drawn from competency questions. Target: under about 3-4k tokens for 50 types (estimate), clearly below the 10k warning in Claude Code.
**C. On-demand detail.** `describe_schema(type_name)` returns full description, examples, roles. Mirrors LangChain list-then-describe and the GraphQL type-describe tool.
**Combine:** B in the first call (or even in the system-prompt text the SDK offers) and C for drill-down.
**Tool spec generation:** enums for `entity_type`, `relation_types`, `fact_types` generated from the merged pack; `as_of` described as ISO date.
**Versioning:** include `pack_name`, `pack_version`, `schema_hash` (hash of merged stack) and `generated_at` in every schema response and optionally in tool-spec metadata. Lets agents/clients cache; changes in hash signal a re-read. Keep tool order deterministic (MCP spec recommends, helps prompt caching). Emit `notifications/tools/list_changed` if packs hot-reload.
**Security:** the schema reveals what the organization tracks (type names, descriptions, examples, competency questions). User-written descriptions and examples may contain internal terms, customer names, or prompt-injection text (descriptions go straight into the model context; MCP says tool annotations are untrusted from untrusted servers). Mitigations: separate "agent-visible" fields from private authoring fields in the pack format; do not expose competency questions verbatim unless flagged; apply caller authorization (spec allows `tools/list` to vary by authorization); lint descriptions at pack-load time; never include sample data values from documents. For TenetRAG's public repo rule (no adopter data in git), keep adopter packs under `docs/private/`.

## Recommendation
Yes, offer it, and offer it as a **tool**, not only a resource.
1. Generate tool specs from the merged pack, with enums and short per-parameter descriptions. Make invalid-value errors return the valid set.
2. Add `describe_schema(detail="summary"|"type", name=None)` (tool name is a proposal; not an existing standard) returning the compact agent summary (option B) plus pack name, version, hash; `name` returns option C detail.
3. Expose the same summary as an MCP resource (e.g. a `tenetrag://schema` URI, proposal) for hosts that attach resources; do not depend on it.
4. Add an `agent-visible` flag/field set in the pack format so authoring notes and sensitive text never leave the process.
5. Evaluate before declaring victory: build a small eval from the competency questions, comparing (no schema) vs (enums only) vs (enums + summary) vs (enums + describe tool), measuring invalid-arg rate, tool-call count, answer accuracy, tokens, on at least two model sizes. Public evidence does not settle this for ontology-style graph tools.

## Gaps and caveats
- Not verified: LightRAG MCP, Vanna, OpenAI enum limits, Cursor and Claude Code resource behaviour as of 2026-10 (reports are about 12 months old or from forums).
- Several evidence rows come from search-tool summaries (Ozsoy 2025 numbers, BEAVER, Graph Explorer abstract); open the PDFs before quoting numbers.
- Graphiti "no schema tool" is inferred from README tool list; I did not read the server code.
- No study found directly comparing "schema tool" against "no schema" for tool-calling over a typed temporal graph.

## Sources
1. [mcp-neo4j-cypher README](https://github.com/neo4j-contrib/mcp-neo4j/blob/main/servers/mcp-neo4j-cypher/README.md) (read, 2026)
2. [neo4j/mcp](https://github.com/neo4j/mcp) (read, 2026)
3. [Graphiti MCP README](https://github.com/getzep/graphiti/blob/main/mcp_server/README.md) (read, 2026)
4. [MCP resources spec 2025-06-18](https://modelcontextprotocol.io/specification/2025-06-18/server/resources) (read)
5. [MCP tools spec, latest = 2026-07-28](https://modelcontextprotocol.io/specification/latest/server/tools) (read)
6. [Anthropic define tools](https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools) (read, 2026)
7. [Anthropic tool search](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-search-tool) (read, 2026)
8. [OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling) (read, 2026)
9. [Claude Code MCP docs](https://code.claude.com/docs/en/mcp) (read, 2026)
10. [OpenAI Agents SDK MCP](https://openai.github.io/openai-agents-python/mcp/) (read, 2026)
11. [arXiv 2408.07702 Death of Schema Linking](https://arxiv.org/abs/2408.07702) (2024-08)
12. [arXiv 2602.14878 MCP tool descriptions smelly](https://arxiv.org/html/2602.14878v1) (2026-02)
13. [arXiv 2608.15834 schema-agnostic graph agent](https://arxiv.org/abs/2608.15834) (2026-08)
14. [arXiv 2505.05118 Text2Cypher schema filtering](https://arxiv.org/pdf/2505.05118v1) (2025-05)
15. [Graph Explorer, ACL 2026 Findings](https://preview.aclanthology.org/ingest-acl/2026.findings-acl.387/) (2026)
16. [LangChain SQL agent](https://docs.langchain.com/oss/python/langchain/sql-agent/index.html) (snippet)
17. [dbt MCP tools](https://docs.getdbt.com/docs/dbt-ai/mcp-available-tools) (snippet)
18. [Genie best practices](https://docs.databricks.com/gcp/en/genie/best-practices) (snippet)
19. [neo4j-graphrag text2cypher source](https://neo4j.com/docs/neo4j-graphrag-python/current/_modules/neo4j_graphrag/retrievers/text2cypher.html) (snippet)
20. [blurrah/mcp-graphql](https://github.com/blurrah/mcp-graphql) (snippet)
21. [BEAVER](https://arxiv.org/html/2409.02038v1) (snippet)
22. Resource-support community reports: [DollhouseMCP report](https://glama.ai/mcp/servers/@DollhouseMCP/DollhouseMCP/blob/62c9b46e851b3753b28f2b916e6379c465abb9d3/docs/development/MCP_RESOURCES_SUPPORT_RESEARCH_2025-10-16.md), [Cursor forum](https://forum.cursor.com/t/mcp-resources-support/151758) (snippets)

## Method
Tier: open survey, single agent. ~25 tool calls (search plus fetch). Sub-questions: precedents; MCP resources vs tools; tool-spec/enum guidance; evidence; design options.
