"""Postgres connections through psycopg and psycopg-pool (contracts/storage.md, research R12).

psycopg is imported only when a connection is opened.

- **Login:** each physical connection gets its password as it connects, from a
  connection class bound to the credential: the `basic` password, or the current
  token of a `token_provider`. So the password never sits in the pool's settings,
  and a rejected token is re-minted once, for that connection.
- **Address:** each physical connection resolves `host` itself and passes every
  address as `hostaddr`, as psycopg would. psycopg skips its own lookup when
  PGHOSTADDR is set, and libpq then connects to that address under the profile's
  host name; an explicit `hostaddr` wins over the variable. PGOPTIONS and
  PGSERVICE, which change the session, are refused (research R12).
- **Opening:** one connection outside the pool first, so a rejected credential or
  a missing database raises at once. The pool's own open would only time out.
- **Errors:** a failed connection attempt keeps libpq's connection object, password
  included, on `exc.pgconn`. The login class re-raises such a failure as a new
  error of the same class, with the password masked and no `pgconn`, so what
  reaches callers, logs and the pool is safe to chain. libpq gives a failed
  login no SQLSTATE, so a rejection is read from the server's message.
"""

from __future__ import annotations

import ipaddress
import math
import os
import re
import socket
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Self, TypeVar

from tenetrag._retry import RetryExhaustedError, RetryPolicy, Verdict, run_with_retry
from tenetrag.auth import Credential, Secret, TargetKind, resolve_credential
from tenetrag.auth.credentials import AccessToken, BearerSource, rejected_error
from tenetrag.config import PostgresSettings, TlsMode
from tenetrag.protocols.errors import (
    ConfigError,
    CredentialMismatchError,
    CredentialRejectedError,
    MissingExtraError,
    QueryError,
    StoreUnavailableError,
    UnsupportedServerError,
)
from tenetrag.storage._shared import HealthReport, address, is_local_host

if TYPE_CHECKING:
    import psycopg

T = TypeVar("T")

# `require_auth` and `sslrootcert=system` need libpq 16.
_MIN_LIBPQ = 160000
_MIN_SERVER = 160000
_MIN_SERVER_TEXT = "16"
_EXTENSIONS = ("pg_trgm", "vector")

# Retried besides class 08: shutdowns, too many connections, serialization
# failures and deadlocks (research R10).
_TRANSIENT_SQLSTATES = frozenset({"57P01", "57P02", "57P03", "53300", "40001", "40P01"})

# The server's words for a refused login, in English. A server set to another
# language for `lc_messages` words them differently, and a refusal then counts
# as a failed connection: it is retried, then reported as unavailable.
_REJECTION_MARKERS = (
    "password authentication failed",
    "no pg_hba.conf entry",
    "pg_hba.conf rejects connection",
)
_MISSING_DATABASE = re.compile(r'database "[^"]*" does not exist')

# libpq applies these to every connection. PGOPTIONS sends server settings, such as
# search_path; PGSERVICE loads parameters, `options` among them, from a service
# file. They are refused rather than masked: masking PGOPTIONS means always sending
# `options`, which poolers that limit startup parameters may reject. An empty value
# is refused too, since libpq looks up a service named "" for an empty PGSERVICE.
_SESSION_VARIABLES = ("PGOPTIONS", "PGSERVICE")


class PostgresConnection:
    """One pool for one identity. Thread-safe: each unit of work checks out its own connection."""

    def __init__(
        self,
        settings: PostgresSettings,
        *,
        name: str,
        credential: Credential | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        try:
            import psycopg
            import psycopg_pool
        except ImportError as exc:
            raise MissingExtraError("postgres") from exc
        libpq = psycopg.pq.version()
        if libpq < _MIN_LIBPQ:
            raise ConfigError(
                f"psycopg uses libpq {libpq // 10000}.{libpq % 10000}, and TenetRAG needs "
                "libpq 16 or later. Install psycopg[binary], which ships a recent libpq, or "
                "upgrade the system libpq."
            )
        self._target = f"connections.{name}"
        self._credential = resolve_credential(
            TargetKind.POSTGRES, self._target, settings.credential, credential
        )
        self._settings = settings
        self._address = address(settings.host, settings.port)
        self._sleep = sleep
        self._clock = clock
        self._policy = RetryPolicy(
            max_attempts=settings.retry.max_attempts,
            max_total_seconds=settings.retry.max_total_seconds,
            initial_backoff_seconds=settings.retry.initial_backoff_seconds,
            max_backoff_seconds=settings.retry.max_backoff_seconds,
        )
        login = _Login(self._credential)
        params = _connection_params(settings, login.user)
        connection_class = _login_class(login)
        self._run(lambda: connection_class.connect(**params)).close()
        self._pool = psycopg_pool.ConnectionPool(
            "",
            connection_class=connection_class,
            kwargs=params,
            min_size=settings.pool.min_size,
            max_size=settings.pool.max_size,
            max_lifetime=settings.pool.max_age_seconds,
            timeout=settings.pool.acquire_timeout_seconds,
            check=psycopg_pool.ConnectionPool.check_connection,
            name=self._target,
            open=False,
        )
        try:
            self._pool.open(wait=True, timeout=settings.pool.acquire_timeout_seconds)
        except psycopg_pool.PoolTimeout as exc:  # the pool has closed itself
            raise StoreUnavailableError(
                f"Postgres at {self._address} accepted one connection, but the pool could not "
                f"open {settings.pool.min_size} within {settings.pool.acquire_timeout_seconds:g} "
                f"s. Check the server's max_connections, or lower pool.min_size in "
                f"{self._target}."
            ) from exc

    def health(self) -> HealthReport:
        """The server version and extensions. `UnsupportedServerError` below the floors."""
        query = "SELECT name FROM pg_available_extensions WHERE name = ANY(%s)"

        def check(conn: psycopg.Connection[Any]) -> tuple[int, str, set[str], bool]:
            version_num = conn.execute("SHOW server_version_num").fetchone()
            version = conn.execute("SHOW server_version").fetchone()
            rows = conn.execute(query, (list(_EXTENSIONS),)).fetchall()
            return (
                int(version_num[0]) if version_num else 0,
                str(version[0]) if version else "unknown",
                {row[0] for row in rows},
                conn.pgconn.ssl_in_use,
            )

        version_num, version, available, encrypted = self.transaction(check, read_only=True)
        if version_num < _MIN_SERVER:
            raise UnsupportedServerError(
                f"Postgres at {self._address} runs {version}, and TenetRAG needs "
                f"{_MIN_SERVER_TEXT} or later. Upgrade the server."
            )
        missing = [name for name in _EXTENSIONS if name not in available]
        if missing:
            raise UnsupportedServerError(
                f"Postgres at {self._address} cannot install the extensions "
                f"{', '.join(missing)}. Install their packages on the server."
            )
        return HealthReport(
            backend="postgres",
            server_version=version,
            edition=None,
            extensions={name: True for name in _EXTENSIONS},
            identity=self._credential.identity,
            encrypted=encrypted,
        )

    def transaction(
        self, work: Callable[[psycopg.Connection[Any]], T], *, read_only: bool = False
    ) -> T:
        """Run `work` in one transaction on a pooled connection, replayed whole when transient."""

        def unit() -> T:
            with self._pool.connection() as conn:
                conn.read_only = read_only
                with conn.transaction():
                    return work(conn)

        return self._run(unit)

    def _run(self, fn: Callable[[], T]) -> T:
        import psycopg

        try:
            return run_with_retry(
                fn, _classify, policy=self._policy, clock=self._clock, sleep=self._sleep
            )
        except RetryExhaustedError as exc:
            raise StoreUnavailableError(
                f"Postgres at {self._address} is unavailable after {exc.attempts} attempts in "
                f"{exc.elapsed_seconds:.1f} s. Check that the server is running and reachable, "
                f"or raise retry.max_attempts or retry.max_total_seconds in {self._target}."
            ) from exc.__cause__
        except psycopg.Error as exc:
            raise self._query_error(exc) from exc

    def _query_error(self, exc: psycopg.Error) -> QueryError:
        message = str(exc)
        if exc.sqlstate is None and _MISSING_DATABASE.search(message):
            return QueryError(
                f"The database {self._settings.database!r} does not exist on Postgres at "
                f"{self._address}. Create it, or fix `database` in {self._target}."
            )
        first_line = message.partition("\n")[0]  # a DETAIL line may repeat row values
        return QueryError(
            f"Postgres at {self._address} failed the unit of work (SQLSTATE "
            f"{exc.sqlstate or 'none'}): {first_line}"
        )

    def close(self) -> None:
        self._pool.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def __repr__(self) -> str:
        return (
            f"PostgresConnection({self._target!r}, host={self._settings.host!r}, "
            f"port={self._settings.port}, database={self._settings.database!r}, "
            f"credential={self._credential.identity!r})"
        )


def _classify(exc: Exception) -> Verdict:
    import psycopg
    import psycopg_pool

    if not isinstance(exc, psycopg.Error) or isinstance(exc, psycopg_pool.PoolClosed):
        return Verdict.fail()  # the caller's own error, a rejected credential, or a closed pool
    sqlstate = exc.sqlstate
    if sqlstate is None:
        # A failed or lost connection, or a pool timeout: libpq gives these no SQLSTATE.
        if isinstance(exc, psycopg.OperationalError) and not _MISSING_DATABASE.search(str(exc)):
            return Verdict.retry()
        return Verdict.fail()
    if sqlstate.startswith("08") or sqlstate in _TRANSIENT_SQLSTATES:
        return Verdict.retry()
    return Verdict.fail()


def _connection_params(settings: PostgresSettings, user: str) -> dict[str, Any]:
    """Everything libpq would otherwise take from `PG*` variables or files, except the
    password and `hostaddr`, which each connection adds as it connects."""
    params: dict[str, Any] = {
        "host": settings.host,
        "port": settings.port,
        "dbname": settings.database,
        "user": user,
        "sslmode": _sslmode(settings.tls, settings.host),
        # No client certificate, GSS encryption, or GSSAPI or SSPI login: each would
        # authenticate with an identity found on the machine, not the credential.
        "sslcertmode": "disable",
        "gssencmode": "disable",
        "require_auth": "!gss,!sspi",
        "connect_timeout": math.ceil(settings.connect_timeout_seconds),  # libpq takes seconds
    }
    if settings.tls is TlsMode.VERIFY:
        params["sslrootcert"] = "system"
    return params


def _refuse_session_variables() -> None:
    for variable in _SESSION_VARIABLES:
        if variable in os.environ:
            raise ConfigError(
                f"{variable} is set, and libpq would apply it to every TenetRAG connection, "
                "where it can change server settings such as search_path. Unset "
                f"{variable} for this process: the profile holds every setting TenetRAG needs."
            )


def _with_addresses(params: dict[str, Any]) -> dict[str, Any]:
    """`params` with every address of `host` as `hostaddr`, looked up now."""
    import psycopg

    host: str = params["host"]
    try:
        ipaddress.ip_address(host)
    except ValueError:
        try:
            found = socket.getaddrinfo(
                host, params["port"], proto=socket.IPPROTO_TCP, type=socket.SOCK_STREAM
            )
        except OSError as exc:
            # psycopg's own error for this, so a failed lookup is retried like a refusal.
            raise psycopg.OperationalError(f"failed to resolve host {host!r}: {exc}") from exc
        addresses = [str(info[4][0]) for info in found]
    else:
        addresses = [host]
    if not addresses:  # an empty `hostaddr` is unset, and PGHOSTADDR would apply again
        raise psycopg.OperationalError(f"failed to resolve host {host!r}: no address")
    return {**params, "host": ",".join([host] * len(addresses)), "hostaddr": ",".join(addresses)}


def _sslmode(tls: TlsMode, host: str) -> str:
    if tls is TlsMode.OFF:
        return "disable"
    if tls is TlsMode.VERIFY:
        return "verify-full"
    if tls is TlsMode.REQUIRE or not is_local_host(host):
        return "require"
    return "disable"


@dataclass(frozen=True, slots=True)
class _Refusal:
    """The server refused a login; `reason` is its message, with the password masked."""

    reason: str


C = TypeVar("C")


class _Login:
    """Gives each new connection its password, and re-mints a rejected token once."""

    def __init__(self, credential: Credential) -> None:
        if credential._user is None:  # basic and token_provider, the kinds admitted, have one
            raise CredentialMismatchError(
                f"A {credential.kind.value} credential cannot be used for a Postgres connection."
            )
        self._credential = credential
        self.user = credential._user

    def connect(self, open_with: Callable[[str], C]) -> C:
        """`open_with(password)` opens one connection."""
        tokens = self._credential._token_source
        if tokens is not None:
            return self._connect_with_token(open_with, tokens)
        password = self._credential._password
        if password is None:  # resolve_credential admits only basic and token_provider
            raise CredentialMismatchError(
                f"A {self._credential.kind.value} credential cannot be used for a Postgres "
                "connection."
            )
        outcome = self._attempt(open_with, password)
        if isinstance(outcome, _Refusal):
            raise self._rejected(outcome)
        return outcome

    def _connect_with_token(self, open_with: Callable[[str], C], tokens: BearerSource) -> C:
        token = tokens.token()
        outcome = self._attempt(open_with, token.value)
        if isinstance(outcome, _Refusal):
            self._invalidate(tokens, token, outcome)
            token = tokens.token()
            outcome = self._attempt(open_with, token.value)
            if isinstance(outcome, _Refusal):
                self._invalidate(tokens, token, outcome)
                # Reached only when another connection replaced the token meanwhile.
                raise self._rejected(outcome)
        return outcome

    def _attempt(self, open_with: Callable[[str], C], password: Secret) -> C | _Refusal:
        import psycopg

        failure: psycopg.Error
        try:
            return open_with(password.reveal())
        except psycopg.Error as exc:
            message = str(exc).replace(password.reveal(), "***")
            if any(marker in message for marker in _REJECTION_MARKERS):
                return _Refusal(message.rpartition("FATAL:")[2].strip())
            failure = type(exc)(message)  # without exc.pgconn, which keeps the password
        raise failure  # outside the except block, so the original is not its context

    def _invalidate(self, tokens: BearerSource, token: AccessToken, refusal: _Refusal) -> None:
        try:
            tokens.invalidate(token)  # raises when the token cannot be re-minted
        except CredentialRejectedError as exc:
            exc.add_note(f"The server said: {refusal.reason}")
            raise

    def _rejected(self, refusal: _Refusal) -> CredentialRejectedError:
        error = rejected_error(self._credential.identity, refreshable=self._credential.refreshable)
        error.add_note(f"The server said: {refusal.reason}")
        return error


def _login_class(login: _Login) -> type[psycopg.Connection[Any]]:
    """A connection class whose `connect`, as the pool calls it, adds the login's password."""
    import psycopg

    class LoginConnection(psycopg.Connection[Any]):
        @classmethod
        def connect(cls, conninfo: str = "", **kwargs: Any) -> LoginConnection:  # noqa: ANN401 - forwarded to psycopg as given
            _refuse_session_variables()
            params = _with_addresses(kwargs)

            def open_with(password: str) -> LoginConnection:
                return super(LoginConnection, cls).connect(conninfo, password=password, **params)

            return login.connect(open_with)

    return LoginConnection
