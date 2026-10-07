"""Neo4j connections on the pinned image (contracts/storage.md, research R13, T055).

Behaviours:
1. `health()` reports 2026.09 Community (test_health_ok).
2. A wrong password raises CredentialRejectedError at once (test_wrong_password).
3. A missing database raises QueryError naming it (test_database_not_found).
4. A server restart in the middle of a unit replays the unit (test_restart_recovers).
5. A stopped server raises StoreUnavailableError with host and port after the
   budget (test_unavailable).
"""

import socket
import time
from collections.abc import Iterator

import pytest
from testcontainers.community.neo4j import Neo4jContainer

from tenetrag import CredentialRejectedError, QueryError, StoreUnavailableError
from tenetrag.auth import Credentials, Secret
from tenetrag.config import Neo4jSettings, PoolSettings, StoreRetrySettings
from tenetrag.storage import Neo4jConnection, open_connection

PASSWORD = "it-neo4j-pass-1"  # a throwaway container's password


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def start(image: str) -> tuple[Neo4jContainer, int]:
    """A container on a fixed host port, so a restart keeps the address."""
    port = free_port()
    container = Neo4jContainer(image, password=PASSWORD).with_bind_ports(7687, port)
    return container.start(), port


@pytest.fixture(scope="module")
def shared(neo4j_image: str) -> Iterator[int]:
    container, port = start(neo4j_image)
    yield port
    container.stop()


@pytest.fixture
def own(neo4j_image: str) -> Iterator[tuple[Neo4jContainer, int]]:
    container, port = start(neo4j_image)
    yield container, port
    container.stop()


def connect(port: int, password: str = PASSWORD, **values) -> Neo4jConnection:
    settings = Neo4jSettings(kind="neo4j", uri=f"bolt://localhost:{port}", **values)
    return open_connection(
        settings, name="graph", credential=Credentials.basic("neo4j", Secret(password))
    )


def test_health_ok(shared):
    with connect(shared) as connection:
        report = connection.health()
    assert report.backend == "neo4j"
    assert report.server_version.startswith("2026.09")
    assert report.edition == "community"
    assert report.identity == "basic:neo4j"
    assert report.encrypted is False


def test_wrong_password(shared):
    started = time.monotonic()
    with (
        connect(shared, password="it-wrong-pass-1") as connection,
        pytest.raises(CredentialRejectedError, match="basic:neo4j"),
    ):
        connection.health()
    assert time.monotonic() - started < 10  # no retry loop


def test_database_not_found(shared):
    with (
        connect(shared, database="tenants") as connection,
        pytest.raises(QueryError, match="tenants"),
    ):
        connection.read(lambda tx: tx.run("RETURN 1").consume())


def test_restart_recovers(own):
    container, port = own
    calls = []

    def work(tx):
        calls.append(len(calls))
        if len(calls) == 1:
            container.get_wrapped_container().restart()
        return tx.run("MERGE (p:Probe {id: 7}) RETURN p.id AS id").single()["id"]

    with connect(port, retry=StoreRetrySettings(max_total_seconds=120)) as connection:
        connection.write(lambda tx: tx.run("RETURN 1").consume())  # a live connection first
        assert connection.write(work) == 7
        assert (
            connection.read(lambda tx: tx.run("MATCH (p:Probe) RETURN count(p) AS n").single()["n"])
            == 1
        )
    assert len(calls) >= 2


def test_unavailable(own):
    container, port = own
    with connect(
        port,
        retry=StoreRetrySettings(max_total_seconds=3),
        pool=PoolSettings(acquire_timeout_seconds=2),
        connect_timeout_seconds=1,
    ) as connection:
        connection.health()
        container.get_wrapped_container().stop()
        with pytest.raises(StoreUnavailableError, match=f"localhost:{port}"):
            connection.read(lambda tx: tx.run("RETURN 1").consume())
