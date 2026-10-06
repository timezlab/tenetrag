# Write vectors with the graph when one store holds both

**Status:** accepted
**Date:** 2026-10-05
**Deciders:** Liam Lee (session 2026-10-05)

## Context
Each indexed document produces graph rows and two kinds of vectors: chunk
vectors and entity-name vectors (engine brief E4). The graph store and the
vector store are separate protocols, and some pairings live in one
database:
- Postgres graph with pgvector in the same database;
- Neo4j graph with the Neo4j vector index;
- Delta graph with an AI Search Delta Sync index that reads the Delta
  tables.

Other pairings, such as a Neo4j graph with pgvector, have no shared
transaction. One document is the unit of consistency
([ADR 0008](0008-build-databricks-and-open-branches-in-parallel.md)),
and a crash between two stores must not leave the graph pointing at
missing vectors.

## Decision
1. **`serving` decides who writes the vectors** when it composes the
   stores from config. The engine sees the choice as a capability.
2. **When one store holds both, the graph store writes the vectors.** They
   travel in `DocumentWrite.vectors` and are written in the document's
   unit:
   - Postgres + pgvector: inside the document's transaction;
   - Neo4j + Neo4j vector index: inside the document's transaction;
   - Delta + AI Search: as columns of the Delta tables that the sync index
     reads. This is not atomic with search, so the SDK reports or waits
     for sync lag.
3. **Otherwise the vector store writes them, before the graph.** The
   engine upserts the document's vectors first, writes the graph, then
   deletes the previous version's vectors. A crash in between leaves
   extra vectors whose chunk ids are not in the graph. Retrieval drops
   hits whose ids the graph does not return, and the next run overwrites
   them.

## Alternatives considered
- **Always write vectors through the vector store.** Rejected: on the
  shared-database pairings it gives up a transaction that is free, and
  leaves a window where the graph and the vectors disagree.
- **Write the graph first, then vectors.** Rejected: a crash leaves graph
  rows with no vectors, so their chunks and entities cannot be found
  until a re-run. Extra vectors are harmless; missing ones are not.
- **A two-phase commit across stores.** Rejected: the backends do not
  share a transaction protocol, and the extra vectors of option 3 are
  already harmless.

## Consequences

**Better:**
- On the default pairings, a document's graph rows and vectors commit or
  fail together.
- On other pairings, a crash leaves only extra vectors, never missing
  ones.

**Worse:**
- Graph stores that hold vectors implement vector writes too, so
  `DocumentWrite` has an optional vectors field.
- Delta + AI Search search results lag the graph until the sync index
  catches up.
- Retrieval must check vector hits against the graph on the split
  pairings.

**Must now be true:**
- Every vector record carries `doc_id` and `run_id`, so leftovers can be
  found and deleted.
- Retrieval ignores vector hits whose chunk or entity ids the graph does
  not return.
- The contract suite simulates a crash between the vector and graph
  writes on a split pairing and checks that the next run converges.

## Revisit if
- Split pairings become common, and leftover vectors from crashes cost
  real storage or slow searches.
- Sync lag on Delta + AI Search breaks the edit-then-query flow that
  users expect.
