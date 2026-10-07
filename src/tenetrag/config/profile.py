"""The profile: named connections, models and the graph language (data-model §2, §5 to §7).

Every model is frozen and rejects unknown fields. Every leaf carries one phase
marker (phases.py); sections such as `retry` or `credential` carry none and
their leaves say Operational() themselves. No field holds a secret (FR-014).
"""

from __future__ import annotations

import enum
from collections.abc import Callable, Mapping
from typing import Annotated, Literal, Self
from urllib.parse import urlsplit

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

from tenetrag.config.phases import Content, IndexTime, Operational, QueryTime, Stage
from tenetrag.config.sources import CredentialSource


class _Settings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _url_check(schemes: frozenset[str]) -> Callable[[str], str]:
    def check(value: str) -> str:
        # Messages never repeat the value: a URL may hold a password.
        parts = urlsplit(value)
        if parts.scheme not in schemes:
            raise ValueError(f"use a URL with scheme {' or '.join(sorted(schemes))}")
        if not parts.hostname:
            raise ValueError("the URL needs a host")
        if parts.username is not None or parts.password is not None:
            raise ValueError(
                "remove the user and password from the URL, and name a credential "
                "source under `credential` instead"
            )
        return value

    return check


_HttpUrl = Annotated[str, AfterValidator(_url_check(frozenset({"http", "https"})))]
_WorkspaceUrl = Annotated[str, AfterValidator(_url_check(frozenset({"https"})))]
_Neo4jUri = Annotated[
    str, AfterValidator(_url_check(frozenset({"neo4j", "neo4j+s", "bolt", "bolt+s"})))
]

# Finite only: JSON, and so a stage hash, has no infinity or NaN.
_Seconds = Annotated[float, Field(gt=0, allow_inf_nan=False), Operational()]
_Count = Annotated[int, Field(ge=1), Operational()]
_Text = Annotated[str, Field(min_length=1), Operational()]


# Retry (§6)


class RetrySettings(_Settings):
    """The shape both retry defaults share; values feed `tenetrag._retry.RetryPolicy`."""

    max_attempts: _Count
    max_total_seconds: _Seconds
    initial_backoff_seconds: _Seconds
    max_backoff_seconds: _Seconds

    @model_validator(mode="after")
    def _backoff_in_order(self) -> Self:
        if self.initial_backoff_seconds > self.max_backoff_seconds:
            raise ValueError("initial_backoff_seconds must not exceed max_backoff_seconds")
        return self


class ModelRetrySettings(RetrySettings):
    max_attempts: _Count = 5
    max_total_seconds: _Seconds = 60.0
    initial_backoff_seconds: _Seconds = 0.5
    max_backoff_seconds: _Seconds = 8.0


class StoreRetrySettings(RetrySettings):
    """Store defaults; a partial `retry:` under a connection keeps these for the rest."""

    max_attempts: _Count = 5
    max_total_seconds: _Seconds = 30.0
    initial_backoff_seconds: _Seconds = 0.2
    max_backoff_seconds: _Seconds = 4.0


# Connections (§7)


class TlsMode(enum.Enum):
    """`auto` requires encryption unless the host is loopback or `localhost`."""

    AUTO = "auto"
    REQUIRE = "require"
    VERIFY = "verify"
    OFF = "off"


class PoolSettings(_Settings):
    max_size: _Count = 8
    # 12 hours, below Lakebase's 3-day connection limit.
    max_age_seconds: _Seconds = 43200.0
    acquire_timeout_seconds: _Seconds = 30.0


class PostgresPoolSettings(PoolSettings):
    min_size: Annotated[int, Field(ge=0), Operational()] = 1

    @model_validator(mode="after")
    def _sizes_in_order(self) -> Self:
        if self.min_size > self.max_size:
            raise ValueError("min_size must not exceed max_size")
        return self


class Neo4jSettings(_Settings):
    kind: Annotated[Literal["neo4j"], Operational()]
    uri: Annotated[_Neo4jUri, Operational()]
    database: _Text = "neo4j"
    credential: CredentialSource | None = None
    tls: Annotated[TlsMode, Operational()] = TlsMode.AUTO
    pool: PoolSettings = Field(default_factory=PoolSettings)
    connect_timeout_seconds: _Seconds = 15.0
    retry: StoreRetrySettings = Field(default_factory=StoreRetrySettings)


class PostgresSettings(_Settings):
    kind: Annotated[Literal["postgres"], Operational()]
    # A bare host name or address: no scheme, path or `user@`.
    host: Annotated[str, Field(pattern=r"^[^\s/@]+$"), Operational()]
    port: Annotated[int, Field(ge=1, le=65535), Operational()] = 5432
    database: _Text
    credential: CredentialSource | None = None
    tls: Annotated[TlsMode, Operational()] = TlsMode.AUTO
    pool: PostgresPoolSettings = Field(default_factory=PostgresPoolSettings)
    connect_timeout_seconds: _Seconds = 15.0
    retry: StoreRetrySettings = Field(default_factory=StoreRetrySettings)


# A plain name, so dotted paths in errors stay unambiguous.
ConnectionName = Annotated[str, Field(pattern=r"^[A-Za-z_][A-Za-z0-9_-]*$")]
Connection = Annotated[Neo4jSettings | PostgresSettings, Field(discriminator="kind")]


# Models (§2, §5)

# The names of tenetrag.llm.Strategy, which config cannot import.
StrategyName = Literal["native_schema", "tool_call", "json_mode", "prompt_parse"]
Provider = Literal["databricks", "openai_compatible", "fake"]

_Limit = Annotated[int | None, Field(ge=1), Content()]
# Limits that only refuse a request before it is sent. They never change an output
# that succeeded, so they move no stage hash.
_RequestLimit = Annotated[int | None, Field(ge=1), Operational()]


class CapabilityOverrides(_Settings):
    """Overrides of single fields of the shipped capability profile; unset fields keep it."""

    strategies: Annotated[tuple[StrategyName, ...] | None, Field(min_length=1), Content()] = None
    accepts_temperature: Annotated[bool | None, Content()] = None
    accepts_top_p: Annotated[bool | None, Content()] = None
    forbidden_schema_keywords: Annotated[tuple[str, ...] | None, Operational()] = None
    max_schema_properties: _RequestLimit = None
    max_input_tokens: _RequestLimit = None
    max_output_tokens: _Limit = None
    embedding_dimensions: _Limit = None
    query_prefix: Annotated[str | None, Content()] = None
    passage_prefix: Annotated[str | None, Content()] = None
    parse_retries: Annotated[int | None, Field(ge=0), Content()] = None


# Credential kinds whose source already names the workspace host.
_HOST_CARRYING_KINDS = frozenset({"cli_profile", "runtime"})


class _ModelSettings(_Settings):
    """Fields shared by chat and embedding models, and the per-provider rules."""

    provider: Annotated[Provider, Content()]
    model: Annotated[str, Field(min_length=1), Content()]
    base_url: Annotated[_HttpUrl | None, Operational()] = None
    workspace_url: Annotated[_WorkspaceUrl | None, Operational()] = None
    capabilities: CapabilityOverrides = Field(default_factory=CapabilityOverrides)
    credential: CredentialSource | None = None
    log_content: Annotated[bool, Operational()] = False

    @model_validator(mode="after")
    def _fields_match_provider(self) -> Self:
        problems: list[str] = []
        if self.provider == "openai_compatible":
            if self.base_url is None:
                problems.append("base_url is required for provider 'openai_compatible'")
        elif self.base_url is not None:
            problems.append("base_url applies only to provider 'openai_compatible'")
        if self.provider == "databricks":
            carries_host = (
                self.credential is not None and self.credential.kind in _HOST_CARRYING_KINDS
            )
            if self.workspace_url is None and not carries_host:
                problems.append(
                    "workspace_url is required for provider 'databricks' unless the "
                    "credential is cli_profile or runtime"
                )
        elif self.workspace_url is not None:
            problems.append("workspace_url applies only to provider 'databricks'")
        if self.provider == "fake" and self.credential is not None:
            problems.append("credential does not apply to provider 'fake'")
        if problems:
            raise ValueError("; ".join(problems))
        return self


class ChatModelSettings(_ModelSettings):
    temperature: Annotated[float, Field(ge=0, allow_inf_nan=False), Content()] = 0.0
    max_output_tokens: Annotated[int | None, Field(ge=1), Content()] = None
    timeout_seconds: _Seconds = 120.0
    retry: ModelRetrySettings = Field(default_factory=ModelRetrySettings)


class EmbeddingModelSettings(_ModelSettings):
    # Required by tenetrag.llm unless the shipped capability profile gives it.
    dimensions: Annotated[int | None, Field(ge=1), Content()] = None
    batch_size: _Count = 64
    timeout_seconds: _Seconds = 60.0
    retry: ModelRetrySettings = Field(default_factory=ModelRetrySettings)


class ModelsSettings(_Settings):
    extraction: Annotated[ChatModelSettings | None, IndexTime(Stage.EXTRACT)] = None
    answer: Annotated[ChatModelSettings | None, QueryTime()] = None
    embedding: Annotated[EmbeddingModelSettings | None, IndexTime(Stage.EMBED)] = None


# The profile


class Profile(_Settings):
    connections: Mapping[ConnectionName, Connection] = Field(default_factory=dict)
    models: ModelsSettings = Field(default_factory=ModelsSettings)
    language: Annotated[
        str, Field(pattern=r"^[a-z]{2,3}(-[A-Z]{2})?$"), IndexTime(Stage.EXTRACT)
    ] = "en"
