# Build our own GraphRAG core instead of wrapping existing engines

**Status:** accepted; amended by
[ADR 0009](0009-reuse-permissive-libraries-behind-adapters.md) (2026-10-04).
Permissive libraries, LlamaIndex included, may now be reused outside the
engine behind adapters. `graphrag` and `lightrag-hku` stay references only.
**Date:** 2026-10-02
**Deciders:** Liam Lee (brainstorm session, 2026-10-02)

## Context
The SDK must keep its graph in Databricks-native storage (Delta tables or
Lakebase), delete and update documents incrementally, track when facts and
decisions happened, and let users plug in their own retrievers and prompts.
The original plan was to support several engines (Microsoft GraphRAG,
LightRAG, LlamaIndex). Reading their source at pinned tags
([graphrag-engines.md](../reference/graphrag-engines.md)) showed that none
fits as a core. Microsoft GraphRAG is in maintenance mode and cannot delete
documents. LightRAG has closed query modes and no claim or temporal layer, and
its storage pattern is many small writes. LlamaIndex has no Postgres graph
store and cannot cascade deletes.

## Decision
We write our own engine (parse → chunk → extract → resolve → communities →
retrieve) against our own store protocols. Microsoft GraphRAG and LightRAG
(both MIT) are architecture references: we port algorithms and prompts from
them with attribution, but never import them at runtime. The exact engine
design and protocol methods are settled in a separate engine brief.

## Alternatives considered
- **Wrap several engines behind one interface** — rejected: a shared schema
  across the three is lossy, their retrieval modes are not interchangeable
  ("global" means different things in each), and every engine would need its
  own Delta and Postgres backends.
- **LightRAG core with a Databricks shell** — the fastest route to a demo, so
  it was seriously considered. Rejected because its many small writes suit
  Lakebase but not Delta, its query modes are a closed `Literal` with no hook
  for custom retrievers, it has no claims with dates, and upstream ships about
  eight releases a quarter, which a fork would have to track. Would revisit if
  LightRAG opens its retriever API and adds temporal claims.
- **Microsoft GraphRAG core** — rejected: maintenance mode (no new PRs) and
  no document deletion (`InputDelta.deleted_inputs` is never consumed).
- **No graph (Knowledge Assistant, or AI Search over entity-tagged chunks)** —
  rejected: retrieval would not be customizable by the user's agents. A
  naive-vector mode inside the SDK serves as the benchmark baseline instead.

## Consequences

**Better:**
- Storage-shaped writes (batched, idempotent, per-run) that work on both Delta
  and Postgres.
- Delete-by-document and incremental update designed in from the start.
- Facts with time and source, and verbatim figures, are first-class.
- Retrievers and prompts are open extension points, not forks.

**Worse:**
- More code to write and maintain than a wrapper. Quality is unproven until
  the benchmark shows it matching the reference engines; the hard parts are
  entity resolution, community updates on edit/delete, and prompt quality.
- Algorithm upgrades in the reference engines have to be ported by hand.
- M1 is blocked on the engine brief.

**Must now be true:**
- No runtime dependency on `graphrag`, `lightrag-hku` or `llama-index-*` in
  `pyproject.toml`.
- Any ported prompt or algorithm keeps an attribution comment that names the
  source repo, tag and file.
- The engine reaches storage and models only through the protocols in
  [ADR 0002](0002-graph-and-vector-storage-backends.md) and the `llm` layer.

## Revisit if
Benchmarks on a real golden set show our engine clearly below the SDK's own
naive-vector baseline, or below a reference engine run separately (outside
the SDK) on the same corpus, and tuning does not close the gap; or a
reference engine gains a pluggable storage and retriever API that fits
Delta.
