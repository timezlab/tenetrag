# Reuse permissive libraries behind adapters, outside the engine

**Status:** accepted; exceptions granted by
[ADR 0017](0017-allow-psycopg-as-a-narrow-license-exception.md) (psycopg
under LGPL) and
[ADR 0018](0018-name-credential-sources-in-the-profile.md) (the OpenAI and
Databricks SDKs' environment reads), both 2026-10-06.
**Date:** 2026-10-04
**Deciders:** Liam Lee (session 2026-10-04)

## Context
[ADR 0001](0001-build-own-graphrag-core.md) made us write our own engine.
It also banned any runtime dependency on `graphrag`, `lightrag-hku` and
`llama-index-*`. That ban targeted wrapping those projects as engines. The
author wants to reuse existing libraries, LlamaIndex included, at the steps
where they fit the flow without conflict.

A source audit on 2026-10-04 read `llama-index-core` 0.14.25 (2026-09-21)
and lighter alternatives
([snapshot](../research/2026-10-04-library-reuse.md); summary in
[supporting-libraries.md](../reference/supporting-libraries.md#reuse-audit-2026-10-04)).
It found:
- **Ambient credentials.** `Settings.llm` and `Settings.embed_model` default
  to OpenAI and read `OPENAI_API_KEY` on first access. Many components fall
  back to `Settings.llm` when no model is passed. The Databricks LLM class
  falls through to `OPENAI_API_KEY` when its own variables are unset. Each
  of these breaks [ADR 0003](0003-caller-supplied-credentials.md) unless
  every object is passed explicitly.
- **Import weight.** 25 required dependencies. `import llama_index.core`
  imports SQLAlchemy and Pillow eagerly.
- **Provenance.** Splitters recover character offsets with `str.find` after
  stripping the chunk, use `uuid4` ids by default and count tokens with the
  gpt-3.5 tiktoken encoding.
- **Pipeline conflicts.** `IngestionPipeline` hashes text plus all metadata
  and keeps its own docstore, which conflicts with our two-level hashing and
  run model. The property-graph extractors emit triples with no dates,
  evidence or facts and bypass our pack compiler.
- **Small pieces.** HyDE is about 25 lines and RRF about 25.
  `StepDecomposeQueryTransform` says "NOTE: doesn't work yet."
- **Churn.** 20 core releases in 12 months, with small breaking changes in
  patch versions.
- **Better fits elsewhere.** `semchunk` (MIT, one dependency) returns exact
  offsets by construction. pypdf, python-docx, python-pptx and openpyxl
  work directly. `bm25s`, sentence-transformers `CrossEncoder` and the
  MLflow RAGAS and DeepEval scorers cover sparse search, reranking and
  evaluation.

## Decision
1. **Reuse is allowed outside `engine`.** A third-party library, LlamaIndex
   included, may be used in `ingest`, `llm`, `storage`, `benchmark` or a
   `serving` adapter. It sits behind an adapter that implements one of our
   protocols or registries, and all six conditions hold:
   1. The license is permissive (MIT, BSD, Apache-2.0 or equivalent). No
      GPL or AGPL, even as an option.
   2. It lives in an optional extra. Importing the base package does not
      import it.
   3. It reads no ambient credentials. The adapter passes every key, token,
      endpoint and base URL explicitly. A missing one raises `AuthError`,
      never a fallback to environment variables, module globals such as
      `Settings` or `openai.api_key`, or another identity.
   4. It sends no telemetry. It downloads nothing at import or first use,
      unless the adapter exposes the download as an explicit, documented
      step that can be turned off.
   5. It owns none of these: chunk ids, offsets, hashes, run or transaction
      state, the graph schema. The adapter produces our deterministic ids
      and hashes and checks `text[start:end] == chunk`.
   6. Its version is pinned, with a golden test wherever its output feeds
      chunking or hashing.
2. **`engine` keeps its import rule:** protocols, `config` and `packs`
   only. Small algorithms such as RRF and query transforms are written in
   `engine`. A ported one keeps an attribution comment naming the source
   repo, tag and file.
3. **`graphrag` and `lightrag-hku` stay references.** They are never
   imported, and no engine is wrapped.
4. **Starting choices from the audit.** Each still passes the dependency
   gate before it is added.

   | Step | Choice | Where |
   |---|---|---|
   | PDF | pypdf; Docling as an optional layout extra | `ingest` parser registry |
   | DOCX, PPTX, XLSX | python-docx, python-pptx, openpyxl; markitdown optional | `ingest` parser registry |
   | Chunking | semchunk inside our wrapper, which sets offsets, ids and hashes | `ingest` |
   | Hashing, incremental index | our own code | `ingest` |
   | LLM and embedding clients | thin classes over the official SDKs | `llm` |
   | Query transforms, RRF | our own code | `engine` |
   | Rerank | sentence-transformers `CrossEncoder` with `trust_remote_code=False`; LLM rerank prompt of our own | `llm`, extra `rerank` |
   | In-memory sparse search | bm25s with stopwords off | tests and small corpora |
   | Evaluation | MLflow scorers with RAGAS and DeepEval | `benchmark`, extra `bench` |

5. **LlamaIndex in v1:** an optional `llamaindex` extra that exposes the
   TenetRAG retriever as a LlamaIndex retriever, beside the LangChain
   adapter. Inside the pipeline, a LlamaIndex component is used only when it
   meets the six conditions. Its splitters would also need an `id_func`, our
   own tokenizer, the offset check and an exact pin. semchunk is preferred.

## Alternatives considered
- **Keep the ADR 0001 ban.** Rejected: it blocks mature parsers, chunkers,
  rerankers and evaluators that do not touch the engine. The ban was about
  engines.
- **Build on LlamaIndex as the framework** (`IngestionPipeline`,
  `PropertyGraphIndex`). Rejected for the conflicts in the context: hashing,
  docstore, triples without time or evidence, and global settings that fall
  back to OpenAI.
- **Depend on LlamaIndex for query transforms and fusion.** Rejected: the
  code is tiny, the transforms fall back to `Settings.llm`, step
  decomposition does not work, and RRF fuses on a node hash instead of our
  chunk id.

## Consequences

**Better:**
- Less code to write for parsing, chunking, reranking and evaluation.
- Users who build on LlamaIndex or LangChain can plug TenetRAG in.

**Worse:**
- Each adapter needs the six checks, a pin and, where it feeds hashing, a
  golden test.
- More extras to maintain. The LlamaIndex bridge follows its 0.x churn.

**Must now be true:**
- ADR 0001's rule "no runtime dependency on `graphrag`, `lightrag-hku` or
  `llama-index-*`" is replaced by decision 1 of this ADR. `graphrag` and
  `lightrag-hku` stay banned.
- A test imports the base package and fails if any optional library is
  imported.
- Every chunking adapter has a test asserting `text[start:end] == chunk`.
- No adapter builds a third-party client without explicit credentials.

## Revisit if
- `llama-index-core` drops its eager SQLAlchemy and Pillow imports and makes
  its `Settings` defaults opt-in. A deeper reuse would then be cheaper.
- An adapted library breaks a golden test in more than one release.
