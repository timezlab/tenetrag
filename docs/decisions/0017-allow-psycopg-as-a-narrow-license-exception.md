# Allow psycopg under LGPL as a narrow exception to the permissive-license rule

**Status:** accepted
**Date:** 2026-10-06
**Deciders:** Liam Lee (M0 planning session, 2026-10-06)

## Context
[ADR 0009](0009-reuse-permissive-libraries-behind-adapters.md) requires
every third-party library outside the engine to have a permissive license:
"MIT, BSD, Apache-2.0 or equivalent". The M0 Postgres connection wrapper
([spec 001](../../specs/001-sdk-foundation/spec.md), Story 5) needs:
- a pool that checks a connection before use;
- a maximum connection age, since Lakebase closes connections after
  3 days;
- a freshly minted token for each new physical connection, since
  Lakebase OAuth tokens live 5 to 60 minutes;
- whole-transaction retry.

M1 also needs bulk writes.

Options read in source on 2026-10-06
([research R12](../../specs/001-sdk-foundation/research.md#r12-postgres-driver-authors-decision)):
- **psycopg 3.3 and psycopg-pool 3.3** (LGPL-3.0-only). The pool takes a
  callable for connection arguments, called per new connection, plus a
  `check` callback and `max_lifetime`. The driver supports COPY.
- **pg8000 1.31** (BSD-3-Clause), pure Python. It has no pool. Its
  default TLS skips certificate checks and falls back to plaintext. It is
  slower, and its last release was in 2025-09.
- **asyncpg** (Apache-2.0), which is async only and does not fit the
  synchronous protocols of
  [ADR 0014](0014-use-synchronous-protocols-with-one-hop-per-store-call.md).

LGPL is copyleft, so it is not "equivalent" to MIT under ADR 0009's
wording. For a Python package installed separately and imported
unmodified, the obligations are light: keep the notice, and let users
replace the library. The usual reading is that this does not reach the
importing code [inferred, not legal advice]. Many permissively licensed
projects depend on psycopg in this way, Django, SQLAlchemy and Apache
Airflow's Postgres provider among them.

## Decision
psycopg (with the `binary` extra) and psycopg-pool may be used under
these conditions:
1. They live only in the `postgres` extra. The base package never
   imports them.
2. They are installed from PyPI as separate packages. They are never
   vendored, copied or modified.
3. The other five conditions of ADR 0009 still hold. In particular, the
   wrapper passes host, port, database, user, password and `sslmode`
   explicitly, so libpq never takes a password from `PGPASSWORD` or
   `~/.pgpass`. Postgres accepts no `none` credential.
4. `NOTICE` names them and their license.

The exception covers these two packages only. Any other non-permissive
library needs its own ADR.

## Alternatives considered
- **pg8000 and our own pool.** Rejected by the author: we would own
  thread-safe pooling, liveness checks, maximum age and token minting,
  with slower bulk writes and unsafe TLS defaults to work around.
- **asyncpg behind a synchronous wrapper.** Rejected: an event loop per
  thread to serve synchronous protocols.
- **Keep ADR 0009 strict and drop Postgres outside Databricks.**
  Rejected: Lakebase, the Databricks default, is Postgres.

## Consequences

**Better:**
- The pool, liveness checks, maximum age and per-connection token minting
  come from a mature library.
- The Lakebase path in M2 needs no new driver.
- COPY is available for M1's bulk writes.

**Worse:**
- An adopter whose legal team bans all LGPL code cannot install the
  `postgres` extra. Neo4j stays available to them, and a pg8000 backend
  could be added later behind the same protocols.
- The `binary` extra ships a compiled libpq inside psycopg-binary wheels.

**Must now be true:**
- Constitution principle IX names this exception (constitution 1.1.0).
- `NOTICE` lists psycopg and psycopg-pool with LGPL-3.0-only.
- A unit test asserts that the wrapper passes every connection parameter
  explicitly.

## Revisit if
- An adopter's license policy blocks the `postgres` extra.
- psycopg changes its license.
- A permissive synchronous driver with a comparable pool appears.
