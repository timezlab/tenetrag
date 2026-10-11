# Record a live index trace per document, outside the document's atomic write

**Status:** accepted
**Date:** 2026-10-11
**Deciders:** Liam Lee (UI brainstorm, 2026-10-06 and 2026-10-07; recorded
in the [app brief](../product/app-brief.md))

## Context
A developer checking extraction and entity merges cannot see how one
document became part of the graph. Today:
- The run record keeps counts per drop reason, with at most five
  examples for the whole run
  ([engine brief §2.5](../product/engine-brief.md#25-validate)).
- Nothing records which chunk lost which item, or why two mentions
  merged or stayed apart.

The author asked for a canvas that shows each pipeline step of one
document with its inputs and outputs, live while the document indexes.

The design is bounded by these rules:
- Each document is one atomic unit
  ([ADR 0008](0008-build-databricks-and-open-branches-in-parallel.md),
  [engine brief §2.10](../product/engine-brief.md#210-write)). Anything
  written inside the unit is invisible until it commits, and is lost
  when the document fails.
- The engine reaches storage only through protocols.
- Whatever the trace records must not change the graph or any stage
  hash
  ([ADR 0005](0005-index-time-vs-query-time-parameters.md)).

## Decision
1. **A `TraceSink` protocol** that the graph store implements. Its
   operations are:
   - start a document's trace;
   - append a batch of events;
   - finish the trace with a status;
   - read the events after a sequence number;
   - mark stale running traces interrupted;
   - delete a document's trace.
2. **Two tables.**
   - `trace_events` (doc_id, run_id, seq, step, payload).
   - `trace_status` (doc_id, run_id, status, started_at, finished_at,
     error). The status is `running`, `done`, `failed` or
     `interrupted`.
3. **Written outside the document unit, step by step.**
   - Trace events go to the store before the document's atomic write,
     and outside it.
   - Each step appends one batch when it finishes.
   - A long step, such as extraction, also appends its progress about
     every 2 seconds.
   - No store call runs per item.
4. **Only the latest run per document is kept.**
   - When a document starts indexing again, its old trace is replaced at
     once.
   - A document delete removes the trace right after
     `delete_documents`.
   - When a run takes the writer lease, it marks traces still `running`
     from a dead process as `interrupted`.
5. **Content.** Every step records its counts, time, LLM calls and
   tokens. Other content is referenced, not copied, except resolution
   decisions:
   - **References.** Rows that live in other tables are referenced by
     id: chunks, entities, items and identity blocks.
   - **Extraction.** Each chunk's extraction is referenced through its
     extraction-cache entry (`cache_key`, plus whether the entry was a
     hit).
   - **Drops.** The cache payload also keeps the chunk's dropped items,
     with their reason codes and offending text. So a cache hit shows
     the same drops as the run that filled the entry.
   - **Resolution decisions** are stored nowhere else, so they are
     copied into the trace: each mention's target, the method, and the
     candidates with the attribute that kept each apart.
6. **Always on, outside every stage hash.** Raw prompts and LLM replies
   are not stored.
7. **Reading the trace.**
   - `client.get_trace(doc, after=None)` takes a source path or a
     `doc_id`.
   - While a trace is `running`, the app polls it every second.
   - `tenetrag trace <doc> --html` exports it as one offline file in M1
     ([ADR 0020](0020-ship-the-app-as-fastapi-with-a-nextjs-static-export.md)).

## Alternatives considered
- **Write the trace with the document, inside its atomic unit.** This
  was the first design. Rejected:
  - the trace cannot be watched live;
  - a document that fails would have no trace, though failures are when
    a trace is most needed.
- **Copy each chunk's extraction into the trace.** Rejected: the
  extraction cache already holds it, keyed by content.
- **Keep every run's trace.** Rejected: it adds storage for history no
  one asked for. The run record keeps the totals per run.
- **Make the trace opt-in.** Rejected: a trace switched off is missing
  exactly when a run goes wrong.
- **Store raw prompts and replies with the graph.** Rejected: they would
  double the stored text. Sending them to MLflow Tracing as an opt-in is
  undecided.
- **Use Dagster as the orchestrator and its UI as the trace view.**
  Rejected:
  - its UI draws a DAG of assets, not one document's content, and
    offers no custom views;
  - one partition per document strains it at 10k–100k documents;
  - splitting the per-document pipeline into assets would break the run
    overlay and the per-document atomic unit.

  Dagster still fits as an optional external orchestrator around
  `apply()`.
- **Use MLflow Tracing as the trace store and view.** Rejected: its span
  tree has no chunk-lineage view, and its limits at 100k documents are
  unmeasured.
- **Server-sent events instead of polling.** Deferred: it is not yet
  known whether the Databricks Apps proxy keeps a stream open.

## Consequences

**Better:**
- A failed document shows the step that failed. An interrupted run is
  marked as such.
- Developers see every drop and every merge decision for one document,
  including chunks served from the cache.
- Indexing can be watched live in the app.
- The trace copies only resolution decisions, so it stays much smaller
  than the document's text.

**Worse:**
- Indexing makes extra writes: one per step, plus progress writes for
  long steps.
- On Delta, a progress write every 2 seconds per document makes many
  small commits. The M2 spec decides whether the Delta store buffers
  them.
- Only the latest run of a document can be inspected.
- A trace can point at an entity or a cache entry that no longer exists.
  The canvas shows "no longer exists".
- The extraction-cache payload grows by the dropped items.

**Must now be true:**
- `tenetrag.engine` writes trace data only through `TraceSink`. No
  `TraceSink` call runs inside a per-chunk or per-mention loop.
- No `TraceSink` write happens inside the `write_documents` unit of a
  document.
- `trace_events` and `trace_status` take no part in any stage hash.
- `extraction_cache` payloads carry the chunk's drops from the first M1
  version on.
- Engine tests on the reference store cover four behaviours:
  - the running example with a planted same-named person and a planted
    bad quote yields the expected scope block and one
    `QUOTE_NOT_IN_CHUNK` drop in the trace;
  - a trace read part way with `after` returns only the later events;
  - a trace left running becomes `interrupted` when the lease is taken
    over;
  - a trace disappears with its document.

## Revisit if
- Users need the traces of earlier runs.
- Trace writes take more than 5% of `apply` time on the synthetic
  corpus.
- A trace store outside the graph store, such as MLflow Tracing, is
  shown to handle 100k documents with a chunk-lineage view.
