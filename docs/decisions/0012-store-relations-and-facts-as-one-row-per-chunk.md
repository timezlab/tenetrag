# Store relations and facts as one row per statement per chunk

**Status:** accepted
**Date:** 2026-10-05
**Deciders:** Liam Lee (session 2026-10-05)

## Context
Engine brief question E1 asked how to store a relation or fact that
several chunks state. In the running example, D1 and a later handbook can
both say that Phòng Tài chính owns the travel policy.

Reference engines keep one record per relation with a list of sources
([graphrag-engines.md](../reference/graphrag-engines.md)):
- LightRAG keeps a `source_id` list on nodes and edges.
- cognee and post-graph-rag keep chunk-id arrays with GIN indexes and
  delete by reference count. Orphaned rows go dormant.

Settled constraints:
- One document is the unit of consistency, and deleting a document must
  be cheap on every backend
  ([ADR 0008](0008-build-databricks-and-open-branches-in-parallel.md)).
- Every item carries a checked verbatim quote, its own valid time and a
  version status ([domain-packs.md](../product/domain-packs.md#how-the-pack-is-used)).
- The same protocol methods must fit Postgres, Delta and Neo4j.

## Decision
1. **A relation or fact is one row per statement per chunk.** It carries
   its own evidence: `doc_id`, `chunk_id`, `quote`, `quote_start`,
   `quote_end` and `quote_match`, plus its own time fields and status.
2. **Entities and events are resolved nodes.** Many chunks point to them:
   entities through mention rows, events through `event_evidence` rows.
3. **Roles are one row per source.** A role row carries the `doc_id` and
   `chunk_id` that stated it.
4. **Ids are content hashes.** `relation_id` and `fact_id` hash the chunk
   id, type, resolved endpoints or role targets, normalized attributes and
   valid time, so a replay writes the same rows.
5. **On Neo4j, two sources give two parallel typed edges.** Each edge
   carries the row's columns. A fact node keeps its evidence as
   properties, since it has exactly one source.
6. **Retrieval groups agreeing rows.** Rows with equal normalized content
   in one version group count as one version backed by several sources
   ([engine brief §3.2](../product/engine-brief.md#32-version-groups-e3)).
   `hop` reports how many rows support an edge.

## Alternatives considered
- **One row per relation with an evidence list (option B).** Rejected:
  - deleting a document must edit lists or count references on every
    backend;
  - one row cannot hold two quotes with different times or statuses;
  - Neo4j would need list properties or reified edges for the evidence.
- **Chunk-id arrays with reference-count delete, as in cognee and
  post-graph-rag.** Rejected for the same reasons. It also relies on
  array indexes (GIN on Postgres), which Delta does not have.

## Consequences

**Better:**
- Deleting or editing a document removes its rows by `doc_id`. No
  reference counts and no list edits.
- Each row keeps its own quote, time and status, so two sources that
  disagree stay visible.
- The row layout is the same on Postgres and Delta, and maps to plain
  typed edges on Neo4j.

**Worse:**
- More rows: a relation stated in five chunks is five rows.
- Neo4j shows parallel edges between the same two nodes, so traversal and
  the app must group them.
- Degree counts rows, not distinct neighbours, so a relation repeated
  across chunks raises an entity's hub penalty.

**Must now be true:**
- Every relation, fact and role row has a `doc_id` and `chunk_id`, and no
  write path omits them.
- `hop` groups rows by neighbour and type, and returns their count as
  support.
- The contract suite checks that deleting one of two sources keeps the
  other row and its edge.

## Revisit if
- Row counts make `hop` or `delete_documents` slow on the largest real
  index.
- Users ask for one edge per relation in the app, and grouping at read
  time is not enough.
