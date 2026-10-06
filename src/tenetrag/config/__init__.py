"""The profile: load, validate and classify configuration (contracts/config.md).

Stage hashes live in `tenetrag.config.hashing`, the one module of ADR 0005.
"""

from tenetrag.config.loading import load_profile, profile_from_dict, profile_from_yaml
from tenetrag.config.phases import (
    Content,
    IndexTime,
    Operational,
    Phase,
    QueryTime,
    Stage,
    field_phases,
)
from tenetrag.config.profile import (
    CapabilityOverrides,
    ChatModelSettings,
    EmbeddingModelSettings,
    ModelRetrySettings,
    ModelsSettings,
    Neo4jSettings,
    PoolSettings,
    PostgresPoolSettings,
    PostgresSettings,
    Profile,
    RetrySettings,
    StoreRetrySettings,
    TlsMode,
)
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

__all__ = [
    "ApiKeySource",
    "BasicSource",
    "CapabilityOverrides",
    "ChatModelSettings",
    "CliProfileSource",
    "Content",
    "CredentialSource",
    "EmbeddingModelSettings",
    "IndexTime",
    "ModelRetrySettings",
    "ModelsSettings",
    "Neo4jSettings",
    "NoneSource",
    "OAuthM2MSource",
    "OAuthU2MSource",
    "Operational",
    "PatSource",
    "Phase",
    "PoolSettings",
    "PostgresPoolSettings",
    "PostgresSettings",
    "Profile",
    "QueryTime",
    "RetrySettings",
    "RuntimeSource",
    "Stage",
    "StoreRetrySettings",
    "TlsMode",
    "field_phases",
    "load_profile",
    "profile_from_dict",
    "profile_from_yaml",
]
