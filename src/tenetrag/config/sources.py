"""Credential sources a profile may name (data-model §3, ADR 0018).

A source says where a secret comes from, never the secret. Which kinds a
target accepts is checked when the credential is resolved (`tenetrag.auth`).
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from tenetrag.config.phases import Operational

EnvVarName = Annotated[str, Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]*$"), Operational()]
_Name = Annotated[str, Field(min_length=1), Operational()]


class _Source(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class NoneSource(_Source):
    """No credential, for targets that accept anonymous access, such as a local proxy."""

    kind: Annotated[Literal["none"], Operational()]


class ApiKeySource(_Source):
    kind: Annotated[Literal["api_key"], Operational()]
    env: EnvVarName


class BasicSource(_Source):
    kind: Annotated[Literal["basic"], Operational()]
    user: _Name
    password_env: EnvVarName


class PatSource(_Source):
    kind: Annotated[Literal["pat"], Operational()]
    token_env: EnvVarName


class OAuthM2MSource(_Source):
    kind: Annotated[Literal["oauth_m2m"], Operational()]
    client_id: _Name
    client_secret_env: EnvVarName


class OAuthU2MSource(_Source):
    """A browser login for the model's `workspace_url`; terminal sessions only."""

    kind: Annotated[Literal["oauth_u2m"], Operational()]


class CliProfileSource(_Source):
    """A Databricks CLI profile, passed to the Databricks SDK by name."""

    kind: Annotated[Literal["cli_profile"], Operational()]
    name: _Name
    config_file: Annotated[str | None, Field(min_length=1), Operational()] = None


class RuntimeSource(_Source):
    """The identity of the Databricks runtime the code runs in."""

    kind: Annotated[Literal["runtime"], Operational()]


CredentialSource = Annotated[
    NoneSource
    | ApiKeySource
    | BasicSource
    | PatSource
    | OAuthM2MSource
    | OAuthU2MSource
    | CliProfileSource
    | RuntimeSource,
    Field(discriminator="kind"),
]
