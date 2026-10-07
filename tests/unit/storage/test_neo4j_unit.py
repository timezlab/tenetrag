"""Neo4j connections on a fake driver (contracts/storage.md, research R13, T053).

Behaviours:
1. `auto` TLS refuses a plain scheme for a non-local host; loopback hosts pass
   (test_tls_auto). `require` and `verify` encrypt a plain scheme; `off`
   contradicts a `+s` scheme.
2. The driver is created with telemetry off and the pool, retry and timeout
   settings of the profile (test_telemetry_disabled, test_pool_max_age).
3. Each identity gets its own driver (test_identity_isolation).
4. `health()` reports the kernel version and edition, and refuses a server
   below 2026.09 (test_health_floor).
5. Driver errors map to SDK errors: rejected auth, an unavailable server, a
   missing database. Errors from the caller's own work pass through.
6. `read` and `write` run one managed transaction on the configured database.
7. Without the `neo4j` extra, opening raises MissingExtraError.
"""

import sys

import neo4j
import pytest

from tenetrag import (
    ConfigError,
    CredentialMismatchError,
    CredentialRejectedError,
    MissingCredentialError,
    MissingExtraError,
    QueryError,
    StoreUnavailableError,
    UnsupportedServerError,
)
from tenetrag.auth import Credentials, Secret
from tenetrag.config import BasicSource, Neo4jSettings, PoolSettings, StoreRetrySettings
from tenetrag.storage import HealthReport, Neo4jConnection, open_connection
from tests.support.fake_stores import CYPHER, FakeNeo4j, neo4j_error

PASSWORD = "pw-unit-neo4j"


@pytest.fixture
def fake_neo4j(monkeypatch) -> FakeNeo4j:
    fake = FakeNeo4j()
    monkeypatch.setattr(neo4j.GraphDatabase, "driver", fake)
    return fake


def settings(uri: str = "neo4j+s://graph.example.com", **values) -> Neo4jSettings:
    return Neo4jSettings(kind="neo4j", uri=uri, **values)


def login(user: str = "neo4j") -> object:
    return Credentials.basic(user, Secret(PASSWORD))


def connect(uri: str = "neo4j+s://graph.example.com", **values) -> Neo4jConnection:
    return open_connection(settings(uri, **values), name="graph", credential=login())


# 1. TLS


@pytest.mark.parametrize(
    "uri",
    [
        "neo4j+s://graph.example.com",
        "bolt+s://graph.example.com:7687",
        "bolt://localhost:7687",
        "neo4j://127.0.0.1",
        "bolt://127.8.9.10:7687",
        "bolt://[::1]:7687",
    ],
)
def test_tls_auto_allows(uri, fake_neo4j):
    connect(uri)
    assert fake_neo4j.last.uri == uri
    assert "encrypted" not in fake_neo4j.last.config


@pytest.mark.parametrize("uri", ["neo4j://graph.example.com", "bolt://10.0.0.5:7687"])
def test_tls_auto(uri, fake_neo4j):
    with pytest.raises(ConfigError, match=r"\+s://"):
        connect(uri)
    assert fake_neo4j.drivers == []


def test_tls_require_encrypts_without_checking_the_certificate(fake_neo4j):
    connect("neo4j://graph.example.com", tls="require")
    assert fake_neo4j.last.config["encrypted"] is True
    assert isinstance(fake_neo4j.last.config["trusted_certificates"], neo4j.TrustAll)


def test_tls_verify_checks_the_certificate(fake_neo4j):
    connect("bolt://graph.example.com", tls="verify")
    assert fake_neo4j.last.config["encrypted"] is True
    assert isinstance(fake_neo4j.last.config["trusted_certificates"], neo4j.TrustSystemCAs)


def test_tls_off_allows_a_plain_scheme_for_a_remote_host(fake_neo4j):
    connect("neo4j://graph.example.com", tls="off")
    assert fake_neo4j.last.config["encrypted"] is False


def test_tls_off_contradicts_a_secure_scheme(fake_neo4j):
    with pytest.raises(ConfigError, match="tls"):
        connect("neo4j+s://graph.example.com", tls="off")


# 2. Driver settings


def test_telemetry_disabled(fake_neo4j):
    connect()
    assert fake_neo4j.last.config["telemetry_disabled"] is True


def test_pool_max_age(fake_neo4j):
    connect(
        pool=PoolSettings(max_size=3, max_age_seconds=600, acquire_timeout_seconds=7),
        retry=StoreRetrySettings(max_total_seconds=12),
        connect_timeout_seconds=4,
    )
    config = fake_neo4j.last.config
    assert config["max_connection_pool_size"] == 3
    assert config["max_connection_lifetime"] == 600
    assert config["connection_acquisition_timeout"] == 7
    assert config["max_transaction_retry_time"] == 12
    assert config["connection_timeout"] == 4
    assert config["liveness_check_timeout"] == 30


def test_basic_credential_becomes_driver_auth(fake_neo4j):
    connect()
    auth = fake_neo4j.last.auth
    assert (auth.scheme, auth.principal, auth.credentials) == ("basic", "neo4j", PASSWORD)


def test_none_credential_sends_no_auth(fake_neo4j):
    open_connection(settings("bolt://localhost"), name="graph", credential=Credentials.none())
    assert fake_neo4j.last.auth is None


# 3. Identity


def test_identity_isolation(fake_neo4j):
    first = open_connection(settings(), name="graph", credential=login("alice"))
    second = open_connection(settings(), name="graph", credential=login("bob"))
    assert first is not second
    assert len(fake_neo4j.drivers) == 2
    assert [d.auth.principal for d in fake_neo4j.drivers] == ["alice", "bob"]
    assert first.health().identity == "basic:alice"
    assert second.health().identity == "basic:bob"


def test_credential_from_the_profile_source(fake_neo4j, monkeypatch):
    monkeypatch.setenv("GRAPH_PASSWORD", PASSWORD)
    source = BasicSource(kind="basic", user="reader", password_env="GRAPH_PASSWORD")
    open_connection(settings(credential=source), name="graph")
    assert fake_neo4j.last.auth.principal == "reader"


def test_missing_credential_names_the_connection(fake_neo4j):
    with pytest.raises(MissingCredentialError, match=r"connections\.graph"):
        open_connection(settings(), name="graph")


def test_api_key_cannot_open_neo4j(fake_neo4j):
    with pytest.raises(CredentialMismatchError):
        open_connection(settings(), name="graph", credential=Credentials.api_key(Secret("k")))


# 4. Health


def test_health_reports_version_and_edition(fake_neo4j):
    report = connect("bolt://localhost").health()
    assert report == HealthReport(
        backend="neo4j",
        server_version="2026.09.0",
        edition="community",
        extensions={},
        identity="basic:neo4j",
        encrypted=False,
    )


@pytest.mark.parametrize("version", ["5.26.0", "2025.12.1", "2026.08.0"])
def test_health_floor(version, fake_neo4j):
    connection = connect()
    fake_neo4j.last.components = [
        {"name": "Neo4j Kernel", "versions": [version], "edition": "community"},
        CYPHER,
    ]
    with pytest.raises(UnsupportedServerError) as caught:
        connection.health()
    assert version in str(caught.value)
    assert "2026.09" in str(caught.value)


def test_health_accepts_a_later_version(fake_neo4j):
    connection = connect()
    fake_neo4j.last.components = [
        {"name": "Neo4j Kernel", "versions": ["2027.01.0"], "edition": "enterprise"},
    ]
    assert connection.health().edition == "enterprise"


# 5. Errors


def test_rejected_auth(fake_neo4j):
    connection = connect()
    fake_neo4j.last.failures = [neo4j_error("Neo.ClientError.Security.Unauthorized")]
    with pytest.raises(CredentialRejectedError, match="basic:neo4j"):
        connection.health()


def test_unavailable_names_host_and_port(fake_neo4j):
    connection = connect("neo4j+s://graph.example.com:7690")
    fake_neo4j.last.failures = [neo4j.exceptions.ServiceUnavailable("Couldn't connect")]
    with pytest.raises(StoreUnavailableError, match=r"graph\.example\.com:7690"):
        connection.read(lambda tx: tx.run("RETURN 1").data())


def test_unavailable_with_the_default_port(fake_neo4j):
    connection = connect()
    fake_neo4j.last.failures = [neo4j.exceptions.SessionExpired("gone")]
    with pytest.raises(StoreUnavailableError, match=r"graph\.example\.com:7687"):
        connection.write(lambda tx: None)


def test_database_not_found_names_the_database(fake_neo4j):
    connection = connect(database="tenants")
    fake_neo4j.last.failures = [
        neo4j_error("Neo.ClientError.Database.DatabaseNotFound", "Graph not found: tenants")
    ]
    with pytest.raises(QueryError, match="tenants"):
        connection.read(lambda tx: None)


def test_database_not_found_says_how_to_fix(fake_neo4j):
    # The server's message here does not name the database, so ours must.
    connection = connect(database="tenants")
    fake_neo4j.last.failures = [neo4j_error("Neo.ClientError.Database.DatabaseNotFound")]
    with pytest.raises(QueryError, match=r"'tenants'.*connections\.graph"):
        connection.read(lambda tx: None)


def test_other_server_errors_are_query_errors(fake_neo4j):
    connection = connect()
    fake_neo4j.last.failures = [neo4j_error("Neo.ClientError.Statement.SyntaxError", "bad")]
    with pytest.raises(QueryError, match="SyntaxError"):
        connection.write(lambda tx: None)


def test_errors_from_the_callers_work_pass_through(fake_neo4j):
    def work(tx):
        raise ValueError("caller bug")

    with pytest.raises(ValueError, match="caller bug"):
        connect().write(work)


# 6. Units of work


def test_read_and_write_use_the_configured_database(fake_neo4j):
    connection = connect(database="tenants")
    assert connection.read(lambda tx: "r") == "r"
    assert connection.write(lambda tx: "w") == "w"
    assert fake_neo4j.last.units == [("read", "tenants"), ("write", "tenants")]


def test_context_manager_closes_the_driver(fake_neo4j):
    with connect() as connection:
        assert isinstance(connection, Neo4jConnection)
    assert fake_neo4j.last.closed


def test_repr_names_target_and_identity(fake_neo4j):
    text = repr(connect())
    assert "graph.example.com" in text
    assert "basic:neo4j" in text
    assert PASSWORD not in text


# 7. Extra


def test_missing_extra(monkeypatch):
    monkeypatch.setitem(sys.modules, "neo4j", None)
    with pytest.raises(MissingExtraError, match="neo4j"):
        connect()
