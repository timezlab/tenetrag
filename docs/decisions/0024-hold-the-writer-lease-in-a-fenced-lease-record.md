# Hold the writer lease in a fenced lease record

**Status:** accepted; amends [0008](0008-build-databricks-and-open-branches-in-parallel.md)
**Date:** 2026-10-21
**Deciders:** Liam Lee (plan of feature 003, 2026-10-21)

## Context
ADR 0008 §7 allows one writer per index: "an advisory lock on Postgres,
a lease node on Neo4j". Feature 003's spec asks more of that rule
(FR-015). A writer that dies must not hold the index for good, so the
lease ends at a time. A long run renews it, a finished run releases it,
and a second writer is told who holds the index and until when
([spec](../../specs/003-stores-and-contract-suite/spec.md)).

The pinned Postgres images were checked on 2026-10-21
([research R4 of 003](../../specs/003-stores-and-contract-suite/research.md#r4-the-writer-lease)):
- A session advisory lock survives commit and lasts until its connection
  closes. `idle_session_timeout` and `lock_timeout` are 0 by default, so
  a client that hangs with its connection open holds the index with no
  end.
- The store takes connections from a pool. A lock taken on one pooled
  connection stays on it when the connection goes back to the pool, and
  the next document's transaction may run on another connection.
- A transaction-level advisory lock ends with each document's
  transaction, so it cannot span a run.
- An advisory lock carries no owner name and no end time to report.

A lease checked only when it is taken has a second gap. A writer that
pauses past its lease (a long garbage collection, a suspended laptop)
can wake after another writer took over and still commit a document.

## Decision
1. **One lease record per index, on every backend.** Postgres keeps a
   `writer_lease` row and Neo4j a `WriterLease` node, unique on the index
   id. Each holds the owner, an end time from the server's clock, and a
   fence counter. Delta (M2) follows the same design.
2. **Taking, renewing and releasing are each one conditional statement.**
   Taking succeeds when the lease is free, expired or already held by
   the same owner, and a new holder increments the fence. Renewing
   succeeds while the owner and fence still match. Releasing ends the
   lease and is a no-op when the lease is already gone or taken. A
   refused take raises `WriterBusyError` naming the holder and the end
   time.
3. **Every write unit checks the lease inside its transaction.** It
   reads the lease row or node under a lock and checks the owner, fence
   and end time before writing. A takeover then waits for a running unit
   to commit, and a writer whose lease was taken fails its next unit
   with `WriterBusyError` instead of writing.
4. **Owners are unique per process.** The engine builds the owner from
   the host, the process id and a random suffix, so two processes on one
   host never share a lease.

## Alternatives considered
- **Advisory locks, as ADR 0008 §7 said.** Rejected for the reasons in
  Context: no end time, pinned to a connection a pool reuses, and no
  holder to report.
- **A lease checked only when taken.** Rejected: a paused writer could
  commit after a takeover, and two writers would then write one index.
- **Advisory locks with `idle_session_timeout` set by the store.**
  Rejected: a server setting the SDK does not own, and a connection
  closed by the server mid-run would surface as a dropped connection,
  not as a lease that ended.

## Consequences
**Better:**
- One lease design on Postgres, Neo4j and later Delta. The contract
  suite runs the same lease cases on each.
- A dead writer frees the index when its lease ends, with no operator
  action.
- `WriterBusyError` can say who holds the index and until when.

**Worse:**
- Each write unit reads one more row or node, under a lock.
- The engine must renew the lease during a long run. A run that stops
  renewing loses the index at the end time, and its next document fails.
- Clock skew between server nodes would shift end times. Every end time
  comes from one server's clock, so a single server is safe.

**Must now be true:**
- Spec 003 FR-015 and FR-030 describe the lease record, not a lock that
  ends with its session.
- Engine brief §6.1 lists `renew_writer` and `release_writer`, and §6.5
  names the lease record on Postgres and Neo4j.
- ADR 0008's status notes this amendment.

## Revisit if
- A backend offers a native lease with an end time and an owner.
- Runs on one index need more than one writer, for example one per
  document shard.
- Fencing at the unit is too slow for large runs; the store could then
  check the fence once per batch of documents.
