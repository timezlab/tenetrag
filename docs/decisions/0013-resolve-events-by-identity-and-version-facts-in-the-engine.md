# Resolve events by pack identity and version facts in the engine

**Status:** accepted
**Date:** 2026-10-05
**Deciders:** Liam Lee (session 2026-10-05)

## Context
Engine brief questions E2 and E3 asked two questions:
- When do two extracted events become one node?
- How do facts get versions?

The running example shows both problems:
- In D3, chunk 1 describes the risk committee meeting with its date, chair
  and attendees. Chunk 3 refers to the same meeting by date only, to
  assign an action item. Without event resolution, the action item points
  to a second meeting node.
- D1 sets the lodging allowance at 2,000,000 VND a day, and D2 sets
  2,500,000 from 2026-01-15. Without fact versions, both limits are
  "current", and an as-of question about March 2025 has no single answer.

Settled inputs:
- Relations already supersede through `one_at_a_time` cardinality with
  conflict flags ([domain-packs.md](../product/domain-packs.md#how-the-pack-is-used)).
- Supersession ordering lives in the engine, so that every backend gives
  the same result
  ([ADR 0008](0008-build-databricks-and-open-branches-in-parallel.md)).
- Graphiti's `remove_episode` does not reopen the facts that the deleted
  episode had superseded
  ([pitfalls](../reference/graphrag-engines.md#pitfalls-to-avoid)).

## Decision
1. **Events merge within a document by time and roles.** Two events of
   the same type merge when their times are equal or one is missing, and
   no role has two disjoint, non-empty sets of targets.
2. **Events merge across documents only on pack `identity`.** `identity`,
   a pack field until now used for entities, now applies to event types,
   for example `Decision: [time, about, decided_by]`. A type without
   `identity` never merges across documents. v1 has no fuzzy or LLM event
   matching.
3. **Facts get versions through `version_key`.** It is a new pack field on
   fact types. It names the roles and attributes that make two facts
   statements of the same thing, for example
   `Requirement: [metric, applies_to, condition]`. A fact type without
   `version_key` has no versions, so each of its facts is current.
4. **The engine computes statuses.** Within a version group, from
   `one_at_a_time` or `version_key`:
   - rows order by `valid_from`, then `observed_at`;
   - the newest version is `current`;
   - older versions are `superseded`, with `closed_at` set to the next
     version's start;
   - two different contents with the same start are both `conflicting`.
5. **Writes and deletes recompute every group they touch.** Status
   changes to other documents' rows travel with the document's write or
   delete, in the same unit. Deleting D2 makes D1's limit current again.
6. **Nothing is deleted for being old.** `as_of`, `during` and
   `all_versions` choose which versions a query returns
   ([engine brief §3.3](../product/engine-brief.md#33-as-of-and-ranges-e9)).

The proposed `identity` and `version_key` values for the shipped types are
in [engine brief §2.7](../product/engine-brief.md#27-resolve-events-e2)
and [§3.2](../product/engine-brief.md#32-version-groups-e3).

## Alternatives considered
- **No event resolution (E2 option A).** Rejected: each extraction
  becomes its own node, so one meeting splits across chunks and
  documents.
- **Fuzzy and LLM event matching (E2 option C).** Rejected for v1: no
  measured need, and wrong merges of events are hard to see. It can come
  back as a benchmark variant.
- **No fact versions; only relations supersede (E3 option B).** Rejected:
  figures, limits and definitions are facts, and they are what as-of
  questions ask about.
- **Statuses computed in each backend.** Rejected: SQL and Cypher would
  each need the ordering rules, and the contract suite could not promise
  equal results.

## Consequences

**Better:**
- One meeting is one node however many chunks describe it, so decisions
  and action items attach to it.
- As-of questions get one current version per group, and deletes restore
  older versions.
- The rules are in the engine, so all backends agree.

**Worse:**
- Pack authors must choose `identity` for event types and `version_key`
  for fact types. A wrong key merges or splits versions.
- Every write and delete reads the version groups it touches first, one
  batched store call.
- An acquisition announced in March and completed in June stays two
  events, because the times differ.

**Must now be true:**
- `domain-packs.md` and the draft packs define `identity` for event types
  and `version_key` for fact types, and pack validation checks that the
  named roles and attributes exist.
- `write_documents` and `delete_documents` accept status changes for rows
  of other documents and apply them in the same unit.
- The contract suite covers supersession, conflict and the restore after
  a delete.

## Revisit if
- Users need deal stages or other multi-step happenings linked across
  time.
- Real golden-set questions show split events that pack identity cannot
  merge.
