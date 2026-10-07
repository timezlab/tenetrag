"""Fake models for engine tests: scripted, deterministic, never on the network (data-model §10).

The fake chat model runs the same structured-output loop as the real classes,
so schema checks, validation and re-asking behave the same on scripted data.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from tenetrag.llm import structured
from tenetrag.llm._inputs import refuse_unusable_texts
from tenetrag.llm.capabilities import CapabilityProfile, capability_profile
from tenetrag.protocols.models import ChatResult, Message, Usage

# A scripted item: text, a dict (data and its JSON text), an exception to raise,
# or a ChatResult (text, usage and finish reason).
ScriptItem = str | Mapping[str, Any] | BaseException | ChatResult
Script = Sequence[ScriptItem] | Callable[[Sequence[Message], Mapping[str, Any] | None], ScriptItem]

_UNKNOWN = Usage(input_tokens=None, cached_input_tokens=None, output_tokens=None)


class FakeChatModel:
    """Answers each call from `responses`, and records it in `calls`.

    `responses` is a sequence of items, used one per call (one per attempt when
    an answer is re-asked), or a callable `(messages, schema) -> item`.
    """

    def __init__(
        self,
        responses: Script = (),
        *,
        model_id: str = "fake-chat",
        capabilities: CapabilityProfile | None = None,
    ) -> None:
        self._script = responses if callable(responses) else list(responses)
        self._used = 0
        self._model_id = model_id
        self._capabilities = capabilities or capability_profile("fake", model_id)
        self.calls: list[tuple[list[Message], Mapping[str, Any] | None, dict[str, Any]]] = []

    @property
    def model_id(self) -> str:
        return self._model_id

    def generate(
        self,
        messages: Sequence[Message],
        *,
        schema: Mapping[str, Any] | None = None,
        max_output_tokens: int | None = None,
        temperature: float | None = None,
    ) -> ChatResult:
        if schema is not None:  # checked before recording, so a refused request leaves no call
            structured.check_schema(schema, self._capabilities, self._model_id)
        params = {
            "max_output_tokens": max_output_tokens,
            "temperature": 0.0 if temperature is None else temperature,
        }
        self.calls.append((list(messages), schema, params))

        def send(conversation: Sequence[Message], fragment: Mapping[str, Any]) -> structured.Reply:
            return _reply(self._next(conversation, schema))

        return structured.generate(
            send, messages, schema, self._capabilities, model_id=self._model_id
        )

    def _next(self, messages: Sequence[Message], schema: Mapping[str, Any] | None) -> ScriptItem:
        if callable(self._script):
            return self._script(list(messages), schema)
        if self._used >= len(self._script):
            raise AssertionError(
                f"FakeChatModel's script has no answer left for call {self._used + 1}; "
                "add one to responses."
            )
        item = self._script[self._used]
        self._used += 1
        return item

    def __repr__(self) -> str:
        return f"FakeChatModel(model_id={self._model_id!r})"


def _reply(item: ScriptItem) -> structured.Reply:
    if isinstance(item, BaseException):
        raise item
    if isinstance(item, ChatResult):
        return structured.Reply(item.text, None, item.finish_reason, item.usage)
    if isinstance(item, str):
        return structured.Reply(item, None, "stop", _UNKNOWN)
    return structured.Reply(json.dumps(item, ensure_ascii=False), None, "stop", _UNKNOWN)


class FakeEmbeddingModel:
    """Unit vectors from SHA-256 of the prefixed text, so a text always gives the same vector."""

    def __init__(
        self,
        dimensions: int = 8,
        *,
        model_id: str = "fake-embed",
        max_input_tokens: int = 8192,
        query_prefix: str = "query: ",
        passage_prefix: str = "passage: ",
    ) -> None:
        self._dimensions = dimensions
        self._model_id = model_id
        self._max_input_tokens = max_input_tokens
        self._query_prefix = query_prefix
        self._passage_prefix = passage_prefix
        self.calls: list[tuple[str, list[str]]] = []

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def dimensions(self) -> int:
        return self._dimensions

    @property
    def max_input_tokens(self) -> int:
        return self._max_input_tokens

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return self._embed("documents", texts, self._passage_prefix)

    def embed_queries(self, texts: Sequence[str]) -> list[list[float]]:
        return self._embed("queries", texts, self._query_prefix)

    def count_tokens(self, text: str) -> int | None:
        return None

    def _embed(self, kind: str, texts: Sequence[str], prefix: str) -> list[list[float]]:
        self.calls.append((kind, list(texts)))
        refuse_unusable_texts(
            texts,
            prefix=prefix,
            max_input_tokens=self._max_input_tokens,
            count_tokens=self.count_tokens,
        )
        return [self._vector(prefix + text) for text in texts]

    def _vector(self, text: str) -> list[float]:
        values: list[float] = []
        block = 0
        while len(values) < self._dimensions:
            digest = hashlib.sha256(f"{block}:{text}".encode()).digest()
            values.extend(byte / 127.5 - 1.0 for byte in digest)
            block += 1
        vector = values[: self._dimensions]
        norm = math.sqrt(math.fsum(x * x for x in vector)) or 1.0
        return [x / norm for x in vector]

    def __repr__(self) -> str:
        return f"FakeEmbeddingModel(model_id={self._model_id!r}, dimensions={self._dimensions})"
