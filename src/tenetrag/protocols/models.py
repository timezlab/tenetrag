"""Model protocols and results (engine brief §6.4, data-model §9, contracts/llm.md).

Standard library only, so the engine can depend on them. The structured-output
strategy stays in `tenetrag.llm`; the engine sees only its name.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal, Protocol

Role = Literal["system", "user", "assistant"]


@dataclass(frozen=True, slots=True)
class Message:
    role: Role
    content: str


@dataclass(frozen=True, slots=True)
class Usage:
    """Token counts. Each is None when the provider does not report it, never a guessed zero."""

    input_tokens: int | None
    cached_input_tokens: int | None
    output_tokens: int | None


@dataclass(frozen=True, slots=True)
class ChatResult:
    """One answer. `data` is the parsed JSON when a schema was given, else None.

    `strategy` names the structured-output strategy that ran (a
    `tenetrag.llm.Strategy`, which is a `str`), or is None without a schema.
    """

    text: str
    data: Any
    usage: Usage
    model_id: str
    strategy: str | None
    finish_reason: str | None


class ChatModel(Protocol):
    @property
    def model_id(self) -> str: ...

    def generate(
        self,
        messages: Sequence[Message],
        *,
        schema: Mapping[str, Any] | None = None,
        max_output_tokens: int | None = None,
        temperature: float | None = None,
    ) -> ChatResult:
        """`max_output_tokens` and `temperature` default to the model's settings when None."""
        ...


class EmbeddingModel(Protocol):
    @property
    def model_id(self) -> str: ...

    @property
    def dimensions(self) -> int: ...

    @property
    def max_input_tokens(self) -> int: ...

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...

    def embed_queries(self, texts: Sequence[str]) -> list[list[float]]:
        """A separate call, so models with query and passage prefixes work."""
        ...

    def count_tokens(self, text: str) -> int | None:
        """The token count when a local tokenizer knows it, else None."""
        ...
