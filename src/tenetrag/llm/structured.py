"""Structured output shared by every chat model, the fakes included (contracts/llm.md, research R9).

A chat model supplies `send`, which makes one call with the given messages
and request fragment. This module does the rest: it checks the schema against
the capability profile before any call, picks the strategy, shapes the
request, parses and validates the answer, and re-asks with the validation
error up to `parse_retries` times.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, best_match
from referencing import Registry

from tenetrag.llm.capabilities import CapabilityProfile, Strategy
from tenetrag.protocols.errors import (
    OutputTruncatedError,
    StructuredOutputError,
    UnsupportedRequestError,
)
from tenetrag.protocols.models import ChatResult, Message, Usage

SCHEMA_NAME = "output"
_TOOL_DESCRIPTION = "Return the answer as this function's arguments."

# Keywords whose value maps names to schemas: the names are not keywords.
_NAME_MAPS = frozenset(
    {"properties", "patternProperties", "$defs", "definitions", "dependentSchemas"}
)
# Keywords whose value is data, never a schema.
_DATA_KEYWORDS = frozenset({"enum", "const", "default", "examples", "required"})
_FENCE = re.compile(r"^\s*```[A-Za-z]*\s*\n(.*?)\n?\s*```\s*$", re.DOTALL)


@dataclass(frozen=True, slots=True)
class Reply:
    """What one call returned."""

    content: str | None
    tool_arguments: str | None
    finish_reason: str | None
    usage: Usage


Send = Callable[[Sequence[Message], Mapping[str, Any]], Reply]


def check_schema(schema: Mapping[str, Any], profile: CapabilityProfile, model_id: str) -> None:
    """Refuse, before any call, a schema the model or this SDK cannot take."""
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise UnsupportedRequestError(
            f"The schema is not valid JSON Schema: {exc.message}. Fix the schema."
        ) from None
    keywords = list(_keywords(schema))
    for keyword, value in keywords:
        if keyword == "$ref" and not (isinstance(value, str) and value.startswith("#")):
            raise UnsupportedRequestError(
                f"The schema has a $ref to {value!r}. Only references inside the schema, "
                "starting with #, are allowed: no schema is ever fetched."
            )
    forbidden = set(profile.forbidden_schema_keywords)
    for keyword, _ in keywords:
        if keyword in forbidden:
            raise UnsupportedRequestError(
                f"{model_id} does not accept the schema keyword {keyword!r}. Rewrite the "
                "schema without it, or override capabilities.forbidden_schema_keywords "
                "if the server accepts it."
            )
    limit = profile.max_schema_properties
    if limit is not None:
        count = sum(
            len(value)
            for keyword, value in keywords
            if keyword == "properties" and isinstance(value, Mapping)
        )
        if count > limit:
            raise UnsupportedRequestError(
                f"The schema has {count} properties, and {model_id} accepts at most {limit}. "
                "Split the request into smaller schemas."
            )


def generate(
    send: Send,
    messages: Sequence[Message],
    schema: Mapping[str, Any] | None,
    profile: CapabilityProfile,
    *,
    model_id: str,
) -> ChatResult:
    """One answer: plain text without a schema, else validated data. `check_schema` runs first."""
    if schema is None:
        reply = send(messages, {})
        _refuse_truncated(reply, model_id)
        return ChatResult(
            text=reply.content or "",
            data=None,
            usage=reply.usage,
            model_id=model_id,
            strategy=None,
            finish_reason=reply.finish_reason,
        )
    check_schema(schema, profile, model_id)
    strategy = profile.strategy
    validator = Draft202012Validator(schema, registry=Registry())
    fragment = request_fragment(strategy, schema)
    conversation = with_instructions(strategy, messages, schema)
    attempts = 1 + profile.parse_retries
    usages: list[Usage] = []
    problem = ""
    for _ in range(attempts):
        reply = send(conversation, fragment)
        usages.append(reply.usage)
        _refuse_truncated(reply, model_id)
        raw = reply.tool_arguments if reply.tool_arguments is not None else reply.content
        outcome = _parse(raw or "", validator)
        if isinstance(outcome, _Valid):
            return ChatResult(
                text=raw or "",
                data=outcome.data,
                usage=_total(usages),
                model_id=model_id,
                strategy=strategy,
                finish_reason=reply.finish_reason,
            )
        problem = outcome.summary
        conversation = [
            *conversation,
            Message("assistant", raw or ""),
            Message("user", outcome.reask),
        ]
    raise StructuredOutputError(
        f"{model_id} gave no answer that matches the schema in {attempts} attempts with the "
        f"{strategy} strategy (last problem: {problem}). Simplify the schema, raise "
        "capabilities.parse_retries, or list another strategy in capabilities.strategies.",
        strategy=strategy,
        attempts=attempts,
    )


def request_fragment(strategy: Strategy, schema: Mapping[str, Any]) -> dict[str, Any]:
    """The request fields of research R9 that carry the schema, beside the messages."""
    match strategy:
        case Strategy.NATIVE_SCHEMA:
            json_schema = {"name": SCHEMA_NAME, "schema": dict(schema), "strict": True}
            return {"response_format": {"type": "json_schema", "json_schema": json_schema}}
        case Strategy.TOOL_CALL:
            function = {
                "name": SCHEMA_NAME,
                "description": _TOOL_DESCRIPTION,
                "parameters": dict(schema),
            }
            return {
                "tools": [{"type": "function", "function": function}],
                "tool_choice": {"type": "function", "function": {"name": SCHEMA_NAME}},
            }
        case Strategy.JSON_MODE:
            return {"response_format": {"type": "json_object"}}
        case Strategy.PROMPT_PARSE:
            return {}


def with_instructions(
    strategy: Strategy, messages: Sequence[Message], schema: Mapping[str, Any]
) -> list[Message]:
    """For json_mode and prompt_parse, the schema goes into the first system message."""
    if strategy not in (Strategy.JSON_MODE, Strategy.PROMPT_PARSE):
        return list(messages)
    instructions = (
        "Answer with one JSON value that matches this JSON schema, and nothing else:\n"
        + json.dumps(schema, ensure_ascii=False, sort_keys=True)
    )
    if messages and messages[0].role == "system":
        first = Message("system", f"{messages[0].content}\n\n{instructions}")
        return [first, *messages[1:]]
    return [Message("system", instructions), *messages]


@dataclass(frozen=True, slots=True)
class _Valid:
    data: Any


@dataclass(frozen=True, slots=True)
class _Invalid:
    reask: str  # sent to the model, so it may quote the answer
    summary: str  # for the error, so it names where, never the answer's content


def _parse(raw: str, validator: Draft202012Validator) -> _Valid | _Invalid:
    fenced = _FENCE.match(raw)
    text = fenced.group(1) if fenced else raw
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return _Invalid(
            reask=f"Your answer is not valid JSON ({exc.msg}). Answer again with only one "
            "JSON value that matches the schema.",
            summary=f"not valid JSON ({exc.msg})",
        )
    error = best_match(validator.iter_errors(data))
    if error is None:
        return _Valid(data)
    where = error.json_path
    return _Invalid(
        reask=f"Your answer does not match the schema: at {where}, {error.message}. Answer "
        "again with only one JSON value that matches the schema.",
        summary=f"{error.validator} at {where}",
    )


def _refuse_truncated(reply: Reply, model_id: str) -> None:
    if reply.finish_reason == "length":
        raise OutputTruncatedError(
            f"{model_id} stopped at its output limit before the answer was complete. Raise "
            "max_output_tokens in the settings or the call."
        )


def _total(usages: Sequence[Usage]) -> Usage:
    """Usage over all attempts. A count any attempt did not report stays unknown."""

    def add(counts: list[int | None]) -> int | None:
        known = [count for count in counts if count is not None]
        return sum(known) if len(known) == len(counts) else None

    return Usage(
        input_tokens=add([usage.input_tokens for usage in usages]),
        cached_input_tokens=add([usage.cached_input_tokens for usage in usages]),
        output_tokens=add([usage.output_tokens for usage in usages]),
    )


def _keywords(node: object) -> Iterator[tuple[str, object]]:
    """Every (keyword, value) of a schema, in document order."""
    if isinstance(node, Mapping):
        for key, value in node.items():
            yield key, value
            if key in _DATA_KEYWORDS:
                continue
            if key in _NAME_MAPS and isinstance(value, Mapping):
                for subschema in value.values():
                    yield from _keywords(subschema)
            else:
                yield from _keywords(value)
    elif isinstance(node, list):
        for item in node:
            yield from _keywords(item)
