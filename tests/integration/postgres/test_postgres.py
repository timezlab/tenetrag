"""Postgres connections on the pinned pgvector images (contracts/storage.md, research R12, T056).

Each test runs on pg16 (the floor) and pg17.

Behaviours:
1. `health()` reports the version and finds `vector` and `pg_trgm` (test_health_ok).
2. A wrong password raises CredentialRejectedError at once (test_wrong_password).
3. A server restart in the middle of a unit replays the unit (test_restart_recovers).
4. A stopped server raises StoreUnavailableError with host and port after the
   budget (test_unavailable).
5. Each new physical connection asks the credential for its token, so a
   short-lived token is minted again (test_new_token_per_connection).
6. A rejected first token is re-minted once; a token rejected twice raises
   CredentialRejectedError (test_token_remint_once).
7. PGHOSTADDR naming another address does not redirect the connection
   (test_pghostaddr_cannot_redirect).
"""

import socket
import time
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from testcontainers.community.postgres import PostgresContainer

from tenetrag import CredentialRejectedError, StoreUnavailableError
from tenetrag.auth import AccessToken, Credentials, Secret
from tenetrag.config import PostgresPoolSettings, PostgresSettings, StoreRetrySettings
from tenetrag.storage import PostgresConnection, open_connection

USER = "tenetrag"
PASSWORD = "it-postgres-pass-1"  # a throwaway container's password


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def start(image: str) -> tuple[PostgresContainer, int]:
    """A container on a fixed host port, so a restart keeps the address."""
    port = free_port()
    container = PostgresContainer(
        image, username=USER, password=PASSWORD, dbname="graph", driver=None
    ).with_bind_ports(5432, port)
    return container.start(), port


@pytest.fixture(scope="module")
def shared(pgvector_image: str) -> Iterator[int]:
    container, port = start(pgvector_image)
    yield port
    container.stop()


@pytest.fixture
def own(pgvector_image: str) -> Iterator[tuple[PostgresContainer, int]]:
    container, port = start(pgvector_image)
    yield container, port
    container.stop()


def settings(port: int, **values) -> PostgresSettings:
    return PostgresSettings(
        kind="postgres", host="localhost", port=port, database="graph", **values
    )


def connect(port: int, password: str = PASSWORD, **values) -> PostgresConnection:
    return open_connection(
        settings(port, **values),
        name="vectors",
        credential=Credentials.basic(USER, Secret(password)),
    )


class Minter:
    """Returns the scripted passwords, then the last one again; counts its calls."""

    def __init__(self, *passwords: str, lifetime: timedelta = timedelta(hours=1)) -> None:
        self.passwords = list(passwords)
        self.lifetime = lifetime
        self.calls = 0

    def __call__(self) -> AccessToken:
        self.calls += 1
        password = self.passwords[min(self.calls, len(self.passwords)) - 1]
        return AccessToken(Secret(password), expires_at=datetime.now(UTC) + self.lifetime)


def with_token(port: int, minter: Minter, **values) -> PostgresConnection:
    credential = Credentials.token_provider(USER, minter, identity="it-app")
    return open_connection(settings(port, **values), name="vectors", credential=credential)


def test_health_ok(shared):
    with connect(shared) as connection:
        report = connection.health()
    assert report.backend == "postgres"
    assert report.server_version.split(".")[0] in {"16", "17"}
    assert report.extensions == {"pg_trgm": True, "vector": True}
    assert report.identity == f"basic:{USER}"
    assert report.encrypted is False


def test_wrong_password(shared):
    started = time.monotonic()
    with pytest.raises(CredentialRejectedError, match=f"basic:{USER}"):
        connect(shared, password="it-wrong-pass-1")
    assert time.monotonic() - started < 5  # no retry loop


def test_restart_recovers(own):
    container, port = own
    calls = []

    def work(conn):
        calls.append(len(calls))
        if len(calls) == 1:
            container.get_wrapped_container().restart()
        return conn.execute("SELECT 42").fetchone()[0]

    with connect(port, retry=StoreRetrySettings(max_total_seconds=60)) as connection:
        assert connection.transaction(work) == 42
    assert len(calls) >= 2


def test_unavailable(own):
    container, port = own
    with connect(
        port,
        retry=StoreRetrySettings(max_total_seconds=3),
        pool=PostgresPoolSettings(acquire_timeout_seconds=1),
        connect_timeout_seconds=1,
    ) as connection:
        container.get_wrapped_container().stop()
        with pytest.raises(StoreUnavailableError, match=f"localhost:{port}"):
            connection.transaction(lambda conn: conn.execute("SELECT 1"))


def test_new_token_per_connection(shared):
    # Tokens inside the refresh margin, so every token() call mints a new one.
    minter = Minter(PASSWORD, lifetime=timedelta(seconds=0))
    pool = PostgresPoolSettings(min_size=1, max_size=1)
    pids = set()

    def kill_own_backend_once(conn):
        pid = conn.execute("SELECT pg_backend_pid()").fetchone()[0]
        pids.add(pid)
        if len(pids) == 1:
            conn.execute("SELECT pg_terminate_backend(pg_backend_pid())")
        return pid

    with with_token(shared, minter, pool=pool) as connection:
        connection.transaction(kill_own_backend_once)
    assert len(pids) == 2
    assert minter.calls == 1 + len(pids)  # the opening connection, then one per pool connection


def test_token_remint_once(shared):
    minter = Minter("it-wrong-pass-1", PASSWORD)
    with with_token(shared, minter) as connection:
        assert connection.transaction(lambda conn: conn.execute("SELECT 1").fetchone()[0]) == 1
    assert minter.calls == 2

    always_wrong = Minter("it-wrong-pass-1")
    with pytest.raises(CredentialRejectedError, match="it-app"):
        with_token(shared, always_wrong)
    assert always_wrong.calls == 2


def test_pghostaddr_cannot_redirect(shared, monkeypatch):
    monkeypatch.setenv("PGHOSTADDR", "192.0.2.1")  # TEST-NET-1 (RFC 5737): nothing answers
    with connect(
        shared, connect_timeout_seconds=1, retry=StoreRetrySettings(max_attempts=2)
    ) as connection:
        assert connection.health().backend == "postgres"
