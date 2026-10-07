"""The OpenAI-compatible embedding model on a scripted server (contracts/llm.md, T041).

Behaviours:
1. Vectors come back in input order whatever order the server sends; a wrong
   dimension or count raises ResponseError; [] makes no request.
2. Documents and queries get their own prefixes.
3. Empty texts, and texts over max_input_tokens when the count is known, are
   refused before any request, by position.
4. encoding_format "float" is sent, and inputs are batched by batch_size.
5. count_tokens is unknown without a local tokenizer.
"""

import pytest

from tenetrag import ResponseError, UnsupportedRequestError
from tenetrag.auth import Credentials, Secret
from tenetrag.config import CapabilityOverrides, EmbeddingModelSettings
from tenetrag.llm import OpenAICompatibleEmbeddingModel, capability_profile
from tests.support.fake_openai import FakeServer, embedding_reply

BASE_URL = "https://llm.example.net/v1"


def unit(index: int, dimensions: int = 3) -> list[float]:
    return [1.0 if i == index % dimensions else 0.0 for i in range(dimensions)]


def embedder(server, *, dimensions=3, batch_size=64, **overrides) -> OpenAICompatibleEmbeddingModel:
    capabilities = CapabilityOverrides(**{"max_input_tokens": 100, **overrides})
    settings = EmbeddingModelSettings(
        provider="openai_compatible",
        base_url=BASE_URL,
        model="bge-m3",
        dimensions=dimensions,
        batch_size=batch_size,
        capabilities=capabilities,
    )
    return OpenAICompatibleEmbeddingModel(
        settings,
        credential=Credentials.api_key(Secret("sk-test-key-1")),
        capabilities=capability_profile("openai_compatible", "bge-m3", capabilities),
        http_client=server.client(),
    )


def test_embedding_order_and_dimension():
    server = FakeServer(embedding_reply([unit(0), unit(1), unit(2)], order=[2, 0, 1]))
    assert embedder(server).embed_documents(["a", "b", "c"]) == [unit(0), unit(1), unit(2)]
    assert server.last.path == "/v1/embeddings"
    assert server.last.body["input"] == ["a", "b", "c"]
    assert server.last.body["model"] == "bge-m3"

    wrong = FakeServer(embedding_reply([[1.0, 0.0], [0.0, 1.0]]))
    with pytest.raises(ResponseError, match="dimension"):
        embedder(wrong).embed_documents(["a", "b"])

    empty = FakeServer()
    assert embedder(empty).embed_documents([]) == []
    assert embedder(empty).embed_queries([]) == []
    assert empty.requests == []


def test_wrong_vector_count_raises():
    server = FakeServer(embedding_reply([unit(0)]))
    with pytest.raises(ResponseError):
        embedder(server).embed_documents(["a", "b"])


def test_prefixes():
    server = FakeServer(embedding_reply([unit(0)]), embedding_reply([unit(1)]))
    model = embedder(server, query_prefix="query: ", passage_prefix="passage: ")
    model.embed_queries(["Ai là thống đốc?"])
    assert server.last.body["input"] == ["query: Ai là thống đốc?"]
    model.embed_documents(["Ông A là thống đốc."])
    assert server.last.body["input"] == ["passage: Ông A là thống đốc."]


def test_no_prefix_by_default():
    server = FakeServer(embedding_reply([unit(0)]))
    embedder(server).embed_queries(["q"])
    assert server.last.body["input"] == ["q"]


def test_empty_texts_are_refused_by_position():
    server = FakeServer()
    with pytest.raises(UnsupportedRequestError) as caught:
        embedder(server).embed_documents(["a", "", "b", ""])
    assert "1, 3" in str(caught.value)
    assert server.requests == []


def test_over_long_texts_are_refused_when_the_count_is_known(monkeypatch):
    server = FakeServer()
    model = embedder(server, max_input_tokens=5)
    monkeypatch.setattr(model, "count_tokens", lambda text: len(text))
    with pytest.raises(UnsupportedRequestError) as caught:
        model.embed_documents(["short", "much too long"])
    assert "1" in str(caught.value)
    assert "5" in str(caught.value)
    assert server.requests == []


def test_count_tokens_is_unknown():
    assert embedder(FakeServer()).count_tokens("xin chào") is None


def test_encoding_format_float():
    server = FakeServer(embedding_reply([unit(0)]))
    embedder(server).embed_documents(["a"])
    assert server.last.body["encoding_format"] == "float"


def test_batching_respects_batch_size():
    server = FakeServer(
        embedding_reply([unit(0), unit(1)]),
        embedding_reply([unit(2), unit(0)]),
        embedding_reply([unit(1)]),
    )
    vectors = embedder(server, batch_size=2).embed_documents(["a", "b", "c", "d", "e"])
    assert [request.body["input"] for request in server.requests] == [["a", "b"], ["c", "d"], ["e"]]
    assert vectors == [unit(0), unit(1), unit(2), unit(0), unit(1)]
