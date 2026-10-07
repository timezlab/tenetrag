# Docs index

## Product
- [product/sdk-platform-brief.md](product/sdk-platform-brief.md) — TenetRAG design brief: goal, storage, auth, LLM, serving, benchmark, versioning, milestones, open questions (reviewed 2026-10-04)
- [product/domain-packs.md](product/domain-packs.md) — the graph schema as domain packs: node and edge kinds, pack format, how the pack drives the pipeline, schema design workflow, the v1 packs `core`, `enterprise-docs`, `finance` (draft)
- [product/engine-brief.md](product/engine-brief.md) — core engine: data model, ids, index pipeline, entity and event resolution, versions and as-of, `retrieve()` flow and output, agent methods, exact `GraphStore` and `VectorStore` methods, community details; decisions E1–E14 (reviewed 2026-10-05)
- [product/v1-packs.md](product/v1-packs.md) — schemas of the v1 default packs and why; industry packs such as banking are user packs; draft pack files in [product/packs/](product/packs/) (draft)

## Decisions
- [decisions/0001-build-own-graphrag-core.md](decisions/0001-build-own-graphrag-core.md) — own engine; MS GraphRAG / LightRAG are references, not dependencies (accepted; amended by 0009)
- [decisions/0002-graph-and-vector-storage-backends.md](decisions/0002-graph-and-vector-storage-backends.md) — graph in Delta or Postgres family, vectors in pgvector or AI Search; no Volumes/SQLite (accepted; amended by 0006 and 0008)
- [decisions/0003-caller-supplied-credentials.md](decisions/0003-caller-supplied-credentials.md) — explicit credentials, preflight matrix, never fall back to another identity (accepted)
- [decisions/0004-sdk-owned-versioning.md](decisions/0004-sdk-owned-versioning.md) — prompt and run versioning in the SDK via MLflow Prompt Registry (accepted)
- [decisions/0005-index-time-vs-query-time-parameters.md](decisions/0005-index-time-vs-query-time-parameters.md) — one parameter classification drives re-index, benchmark reuse and run records (accepted; amended by 0007)
- [decisions/0006-rename-to-tenetrag-and-run-beyond-databricks.md](decisions/0006-rename-to-tenetrag-and-run-beyond-databricks.md) — name TenetRAG; Postgres runs anywhere, Databricks first-class, graph DBs later; graph always built, graph-guided retrieval, optional vector/graph router (accepted; amended by 0008)
- [decisions/0007-define-the-graph-schema-as-layered-domain-packs.md](decisions/0007-define-the-graph-schema-as-layered-domain-packs.md) — schema as versioned, layered domain packs; engine owns evidence and time fields; own YAML compiled to flat schemas; v1 packs core, enterprise-docs, finance (accepted)
- [decisions/0008-build-databricks-and-open-branches-in-parallel.md](decisions/0008-build-databricks-and-open-branches-in-parallel.md) — Databricks branch (Lakebase default, Delta, pgvector default, AI Search optional) and open branch (Neo4j preferred, Postgres fallback) built in parallel; one contract suite; per-document consistency floor; AI Search only with Delta (accepted)
- [decisions/0009-reuse-permissive-libraries-behind-adapters.md](decisions/0009-reuse-permissive-libraries-behind-adapters.md) — LlamaIndex and other permissive libraries allowed outside the engine behind adapters, under six conditions (accepted)
- [decisions/0010-offer-query-strategies-as-opt-in-benchmarked-options.md](decisions/0010-offer-query-strategies-as-opt-in-benchmarked-options.md) — query strategies off by default, each a benchmark variant reported per question type; `retrieve_multi_step()`; conversational rewriting left to the agent (accepted)
- [decisions/0011-cluster-by-default-and-make-community-reports-opt-in.md](decisions/0011-cluster-by-default-and-make-community-reports-opt-in.md) — the graph is re-clustered by default with no LLM; community reports and `retrieve_global()` are opt-in and rewrite only changed communities (accepted)
- [decisions/0012-store-relations-and-facts-as-one-row-per-chunk.md](decisions/0012-store-relations-and-facts-as-one-row-per-chunk.md) — relations and facts are one row per statement per chunk with their own quote, time and status; parallel edges on Neo4j; deletes by `doc_id` (accepted)
- [decisions/0013-resolve-events-by-identity-and-version-facts-in-the-engine.md](decisions/0013-resolve-events-by-identity-and-version-facts-in-the-engine.md) — events merge within a document by time and roles, across documents only on pack `identity`; facts get versions through `version_key`; statuses computed in the engine (accepted)
- [decisions/0014-use-synchronous-protocols-with-one-hop-per-store-call.md](decisions/0014-use-synchronous-protocols-with-one-hop-per-store-call.md) — synchronous, batched protocols with a bounded thread pool; the store runs one `hop` per call and the engine composes hops (accepted)
- [decisions/0015-write-vectors-with-the-graph-when-one-store-holds-both.md](decisions/0015-write-vectors-with-the-graph-when-one-store-holds-both.md) — vectors go in the document's graph transaction when one store holds both; otherwise vectors first, then graph, then cleanup (accepted)
- [decisions/0016-identify-entities-by-scope-keys-and-vetoes.md](decisions/0016-identify-entities-by-scope-keys-and-vetoes.md) — names are labels, not identity: each entity type declares scope, keys, vetoes and a name rule; extraction quotes every identity value; identity cases in CI with zero wrong merges (accepted)
- [decisions/0017-allow-psycopg-as-a-narrow-license-exception.md](decisions/0017-allow-psycopg-as-a-narrow-license-exception.md) — psycopg and psycopg-pool (LGPL) allowed in the `postgres` extra only, unmodified and not vendored; every connection parameter passed explicitly (accepted)
- [decisions/0018-name-credential-sources-in-the-profile.md](decisions/0018-name-credential-sources-in-the-profile.md) — the profile names where a credential comes from, never its value; the OpenAI and Databricks SDKs' own environment reads are accepted with a warning (accepted)
- [decisions/0019-use-uv-ruff-mypy-pytest-and-import-linter-as-gates.md](decisions/0019-use-uv-ruff-mypy-pytest-and-import-linter-as-gates.md) — repository gates: uv with a 24-hour `exclude-newer`, ruff, mypy strict, pytest with the network blocked, import-linter, GitHub Actions pinned by SHA (accepted)

## Guides
- [guides/local-stack.md](guides/local-stack.md) — Neo4j and Postgres in Docker Compose: development and production modes, secret files, connecting the SDK, what joins later

## Reference
- [reference/databricks-platform.md](reference/databricks-platform.md) — verified, dated Databricks facts: Lakebase, OBO matrix, Volumes, AI Search, models, parsing, MLflow, regions
- [reference/neo4j-platform.md](reference/neo4j-platform.md) — verified, dated Neo4j facts: editions and licenses, version floors, vector and full-text search, transactions, modelling, reusable code
- [reference/graphrag-engines.md](reference/graphrag-engines.md) — source analysis of MS GraphRAG, LightRAG, LlamaIndex, RAGFlow, post-graph-rag, Graphiti, cognee, SAG, HippoRAG 2 and others: what to borrow, pitfalls, what no engine provides
- [reference/graphrag-research.md](reference/graphrag-research.md) — what papers show: where graphs beat plain RAG, evaluation pitfalls, MaGiX (Vietnamese–English), temporal, cost, query strategies; inputs for the engine brief
- [reference/supporting-libraries.md](reference/supporting-libraries.md) — license and Vietnamese-support check of community detection, embeddings, rerankers, text processing and parsers; LlamaIndex reuse audit and lighter alternatives
- [reference/graph-schema-design.md](reference/graph-schema-design.md) — schema features of 13 engines, schema components across formalisms (PG-Schema, LinkML, Wikidata…), evidence on schema design, practitioner rules, standards and their licenses
- [reference/domain-schemas.md](reference/domain-schemas.md) — evidence for the v1 packs: finance type inventories, finance and banking standards, the banking split, enterprise documents, glossaries and semantic layers, cross-domain types, datasets
- [reference/test-corpora.md](reference/test-corpora.md) — test data without adopter documents: synthetic corpus, public proxies with licenses and fit, running the real corpus in place

## Tech debt
- [tech-debt.md](tech-debt.md) — gaps and quirks left for later on purpose, each with where, why and the trigger to fix

## Research snapshots
Raw lane reports from 2026-10-02 to 2026-10-05, kept for detail and audit. They are not
maintained: each starts with its errata and a link to the reference doc that
holds the maintained, re-verified summary.

Round 1 — platform and core engines:
- [research/2026-10-02-databricks-storage-auth.md](research/2026-10-02-databricks-storage-auth.md) — Lakebase, identity and OBO, Volumes, synced tables, regions, compliance
- [research/2026-10-02-databricks-ai-integrations.md](research/2026-10-02-databricks-ai-integrations.md) — models, embeddings, cross-geo, parsing, AI Search, MLflow, serving, Databricks prior art
- [research/2026-10-02-factcheck-lakebase-obo.md](research/2026-10-02-factcheck-lakebase-obo.md) — fact-check of four load-bearing Lakebase and OBO claims
- [research/2026-10-02-core-engines-source.md](research/2026-10-02-core-engines-source.md) — MS GraphRAG, LightRAG, LlamaIndex in source: storage, data model, customization
- [research/2026-10-02-round1-digest.md](research/2026-10-02-round1-digest.md) — synthesis of round 1

Round 2 — wider engines, papers, libraries:
- [research/2026-10-02-landscape.md](research/2026-10-02-landscape.md) — GraphRAG project landscape, practitioner reports, vendors
- [research/2026-10-02-ragflow.md](research/2026-10-02-ragflow.md) — RAGFlow classic GraphRAG (v0.27.2) and Knowledge Compilation (v1.0.0-rc1)
- [research/2026-10-02-post-graph-rag.md](research/2026-10-02-post-graph-rag.md) — post-graph-rag: Postgres bi-temporal graph RAG
- [research/2026-10-02-kg-construction-libs.md](research/2026-10-02-kg-construction-libs.md) — Graphiti, cognee, neo4j-graphrag, R2R, Mem0, iText2KG, AutoSchemaKG, KGGen
- [research/2026-10-02-retrieval-algorithm-libs.md](research/2026-10-02-retrieval-algorithm-libs.md) — HippoRAG 2, SAG, fast-graphrag, NodeRAG, KAG and other retrieval algorithms
- [research/2026-10-02-papers.md](research/2026-10-02-papers.md) — GraphRAG literature 2024–2026
- [research/2026-10-02-magix.md](research/2026-10-02-magix.md) — MaGiX read in full from the PDF
- [research/2026-10-02-supporting-libs.md](research/2026-10-02-supporting-libs.md) — community detection, embeddings, rerankers, Vietnamese text, parsers

Follow-up — node model and retrieval flow:
- [research/2026-10-02-aws-graphrag-toolkit.md](research/2026-10-02-aws-graphrag-toolkit.md) — AWS graphrag-toolkit lexical graph, LightRAG chunk selection, and a review of a graph-first retrieval flow

Round 3 — graph schema (2026-10-03):
- [research/2026-10-03-schema-engine-customization.md](research/2026-10-03-schema-engine-customization.md) — how 13 engines define, enforce and evolve a schema, in source
- [research/2026-10-03-schema-papers.md](research/2026-10-03-schema-papers.md) — papers on schema-guided extraction, induction, CQ-driven ontology drafting, evaluation
- [research/2026-10-03-schema-practice.md](research/2026-10-03-schema-practice.md) — vendor and practitioner guidance, anti-patterns
- [research/2026-10-03-schema-domain-standards.md](research/2026-10-03-schema-domain-standards.md) — standards, datasets and starter schemas for 13 domains
- [research/2026-10-03-schema-metamodel.md](research/2026-10-03-schema-metamodel.md) — schema components across formalisms; LinkML, OntoGPT, PG-Schema verified in source
- [research/2026-10-03-schema-factchecks.md](research/2026-10-03-schema-factchecks.md) — fact-checks of the paper figures and the standards' licenses

Round 4 — v1 pack schemas (2026-10-04):
- [research/2026-10-04-pack-finance-papers.md](research/2026-10-04-pack-finance-papers.md) — finance IE, KG and QA papers: types, numbers, events
- [research/2026-10-04-pack-finance-banking-standards.md](research/2026-10-04-pack-finance-banking-standards.md) — FIBO, GLEIF, ISO, BIAN, BIRD, industry models, open banking, XBRL, BIS and IMF
- [research/2026-10-04-pack-banking-split.md](research/2026-10-04-pack-banking-split.md) — bank corpora and questions, domain splits, whether banking needs its own pack
- [research/2026-10-04-pack-enterprise-papers.md](research/2026-10-04-pack-enterprise-papers.md) — meetings, obligations, definitions and versions in papers
- [research/2026-10-04-pack-enterprise-practice.md](research/2026-10-04-pack-enterprise-practice.md) — enterprise knowledge products, glossaries, semantic layers, decision and RAID logs
- [research/2026-10-04-pack-core-types.md](research/2026-10-04-pack-core-types.md) — cross-domain types, positions, events, statements, Vietnamese NER inventories
- [research/2026-10-04-pack-factchecks.md](research/2026-10-04-pack-factchecks.md) — fact-checks of the pack papers, standards and licenses

Round 5 — backends, libraries, query strategies, agents (2026-10-04):
- [research/2026-10-04-neo4j-backend.md](research/2026-10-04-neo4j-backend.md) — Neo4j as a parallel `GraphStore`: licenses, search, writes, modelling, traversal, delete, parity with Postgres
- [research/2026-10-04-library-reuse.md](research/2026-10-04-library-reuse.md) — LlamaIndex read in source per pipeline step, side effects, lighter alternatives, proposed reuse rule
- [research/2026-10-04-query-strategies.md](research/2026-10-04-query-strategies.md) — HyDE, Query2doc, multi-query, decomposition, temporal parsing, HyPE: evidence and when they hurt
- [research/2026-10-04-schema-for-agents.md](research/2026-10-04-schema-for-agents.md) — how data agents discover schemas, MCP resources vs tools, enums in tool specs, evidence

Round 6 — communities (2026-10-05):
- [research/2026-10-05-graphrag-communities.md](research/2026-10-05-graphrag-communities.md) — how Microsoft GraphRAG v3.2.0 builds communities, writes reports and uses them in global, local and DRIFT search, with file:line

Round 7 — entity identity (2026-10-05):
- [research/2026-10-05-entity-homonyms.md](research/2026-10-05-entity-homonyms.md) — same-name entities: how engines, identity standards (FRBR, Akoma Ntoso, W3C ORG, Nghị định 30/2020) and papers keep homonyms apart; scoped-identity prototype; proposal revised by the next snapshot
- [research/2026-10-05-entity-identity-criteria.md](research/2026-10-05-entity-identity-criteria.md) — what makes an attribute identifying (OntoClean, minimal and conditional keys, temporal decay; Senzing, nomenklatura, Splink, Reltio; Vietnamese identifiers); key / veto / evidence / profile roles; identity suite (57 cases, 60 since 2026-10-06); revised proposal decided in ADR 0016

## Private
- `private/` — gitignored; adopter-specific notes that must never be committed
