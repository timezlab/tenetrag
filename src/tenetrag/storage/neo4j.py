"""Neo4j connections (contracts/storage.md, research R13).

The `neo4j` driver is imported only when a connection is opened. The driver's
managed transactions replay a unit of work on transient errors, within the
store retry budget; this module maps what is left to SDK errors. A rejected
credential is raised without the driver's error, whose text came from the
server; other driver errors hold no secret and are chained.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Self, TypeVar
from urllib.parse import urlsplit

from tenetrag.auth import Credential, CredentialKind, TargetKind, resolve_credential
from tenetrag.auth.credentials import rejected_error
from tenetrag.config import Neo4jSettings, TlsMode
from tenetrag.protocols.errors import (
    ConfigError,
    CredentialMismatchError,
    MissingExtraError,
    QueryError,
    StoreUnavailableError,
    UnsupportedServerError,
)
from tenetrag.storage._shared import HealthReport, address, is_local_host

if TYPE_CHECKING:
    import neo4j

T = TypeVar("T")

_DEFAULT_PORT = 7687
_MIN_VERSION = (2026, 9)
_MIN_VERSION_TEXT = "2026.09"
# A pooled connection idle longer than this is checked with a round trip before use (R13).
_LIVENESS_CHECK_SECONDS = 30
_DATABASE_NOT_FOUND = "Neo.ClientError.Database.DatabaseNotFound"
_COMPONENTS = "CALL dbms.components() YIELD name, versions, edition RETURN name, versions, edition"


class Neo4jConnection:
    """One driver, so one pool, for one identity. Thread-safe: each unit gets its own session."""

    def __init__(
        self, settings: Neo4jSettings, *, name: str, credential: Credential | None = None
    ) -> None:
        try:
            import neo4j
        except ImportError as exc:
            raise MissingExtraError("neo4j") from exc
        self._target = f"connections.{name}"
        self._credential = resolve_credential(
            TargetKind.NEO4J, self._target, settings.credential, credential
        )
        parts = urlsplit(settings.uri)
        host = parts.hostname or ""  # the profile refuses a URI without a host
        self._uri = settings.uri
        self._address = address(host, parts.port or _DEFAULT_PORT)
        self._database = settings.database
        self._retry_seconds = settings.retry.max_total_seconds
        config: dict[str, Any] = {
            "telemetry_disabled": True,
            "max_connection_pool_size": settings.pool.max_size,
            "max_connection_lifetime": settings.pool.max_age_seconds,
            "connection_acquisition_timeout": settings.pool.acquire_timeout_seconds,
            "max_transaction_retry_time": settings.retry.max_total_seconds,
            "connection_timeout": settings.connect_timeout_seconds,
            "liveness_check_timeout": _LIVENESS_CHECK_SECONDS,
            **_tls_config(parts.scheme, host, settings.tls, self._target),
        }
        self._driver = neo4j.GraphDatabase.driver(
            settings.uri, auth=_auth(self._credential), **config
        )

    def health(self) -> HealthReport:
        """The kernel's version and edition. `UnsupportedServerError` below 2026.09."""
        rows = self.read(lambda tx: tx.run(_COMPONENTS).data())
        kernel = next((row for row in rows if row.get("name") == "Neo4j Kernel"), {})
        versions = kernel.get("versions") or ["unknown"]
        version, edition = str(versions[0]), kernel.get("edition")
        match = re.match(r"(\d+)\.(\d+)", version)
        if match is None or (int(match[1]), int(match[2])) < _MIN_VERSION:
            raise UnsupportedServerError(
                f"Neo4j at {self._address} runs {version} ({edition}), and TenetRAG needs "
                f"{_MIN_VERSION_TEXT} or later. Upgrade the server."
            )
        return HealthReport(
            backend="neo4j",
            server_version=version,
            edition=edition,
            extensions={},
            identity=self._credential.identity,
            encrypted=self._driver.encrypted,
        )

    def read(self, work: Callable[[neo4j.ManagedTransaction], T]) -> T:
        """Run `work` in one read transaction, replayed whole on a transient error."""
        return self._run(work, write=False)

    def write(self, work: Callable[[neo4j.ManagedTransaction], T]) -> T:
        """Run `work` in one write transaction, replayed whole on a transient error."""
        return self._run(work, write=True)

    def _run(self, work: Callable[[neo4j.ManagedTransaction], T], *, write: bool) -> T:
        import neo4j

        try:
            with self._driver.session(database=self._database) as session:
                if write:
                    return session.execute_write(work)
                return session.execute_read(work)
        except neo4j.exceptions.AuthError:
            pass  # raised below, outside this block, so the driver's error is not its context
        except (
            neo4j.exceptions.ServiceUnavailable,
            neo4j.exceptions.SessionExpired,
            neo4j.exceptions.ConnectionAcquisitionTimeoutError,
        ) as exc:
            raise StoreUnavailableError(
                f"Neo4j at {self._address} is unavailable ({type(exc).__name__}) after the "
                f"retry budget of {self._retry_seconds:g} s. Check that the server is running "
                f"and reachable, or raise retry.max_total_seconds in {self._target}."
            ) from exc
        except neo4j.exceptions.Neo4jError as exc:
            if exc.code == _DATABASE_NOT_FOUND:
                raise QueryError(
                    f"The database {self._database!r} does not exist on Neo4j at "
                    f"{self._address}. Create it, or fix `database` in {self._target}."
                ) from exc
            raise QueryError(
                f"Neo4j at {self._address} failed the unit of work with {exc.code}: {exc.message}"
            ) from exc
        # Only a rejected credential gets here: every other path returns or raises.
        raise rejected_error(self._credential.identity, refreshable=self._credential.refreshable)

    def close(self) -> None:
        self._driver.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def __repr__(self) -> str:
        return (
            f"Neo4jConnection({self._target!r}, uri={self._uri!r}, "
            f"database={self._database!r}, credential={self._credential.identity!r})"
        )


def _tls_config(scheme: str, host: str, tls: TlsMode, target: str) -> dict[str, Any]:
    """Driver settings for `tls`. A `+s` scheme sets its own, which the driver lets nothing
    override: it encrypts and checks the certificate against the system CAs."""
    import neo4j

    secure = scheme.endswith("+s")
    if tls is TlsMode.OFF:
        if secure:
            raise ConfigError(
                f"{target}: tls is off, but the URI scheme {scheme}:// encrypts. Use "
                f"{scheme.removesuffix('+s')}:// with tls: off, or remove tls: off."
            )
        return {"encrypted": False}
    if secure:
        return {}
    if tls is TlsMode.REQUIRE:
        return {"encrypted": True, "trusted_certificates": neo4j.TrustAll()}
    if tls is TlsMode.VERIFY:
        return {"encrypted": True, "trusted_certificates": neo4j.TrustSystemCAs()}
    if is_local_host(host):
        return {}
    raise ConfigError(
        f"{target}: {scheme}:// would send data unencrypted to {host}. Use {scheme}+s:// "
        "instead, or set tls to require, verify or off."
    )


def _auth(credential: Credential) -> neo4j.Auth | None:
    import neo4j

    if credential.kind is CredentialKind.NONE:
        return None
    user, password = credential._user, credential._password
    if user is None or password is None:  # resolve_credential admits only basic and none
        raise CredentialMismatchError(
            f"A {credential.kind.value} credential cannot be used for a Neo4j connection."
        )
    return neo4j.basic_auth(user, password.reveal())
