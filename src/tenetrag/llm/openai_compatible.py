"""Chat and embedding models for any OpenAI-compatible server (contracts/llm.md, research R9, R10).

The `openai` SDK sends the requests; it is imported only when a model is built.

- **Authorization:** every request carries the header itself, built from the
  credential's current token and passed per request, which the SDK merges
  last. So neither `OPENAI_API_KEY` nor an `Authorization` line in
  `OPENAI_CUSTOM_HEADERS` can replace it, and a rejected token is known exactly.
  The `none` credential removes the header.
- **Errors:** built from the status code and our own text, raised outside the
  `except` block. The SDK's exceptions are never chained, since their text
  holds the server's body, which may echo the key. A server's message is kept
  only for a refused request, with every token we sent masked.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from typing import TYPE_CHECKING, Any, TypeVar

from tenetrag._retry import (
    RetryExhaustedError,
    RetryPolicy,
    Verdict,
    parse_retry_after,
    run_with_retry,
)
from tenetrag.auth.credentials import AccessToken, Credential, CredentialKind, rejected_error
from tenetrag.config import ChatModelSettings, EmbeddingModelSettings, ModelRetrySettings
from tenetrag.llm import structured
from tenetrag.llm._inputs import refuse_unusable_texts
from tenetrag.llm.capabilities import CapabilityProfile
from tenetrag.protocols.errors import (
    AuthError,
    ConfigError,
    CredentialMismatchError,
    CredentialRejectedError,
    LLMError,
    MissingExtraError,
    ModelUnavailableError,
    ResponseError,
)
from tenetrag.protocols.models import ChatResult, Message, Usage

if TYPE_CHECKING:
    import httpx2
    import openai

T = TypeVar("T")

logger = logging.getLogger(__name__)

# Variables the openai SDK reads on its own and adds to every request (ADR 0018).
_OPENAI_ENV_READS = ("OPENAI_ORG_ID", "OPENAI_PROJECT_ID", "OPENAI_CUSTOM_HEADERS")
_env_warning_lock = threading.Lock()
_env_warning_logged = False

# Characters of a server's error message kept in our error.
_SERVER_MESSAGE_LIMIT = 500


class OpenAICompatibleChatModel:
    """A chat model at `{base_url}/chat/completions`."""

    _max_tokens_field = "max_completion_tokens"

    def __init__(
        self,
        settings: ChatModelSettings,
        *,
        credential: Credential,
        capabilities: CapabilityProfile,
        http_client: httpx2.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._settings = settings
        self._capabilities = capabilities
        self._transport = _Transport(
            model_id=settings.model,
            base_url=self._base_url(settings, credential),
            credential=credential,
            timeout_seconds=settings.timeout_seconds,
            retry=settings.retry,
            http_client=http_client,
            sleep=sleep,
            clock=clock,
        )

    @property
    def model_id(self) -> str:
        return self._settings.model

    def generate(
        self,
        messages: Sequence[Message],
        *,
        schema: Mapping[str, Any] | None = None,
        max_output_tokens: int | None = None,
        temperature: float | None = None,
    ) -> ChatResult:
        def send(conversation: Sequence[Message], fragment: Mapping[str, Any]) -> structured.Reply:
            return self._complete(conversation, fragment, max_output_tokens, temperature)

        return structured.generate(
            send, messages, schema, self._capabilities, model_id=self.model_id
        )

    def _base_url(self, settings: ChatModelSettings, credential: Credential) -> str:
        return _required_base_url(settings.base_url, settings.model)

    def _complete(
        self,
        messages: Sequence[Message],
        fragment: Mapping[str, Any],
        max_output_tokens: int | None,
        temperature: float | None,
    ) -> structured.Reply:
        body: dict[str, Any] = {
            "model": self.model_id,
            "messages": [
                {"role": message.role, "content": message.content} for message in messages
            ],
            **fragment,
        }
        limit = self._settings.max_output_tokens if max_output_tokens is None else max_output_tokens
        if limit is not None:
            body[self._max_tokens_field] = limit
        if self._capabilities.accepts_temperature:
            body["temperature"] = self._settings.temperature if temperature is None else temperature
        logger.debug("Calling %s with %d messages", self.model_id, len(messages))
        if self._settings.log_content:
            text = json.dumps(body["messages"], ensure_ascii=False)
            logger.debug("Messages to %s: %s", self.model_id, text)
        client = self._transport.client
        completion = self._transport.call(
            lambda headers: client.chat.completions.create(**body, extra_headers=headers)
        )
        reply = _chat_reply(completion, self.model_id)
        if self._settings.log_content:
            answer = reply.content if reply.tool_arguments is None else reply.tool_arguments
            logger.debug("Answer from %s: %s", self.model_id, answer)
        return reply

    def __repr__(self) -> str:
        identity = self._transport.identity
        return f"{type(self).__name__}(model_id={self.model_id!r}, credential={identity!r})"


class OpenAICompatibleEmbeddingModel:
    """An embedding model at `{base_url}/embeddings`."""

    def __init__(
        self,
        settings: EmbeddingModelSettings,
        *,
        credential: Credential,
        capabilities: CapabilityProfile,
        http_client: httpx2.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._settings = settings
        self._capabilities = capabilities
        self._dimensions, self._max_input_tokens = embedding_limits(
            settings, capabilities, label=settings.model
        )
        self._transport = _Transport(
            model_id=settings.model,
            base_url=self._base_url(settings, credential),
            credential=credential,
            timeout_seconds=settings.timeout_seconds,
            retry=settings.retry,
            http_client=http_client,
            sleep=sleep,
            clock=clock,
        )

    @property
    def model_id(self) -> str:
        return self._settings.model

    @property
    def dimensions(self) -> int:
        return self._dimensions

    @property
    def max_input_tokens(self) -> int:
        return self._max_input_tokens

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return self._embed(texts, self._capabilities.passage_prefix)

    def embed_queries(self, texts: Sequence[str]) -> list[list[float]]:
        return self._embed(texts, self._capabilities.query_prefix)

    def count_tokens(self, text: str) -> int | None:
        # No local tokenizer is known for an arbitrary server's model.
        return None

    def _base_url(self, settings: EmbeddingModelSettings, credential: Credential) -> str:
        return _required_base_url(settings.base_url, settings.model)

    def _embed(self, texts: Sequence[str], prefix: str) -> list[list[float]]:
        if not texts:
            return []
        refuse_unusable_texts(
            texts,
            prefix=prefix,
            max_input_tokens=self._max_input_tokens,
            count_tokens=self.count_tokens,
        )
        size = self._settings.batch_size
        vectors: list[list[float]] = []
        for start in range(0, len(texts), size):
            vectors.extend(
                self._embed_batch([prefix + text for text in texts[start : start + size]])
            )
        return vectors

    def _embed_batch(self, batch: list[str]) -> list[list[float]]:
        logger.debug("Embedding %d texts with %s", len(batch), self.model_id)
        client = self._transport.client
        response = self._transport.call(
            lambda headers: client.embeddings.create(
                model=self.model_id, input=batch, encoding_format="float", extra_headers=headers
            )
        )
        return _vectors(response, len(batch), self._dimensions, self.model_id)

    def __repr__(self) -> str:
        identity = self._transport.identity
        return f"{type(self).__name__}(model_id={self.model_id!r}, credential={identity!r})"


def embedding_limits(
    settings: EmbeddingModelSettings, capabilities: CapabilityProfile, *, label: str
) -> tuple[int, int]:
    """The dimension and input limit, from the settings or the shipped profile.

    `label` names the model in errors: its profile path when the factory checks.
    """
    dimensions = settings.dimensions
    if dimensions is None:
        dimensions = capabilities.embedding_dimensions
    if dimensions is None:
        raise ConfigError(
            f"{label}: the dimension of {settings.model} is unknown. Set `dimensions` on the "
            "model in the profile."
        )
    if capabilities.max_input_tokens is None:
        raise ConfigError(
            f"{label}: the input limit of {settings.model} is unknown. Set "
            "`capabilities.max_input_tokens` on the model in the profile, so over-long texts "
            "are refused before the call."
        )
    return dimensions, capabilities.max_input_tokens


class _Transport:
    """One openai client, the credential's token on every request, and the retry policy."""

    def __init__(
        self,
        *,
        model_id: str,
        base_url: str,
        credential: Credential,
        timeout_seconds: float,
        retry: ModelRetrySettings,
        http_client: httpx2.Client | None,
        sleep: Callable[[float], None],
        clock: Callable[[], float],
    ) -> None:
        try:
            import openai
        except ImportError as exc:
            raise MissingExtraError("openai") from exc
        if credential._token_source is None and credential.kind is not CredentialKind.NONE:
            raise CredentialMismatchError(
                f"{model_id}: a {credential.kind.value} credential cannot be used for a model. "
                "Use api_key or none, or a Databricks credential for a Databricks model."
            )
        _warn_about_openai_env()
        self._model_id = model_id
        self._credential = credential
        self._sleep = sleep
        self._clock = clock
        self._policy = RetryPolicy(
            max_attempts=retry.max_attempts,
            max_total_seconds=retry.max_total_seconds,
            initial_backoff_seconds=retry.initial_backoff_seconds,
            max_backoff_seconds=retry.max_backoff_seconds,
        )
        self.client = openai.OpenAI(
            api_key="unused",  # each request sets Authorization itself (module docstring)
            admin_api_key="",  # not None, so OPENAI_ADMIN_KEY is not read
            webhook_secret="",  # not None, so OPENAI_WEBHOOK_SECRET is not read
            base_url=base_url,
            max_retries=0,  # research R10's policy is the only one
            timeout=timeout_seconds,
            http_client=http_client,
        )

    def call(self, send: Callable[[dict[str, Any]], T]) -> T:
        """Run `send(extra_headers)` under the retry policy, with the current token each time."""
        import openai

        tokens = self._credential._token_source
        sent: list[AccessToken] = []

        def attempt() -> T:
            if tokens is None:
                return send({"Authorization": openai.omit})
            token = tokens.token()
            sent.append(token)
            return send({"Authorization": f"Bearer {token.value.reveal()}"})

        def reauth() -> None:
            if tokens is not None:  # always: the hook is passed only with a token source
                tokens.invalidate(sent[-1])  # raises CredentialRejectedError when it cannot refresh

        failure: LLMError | AuthError
        try:
            return run_with_retry(
                attempt,
                _classify,
                policy=self._policy,
                on_reauth=reauth if tokens is not None else None,
                clock=self._clock,
                sleep=self._sleep,
            )
        except RetryExhaustedError as exc:
            failure = self._unavailable(exc)
        except openai.APIStatusError as exc:
            failure = self._refused(exc, sent)
        except (openai.APIResponseValidationError, json.JSONDecodeError):
            failure = ResponseError(
                f"{self._model_id} sent a response this SDK cannot read. Check that the URL "
                "points to an OpenAI-compatible server."
            )
        except openai.OpenAIError as exc:
            failure = LLMError(f"{self._model_id}: the openai SDK failed ({type(exc).__name__}).")
        raise failure

    def _unavailable(self, exc: RetryExhaustedError) -> ModelUnavailableError:
        import openai

        cause = exc.__cause__
        if isinstance(cause, openai.APIStatusError):
            what = f"HTTP {cause.status_code}"
        elif isinstance(cause, openai.APITimeoutError):
            what = "timed out"
        else:
            what = "connection failed"
        return ModelUnavailableError(
            f"{self._model_id} is unavailable ({what}) after {exc.attempts} attempts in "
            f"{exc.elapsed_seconds:.1f} s. Try again later, or raise retry.max_attempts or "
            "retry.max_total_seconds in the settings."
        )

    def _refused(
        self, exc: openai.APIStatusError, sent: Sequence[AccessToken]
    ) -> LLMError | AuthError:
        identity = self._credential.identity
        if exc.status_code == 401:
            # A second rejection after a refresh, or a credential without a token.
            return rejected_error(identity, refreshable=self._credential.refreshable)
        if exc.status_code == 403:
            return CredentialRejectedError(
                f"{self._model_id}: the credential {identity} may not use this model (HTTP 403). "
                "Check its permissions on the model or serving endpoint."
            )
        return LLMError(
            f"{self._model_id} refused the request (HTTP {exc.status_code}): "
            f"{_server_message(exc.body, sent)}"
        )

    @property
    def identity(self) -> str:
        return self._credential.identity


def _classify(exc: Exception) -> Verdict:
    import openai

    if isinstance(exc, openai.AuthenticationError):
        return Verdict.reauth()
    if isinstance(exc, openai.RateLimitError | openai.InternalServerError):
        return Verdict.retry(parse_retry_after(exc.response.headers))
    if isinstance(exc, openai.APIConnectionError):  # timeouts included
        return Verdict.retry()
    return Verdict.fail()


def _server_message(body: object, sent: Sequence[AccessToken]) -> str:
    if isinstance(body, Mapping) and "error" in body:
        body = body["error"]
    message = body.get("message") if isinstance(body, Mapping) else body
    if not isinstance(message, str) or not message:
        return "the server sent no message"
    for token in sent:
        message = message.replace(token.value.reveal(), "***")
    return message[:_SERVER_MESSAGE_LIMIT]


def _chat_reply(completion: object, model_id: str) -> structured.Reply:
    """Read the parts of a chat completion we use, checking each, since servers vary."""
    choices = getattr(completion, "choices", None)
    if not isinstance(choices, list) or not choices:
        raise ResponseError(
            f"{model_id} sent a response that is not a chat completion. Check that the URL "
            "points to an OpenAI-compatible server."
        )
    choice = choices[0]
    message = getattr(choice, "message", None)
    content = getattr(message, "content", None)
    tool_arguments = None
    for tool_call in getattr(message, "tool_calls", None) or []:
        function = getattr(tool_call, "function", None)
        if getattr(function, "name", None) == structured.SCHEMA_NAME:
            tool_arguments = getattr(function, "arguments", None)
            break
    finish_reason = getattr(choice, "finish_reason", None)
    return structured.Reply(
        content=content if isinstance(content, str) else None,
        tool_arguments=tool_arguments if isinstance(tool_arguments, str) else None,
        finish_reason=finish_reason if isinstance(finish_reason, str) else None,
        usage=_usage(getattr(completion, "usage", None)),
    )


def _usage(usage: object) -> Usage:
    details = getattr(usage, "prompt_tokens_details", None)
    return Usage(
        input_tokens=_count(getattr(usage, "prompt_tokens", None)),
        cached_input_tokens=_count(getattr(details, "cached_tokens", None)),
        output_tokens=_count(getattr(usage, "completion_tokens", None)),
    )


def _count(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _vectors(response: object, expected: int, dimensions: int, model_id: str) -> list[list[float]]:
    """The vectors in input order, by the index the server gave each one."""
    data = getattr(response, "data", None)
    if not isinstance(data, list) or len(data) != expected:
        count = len(data) if isinstance(data, list) else 0
        raise ResponseError(f"{model_id} returned {count} vectors for {expected} texts.")
    by_index: dict[int, list[float]] = {}
    for item in data:
        index = getattr(item, "index", None)
        vector = getattr(item, "embedding", None)
        if not isinstance(index, int) or not 0 <= index < expected or index in by_index:
            raise ResponseError(f"{model_id} returned vectors with missing or repeated indexes.")
        if not isinstance(vector, list) or len(vector) != dimensions:
            size = len(vector) if isinstance(vector, list) else 0
            raise ResponseError(
                f"{model_id} returned a vector of dimension {size}, and {dimensions} was "
                "expected. Set `dimensions` to the model's real dimension."
            )
        by_index[index] = vector
    return [by_index[index] for index in range(expected)]


def _required_base_url(base_url: str | None, model: str) -> str:
    if base_url is None:
        raise ConfigError(f"{model}: an OpenAI-compatible model needs `base_url` in the profile.")
    return base_url


def _warn_about_openai_env() -> None:
    """Name, once per process, the variables the openai SDK adds to every request."""
    global _env_warning_logged
    names = [name for name in _OPENAI_ENV_READS if name in os.environ]
    if not names:
        return
    with _env_warning_lock:
        if _env_warning_logged:
            return
        _env_warning_logged = True
    logger.warning(
        "The openai SDK adds headers from these environment variables to every model request: "
        "%s. Unset any that belong to another identity (ADR 0018).",
        ", ".join(names),
    )
