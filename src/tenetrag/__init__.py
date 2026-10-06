"""TenetRAG: a Python SDK for GraphRAG over dated, evidence-backed facts."""

from tenetrag.protocols.errors import (
    AuthError,
    ConfigError,
    CredentialMismatchError,
    CredentialRejectedError,
    CredentialSourceError,
    LLMError,
    MissingCredentialError,
    MissingExtraError,
    ModelUnavailableError,
    OutputTruncatedError,
    QueryError,
    ResponseError,
    StorageError,
    StoreUnavailableError,
    StructuredOutputError,
    TenetRAGError,
    UnsupportedRequestError,
    UnsupportedServerError,
)

__version__ = "0.1.0.dev0"

__all__ = [
    "AuthError",
    "ConfigError",
    "CredentialMismatchError",
    "CredentialRejectedError",
    "CredentialSourceError",
    "LLMError",
    "MissingCredentialError",
    "MissingExtraError",
    "ModelUnavailableError",
    "OutputTruncatedError",
    "QueryError",
    "ResponseError",
    "StorageError",
    "StoreUnavailableError",
    "StructuredOutputError",
    "TenetRAGError",
    "UnsupportedRequestError",
    "UnsupportedServerError",
    "__version__",
]
