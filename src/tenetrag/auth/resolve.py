"""Pick the credential for one target: from code, else from the profile's named source.

contracts/auth.md: a credential from code wins. Otherwise the profile's source
is resolved, reading only what it names. With neither, `MissingCredentialError`.
A kind the target cannot use raises `CredentialMismatchError` before any
source is read.
"""

from __future__ import annotations

import dataclasses
import enum
from collections.abc import Mapping
from types import MappingProxyType
from typing import assert_never

from tenetrag.auth.credentials import Credential, CredentialKind, Credentials, Secret
from tenetrag.config.sources import (
    ApiKeySource,
    BasicSource,
    CliProfileSource,
    CredentialSource,
    NoneSource,
    OAuthM2MSource,
    OAuthU2MSource,
    PatSource,
    RuntimeSource,
)
from tenetrag.protocols.errors import (
    ConfigError,
    CredentialMismatchError,
    CredentialSourceError,
    MissingCredentialError,
)


class TargetKind(enum.Enum):
    """What a credential is for. The value names the target in errors."""

    NEO4J = "Neo4j connection"
    POSTGRES = "Postgres connection"
    OPENAI_COMPATIBLE = "OpenAI-compatible model"
    DATABRICKS_MODEL = "Databricks model"


_Kind = CredentialKind
ACCEPTED_KINDS: Mapping[TargetKind, frozenset[CredentialKind]] = MappingProxyType(
    {
        TargetKind.NEO4J: frozenset({_Kind.BASIC, _Kind.NONE}),
        # libpq reads PGPASSWORD and ~/.pgpass when no password is passed, so no `none`.
        TargetKind.POSTGRES: frozenset({_Kind.BASIC, _Kind.TOKEN_PROVIDER}),
        TargetKind.OPENAI_COMPATIBLE: frozenset({_Kind.API_KEY, _Kind.NONE}),
        TargetKind.DATABRICKS_MODEL: frozenset(
            {
                _Kind.PAT,
                _Kind.OBO,
                _Kind.OAUTH_M2M,
                _Kind.OAUTH_U2M,
                _Kind.CLI_PROFILE,
                _Kind.RUNTIME,
                _Kind.WORKSPACE_CLIENT,
            }
        ),
    }
)


def resolve_credential(
    target: TargetKind,
    target_name: str,
    source: CredentialSource | None,
    override: Credential | None = None,
    *,
    workspace_url: str | None = None,
) -> Credential:
    """The credential for `target`, named `target_name` (a dotted profile path) in errors.

    `workspace_url` is the model's, which `pat`, `oauth_m2m` and `oauth_u2m`
    sources need, since the profile names it on the model, not the source.
    """
    if override is not None:
        _check_kind(override.kind, target, target_name)
        return override
    if source is None:
        raise MissingCredentialError(
            f"{target_name} needs a credential, and none was given. Pass one in code, or name "
            f"a source under `credential` in the profile. A {target.value} accepts: "
            f"{_accepted(target)}."
        )
    _check_kind(CredentialKind(source.kind), target, target_name)
    try:
        return _from_source(source, target_name, workspace_url)
    except CredentialSourceError as exc:
        exc.add_note(f"While resolving the credential of {target_name}.")
        raise


def _from_source(
    source: CredentialSource, target_name: str, workspace_url: str | None
) -> Credential:
    match source:
        case NoneSource():
            return Credentials.none()
        case ApiKeySource(env=env):
            return _named(Credentials.api_key(Secret.from_env(env)), env)
        case BasicSource(user=user, password_env=env):
            return _named(Credentials.basic(user, Secret.from_env(env)), env)
        case PatSource(token_env=env):
            host = _workspace_url(workspace_url, source.kind, target_name)
            return _named(Credentials.pat(host, Secret.from_env(env)), env)
        case OAuthM2MSource(client_id=client_id, client_secret_env=env):
            host = _workspace_url(workspace_url, source.kind, target_name)
            return _named(Credentials.oauth_m2m(host, client_id, Secret.from_env(env)), env)
        case OAuthU2MSource():
            return Credentials.oauth_u2m(_workspace_url(workspace_url, source.kind, target_name))
        case CliProfileSource(name=name, config_file=config_file):
            return Credentials.cli_profile(name, config_file=config_file)
        case RuntimeSource():
            return Credentials.runtime()
        case _:
            assert_never(source)


def _named(credential: Credential, env: str) -> Credential:
    return dataclasses.replace(credential, source=f"env:{env}")


def _workspace_url(workspace_url: str | None, kind: str, target_name: str) -> str:
    if workspace_url is None:
        raise ConfigError(
            f"{target_name}: a {kind} credential needs the workspace URL. "
            "Set `workspace_url` on the model in the profile."
        )
    return workspace_url


def _check_kind(kind: CredentialKind, target: TargetKind, target_name: str) -> None:
    if kind not in ACCEPTED_KINDS[target]:
        raise CredentialMismatchError(
            f"{target_name}: a {kind.value} credential cannot be used for a {target.value}. "
            f"Use one of: {_accepted(target)}."
        )


def _accepted(target: TargetKind) -> str:
    return ", ".join(sorted(kind.value for kind in ACCEPTED_KINDS[target]))
