# GraphRAG landscape, practitioner view, vendors (as of 2026-10-02)

> **Snapshot, 2026-10-02 — not maintained.** Round 2 web research lane:
> landscape of GraphRAG projects (stars, releases, licenses), practitioner
> reports and vendor positioning. The maintained, re-verified summary is in
> [graphrag-engines.md](../reference/graphrag-engines.md) and
> [graphrag-research.md](../reference/graphrag-research.md); where they
> differ, the maintained doc wins.
>
> **Errata and later resolutions:**
> - post-graph-rag does not use "two tables" for the graph. It sits on a
>   generic JSONB property-graph layer (`post-graph`) with vertex tables
>   `documents` (one row per chunk), `entities` and `communities`, and edge
>   tables `relations`, `doc_mentions`, `community_members` and
>   `community_children`; see
>   [2026-10-02-post-graph-rag.md](2026-10-02-post-graph-rag.md).

Labels: verified (read primary: GitHub API or PyPI, today), reported (read, third-party or self-reported), anecdotal (blog or opinion), inferred (mine).
Caveat: stars and push dates come from api.github.com fetched 2026-10-02. PyPI upload times returned by the fetch summarizer looked unreliable (e.g. graphiti 0.30.2 "2025-01"), so release dates use GitHub releases where I fetched them, and are blank otherwise.

## 1. Landscape table

| Project | Stars | Latest release (source) | License | Last push | Positioning |
|---|---|---|---|---|---|
| RAGFlow | 91.6k | v1.0.0-rc1, 2026-09-29 (GH) | Apache-2.0 | 2026-10-01 | Full RAG engine with agents and DeepDoc parsing; rc1 is a Go rewrite, irreversible migration from v0.27.2 |
| mem0 | 66.5k | PyPI 2.2.1 (date n/a) | Apache-2.0 | 2026-10-01 | Agent memory layer, not document GraphRAG |
| LightRAG | 40.0k | v1.5.7, 2026-09-02 (GH) | MIT | 2026-10-01 | Lightweight graph+vector RAG, EMNLP 2025, server and UI |
| Microsoft GraphRAG | 36.2k | 3.2.0, 2026-09-23 (PyPI) | MIT | 2026-09-28 | Community-summary GraphRAG, maintenance mode |
| Graphiti (Zep) | 31.4k | v0.30.2, 2026-09-08 (GH) | Apache-2.0 | 2026-09-30 | Temporal knowledge graph for agent memory, needs a graph DB (FalkorDB, Neo4j) |
| cognee | 31.3k | v1.6.2, 2026-09-29 (GH) | Apache-2.0 | 2026-10-02 | Memory/knowledge engine, pipelines, many backends |
| Kotaemon | 25.8k | n/a | Apache-2.0 | 2026-07-14 | Document-chat UI, GraphRAG optional; push cadence slowing |
| txtai | 13.0k | PyPI 9.13.0 (date n/a) | Apache-2.0 | 2026-10-01 | Embeddings DB and workflows with a semantic-graph feature |
| KAG (OpenSPG) | 9.1k | n/a | Apache-2.0 | 2026-01-28 | Logical-form reasoning over KGs, domain-heavy; no push for 8 months |
| R2R | 8.0k | PyPI 3.6.6 | MIT | 2025-11-07 | Agentic RAG service with graph; stale for 11 months |
| HippoRAG | 4.0k | PyPI 2.0.0a4 (alpha) | MIT | 2026-10-01 | Research code (PPR over a KG); still alpha on PyPI |
| nano-graphrag | 4.0k | PyPI 0.0.8.2 | MIT | 2026-01-27 | Hackable GraphRAG reference, effectively dormant |
| fast-graphrag | 4.0k | PyPI 0.0.5 | MIT | 2025-11-01 | PageRank-based GraphRAG, dormant |
| neo4j-graphrag-python | 1.3k | 1.22.0, 2026-10-01 (PyPI) | Apache-2.0 on PyPI (GH API said "Other") | 2026-10-01 | Neo4j's official GraphRAG library, needs Neo4j |
| FalkorDB GraphRAG-SDK | 1.0k | PyPI graphrag-sdk 1.4.0 | Apache-2.0 | 2026-09-30 | FalkorDB-only; v1.0 rewrite touts production pipeline |
| Memgraph ai-toolkit | 0.1k | n/a | MIT | 2026-10-02 | Memgraph MCP and tools; negligible adoption |

All stars, license and push dates: verified from GitHub API 2026-10-02. Release rows: verified where a source is named.

Missing project found: post-graph-rag (Chandan Rajah, arXiv 2608.24921, submitted 2026-08-14). It is a PostgreSQL-only Graph RAG engine with pgvector, two tables for the graph, a bi-temporal model, a controlled predicate vocabulary and bounded k-hop SQL. It is the closest analogue to our design. Reported, single source, self-benchmarked: LongMemEval 94.0%, ECT-QA 0.807 vs 0.599 and 0.406. Temporal fields in synthesis lifted temporal reasoning from 0.496 to 0.881. [arXiv](https://arxiv.org/abs/2608.24921) (2026-09); [everydev listing](https://www.everydev.ai/tools/post-graph-rag).
Gap: I did not scan GitHub trending for other 2025-26 entrants.

## 2. Practitioner findings

Hard evidence on named-company production deployments is thin. This is the main finding.

- "We barely know of any examples of production deployments that are offering real business value" (Gradient Flow, cited by a 2026 blog). Teams that succeed use GraphRAG for the 15-20% of queries that vector search cannot answer, not as a replacement. Anecdotal. [tianpan.co](https://tianpan.co/blog/2026/04/12/graphrag-production-when-vector-search-fails-multi-hop-reasoning) (2026-04)
- Indexing cost and time, secondary figures: GraphRAG index 5,500-7,700 s vs 135 s for standard RAG; query latency 14.4 s vs 1.7 s; LightRAG at about $0.15 per doc set vs $4-7 for full GraphRAG. Only 65.8% of answer entities exist in the built graph. MultiHop-RAG 71.2% vs 65.8%. Reported, secondary blog quoting papers. Same URL (2026-04).
- A "$33,000 to index 5 GB of legal text (early 2024)" claim circulates. Paywalled Medium, not verified. Anecdotal. [Medium](https://medium.com/graph-praxis/the-graphrag-cost-cliff-how-33-000-became-33-in-eighteen-months-be1b0fbe37e4) (2026)
- RAGSearch benchmark (arXiv 2604.09666, 2026-04), measured: single-shot GraphRAG beats dense RAG on multi-hop by about 27 points. Agentic search closes about 32% of that gap. Offline GraphRAG cost exceeds $13 per million tokens. GraphRAG has lower run-to-run variance. Conclusion: dense RAG plus agentic workflow is the best value for general use. [alphaxiv](https://www.alphaxiv.org/abs/2604.09666)
- SAP-affiliated paper (arXiv 2507.03226, 2025-07), measured on two enterprise code-migration datasets: dependency-parse graph construction reached 94% of LLM-extraction quality (61.87% vs 65.83%) at much lower cost. Hybrid vector plus graph with RRF beat vector baselines by up to 15% and 4.35%. Affiliation was not stated in the fetched abstract. [arXiv](https://arxiv.org/abs/2507.03226)
- Failure modes (entity fragmentation, cascading update conflicts, incremental extraction needing conflict-resolution logic): reported by tianpan (anecdotal). The post-graph-rag paper independently argues that baseline GraphRAG never supersedes old relations because it has no temporal model. This is relevant to the "conflicting versions" requirement.
- I found no named-company "we switched from GraphRAG to X" posts. The searches turned up only generic pieces recommending BM25 plus vector plus reranker. Gap.

## 3. Vendor convergence

- Microsoft: LazyGraphRAG (no up-front summarization, about 0.1% of full indexing cost) is integrated into Microsoft Discovery and Azure Local (public preview, editor's note 2025-06). [MS Research](https://www.microsoft.com/en-us/research/blog/lazygraphrag/) (2025-06). Verified. GraphRAG repo itself is still releasing (3.2.0, 2026-09-23).
- AWS: Bedrock Knowledge Bases GraphRAG with Neptune Analytics, GA 2025-03-07. It auto-extracts entities, stores vectors and graph in Neptune Analytics, with no extra charge beyond the underlying services. [AWS](https://aws.amazon.com/about-aws/whats-new/2025/03/amazon-bedrock-knowledge-bases-graphrag-generally-available) Verified.
- Neo4j: official `neo4j-graphrag` 1.22.0, with Databricks partnership pages and webinars scheduled for 2026. [neo4j.com/databricks](https://neo4j.com/databricks/) Reported.
- FalkorDB: GraphRAG SDK 1.0 and 1.4.0, vendor content on cutting indexing cost. Reported, vendor.
- Postgres: Azure Database for PostgreSQL docs have a GraphRAG module using Apache AGE with pgvector; Snowflake's engineering blog covers Postgres plus AGE graph queries. Reported. Pure-SQL alternative: post-graph-rag.
- NOT covered (budget): Google Spanner Graph/Vertex, Snowflake Cortex, Elastic, Weaviate, Qdrant. Gap.
- Convergence (inferred from the above): vector entry point, then bounded 1-2 hop expansion, with RRF or rerank fusion, and a managed extraction step. Community summaries are being dropped or deferred (LazyGraphRAG). Vendors sell "turn it on" extraction; they do not publish quality numbers.

## 4. Databricks angle

- Only first-party GraphRAG blog found: "Building, Improving, and Deploying Knowledge Graph RAG Systems on Databricks" (2025-04-01). It uses Neo4j as the graph, loads from Delta via the Neo4j Spark Connector, text2cypher and GraphCypherQAChain, and deploys through Mosaic AI Agent Framework and MLflow. There are no quantitative results. [Databricks](https://databricks.com/blog/building-improving-and-deploying-knowledge-graph-rag-systems-databricks) Verified.
- Neo4j and Databricks pitch "GraphRAG apps with Agent Bricks"; webinars 2026-03 and 2026-06. Vendor marketing. [neo4j.com](https://neo4j.com/partners/databricks/)
- Agent Bricks Knowledge Assistant: document Q&A with citations. I found no graph component in it. [MS Learn](https://learn.microsoft.com/fil-ph/azure/databricks/generative-ai/agent-bricks/knowledge-assistant) Inferred: it is vector-based.
- GraphFrames: community-maintained, mostly by Databricks contributors. It has PageRank, connected components, SCC, label propagation, triangle count, shortest paths, BFS and motif finding. Spark 4 and Spark Connect artifacts exist (connect-spark4 2026-03-31; 0.12.1 in 2026-06 per a search summary). Reported, not read on GitHub. Inferred: usable for batch entity-resolution clustering (connected components) over Delta, not for query-time traversal.
- Lakebase plus pgvector GraphRAG: I found no first-party example and no Databricks-native GraphRAG since mid-2025. Gap, and possibly a white space.

## 5. Emerging practice

- Contextual retrieval (Anthropic, 2024-09-19), measured: top-20 retrieval failure 5.7% to 3.7% (contextual embeddings), 2.9% (plus BM25), 1.9% (plus reranking). Cost about $1.02 per million document tokens with prompt caching. [Anthropic](https://www.anthropic.com/news/contextual-retrieval) Verified (self-reported benchmark).
- Hybrid BM25 plus vector plus reranker as baseline: supported by the Anthropic numbers above. A "15-30% / 10-20%" claim appeared in search snippets and is anecdotal and unverified. A 2026 arXiv paper (2609.01617) on hybrid RAG with KG expansion and RRF for enterprise search surfaced; I did not read it.
- Agentic retrieval vs GraphRAG: RAGSearch (above) is the best measured evidence. Agentic search narrows but does not close the multi-hop gap, and GraphRAG is more stable.
- "GraphRAG is dead": no decisive evidence found either way. The 2026 consensus in sources I read is "when and which". Opinion-level.
- Late chunking: not researched (budget). Gap.

## 6. Implications for our design (inferred)

1. Make hybrid chunk retrieval (BM25 or Postgres FTS plus pgvector plus reranker, with contextual chunk prefixes) the default path and ship it first. The graph is an augmentation layer, consistent with the "15-20% of queries" finding.
2. Use vector-seeded bounded k-hop expansion in SQL, with no community summaries. Our questions are entity-centric and temporal, not global. LazyGraphRAG and post-graph-rag both point away from eager summarization.
3. Model time explicitly: validity interval, source document and supersession on every relation. Baseline GraphRAG lacks this, and conflicting versions are our core use case.
4. Constrain extraction with a controlled predicate vocabulary and canonical entity resolution. Run resolution in batch (GraphFrames connected components is an option on Delta) and keep alias tables for Vietnamese diacritics and variants.
5. Make extraction incremental per document (hash, re-extract, retract old facts by document id). Update pain is the most-cited failure mode.
6. Consider cheaper extraction for part of the corpus (the SAP paper found dependency parsing gave 94% of the quality). Caveat: this is English-centric, so Vietnamese needs a separate evaluation.
7. Expose small traversal tools (find_entity, neighbors, facts_about(entity, as_of), sources_for) so an agent can walk the graph. This fits the RAGSearch finding that agentic search captures much of the structure benefit.
8. Lakebase/pgvector GraphRAG on Databricks has no first-party example, so we can fill the gap. Plan our own golden set and measure against the plain hybrid baseline, because public numbers are mostly vendor or self-benchmarked.

## Sources
- GitHub API per repo (infiniflow/ragflow, HKUDS/LightRAG, getzep/graphiti, microsoft/graphrag, topoteretes/cognee, neo4j/neo4j-graphrag-python, OSU-NLP-Group/HippoRAG, OpenSPG/KAG, SciPhi-AI/R2R, gusye1234/nano-graphrag, circlemind-ai/fast-graphrag, Cinnamon/kotaemon, neuml/txtai, FalkorDB/GraphRAG-SDK, mem0ai/mem0, memgraph/ai-toolkit) (2026-10-02)
- PyPI JSON for lightrag-hku, graphiti-core, cognee, neo4j-graphrag, graphrag, mem0ai, txtai, graphrag-sdk, hipporag, r2r, nano-graphrag, fast-graphrag (2026-10-02)
- Links as cited inline above
