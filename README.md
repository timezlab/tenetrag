# TenetRAG

**T**emporal **E**ntity **N**etwork with **E**vidence **T**rails for
Retrieval-Augmented Generation.

A Python SDK for GraphRAG. It builds a domain-defined knowledge graph of
dated, evidence-backed facts from your documents, uses that graph to find the
right chunks, and returns both to the agents you build yourself, through a
Python API, tool specs or an MCP server. It runs anywhere on Neo4j
(preferred) or Postgres, or natively on Databricks: Lakebase (default) or Unity Catalog
Delta tables for the graph, pgvector (default) or Databricks AI Search for
vectors.

> **Status: design phase.** No code or releases yet. Nothing here is
> installable.

## Planned capabilities (v1)

- Index PDF, DOCX, PPTX, XLSX, Markdown and text from a UC Volume, Workspace
  folder or local folder. A plan shows counts, sizes, changes and estimated
  cost before anything runs.
- Incremental updates and deletes by document.
- Graph-guided retrieval: every fact comes with its source chunk, document
  and date. An optional router sends simple questions to plain vector search.
- Opt-in query strategies (time-constraint parsing, entity extraction,
  bilingual and multi-query variants, questions per chunk), each measurable
  in the benchmark.
- Communities: each run groups the graph into topic clusters without an
  LLM. Community reports and global questions over the whole corpus are
  opt-in.
- Agents read the schema: tool specs list the pack's types, and
  `describe_schema` returns a compact summary.
- Explicit credentials (PAT, OAuth, OBO) that fail closed.
- LLMs from Databricks serving endpoints, OpenAI-compatible APIs or Anthropic.
- Benchmarks over your golden set with MLflow, RAGAS and DeepEval.
- Runs fully offline for development: local Neo4j or Postgres and fake
  models.

## Learn more

- [Design brief](docs/product/sdk-platform-brief.md): scope, milestones, open
  questions
- [Architecture](ARCHITECTURE.md): module map and dependency rules
- [Docs index](docs/index.md): decisions and reference
