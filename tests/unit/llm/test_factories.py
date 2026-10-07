"""chat_model_from_settings and embedding_model_from_settings (contracts/llm.md, T051).

Behaviours:
1. The provider picks the class.
2. The credential is resolved with the target name: a credential from code wins,
   a missing one raises MissingCredentialError even with OPENAI_API_KEY set,
   and a kind the target cannot use raises CredentialMismatchError.
3. The capability overrides of the settings reach the model.
"""

import pytest

from tenetrag import CredentialMismatchError, MissingCredentialError
from tenetrag.auth import Credentials, Secret
from tenetrag.config import (
    ApiKeySource,
    CapabilityOverrides,
    ChatModelSettings,
    EmbeddingModelSettings,
    PatSource,
)
from tenetrag.llm import (
    DatabricksChatModel,
    DatabricksEmbeddingModel,
    FakeChatModel,
    FakeEmbeddingModel,
    OpenAICompatibleChatModel,
    OpenAICompatibleEmbeddingModel,
    chat_model_from_settings,
    embedding_model_from_settings,
)
from tenetrag.protocols import Message
from tests.support.fake_openai import FakeServer, chat_reply

BASE_URL = "https://llm.example.net/v1"
HOST = "https://adb-1.example.net"
ASK = [Message("user", "Which city?")]


def openai_settings(**fields) -> ChatModelSettings:
    return ChatModelSettings(
        **{"provider": "openai_compatible", "base_url": BASE_URL, "model": "qwen3-32b", **fields}
    )


def test_provider_picks_the_chat_class(monkeypatch):
    monkeypatch.setenv("LLM_KEY", "sk-test-key-1")
    monkeypatch.setenv("WORKSPACE_PAT", "dapi-test-1")
    key = ApiKeySource(kind="api_key", env="LLM_KEY")
    pat = PatSource(kind="pat", token_env="WORKSPACE_PAT")
    cases = [
        (openai_settings(credential=key), OpenAICompatibleChatModel),
        (
            ChatModelSettings(provider="databricks", model="m", workspace_url=HOST, credential=pat),
            DatabricksChatModel,
        ),
        (ChatModelSettings(provider="fake", model="fake-chat"), FakeChatModel),
    ]
    for settings, cls in cases:
        assert type(chat_model_from_settings(settings, target_name="models.answer")) is cls


def test_provider_picks_the_embedding_class(monkeypatch):
    monkeypatch.setenv("WORKSPACE_PAT", "dapi-test-1")
    limits = CapabilityOverrides(max_input_tokens=512)
    cases = [
        (
            EmbeddingModelSettings(
                provider="openai_compatible",
                base_url=BASE_URL,
                model="e",
                dimensions=4,
                credential={"kind": "none"},
                capabilities=limits,
            ),
            OpenAICompatibleEmbeddingModel,
        ),
        (
            EmbeddingModelSettings(
                provider="databricks",
                model="databricks-qwen3-embedding-0-6b",
                workspace_url=HOST,
                credential={"kind": "pat", "token_env": "WORKSPACE_PAT"},
            ),
            DatabricksEmbeddingModel,
        ),
        (
            EmbeddingModelSettings(provider="fake", model="fake-embed", dimensions=4),
            FakeEmbeddingModel,
        ),
    ]
    for settings, cls in cases:
        model = embedding_model_from_settings(settings, target_name="models.embedding")
        assert type(model) is cls


def test_missing_credential_names_the_target(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-ambient")
    with pytest.raises(MissingCredentialError, match=r"models\.answer"):
        chat_model_from_settings(openai_settings(), target_name="models.answer")


def test_credential_from_code_wins():
    server = FakeServer(chat_reply("Huế"))
    model = chat_model_from_settings(
        openai_settings(credential=ApiKeySource(kind="api_key", env="UNSET_KEY")),
        target_name="models.answer",
        credential=Credentials.api_key(Secret("sk-from-code")),
        http_client=server.client(),
    )
    model.generate(ASK)
    assert server.last.headers["authorization"] == "Bearer sk-from-code"


def test_kind_the_target_cannot_use_is_refused():
    with pytest.raises(CredentialMismatchError, match=r"models\.answer"):
        chat_model_from_settings(
            openai_settings(),
            target_name="models.answer",
            credential=Credentials.pat(HOST, Secret("dapi-test-1")),
        )


def test_capability_overrides_reach_the_model():
    server = FakeServer(chat_reply('{"city": "Huế"}'))
    model = chat_model_from_settings(
        openai_settings(capabilities=CapabilityOverrides(strategies=("json_mode",))),
        target_name="models.answer",
        credential=Credentials.none(),
        http_client=server.client(),
    )
    schema = {"type": "object", "properties": {"city": {"type": "string"}}}
    assert model.generate(ASK, schema=schema).data == {"city": "Huế"}
    assert server.last.body["response_format"] == {"type": "json_object"}


def test_fake_from_settings_answers_its_script():
    model = chat_model_from_settings(
        ChatModelSettings(provider="fake", model="fake-chat"),
        target_name="models.answer",
        fake_responses=["Huế"],
    )
    assert model.generate(ASK).text == "Huế"
    assert model.model_id == "fake-chat"
