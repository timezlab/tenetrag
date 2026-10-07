"""The fake models that engine tests run on (data-model §10, FR-025, T042).

Behaviours:
1. The same inputs give identical outputs; an exhausted script raises AssertionError.
2. Scripted exceptions are raised; a callable script gets (messages, schema).
3. Each call is recorded as (messages, schema, params).
4. A dict answer is returned as data and as JSON text; a ChatResult keeps its usage.
5. Fake vectors are unit length, deterministic, and differ for query and passage.
"""

import json
import math

import pytest

from tenetrag import ModelUnavailableError, UnsupportedRequestError
from tenetrag.llm import FakeChatModel, FakeEmbeddingModel
from tenetrag.protocols import ChatModel, ChatResult, EmbeddingModel, Message, Usage

ASK = [Message("user", "Which city?")]
CITY = {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]}


def test_fake_deterministic():
    def run():
        model = FakeChatModel(["first", {"city": "Huế"}])
        return model.generate(ASK).text, model.generate(ASK, schema=CITY).data

    assert run() == run() == ("first", {"city": "Huế"})
    first = FakeEmbeddingModel().embed_documents(["Huế"])
    assert first == FakeEmbeddingModel().embed_documents(["Huế"])


def test_exhausted_script_raises_assertion_error():
    model = FakeChatModel(["only"])
    model.generate(ASK)
    with pytest.raises(AssertionError, match="script"):
        model.generate(ASK)


def test_unscripted_model_raises_assertion_error():
    with pytest.raises(AssertionError):
        FakeChatModel().generate(ASK)


def test_scripted_exception_is_raised():
    failure = ModelUnavailableError("scripted outage")
    model = FakeChatModel([failure, "after"])
    with pytest.raises(ModelUnavailableError) as caught:
        model.generate(ASK)
    assert caught.value is failure
    assert model.generate(ASK).text == "after"


def test_callable_script_gets_messages_and_schema():
    seen = []

    def script(messages, schema):
        seen.append((list(messages), schema))
        return {"city": "Huế"}

    result = FakeChatModel(script).generate(ASK, schema=CITY)
    assert result.data == {"city": "Huế"}
    assert seen == [(ASK, CITY)]


def test_calls_are_recorded():
    model = FakeChatModel(["a", "b"])
    model.generate(ASK)
    model.generate(ASK, schema=None, max_output_tokens=50, temperature=0.4)
    assert model.calls == [
        (ASK, None, {"max_output_tokens": None, "temperature": 0.0}),
        (ASK, None, {"max_output_tokens": 50, "temperature": 0.4}),
    ]


def test_dict_answer_is_data_and_json_text():
    result = FakeChatModel([{"city": "Huế"}]).generate(ASK, schema=CITY)
    assert result.data == {"city": "Huế"}
    assert json.loads(result.text) == {"city": "Huế"}
    assert result.model_id == "fake-chat"
    assert result.usage == Usage(None, None, None)


def test_chat_result_answer_keeps_its_usage():
    scripted = ChatResult(
        text="Huế",
        data=None,
        usage=Usage(input_tokens=5, cached_input_tokens=0, output_tokens=2),
        model_id="fake-chat",
        strategy=None,
        finish_reason="stop",
    )
    assert FakeChatModel([scripted]).generate(ASK).usage == Usage(5, 0, 2)


def test_vectors_are_unit_length_with_the_dimension():
    vectors = FakeEmbeddingModel(dimensions=16).embed_documents(["Huế", "Hà Nội"])
    assert [len(vector) for vector in vectors] == [16, 16]
    for vector in vectors:
        assert math.isclose(math.fsum(x * x for x in vector), 1.0)
    assert vectors[0] != vectors[1]


def test_query_and_passage_vectors_differ():
    model = FakeEmbeddingModel()
    assert model.embed_queries(["Huế"]) != model.embed_documents(["Huế"])


def test_embedding_calls_are_recorded():
    model = FakeEmbeddingModel()
    model.embed_documents(["a"])
    model.embed_queries(["b"])
    assert model.calls == [("documents", ["a"]), ("queries", ["b"])]


def test_fake_embedding_refuses_empty_texts():
    with pytest.raises(UnsupportedRequestError, match="0"):
        FakeEmbeddingModel().embed_documents([""])


def test_fakes_satisfy_the_protocols():
    chat: ChatModel = FakeChatModel(["a"])
    embedding: EmbeddingModel = FakeEmbeddingModel()
    assert isinstance(chat.model_id, str)
    assert (embedding.dimensions, embedding.max_input_tokens) == (8, 8192)
    assert embedding.count_tokens("a") is None
