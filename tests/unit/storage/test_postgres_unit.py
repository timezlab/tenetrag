"""Postgres connections on a fake libpq and pool (contracts/storage.md, research R12, T054).

Behaviours:
1. Every connection parameter that matters for identity is passed: host, port,
   dbname, user, password and sslmode, plus no client certificate, no GSS
   encryption, and no GSSAPI or SSPI login, so no ambient identity is used.
   The password never sits in the pool's settings.
2. `sslmode` follows `tls`: `require` for a remote host and `disable` for a
   local one under `auto`, `verify-full` against the system CAs with `verify`.
3. `none` is refused: libpq would read PGPASSWORD or ~/.pgpass instead.
4. Opening makes one connection outside the pool, so a rejected credential or
   a missing database raises at once; then the pool opens and waits.
5. A rejected token of a `token_provider` is re-minted once per connection;
   a second rejection, or any rejection of a `basic` password, raises
   CredentialRejectedError.
6. Units of work are retried by the SQLSTATE table of research R10; other
   failures raise QueryError at once; a server that stays away, or a pool
   that cannot fill, raises StoreUnavailableError naming host and port. A
   closed connection fails at once.
7. `health()` refuses Postgres below 16 and missing `vector` or `pg_trgm`.
8. Each identity gets its own pool (test_identity_isolation).
9. Without the `postgres` extra, or with a libpq older than 16, opening fails.
10. The address comes from the profile alone. The SDK resolves `host` itself
    and passes every address as `hostaddr`, as psycopg would, so PGHOSTADDR
    cannot redirect a connection. An IP address is used as given. Each new
    connection resolves again. A name that does not resolve is retried, then
    raises StoreUnavailableError. PGOPTIONS and PGSERVICE are refused, since
    either can change the session the SDK works in (research R12).
"""

import sys
from datetime import UTC, datetime, timedelta

import psycopg
import psycopg_pool
import pytest

from tenetrag import (
    ConfigError,
    CredentialMismatchError,
    CredentialRejectedError,
    MissingExtraError,
    QueryError,
    StoreUnavailableError,
    UnsupportedServerError,
)
from tenetrag.auth import AccessToken, Credentials, Secret
from tenetrag.config import PostgresPoolSettings, PostgresSettings, StoreRetrySettings
from tenetrag.storage import HealthReport, PostgresConnection, open_connection
from tests.support.fake_stores import FakePool, FakePostgres, install_fake_postgres, refused

PASSWORD = "pw-unit-postgres"
REMOTE = "db.example.com"
REJECTED = 'FATAL:  password authentication failed for user "app"'


@pytest.fixture
def server(monkeypatch) -> FakePostgres:
    fake = FakePostgres()
    install_fake_postgres(monkeypatch, fake)
    return fake


def settings(host: str = REMOTE, **values) -> PostgresSettings:
    return PostgresSettings(kind="postgres", host=host, database="graph", **values)


def basic(user: str = "app") -> object:
    return Credentials.basic(user, Secret(PASSWORD))


class Minter:
    """Hands out `tok-1`, `tok-2`, ...; tokens expire at once when `short_lived`."""

    def __init__(self, short_lived: bool = False) -> None:
        self.calls = 0
        self.short_lived = short_lived

    def __call__(self) -> AccessToken:
        self.calls += 1
        expires = datetime.now(UTC) if self.short_lived else datetime.now(UTC) + timedelta(hours=1)
        return AccessToken(Secret(f"tok-{self.calls}"), expires_at=expires)


def lakebase(minter: Minter) -> object:
    return Credentials.token_provider("app", minter, identity="lakebase-app")


def connect(host: str = REMOTE, credential=None, **values) -> PostgresConnection:
    return PostgresConnection(
        settings(host, **values),
        credential=credential or basic(),
        name="vectors",
        sleep=lambda seconds: None,
    )


# 1. Parameters


def test_every_identity_parameter_is_explicit(server):
    connect()
    params = server.attempts[0]
    assert params["host"] == REMOTE
    assert params["port"] == 5432
    assert params["dbname"] == "graph"
    assert params["user"] == "app"
    assert params["password"] == PASSWORD
    assert params["sslmode"] == "require"
    assert params["sslcertmode"] == "disable"
    assert params["gssencmode"] == "disable"
    assert params["require_auth"] == "!gss,!sspi"


def test_the_pool_settings_hold_no_password(server):
    connect()
    pool_params = server.pools[0].settings["kwargs"]
    assert "password" not in pool_params
    assert pool_params["user"] == "app"


def test_connect_timeout_is_whole_seconds(server):
    connect(connect_timeout_seconds=2.5)
    assert server.attempts[0]["connect_timeout"] == 3


# 2. TLS


@pytest.mark.parametrize(
    ("host", "tls", "sslmode"),
    [
        (REMOTE, "auto", "require"),
        ("localhost", "auto", "disable"),
        ("127.0.0.1", "auto", "disable"),
        ("::1", "auto", "disable"),
        ("localhost", "require", "require"),
        (REMOTE, "off", "disable"),
        (REMOTE, "verify", "verify-full"),
    ],
)
def test_sslmode_follows_tls(host, tls, sslmode, server):
    connect(host, tls=tls)
    assert server.attempts[0]["sslmode"] == sslmode


def test_verify_trusts_the_system_cas(server):
    connect(tls="verify")
    assert server.attempts[0]["sslrootcert"] == "system"


# 3. Credential kinds


def test_none_is_refused(server):
    with pytest.raises(CredentialMismatchError, match="none"):
        open_connection(settings(), name="vectors", credential=Credentials.none())
    assert server.attempts == []


def test_open_connection_names_the_target(server):
    connection = open_connection(settings(), name="vectors", credential=basic())
    assert isinstance(connection, PostgresConnection)


# 4. Opening


def test_opening_connects_once_then_opens_the_pool(server):
    connect(
        pool=PostgresPoolSettings(
            min_size=2, max_size=5, max_age_seconds=900, acquire_timeout_seconds=6
        )
    )
    assert len(server.attempts) == 1
    pool = server.pools[0]
    assert pool.settings["min_size"] == 2
    assert pool.settings["max_size"] == 5
    assert pool.settings["max_lifetime"] == 900
    assert pool.settings["timeout"] == 6
    assert pool.settings["check"] is FakePool.check_connection
    assert pool.settings["open"] is False
    assert pool.opened == (True, 6)


def test_pool_max_age(server):
    connect()
    assert server.pools[0].settings["max_lifetime"] == 43200


def test_missing_database_raises_at_once(server):
    server.refusals = [refused(REMOTE, 'FATAL:  database "graph" does not exist')]
    with pytest.raises(QueryError, match="graph"):
        connect()
    assert len(server.attempts) == 1
    assert server.pools == []


def test_missing_database_says_how_to_fix(server):
    server.refusals = [refused(REMOTE, 'FATAL:  database "graph" does not exist')]
    with pytest.raises(QueryError, match=r"connections\.vectors"):
        connect()


# 5. Rejections and re-minting


def test_basic_rejection_fails_fast(server):
    server.refusals = [refused(REMOTE, REJECTED)]
    with pytest.raises(CredentialRejectedError, match="basic:app"):
        connect()
    assert len(server.attempts) == 1


def test_token_remint_once(server):
    minter = Minter()
    server.refusals = [refused(REMOTE, REJECTED)]
    connect(credential=lakebase(minter))
    assert minter.calls == 2
    assert server.passwords == ["tok-1", "tok-2"]


def test_token_rejected_twice(server):
    minter = Minter()
    server.refusals = [refused(REMOTE, REJECTED), refused(REMOTE, REJECTED)]
    with pytest.raises(CredentialRejectedError, match="lakebase-app"):
        connect(credential=lakebase(minter))
    assert minter.calls == 2


def test_rejection_names_the_servers_reason(server):
    server.refusals = [refused(REMOTE, 'FATAL:  no pg_hba.conf entry for host "10.1.2.3"')]
    with pytest.raises(CredentialRejectedError) as caught:
        connect()
    assert "pg_hba.conf" in "\n".join(getattr(caught.value, "__notes__", []))


def test_new_token_per_connection(server):
    minter = Minter(short_lived=True)
    connection = connect(credential=lakebase(minter))
    for _ in range(3):
        connection.transaction(lambda conn: None)
    assert minter.calls == 4  # the opening connection, then one per checkout
    assert server.passwords == ["tok-1", "tok-2", "tok-3", "tok-4"]


# 6. Units of work


def failing_once(error: Exception):
    calls = []

    def work(conn):
        calls.append(conn)
        if len(calls) == 1:
            raise error
        return "done"

    return work, calls


@pytest.mark.parametrize(
    "sqlstate", ["08006", "08001", "57P01", "57P02", "57P03", "53300", "40001", "40P01"]
)
def test_transient_sqlstates_are_retried(sqlstate, server):
    work, calls = failing_once(psycopg.errors.lookup(sqlstate)("transient"))
    assert connect().transaction(work) == "done"
    assert len(calls) == 2


def test_a_lost_connection_is_retried(server):
    work, calls = failing_once(psycopg.OperationalError("server closed the connection"))
    assert connect().transaction(work) == "done"
    assert len(calls) == 2


def test_a_pool_timeout_is_retried(server):
    connection = connect()
    server.pools[0].timeouts = [psycopg_pool.PoolTimeout("no connection")]
    assert connection.transaction(lambda conn: "done") == "done"


@pytest.mark.parametrize("sqlstate", ["23505", "42601", "42P01", "28P01", "22012"])
def test_other_sqlstates_fail_at_once(sqlstate, server):
    work, calls = failing_once(psycopg.errors.lookup(sqlstate)("final"))
    with pytest.raises(QueryError, match=sqlstate):
        connect().transaction(work)
    assert len(calls) == 1


def test_errors_from_the_callers_work_pass_through(server):
    work, calls = failing_once(ValueError("caller bug"))
    with pytest.raises(ValueError, match="caller bug"):
        connect().transaction(work)
    assert len(calls) == 1


def test_unavailable_names_host_and_port(server):
    def work(conn):
        raise psycopg.OperationalError("server closed the connection unexpectedly")

    connection = connect(port=6543, retry=StoreRetrySettings(max_attempts=3))
    with pytest.raises(StoreUnavailableError, match=r"db\.example\.com:6543") as caught:
        connection.transaction(work)
    assert "3 attempts" in str(caught.value)


def test_unavailable_at_opening(server):
    reason = "Connection refused\n\tIs the server running on that host and accepting TCP/IP?"
    server.refusals = [refused(REMOTE, reason)] * 2
    with pytest.raises(StoreUnavailableError, match=r"db\.example\.com:5432"):
        connect(retry=StoreRetrySettings(max_attempts=2))
    assert len(server.attempts) == 2


def test_a_pool_that_cannot_fill_raises_unavailable(server):
    timeout = psycopg_pool.PoolTimeout("pool initialization incomplete after 30.0 sec")
    server.pool_open_failures.append(timeout)
    with pytest.raises(StoreUnavailableError, match=r"db\.example\.com:5432"):
        connect()


def test_a_closed_connection_fails_at_once(server):
    connection = connect()
    connection.close()
    with pytest.raises(QueryError, match="closed"):
        connection.transaction(lambda conn: None)


def test_read_only_reaches_the_transaction(server):
    connection = connect()
    connection.transaction(lambda conn: None, read_only=True)
    connection.transaction(lambda conn: None)
    assert server.transactions == [True, False]


# 7. Health


def test_health_reports_version_extensions_and_tls(server):
    report = connect().health()
    assert report == HealthReport(
        backend="postgres",
        server_version="16.4 (Debian 16.4-1.pgdg120+2)",
        edition=None,
        extensions={"pg_trgm": True, "vector": True},
        identity="basic:app",
        encrypted=True,
    )


def test_health_floor(server):
    server.answers["SHOW server_version_num"] = [("150008",)]
    server.answers["SHOW server_version"] = [("15.8",)]
    with pytest.raises(UnsupportedServerError) as caught:
        connect().health()
    assert "15.8" in str(caught.value)
    assert "16" in str(caught.value)


def test_health_needs_both_extensions(server):
    server.answers["pg_available_extensions"] = [("vector",)]
    with pytest.raises(UnsupportedServerError, match="pg_trgm"):
        connect().health()


# 8. Identity


def test_identity_isolation(server):
    first = open_connection(settings(), name="vectors", credential=basic("alice"))
    second = open_connection(settings(), name="vectors", credential=basic("bob"))
    assert first is not second
    assert len(server.pools) == 2
    assert [pool.settings["kwargs"]["user"] for pool in server.pools] == ["alice", "bob"]
    assert first.health().identity == "basic:alice"
    assert second.health().identity == "basic:bob"


def test_close_and_context_manager(server):
    with connect() as connection:
        assert isinstance(connection, PostgresConnection)
    assert server.pools[0].closed


def test_repr_names_target_and_identity(server):
    text = repr(connect())
    assert "db.example.com" in text
    assert "basic:app" in text
    assert PASSWORD not in text


# 9. Driver


def test_missing_extra(monkeypatch):
    monkeypatch.setitem(sys.modules, "psycopg_pool", None)
    with pytest.raises(MissingExtraError, match="postgres"):
        connect()


def test_libpq_older_than_16(server, monkeypatch):
    monkeypatch.setattr(psycopg.pq, "version", lambda: 150004)
    with pytest.raises(ConfigError, match="libpq"):
        connect()


# 10. Address and environment


def test_pghostaddr_cannot_redirect(server, monkeypatch):
    monkeypatch.setenv("PGHOSTADDR", "203.0.113.9")
    connect()
    assert server.attempts[0]["host"] == REMOTE
    assert server.attempts[0]["hostaddr"] == "192.0.2.10"


def test_every_address_of_the_host_is_passed_in_order(server):
    connect("localhost")
    assert server.attempts[0]["host"] == "localhost,localhost"
    assert server.attempts[0]["hostaddr"] == "::1,127.0.0.1"


@pytest.mark.parametrize("host", ["127.0.0.1", "::1"])
def test_an_address_is_used_as_given(host, server):
    connect(host)
    assert server.attempts[0]["hostaddr"] == host
    assert server.lookups == []


def test_each_new_connection_resolves_again(server):
    connection = connect()
    server.addresses[REMOTE] = ["192.0.2.20"]
    connection.transaction(lambda conn: None)
    assert [attempt["hostaddr"] for attempt in server.attempts] == ["192.0.2.10", "192.0.2.20"]


def test_a_host_that_does_not_resolve_is_retried_then_unavailable(server):
    server.addresses = {}
    with pytest.raises(StoreUnavailableError, match=r"db\.example\.com:5432"):
        connect(retry=StoreRetrySettings(max_attempts=3))
    assert server.lookups == [REMOTE] * 3
    assert server.attempts == []


@pytest.mark.parametrize(
    ("variable", "value"), [("PGOPTIONS", "-c search_path=other"), ("PGSERVICE", "other")]
)
def test_session_variables_are_refused(variable, value, server, monkeypatch):
    monkeypatch.setenv(variable, value)
    with pytest.raises(ConfigError, match=f"Unset {variable}"):
        connect()
    assert server.attempts == []
    assert server.pools == []


@pytest.mark.parametrize("variable", ["PGOPTIONS", "PGSERVICE"])
def test_an_empty_session_variable_is_refused_too(variable, server, monkeypatch):
    # libpq looks up a service named "" for an empty PGSERVICE, and fails as if
    # the server were down; one rule for both variables says what to do instead.
    monkeypatch.setenv(variable, "")
    with pytest.raises(ConfigError, match=f"Unset {variable}"):
        connect()


def test_a_lookup_with_no_address_never_leaves_hostaddr_empty(server):
    # libpq reads an empty `hostaddr` as unset, and PGHOSTADDR would apply again.
    server.addresses[REMOTE] = []
    with pytest.raises(StoreUnavailableError, match=r"db\.example\.com:5432"):
        connect(retry=StoreRetrySettings(max_attempts=2))
    assert server.attempts == []
