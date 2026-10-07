"""Structured output: schema checks, the strategy, validation and re-asking (FR-022, T039).

Run through FakeChatModel, which shares the structured-output loop of the real
classes; the request shapes per strategy are pinned in test_openai_compatible.

Behaviours:
1. The strategy is the first in the fixed order that the profile lists.
2. Forbidden schema keywords and too many properties are refused before any
   call, naming the first offender; a property named like a keyword is fine.
3. A remote $ref, or a schema that is not valid JSON Schema, is refused before
   any call; a local $ref resolves.
4. Invalid output is re-asked with the validation error appended, up to
   parse_retries, then StructuredOutputError(strategy, attempts) with no data.
5. Output that is not JSON counts as invalid.
"""

import pytest

from tenetrag import StructuredOutputError, UnsupportedRequestError
from tenetrag.config import CapabilityOverrides
from tenetrag.llm import FakeChatModel, Strategy, capability_profile
from tenetrag.protocols import Message

ASK = [Message("user", "Which city?")]
CITY = {
    "type": "object",
    "properties": {"city": {"type": "string"}, "population": {"type": "integer"}},
    "required": ["city", "population"],
    "additionalProperties": False,
}
DATABRICKS = capability_profile("databricks", "databricks-gpt-5")


class Recorder:
    """A callable script that answers in turn and keeps the messages of each attempt."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.seen: list[list[Message]] = []

    def __call__(self, messages, schema):
        self.seen.append(list(messages))
        return self.answers.pop(0)


def profile(**overrides):
    return capability_profile("openai_compatible", "qwen3-32b", CapabilityOverrides(**overrides))


def test_strategy_is_the_first_listed_in_the_fixed_order():
    model = FakeChatModel(
        [{"city": "Huế", "population": 650000}],
        capabilities=profile(strategies=("prompt_parse", "tool_call")),
    )
    result = model.generate(ASK, schema=CITY)
    assert result.strategy == Strategy.TOOL_CALL
    assert result.data == {"city": "Huế", "population": 650000}


def test_no_schema_means_no_strategy():
    result = FakeChatModel(["Huế"]).generate(ASK)
    assert (result.text, result.data, result.strategy) == ("Huế", None, None)


@pytest.mark.parametrize(
    ("schema", "named"),
    [
        ({"anyOf": [{"type": "string"}, {"type": "integer"}]}, "anyOf"),
        (
            {"type": "object", "properties": {"code": {"type": "string", "pattern": "^[A-Z]+$"}}},
            "pattern",
        ),
        ({"type": "array", "items": {"oneOf": [{"type": "string"}]}}, "oneOf"),
        ({"type": "array", "prefixItems": [{"type": "string"}]}, "prefixItems"),
        ({"$defs": {"x": {"type": "string"}}, "$ref": "#/$defs/x"}, "$ref"),
    ],
)
def test_forbidden_keyword_is_refused_before_any_call(schema, named):
    script = Recorder({"city": "Huế"})
    model = FakeChatModel(script, capabilities=DATABRICKS)
    with pytest.raises(UnsupportedRequestError) as caught:
        model.generate(ASK, schema=schema)
    assert named in str(caught.value)
    assert script.seen == []
    assert model.calls == []


def test_property_named_like_a_keyword_is_accepted():
    schema = {
        "type": "object",
        "properties": {"pattern": {"type": "string"}, "anyOf": {"type": "string"}},
        "required": ["pattern", "anyOf"],
    }
    model = FakeChatModel([{"pattern": "a", "anyOf": "b"}], capabilities=DATABRICKS)
    assert model.generate(ASK, schema=schema).data == {"pattern": "a", "anyOf": "b"}


def test_too_many_properties_are_refused_before_any_call():
    nested = {f"n{i}": {"type": "string"} for i in range(30)}
    schema = {
        "type": "object",
        "properties": {
            **{f"p{i}": {"type": "string"} for i in range(34)},
            "inner": {"type": "object", "properties": nested},
        },
    }
    script = Recorder({})
    model = FakeChatModel(script, capabilities=DATABRICKS)
    with pytest.raises(UnsupportedRequestError, match="65") as caught:
        model.generate(ASK, schema=schema)
    assert "64" in str(caught.value)
    assert script.seen == []


@pytest.mark.parametrize(
    "schema",
    [
        {"$ref": "https://schemas.example.net/city.json"},
        {"type": "object", "properties": {"city": {"$ref": "city.json#/x"}}},
    ],
)
def test_remote_ref_is_refused_before_any_call(schema):
    script = Recorder({"city": "Huế"})
    with pytest.raises(UnsupportedRequestError, match=r"\$ref"):
        FakeChatModel(script).generate(ASK, schema=schema)
    assert script.seen == []


def test_local_ref_resolves():
    schema = {
        "$defs": {"name": {"type": "string"}},
        "type": "object",
        "properties": {"city": {"$ref": "#/$defs/name"}},
        "required": ["city"],
    }
    model = FakeChatModel([{"city": 7}, {"city": "Huế"}])
    assert model.generate(ASK, schema=schema).data == {"city": "Huế"}


def test_schema_that_is_not_json_schema_is_refused():
    script = Recorder({})
    with pytest.raises(UnsupportedRequestError):
        FakeChatModel(script).generate(ASK, schema={"type": 5})
    assert script.seen == []


def test_invalid_output_is_reasked_with_the_validation_error():
    script = Recorder({"city": "Huế", "population": "many"}, {"city": "Huế", "population": 650000})
    result = FakeChatModel(script).generate(ASK, schema=CITY)
    assert result.data == {"city": "Huế", "population": 650000}
    assert len(script.seen) == 2
    first, second = script.seen
    assert second[: len(first)] == first
    added = second[len(first) :]
    assert [message.role for message in added] == ["assistant", "user"]
    assert "many" in added[0].content
    assert "is not of type 'integer'" in added[1].content


def test_output_that_is_not_json_is_reasked():
    script = Recorder("Huế, about 650 thousand", '{"city": "Huế", "population": 650000}')
    result = FakeChatModel(script).generate(ASK, schema=CITY)
    assert result.data == {"city": "Huế", "population": 650000}
    assert len(script.seen) == 2


def test_json_in_a_code_fence_is_parsed():
    model = FakeChatModel(['```json\n{"city": "Huế", "population": 650000}\n```'])
    assert model.generate(ASK, schema=CITY).data == {"city": "Huế", "population": 650000}


def test_still_invalid_after_retries_raises_with_strategy_and_attempts():
    script = Recorder({"city": 1}, {"city": 2}, {"city": 3}, {"city": 4})
    model = FakeChatModel(script, capabilities=profile(strategies=("json_mode",)))
    with pytest.raises(StructuredOutputError) as caught:
        model.generate(ASK, schema=CITY)
    assert (caught.value.strategy, caught.value.attempts) == ("json_mode", 3)
    assert "json_mode" in str(caught.value)
    assert "3" in str(caught.value)
    assert len(script.seen) == 3


def test_parse_retries_zero_means_one_attempt():
    script = Recorder({"city": 1}, {"city": "Huế", "population": 1})
    with pytest.raises(StructuredOutputError) as caught:
        FakeChatModel(script, capabilities=profile(parse_retries=0)).generate(ASK, schema=CITY)
    assert caught.value.attempts == 1
    assert len(script.seen) == 1
