"""A scripted OpenAI-compatible server on `httpx2.MockTransport`, for model tests offline."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

import httpx2

USAGE = {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18}


@dataclass(frozen=True)
class Sent:
    """One request the server received."""

    method: str
    url: str
    path: str
    headers: Mapping[str, str]  # lower-case names
    body: dict[str, Any]


Reply = httpx2.Response | Callable[[httpx2.Request], httpx2.Response]


class FakeServer:
    """Answers each request with the next scripted reply, and records the request.

    Running out of replies fails the test, so no test passes on a default answer.
    """

    def __init__(self, *replies: Reply) -> None:
        self.replies = list(replies)
        self.requests: list[Sent] = []

    def handle(self, request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content) if request.content else {}
        headers = {name.lower(): value for name, value in request.headers.items()}
        self.requests.append(
            Sent(request.method, str(request.url), request.url.path, headers, body)
        )
        assert self.replies, f"unexpected request to {request.url.path}: the script is empty"
        reply = self.replies.pop(0)
        return reply(request) if callable(reply) else reply

    def client(self) -> httpx2.Client:
        return httpx2.Client(transport=httpx2.MockTransport(self.handle))

    @property
    def last(self) -> Sent:
        return self.requests[-1]


def chat_reply(
    content: str | None = None,
    *,
    tool_args: str | None = None,
    finish_reason: str = "stop",
    usage: Mapping[str, Any] | None = USAGE,
) -> httpx2.Response:
    message: dict[str, Any] = {"role": "assistant", "content": content}
    if tool_args is not None:
        message["tool_calls"] = [
            {
                "id": "call-1",
                "type": "function",
                "function": {"name": "output", "arguments": tool_args},
            }
        ]
    payload: dict[str, Any] = {
        "id": "chat-1",
        "object": "chat.completion",
        "created": 1,
        "model": "served-model",
        "choices": [{"index": 0, "finish_reason": finish_reason, "message": message}],
    }
    if usage is not None:
        payload["usage"] = dict(usage)
    return httpx2.Response(200, json=payload)


def json_reply(data: Any, **kwargs: Any) -> httpx2.Response:
    return chat_reply(json.dumps(data), **kwargs)


def embedding_reply(
    vectors: list[list[float]], *, order: list[int] | None = None
) -> httpx2.Response:
    """Vectors for inputs 0..n-1, listed in `order` (input order when None)."""
    indexes = order if order is not None else list(range(len(vectors)))
    data = [{"object": "embedding", "index": i, "embedding": vectors[i]} for i in indexes]
    return httpx2.Response(
        200, json={"object": "list", "model": "served-model", "data": data, "usage": USAGE}
    )


def error_reply(
    status: int, message: str = "error", headers: Mapping[str, str] | None = None
) -> httpx2.Response:
    return httpx2.Response(
        status,
        json={"error": {"message": message, "type": "test_error", "code": None}},
        headers=dict(headers or {}),
    )


def messages_of(sent: Sent) -> list[dict[str, Any]]:
    return list(sent.body["messages"])
