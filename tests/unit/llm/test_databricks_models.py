"""Databricks serving endpoints through the OpenAI-compatible classes (research R9, T050).

Behaviours:
1. Requests go to {workspace}/serving-endpoints with the credential's token.
2. The workspace comes from the settings, or from a cli_profile or runtime
   credential; a mismatch between the two, or neither, raises ConfigError.
3. A 401 on a refreshable credential gets a new token once (test_reauth_once);
   a second 401 raises CredentialRejectedError.
4. The output limit is sent as max_tokens.
5. Embeddings use the shipped dimension of the endpoint.
"""

import pytest

from tenetrag import ConfigError, CredentialRejectedError
from tenetrag.auth import Credentials, Secret
from tenetrag.config import ChatModelSettings, CliProfileSource, EmbeddingModelSettings
from tenetrag.llm import DatabricksChatModel, DatabricksEmbeddingModel, capability_profile
from tenetrag.protocols import Message
from tests.support.fake_databricks import HOST, FakeConfig, FakeWorkspaceClient
from tests.support.fake_openai import FakeServer, chat_reply, embedding_reply, error_reply

CHAT_MODEL = "databricks-claude-sonnet-5"
EMBED_MODEL = "databricks-qwen3-embedding-0-6b"
PAT = "dapi-test-1"
ASK = [Message("user", "Which city?")]
CLI = CliProfileSource(kind="cli_profile", name="dev")


def chat(server, login, **settings) -> DatabricksChatModel:
    """`login` is the credential passed in code; `settings` may name a source as `credential`."""
    values = {"provider": "databricks", "model": CHAT_MODEL, **settings}
    return DatabricksChatModel(
        ChatModelSettings(**values),
        credential=login,
        capabilities=capability_profile("databricks", CHAT_MODEL),
        http_client=server.client(),
    )


def test_requests_go_to_serving_endpoints_with_the_token():
    server = FakeServer(chat_reply("Huế"))
    model = chat(server, Credentials.pat(HOST, Secret(PAT)), workspace_url=HOST)
    assert model.generate(ASK).text == "Huế"
    assert server.last.url == f"{HOST}/serving-endpoints/chat/completions"
    assert server.last.headers["authorization"] == f"Bearer {PAT}"
    assert server.last.body["model"] == CHAT_MODEL
    assert "temperature" not in server.last.body  # sonnet-5's profile drops it


def test_workspace_from_a_cli_profile_credential(fake_sdk):
    server = FakeServer(chat_reply("Huế"))
    chat(server, Credentials.cli_profile("dev"), credential=CLI).generate(ASK)
    assert server.last.url == f"{HOST}/serving-endpoints/chat/completions"
    assert server.last.headers["authorization"] == "Bearer tok-1"


def test_workspace_mismatch_raises_before_any_request(fake_sdk):
    server = FakeServer()
    with pytest.raises(ConfigError) as caught:
        chat(
            server,
            Credentials.cli_profile("dev"),
            credential=CLI,
            workspace_url="https://adb-2.example.net",
        )
    assert "adb-1.example.net" in str(caught.value)
    assert "adb-2.example.net" in str(caught.value)
    assert server.requests == []


def test_no_workspace_raises():
    client = FakeWorkspaceClient(FakeConfig("tok", host=None))
    with pytest.raises(ConfigError, match="workspace"):
        chat(FakeServer(), Credentials.workspace_client(client), credential=CLI)


def test_reauth_once(fake_sdk):
    server = FakeServer(error_reply(401, "expired"), chat_reply("Huế"))
    result = chat(server, Credentials.cli_profile("dev"), credential=CLI).generate(ASK)
    assert result.text == "Huế"
    assert [request.headers["authorization"] for request in server.requests] == [
        "Bearer tok-1",
        "Bearer tok-2",
    ]


def test_second_rejection_raises(fake_sdk):
    server = FakeServer(error_reply(401), error_reply(401))
    with pytest.raises(CredentialRejectedError, match="cli_profile:dev"):
        chat(server, Credentials.cli_profile("dev"), credential=CLI).generate(ASK)
    assert len(server.requests) == 2


def test_output_limit_is_sent_as_max_tokens():
    server = FakeServer(chat_reply("Huế"))
    model = chat(server, Credentials.pat(HOST, Secret(PAT)), workspace_url=HOST)
    model.generate(ASK, max_output_tokens=200)
    assert server.last.body["max_tokens"] == 200
    assert "max_completion_tokens" not in server.last.body


def test_embeddings_use_the_shipped_dimension():
    vectors = [[0.5] * 1024, [0.25] * 1024]
    server = FakeServer(embedding_reply(vectors))
    model = DatabricksEmbeddingModel(
        EmbeddingModelSettings(provider="databricks", model=EMBED_MODEL, workspace_url=HOST),
        credential=Credentials.pat(HOST, Secret(PAT)),
        capabilities=capability_profile("databricks", EMBED_MODEL),
        http_client=server.client(),
    )
    assert model.dimensions == 1024
    assert model.embed_documents(["Huế", "Hà Nội"]) == vectors
    assert server.last.url == f"{HOST}/serving-endpoints/embeddings"
