# Classify every configuration parameter as index-time or query-time

**Status:** accepted; amended by
[ADR 0007](0007-define-the-graph-schema-as-layered-domain-packs.md)
(2026-10-04). "Entity types" are now a domain pack: its extraction and
resolution content is index-time, its `retrieval` section is query-time.
**Date:** 2026-10-02
**Deciders:** Liam Lee (brainstorm session, 2026-10-02)

## Context
Three features need the same answer to "does changing this parameter change
the graph?". Re-index detection has to mark documents stale when the
pipeline changes. The benchmark has to know when a variant can reuse an
existing index and when it pays for a new one. Versioning has to record what
produced an index. Indexing a corpus costs LLM tokens per chunk, and
retrieval settings cost nothing to vary. Some index-time changes are cheaper
than others: changing only the embedding model should reuse existing chunks
and extractions. Answering the question separately in each feature would let
them disagree.

## Decision
Every profile parameter is declared either **index-time** or **query-time**
in the config model. Index-time parameters change graph contents: parser,
chunking, embedding model, extraction prompts and model, entity types,
entity resolution, graph language. Query-time parameters do not: retriever
method, top-k, rerank, answer prompt and model. The pipeline version and the
configuration hash that drive re-index detection, benchmark index reuse and
run records are computed from index-time parameters only, per stage (at least
chunking/extraction separately from embedding), so a variant that changes only
the embedding model reuses chunks and extractions.

## Alternatives considered
- **Hash the whole configuration** — rejected: changing top-k would trigger a
  full, paid re-index.
- **Let each feature decide** — rejected: re-index, benchmark and versioning
  would drift apart and disagree about staleness.
- **No automatic detection; users re-index manually** — rejected: silent
  stale graphs after a prompt change are the failure we want to prevent.

## Consequences

**Better:**
- Changing an index-time parameter marks the affected documents in the next
  `scan` plan; changing a query-time parameter does not.
- Benchmark variants that differ only in query-time parameters share one
  index.
- The same stage hashes identify an index's provenance across features.

**Worse:**
- Every new parameter needs a classification, and a misclassified one either
  wastes money or leaves the graph stale.
- Stage-level hashes are more complex than one hash, and each new parameter
  must also be assigned to the right stage.

**Must now be true:**
- Each config field declares its phase, and a test fails if a field has
  none.
- The pipeline version and stage hashes are computed in exactly one module,
  used by `scan`, `benchmark` and run records alike.

## Revisit if
Re-index cost on index-time changes is still too high with the current stage
split, which would call for finer stages (parse, chunk, extract, resolve,
embed).
