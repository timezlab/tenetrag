# Use synchronous protocols with one hop per store call

**Status:** accepted
**Date:** 2026-10-05
**Deciders:** Liam Lee (session 2026-10-05)

## Context
Engine brief questions E13 and E14 asked two questions:
- Is the API synchronous or asynchronous?
- How much graph expansion runs inside the store?

Inputs:
- Callers run the SDK in Databricks notebooks, jobs, Apps, Model Serving
  and plain scripts. Notebooks already run an event loop, so sync
  wrappers over async code break there unless they patch the loop.
- The protocol methods are engine operations, not query languages, and
  must fit Postgres, Neo4j and Delta
  ([ADR 0008](0008-build-databricks-and-open-branches-in-parallel.md)).
- `retrieve()` runs two hops by default
  ([engine brief §4.1](../product/engine-brief.md#41-retrieve)).
- One developer builds v1.

## Decision
1. **The API and protocols are synchronous.** The engine runs model calls
   and the two retrieval branches in a bounded thread pool. During
   indexing, `max_concurrency` (default 8) caps concurrent model calls;
   resolution and writes run one document at a time. The MCP server calls
   the engine from worker threads. `serving` can add async wrappers later.
2. **The store runs one hop per call.** `GraphStore.hop(entity_ids, spec)`
   returns the edges and items one step from the given entities, with
   per-entity neighbour and item limits and the as-of pre-filter. The
   engine composes hops, applies decay and the hub penalty, and decides
   the next frontier.
3. **Every store read is batched.** It takes a list of ids or keys, and
   no store call sits inside a loop over unbounded data.

## Alternatives considered
- **Async first, with sync wrappers (E13 option B).** Rejected: the
  wrappers break in notebooks, the main runtime for data engineers.
- **Both sync and async everywhere (E13 option C).** Rejected: it doubles
  the protocol surface, the backends and the contract suite for one
  developer.
- **One `expand` call that runs every hop in the backend (E14 option
  B).** Rejected:
  - scoring would live in SQL and Cypher, so backends could rank
    differently;
  - on Delta, `hop` already runs on an in-process cache, so a backend
    `expand` would save nothing there;
  - it saves one round trip per hop, a few milliseconds.

## Consequences

**Better:**
- One code path works in notebooks, jobs, Apps and scripts.
- Scoring, decay and the hub penalty live in the engine, so the contract
  suite can compare backends on candidate sets.
- Backends stay thin: each implements one bounded step.

**Worse:**
- A two-hop retrieval makes two round trips to the graph store.
- Thread-pool concurrency is bounded by the pool, and async callers must
  wrap calls in a thread.

**Must now be true:**
- No protocol method is `async`.
- `hop` enforces `neighbour_limit` and `item_limit` per entity inside the
  backend query, so a hub cannot return unbounded rows.
- The engine never calls a store inside a loop over entities or chunks.

## Revisit if
- Profiling shows round trips dominate retrieval latency on a remote
  graph store.
- A major caller needs native async, such as an async agent framework at
  high concurrency.
