# Contract: `tenetrag.storage` connections

Imports allowed: the standard library, `tenetrag.protocols`,
`tenetrag.config`, `tenetrag.auth`, `tenetrag._retry`, and the drivers
behind the `neo4j` and `postgres` extras, imported lazily. M0 has
connections only. The `GraphStore` and `VectorStore` implementations
arrive in M1 and build on these.

```python
def open_connection(settings: Neo4jSettings | PostgresSettings, *, name: str,
                    credential: Credential | None = None) -> Neo4jConnection | PostgresConnection: ...
    # `name` is the profile key, e.g. "graph" -> target "connections.graph".
    # MissingExtraError when the driver extra is missing.

class Neo4jConnection:
    def health(self) -> HealthReport: ...
    def read(self, work: Callable[["neo4j.ManagedTransaction"], T]) -> T: ...
    def write(self, work: Callable[["neo4j.ManagedTransaction"], T]) -> T: ...
    def close(self) -> None: ...
    def __enter__(self) -> Self: ...
    def __exit__(self, *exc: object) -> None: ...

class PostgresConnection:
    def health(self) -> HealthReport: ...
    def transaction(self, work: Callable[["psycopg.Connection[Any]"], T], *,
                    read_only: bool = False) -> T: ...
    def close(self) -> None: ...
    def __enter__(self) -> Self: ...
    def __exit__(self, *exc: object) -> None: ...

@dataclass(frozen=True, slots=True)
class HealthReport: ...        # data-model §7
```

## Rules

- `work` is a whole unit. It runs in one transaction, and on a transient
  error the whole unit runs again (research R10, R13). `work` must
  therefore be safe to replay, which M1's idempotent writes are.
- Opening does not check health. The caller calls `health()`, which
  raises `UnsupportedServerError` below the floors (data-model §7).
- No method takes query text with values spliced in. Values go as driver
  parameters. No method formats SQL or Cypher.
- `auto` TLS rejects a plain scheme or `sslmode` for a non-local host
  with a `ConfigError`, unless `tls: off` is set.
- Each connection object holds one pool for one `Credential.identity`.
  `open_connection` with another identity returns another object with
  another pool.

## Behaviour pinned by tests

Integration tests are marked `docker` and run on the pinned images of
research R4. Unit tests use fakes for the driver layer.

| Test | Asserts |
|---|---|
| `test_health_ok` (docker) | Neo4j reports version ≥ 2026.09 and its edition; Postgres reports ≥ 16 with `vector` and `pg_trgm` |
| `test_health_floor` (unit) | a faked older version or missing extension raises `UnsupportedServerError` naming both values |
| `test_wrong_password` (docker) | raises `CredentialRejectedError` at once; one connection attempt |
| `test_restart_recovers` (docker) | restarting the container during a unit replays the unit within budget |
| `test_unavailable` (docker) | a stopped container raises `StoreUnavailableError` with host and port, after the budget |
| `test_token_remint_once` (docker, Postgres) | a minter whose first token is rejected is called twice, then succeeds; always rejected raises `CredentialRejectedError` |
| `test_new_token_per_connection` (docker, Postgres) | each new physical connection calls the minter |
| `test_pool_max_age` (unit) | the configured age reaches the pool and driver settings |
| `test_identity_isolation` (unit) | two identities never share a pool |
| `test_tls_auto` (unit) | `neo4j://db.example.com` and `sslmode=disable` on a remote host raise `ConfigError`; localhost passes |
| `test_database_not_found` (docker, Neo4j) | raises `QueryError` naming the database |
| `test_telemetry_disabled` (unit) | the driver is created with `telemetry_disabled=True` |
