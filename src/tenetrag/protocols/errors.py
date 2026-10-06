"""The TenetRAG error hierarchy (data-model §1).

Standard library only, so every module may import it, the engine included.
Messages say what failed and what to do next, and never hold a secret.
A third-party exception is re-raised as one of these with ``raise ... from exc``.
"""

from __future__ import annotations


class TenetRAGError(Exception):
    """Base class of every error the SDK raises."""


class ConfigError(TenetRAGError, ValueError):
    """The profile or the code's configuration is invalid."""


class MissingExtraError(ConfigError):
    """An optional extra that the requested feature needs is not installed."""

    def __init__(self, extra: str) -> None:
        self.extra = extra
        super().__init__(
            f"The '{extra}' extra is not installed. "
            f"Install it with: pip install 'tenetrag[{extra}]'"
        )


class AuthError(TenetRAGError):
    """A credential is missing, unusable or refused."""


class MissingCredentialError(AuthError):
    """The target needs a credential and none was given."""


class CredentialSourceError(AuthError):
    """A named credential source is unset, empty, missing or expired."""


class CredentialMismatchError(AuthError):
    """The credential's kind cannot be used for the target."""


class CredentialRejectedError(AuthError):
    """The server refused the credential, after the one allowed refresh."""


class StorageError(TenetRAGError):
    """A store failed."""


class StoreUnavailableError(StorageError):
    """The store is unreachable, or the retry budget ran out."""


class UnsupportedServerError(StorageError):
    """The server's version, edition or extensions are below the floor."""


class QueryError(StorageError):
    """A unit of work failed in a way that retrying will not fix."""


class LLMError(TenetRAGError):
    """A chat or embedding model call failed."""


class ModelUnavailableError(LLMError):
    """Rate limit, timeout or server error, after the retry budget."""


class StructuredOutputError(LLMError):
    """The model's output failed to parse or validate against the schema."""

    def __init__(self, message: str, *, strategy: str, attempts: int) -> None:
        super().__init__(message)
        self.strategy = strategy
        self.attempts = attempts


class OutputTruncatedError(LLMError):
    """The output hit the output-token limit."""


class UnsupportedRequestError(LLMError):
    """The request was rejected before any call: schema construct, empty or over-long text."""


class ResponseError(LLMError):
    """The provider's response was malformed, such as a vector of the wrong dimension."""
