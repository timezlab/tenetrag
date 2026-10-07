"""Stand-ins for the Neo4j driver and the psycopg pool, so store tests run without a server.

`FakeNeo4j` replaces `neo4j.GraphDatabase.driver`. `FakePostgres` replaces
`psycopg.Connection.connect` (under the SDK's own connection class),
`psycopg_pool.ConnectionPool` and `socket.getaddrinfo`, which answers from a
table of host names. Each records what the SDK passed, and answers from a
script, so a test that runs out of answers fails instead of passing on a
default.
"""

from __future__ import annotations

import contextlib
import socket
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any

import neo4j
import psycopg
import psycopg_pool

KERNEL_2026_09 = {"name": "Neo4j Kernel", "versions": ["2026.09.0"], "edition": "community"}
CYPHER = {"name": "Cypher", "versions": ["5", "25"], "edition": ""}


# Neo4j


class FakeTransaction:
    def __init__(self, driver: FakeDriver) -> None:
        self._driver = driver

    def run(self, query: str, **parameters: Any) -> FakeResult:
        self._driver.queries.append(query)
        if "dbms.components" in query:
            return FakeResult(self._driver.components)
        return FakeResult([])


@dataclass
class FakeResult:
    rows: list[dict[str, Any]]

    def data(self) -> list[dict[str, Any]]:
        return self.rows


class FakeSession:
    def __init__(self, driver: FakeDriver, database: str | None) -> None:
        self._driver = driver
        self.database = database

    def __enter__(self) -> FakeSession:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def execute_read(self, work: Callable[[FakeTransaction], Any]) -> Any:
        return self._execute("read", work)

    def execute_write(self, work: Callable[[FakeTransaction], Any]) -> Any:
        return self._execute("write", work)

    def _execute(self, access: str, work: Callable[[FakeTransaction], Any]) -> Any:
        self._driver.units.append((access, self.database))
        if self._driver.failures:
            raise self._driver.failures.pop(0)
        return work(FakeTransaction(self._driver))


class FakeDriver:
    def __init__(self, uri: str, auth: Any, config: dict[str, Any]) -> None:
        self.uri = uri
        self.auth = auth
        self.config = config
        self.components: list[dict[str, Any]] = [KERNEL_2026_09, CYPHER]
        self.failures: list[Exception] = []  # raised by the next units, in order
        self.units: list[tuple[str, str | None]] = []
        self.queries: list[str] = []
        self.closed = False

    @property
    def encrypted(self) -> bool:
        return "+s" in self.uri or bool(self.config.get("encrypted"))

    def session(self, database: str | None = None, **config: Any) -> FakeSession:
        return FakeSession(self, database)

    def close(self) -> None:
        self.closed = True


@dataclass
class FakeNeo4j:
    """Replaces `neo4j.GraphDatabase.driver`; `drivers` holds one per call."""

    drivers: list[FakeDriver] = field(default_factory=list)

    def __call__(self, uri: str, *, auth: Any = None, **config: Any) -> FakeDriver:
        driver = FakeDriver(uri, auth, config)
        self.drivers.append(driver)
        return driver

    @property
    def last(self) -> FakeDriver:
        return self.drivers[-1]


def neo4j_error(code: str, message: str = "scripted") -> neo4j.exceptions.Neo4jError:
    """The driver's error for a server code, built the way the driver builds it."""
    return neo4j.exceptions.Neo4jError._hydrate_neo4j(code=code, message=message)


# Postgres

POSTGRES_16 = {
    "SHOW server_version_num": [("160004",)],
    "SHOW server_version": [("16.4 (Debian 16.4-1.pgdg120+2)",)],
    "pg_available_extensions": [("vector",), ("pg_trgm",)],
}


class FakeCursor:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self._rows = rows

    def fetchone(self) -> tuple[Any, ...] | None:
        return self._rows[0] if self._rows else None

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self._rows


@dataclass
class FakePgConn:
    ssl_in_use: bool


class FakePgConnection:
    """What the SDK's work functions receive: `execute`, `transaction`, `read_only`."""

    def __init__(self, server: FakePostgres, params: dict[str, Any]) -> None:
        self._server = server
        self.params = params
        self.read_only = False
        self.pgconn = FakePgConn(ssl_in_use=params.get("sslmode") not in (None, "disable"))
        self.closed = False

    def execute(self, query: str, params: Any = None) -> FakeCursor:
        self._server.queries.append(query)
        for prefix, rows in self._server.answers.items():
            if prefix in query:
                return FakeCursor(rows)
        return FakeCursor([])

    @contextlib.contextmanager
    def transaction(self) -> Iterator[None]:
        self._server.transactions.append(self.read_only)
        yield

    def close(self) -> None:
        self.closed = True


class FakePool:
    """Replaces `psycopg_pool.ConnectionPool`. Each checkout opens a new physical
    connection through the SDK's connection class, as a pool refill would."""

    instances: list[FakePool]
    open_failures: list[Exception]  # raised by the next opens, in order; FakePostgres's list

    def __init__(self, conninfo: str = "", **settings: Any) -> None:
        self.settings = settings
        self.opened: tuple[bool, float] | None = None
        self.closed = False
        self.timeouts: list[Exception] = []  # raised by the next checkouts, in order
        FakePool.instances.append(self)

    @staticmethod
    def check_connection(conn: Any) -> None:
        return None

    def open(self, wait: bool = False, timeout: float = 30.0) -> None:
        self.opened = (wait, timeout)
        if FakePool.open_failures:
            self.closed = True  # as the real pool does when it cannot fill in time
            raise FakePool.open_failures.pop(0)

    @contextlib.contextmanager
    def connection(self, timeout: float | None = None) -> Iterator[FakePgConnection]:
        if self.closed:
            raise psycopg_pool.PoolClosed(
                f"the pool {self.settings.get('name')!r} is already closed"
            )
        if self.timeouts:
            raise self.timeouts.pop(0)
        connection_class = self.settings["connection_class"]
        yield connection_class.connect(**self.settings["kwargs"])

    def close(self) -> None:
        self.closed = True


# A documentation address (RFC 5737) for the remote host, so nothing real is named,
# and both loopbacks for localhost, as most machines answer.
ADDRESSES = {"db.example.com": ["192.0.2.10"], "localhost": ["::1", "127.0.0.1"]}


@dataclass
class FakePostgres:
    """Answers each connection attempt from `refusals` (the libpq messages to raise,
    in order), then with a connection; records every attempt's parameters."""

    refusals: list[str] = field(default_factory=list)
    answers: dict[str, list[tuple[Any, ...]]] = field(default_factory=lambda: dict(POSTGRES_16))
    attempts: list[dict[str, Any]] = field(default_factory=list)
    queries: list[str] = field(default_factory=list)
    transactions: list[bool] = field(default_factory=list)
    pool_open_failures: list[Exception] = field(default_factory=list)
    addresses: dict[str, list[str]] = field(default_factory=lambda: dict(ADDRESSES))
    lookups: list[str] = field(default_factory=list)

    def getaddrinfo(self, host: str, port: Any, *args: Any, **kwargs: Any) -> list[Any]:
        self.lookups.append(host)
        if host not in self.addresses:
            raise socket.gaierror(socket.EAI_NONAME, "Name or service not known")
        return [
            (
                socket.AF_INET6 if ":" in address else socket.AF_INET,
                socket.SOCK_STREAM,
                socket.IPPROTO_TCP,
                "",
                (address, int(port)),
            )
            for address in self.addresses[host]
        ]

    def connect(self, conninfo: str = "", **params: Any) -> FakePgConnection:
        self.attempts.append(params)
        if self.refusals:
            # As psycopg does, the error keeps the finished connection, password included.
            pgconn = psycopg.errors.FinishedPGconn(password=params["password"].encode())
            raise psycopg.OperationalError(self.refusals.pop(0), pgconn=pgconn)
        return FakePgConnection(self, params)

    @property
    def pools(self) -> list[FakePool]:
        return FakePool.instances

    @property
    def passwords(self) -> list[str]:
        return [attempt["password"] for attempt in self.attempts]


def refused(host: str, reason: str, port: int = 5432) -> str:
    """A libpq connection failure as psycopg words it, with the server's FATAL reason."""
    return f'connection failed: connection to server at "{host}", port {port} failed: {reason}'


def install_fake_postgres(monkeypatch: Any, server: FakePostgres) -> None:
    FakePool.instances = []
    FakePool.open_failures = server.pool_open_failures
    monkeypatch.setattr(
        psycopg.Connection,
        "connect",
        classmethod(lambda cls, conninfo="", **params: server.connect(conninfo, **params)),
    )
    monkeypatch.setattr(psycopg_pool, "ConnectionPool", FakePool)
    monkeypatch.setattr(socket, "getaddrinfo", server.getaddrinfo)
