"""Credentials passed in code (data-model §4, contracts/auth.md, ADR 0003).

A `Credential` names one identity and holds what authenticates it: a user and
password, or a token source for the bearer kinds. Nothing here reads a
variable, file or runtime the caller did not name, and nothing prints a
secret: `Secret` masks itself, and errors name identities, never values.
The Databricks kinds that need the Databricks SDK are built in `databricks.py`,
which is imported only when one of them is asked for.
"""

from __future__ import annotations

import enum
import os
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Protocol
from urllib.parse import urlsplit

from tenetrag.protocols.errors import ConfigError, CredentialRejectedError, CredentialSourceError

if TYPE_CHECKING:
    from tenetrag.auth.databricks import WorkspaceClientLike

# A token this close to its expiry is refreshed before use, so it cannot expire in flight.
_REFRESH_MARGIN = timedelta(seconds=60)


class Secret:
    """A string that never prints. Only code that builds a header or driver argument reveals it."""

    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        if not value:
            raise CredentialSourceError(
                "A secret cannot be empty. Pass the real value, or name its source."
            )
        self._value = value

    @classmethod
    def from_env(cls, name: str) -> Secret:
        """Read the named environment variable, and only that one."""
        value = os.environ.get(name)
        if not value:
            raise CredentialSourceError(
                f"The environment variable {name} is unset or empty. Set it to the secret, "
                "or name another credential source."
            )
        return cls(value)

    def reveal(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return "Secret('***')"

    def __str__(self) -> str:
        return "Secret('***')"


@dataclass(frozen=True, slots=True)
class AccessToken:
    """A bearer token and, when known, the time-zone-aware time it expires."""

    value: Secret
    expires_at: datetime | None

    def __post_init__(self) -> None:
        if self.expires_at is not None and self.expires_at.utcoffset() is None:
            raise ConfigError(
                "AccessToken.expires_at needs a time zone, such as datetime.now(UTC) + lifetime."
            )


class CredentialKind(enum.Enum):
    NONE = "none"
    API_KEY = "api_key"
    BASIC = "basic"
    TOKEN_PROVIDER = "token_provider"  # noqa: S105 - a kind name, not a secret
    PAT = "pat"
    OBO = "obo"
    OAUTH_M2M = "oauth_m2m"
    OAUTH_U2M = "oauth_u2m"
    CLI_PROFILE = "cli_profile"
    RUNTIME = "runtime"
    WORKSPACE_CLIENT = "workspace_client"


class BearerSource(Protocol):
    """What a bearer credential gives the code that sends requests.

    `invalidate(rejected)` reports that the server rejected `rejected`. A
    refreshable source fetches a new token on the next `token()`; a rejection of
    that new token, or of any token of a source that cannot refresh, raises
    `CredentialRejectedError`.
    """

    def token(self) -> AccessToken: ...

    def invalidate(self, rejected: AccessToken) -> None: ...


@dataclass(frozen=True)
class Credential:
    """One identity and what authenticates it. Build it with `Credentials`.

    `identity` is a label without secrets, such as `basic:neo4j`; pools are
    keyed by it and errors name it. `source` says where the secret came from:
    `code`, `env:NAME`, `cli_profile:NAME`, `runtime`, `browser`, or `none`.
    """

    kind: CredentialKind
    identity: str
    source: str
    refreshable: bool
    _token_source: BearerSource | None = field(default=None, repr=False, kw_only=True)
    _user: str | None = field(default=None, repr=False, kw_only=True)
    _password: Secret | None = field(default=None, repr=False, kw_only=True)
    _host: str | None = field(default=None, repr=False, kw_only=True)


def _utc_now() -> datetime:
    return datetime.now(UTC)


class _TokenSource:
    """The current token of one identity: cached, refreshed before expiry, one reauth.

    One lock covers the cache and the fetch, so threads that find the token
    missing or expiring wait for a single refresh. A token replaced near its
    expiry is a schedule, not a rejection, so it does not use up the reauth.
    """

    def __init__(
        self,
        fetch: Callable[[], AccessToken],
        *,
        identity: str,
        refreshable: bool,
        now: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._fetch = fetch
        self._identity = identity
        self._refreshable = refreshable
        self._now = now
        self._lock = threading.Lock()
        self._token: AccessToken | None = None
        self._rejected = False
        self._after_rejection: AccessToken | None = None

    def token(self) -> AccessToken:
        with self._lock:
            if self._token is None or self._expiring(self._token):
                self._token = self._fetch()
                # Only a fetch forced by a rejection uses up the one reauth.
                self._after_rejection = self._token if self._rejected else None
                self._rejected = False
            return self._token

    def invalidate(self, rejected: AccessToken) -> None:
        with self._lock:
            if not self._refreshable or rejected is self._after_rejection:
                raise rejected_error(self._identity, refreshable=self._refreshable)
            if rejected is not self._token:
                return  # already replaced, after another request reported it
            self._token = None
            self._rejected = True

    def _expiring(self, token: AccessToken) -> bool:
        return token.expires_at is not None and self._now() >= token.expires_at - _REFRESH_MARGIN


def rejected_error(identity: str, *, refreshable: bool) -> CredentialRejectedError:
    if refreshable:
        return CredentialRejectedError(
            f"The server rejected the credential {identity} again after a refresh. "
            "Check that this identity may use the target."
        )
    return CredentialRejectedError(
        f"The server rejected the credential {identity}, which cannot be refreshed. "
        "Pass a valid credential, or check that this identity may use the target."
    )


def _workspace(host: str) -> tuple[str, str]:
    """The workspace URL as `https://<host>`, and the host name for identities."""
    parts = urlsplit(host)
    if (
        parts.scheme != "https"
        or not parts.hostname
        or parts.username is not None
        or parts.password is not None
    ):
        # The message never repeats the value: a URL may hold a password.
        raise ConfigError(
            "Pass the workspace URL as https://<workspace host>, without a user or password."
        )
    return f"https://{parts.netloc}", parts.hostname


def _static_bearer(
    kind: CredentialKind, identity: str, token: Secret, host: str | None = None
) -> Credential:
    access = AccessToken(token, expires_at=None)
    return Credential(
        kind=kind,
        identity=identity,
        source="code",
        refreshable=False,
        _token_source=_TokenSource(lambda: access, identity=identity, refreshable=False),
        _host=host,
    )


class Credentials:
    """Constructors for every credential kind (contracts/auth.md).

    The Databricks constructors that delegate to the Databricks SDK need the
    `databricks` extra; `pat` and `obo` are plain bearer tokens and do not.
    """

    @staticmethod
    def none() -> Credential:
        return Credential(
            kind=CredentialKind.NONE, identity="none", source="none", refreshable=False
        )

    @staticmethod
    def api_key(key: Secret) -> Credential:
        return _static_bearer(CredentialKind.API_KEY, "api_key", key)

    @staticmethod
    def basic(user: str, password: Secret) -> Credential:
        return Credential(
            kind=CredentialKind.BASIC,
            identity=f"basic:{user}",
            source="code",
            refreshable=False,
            _user=user,
            _password=password,
        )

    @staticmethod
    def token_provider(user: str, mint: Callable[[], AccessToken], *, identity: str) -> Credential:
        """`mint` returns a new token for `identity` on each call, such as a Lakebase token."""
        label = f"token_provider:{identity}"
        return Credential(
            kind=CredentialKind.TOKEN_PROVIDER,
            identity=label,
            source="code",
            refreshable=True,
            _token_source=_TokenSource(mint, identity=label, refreshable=True),
            _user=user,
        )

    @staticmethod
    def pat(host: str, token: Secret) -> Credential:
        url, hostname = _workspace(host)
        return _static_bearer(CredentialKind.PAT, f"pat:{hostname}", token, host=url)

    @staticmethod
    def obo(host: str, token: Secret) -> Credential:
        """The end user's token from a Databricks Apps request header. Never refreshed."""
        url, hostname = _workspace(host)
        return _static_bearer(CredentialKind.OBO, f"obo:{hostname}", token, host=url)

    @staticmethod
    def oauth_m2m(host: str, client_id: str, client_secret: Secret) -> Credential:
        from tenetrag.auth import databricks

        url, hostname = _workspace(host)
        return databricks.oauth_m2m(url, hostname, client_id, client_secret)

    @staticmethod
    def oauth_u2m(host: str) -> Credential:
        """A browser login. Terminal sessions only; elsewhere use `cli_profile`."""
        from tenetrag.auth import databricks

        url, hostname = _workspace(host)
        return databricks.oauth_u2m(url, hostname)

    @staticmethod
    def cli_profile(name: str, *, config_file: str | None = None) -> Credential:
        from tenetrag.auth import databricks

        return databricks.cli_profile(name, config_file)

    @staticmethod
    def runtime() -> Credential:
        """The identity of the Databricks compute the code runs on."""
        from tenetrag.auth import databricks

        return databricks.runtime()

    @staticmethod
    def workspace_client(client: WorkspaceClientLike) -> Credential:
        """The caller's `databricks.sdk.WorkspaceClient`, used as given."""
        from tenetrag.auth import databricks

        return databricks.workspace_client(client)
