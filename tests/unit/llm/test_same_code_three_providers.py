"""One calling function runs on fake, OpenAI-compatible and Databricks models (SC-009, T043).

Only the profile changes. The HTTP providers answer from a scripted server and
the fake from its script, passed through the factories' test seams.
"""

import pytest

from tenetrag.config import Profile, profile_from_yaml
from tenetrag.llm import chat_model_from_settings, embedding_model_from_settings
from tenetrag.protocols import Message
from tests.support.fake_openai import FakeServer, embedding_reply, json_reply

CITY = {
    "type": "object",
    "properties": {"city": {"type": "string"}},
    "required": ["city"],
    "additionalProperties": False,
}
ANSWER = {"city": "Huế"}

PROFILES = {
    "fake": """
models:
  extraction: {provider: fake, model: fake-chat}
  embedding: {provider: fake, model: fake-embed, dimensions: 8}
""",
    "openai_compatible": """
models:
  extraction:
    provider: openai_compatible
    base_url: https://llm.example.net/v1
    model: qwen3-32b
    credential: {kind: api_key, env: LLM_KEY}
    capabilities: {strategies: [json_mode, prompt_parse]}
  embedding:
    provider: openai_compatible
    base_url: https://llm.example.net/v1
    model: bge-m3
    dimensions: 8
    credential: {kind: api_key, env: LLM_KEY}
    capabilities: {max_input_tokens: 8192}
""",
    "databricks": """
models:
  extraction:
    provider: databricks
    model: databricks-claude-sonnet-5
    workspace_url: https://adb-1.example.net
    credential: {kind: pat, token_env: WORKSPACE_PAT}
  embedding:
    provider: databricks
    model: databricks-qwen3-embedding-0-6b
    workspace_url: https://adb-1.example.net
    credential: {kind: pat, token_env: WORKSPACE_PAT}
""",
}
DIMENSIONS = {"fake": 8, "openai_compatible": 8, "databricks": 1024}


def city_and_vectors(profile: Profile, server: FakeServer):
    """The calling code under test: the same for every provider."""
    chat = chat_model_from_settings(
        profile.models.extraction,
        target_name="models.extraction",
        http_client=server.client(),
        fake_responses=[ANSWER],
    )
    embedding = embedding_model_from_settings(
        profile.models.embedding, target_name="models.embedding", http_client=server.client()
    )
    result = chat.generate([Message("user", "Which city was the old capital?")], schema=CITY)
    vectors = embedding.embed_documents(["Huế", "Hà Nội"])
    return result.data, [len(vector) for vector in vectors]


@pytest.mark.parametrize("provider", list(PROFILES))
def test_same_code_three_providers(provider, monkeypatch):
    monkeypatch.setenv("LLM_KEY", "sk-test-key-1")
    monkeypatch.setenv("WORKSPACE_PAT", "dapi-test-1")
    dimensions = DIMENSIONS[provider]
    server = FakeServer(json_reply(ANSWER), embedding_reply([[0.5] * dimensions] * 2))
    profile = profile_from_yaml(PROFILES[provider])
    assert city_and_vectors(profile, server) == (ANSWER, [dimensions, dimensions])
    expected_requests = 0 if provider == "fake" else 2
    assert len(server.requests) == expected_requests
