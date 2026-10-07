"""Databricks credentials that delegate to the Databricks SDK (research R11, ADR 0018).

`databricks.sdk` is imported inside functions only, so `import tenetrag.auth`
works without the `databricks` extra. Each kind passes `auth_type`, so the SDK
cannot pick another auth family. The SDK still fills settings left unset from
its environment variables, with no switch to stop it. ADR 0018 accepts that,
and the first such credential in a process logs a warning naming them.

`ModelServingUserCredentials` and `get_user_workspace_client` are never used:
outside Model Serving they fall back to the default credential chain, which is
another identity (ADR 0003).
"""

from __future__ import annotations

import logging
import os
import sys
import threading
from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, Any, Protocol, TextIO
from urllib.parse import urlsplit

from tenetrag.auth.credentials import (
    AccessToken,
    Credential,
    CredentialKind,
    Secret,
    rejected_error,
)
from tenetrag.protocols.errors import CredentialSourceError, MissingExtraError, TenetRAGError

if TYPE_CHECKING:
    from databricks.sdk.core import Config

logger = logging.getLogger(__name__)

_env_warning_lock = threading.Lock()
_env_warning_logged = False

# What the SDK raises when it cannot get a token: ValueError for settings and
# profiles, OSError (IOError) when `databricks auth token` fails, as for an
# expired login, and for network failures.
_SDK_ERRORS = (ValueError, OSError)


class SdkConfig(Protocol):
    """The part of the SDK's `Config` used here."""

    @property
    def host(self) -> str | None: ...

    def authenticate(self) -> Mapping[str, str]: ...


class WorkspaceClientLike(Protocol):
    """The part of `databricks.sdk.WorkspaceClient` used here."""

    @property
    def config(self) -> SdkConfig: ...


def oauth_m2m(url: str, hostname: str, client_id: str, client_secret: Secret) -> Credential:
    settings = {
        "host": url,
        "client_id": client_id,
        "client_secret": client_secret.reveal(),
        "auth_type": "oauth-m2m",
    }
    return _delegated(
        CredentialKind.OAUTH_M2M,
        identity=f"oauth_m2m:{client_id}@{hostname}",
        source="code",
        remedy="Check the service principal's client ID and secret, and the workspace URL.",
        settings=settings,
    )


def oauth_u2m(url: str, hostname: str) -> Credential:
    # The SDK's browser flow waits with no timeout, so a run with no user present would hang.
    if not (_is_terminal(sys.stdin) and _is_terminal(sys.stdout)):
        raise CredentialSourceError(
            "oauth_u2m opens a browser login, which needs a terminal, and this process has "
            "none. Log in once with `databricks auth login --profile <name>`, then use a "
            "cli_profile credential."
        )
    return _delegated(
        CredentialKind.OAUTH_U2M,
        identity=f"oauth_u2m:{hostname}",
        source="browser",
        remedy="Run the login again in a terminal, or use a cli_profile credential.",
        settings={"host": url, "auth_type": "external-browser"},
    )


def cli_profile(name: str, config_file: str | None) -> Credential:
    settings = {"profile": name, "auth_type": "databricks-cli"}
    if config_file is not None:
        settings["config_file"] = config_file
    identity = f"cli_profile:{name}"
    return _delegated(
        CredentialKind.CLI_PROFILE,
        identity=identity,
        source=identity,
        remedy=f"Run `databricks auth login --profile {name}`, then try again.",
        settings=settings,
    )


def runtime() -> Credential:
    if "DATABRICKS_RUNTIME_VERSION" not in os.environ:
        raise CredentialSourceError(
            "The runtime credential works only on Databricks compute, and "
            "DATABRICKS_RUNTIME_VERSION is not set. Elsewhere, use cli_profile, oauth_m2m or pat."
        )
    return _delegated(
        CredentialKind.RUNTIME,
        identity="runtime",
        source="runtime",
        remedy="Check that the code runs on Databricks compute that has an identity.",
        settings={"auth_type": "runtime"},
    )


def workspace_client(client: WorkspaceClientLike) -> Credential:
    _warn_about_sdk_env()
    config = client.config
    hostname = urlsplit(config.host).hostname if config.host else None
    identity = f"workspace_client:{hostname}" if hostname else "workspace_client"
    tokens = _SdkTokenSource(
        config,
        identity=identity,
        remedy="Check how the WorkspaceClient authenticates.",
        rebuild=None,
    )
    return Credential(
        kind=CredentialKind.WORKSPACE_CLIENT,
        identity=identity,
        source="code",
        refreshable=True,
        _token_source=tokens,
        _host=config.host,
    )


def _delegated(
    kind: CredentialKind, *, identity: str, source: str, remedy: str, settings: dict[str, str]
) -> Credential:
    _warn_about_sdk_env()

    def build() -> SdkConfig:
        try:
            return _new_config(**settings)
        except TenetRAGError:
            raise  # MissingExtraError is also a ValueError
        except _SDK_ERRORS as exc:
            raise _source_error(identity, remedy) from exc

    config = build()
    tokens = _SdkTokenSource(config, identity=identity, remedy=remedy, rebuild=build)
    return Credential(
        kind=kind,
        identity=identity,
        source=source,
        refreshable=True,
        _token_source=tokens,
        _host=config.host,
    )


class _SdkTokenSource:
    """Takes each token from the SDK's `Config`, which caches and refreshes it under its own lock.

    A rejection builds a new `Config` once, which fetches a fresh token. The
    caller's own `WorkspaceClient` cannot be rebuilt, so it is asked once more.
    Tokens are compared by value, since each `token()` wraps a new header.
    """

    def __init__(
        self,
        config: SdkConfig,
        *,
        identity: str,
        remedy: str,
        rebuild: Callable[[], SdkConfig] | None,
    ) -> None:
        self._config = config
        self._identity = identity
        self._remedy = remedy
        self._rebuild = rebuild
        self._lock = threading.Lock()
        self._rejected: Secret | None = None
        self._awaiting_new = False
        self._after_rejection: Secret | None = None

    def token(self) -> AccessToken:
        with self._lock:
            try:
                headers = self._config.authenticate()
            except _SDK_ERRORS as exc:
                raise _source_error(self._identity, self._remedy) from exc
            value = Secret(_bearer_value(headers, self._identity))
            if self._awaiting_new:
                self._after_rejection = value
                self._awaiting_new = False
            return AccessToken(value, expires_at=None)

    def invalidate(self, rejected: AccessToken) -> None:
        with self._lock:
            if _same(self._after_rejection, rejected.value):
                raise rejected_error(self._identity, refreshable=True)
            if _same(self._rejected, rejected.value):
                return  # already reported by another request
            self._rejected = rejected.value
            self._awaiting_new = True
            if self._rebuild is not None:
                self._config = self._rebuild()


def _same(known: Secret | None, other: Secret) -> bool:
    return known is not None and known.reveal() == other.reveal()


def _bearer_value(headers: Mapping[str, str], identity: str) -> str:
    scheme, _, value = headers.get("Authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not value:
        raise CredentialSourceError(
            f"The Databricks SDK gave no bearer token for {identity}. "
            "Use a credential kind that issues OAuth or personal access tokens."
        )
    return value


def _source_error(identity: str, remedy: str) -> CredentialSourceError:
    return CredentialSourceError(f"The Databricks credential {identity} got no token. {remedy}")


def _is_terminal(stream: TextIO | None) -> bool:
    return stream is not None and stream.isatty()


def _config_class() -> type[Config]:
    try:
        from databricks.sdk.core import Config
    except ImportError as exc:
        raise MissingExtraError("databricks") from exc
    return Config


def _new_config(**settings: str) -> SdkConfig:
    """Build the SDK's `Config`. The unit tests replace this function, so they make no SDK call."""
    keyword_args: dict[str, Any] = settings  # Config takes them through **kwargs
    return _config_class()(**keyword_args)


def _warn_about_sdk_env() -> None:
    """Name, once per process, the variables the SDK will read for settings left unset."""
    global _env_warning_logged
    names = sorted(name for name in _sdk_env_names() if os.environ.get(name))
    if not names:
        return
    with _env_warning_lock:
        if _env_warning_logged:
            return
        _env_warning_logged = True
    logger.warning(
        "The Databricks SDK fills settings this credential leaves unset from these environment "
        "variables: %s. Unset any that belong to another identity (ADR 0018).",
        ", ".join(names),
    )


def _sdk_env_names() -> set[str]:
    # The SDK's own list, so markers it never reads (DATABRICKS_RUNTIME_VERSION) stay out.
    names: set[str] = set()
    for attribute in _config_class().attributes():
        if attribute.env:
            names.add(attribute.env)
        names.update(attribute.env_aliases)
    return names
