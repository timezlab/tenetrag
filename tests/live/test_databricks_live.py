"""Model calls against a real Databricks workspace (T044). Opt-in, never run in CI.

Set TENETRAG_LIVE_DATABRICKS_PROFILE to a Databricks CLI profile you have logged
in with. TENETRAG_LIVE_DATABRICKS_CHAT_MODEL and
TENETRAG_LIVE_DATABRICKS_EMBEDDING_MODEL pick other serving endpoints.

    TENETRAG_LIVE_DATABRICKS_PROFILE=dev uv run pytest -m live -q
"""

import logging
import os

import pytest

from tenetrag.auth import Credentials
from tenetrag.auth import databricks as databricks_auth
from tenetrag.config import ChatModelSettings, CliProfileSource, EmbeddingModelSettings
from tenetrag.llm import capability_profile, chat_model_from_settings, embedding_model_from_settings
from tenetrag.protocols import Message

PROFILE = os.environ.get("TENETRAG_LIVE_DATABRICKS_PROFILE", "")
CHAT_MODEL = os.environ.get(
    "TENETRAG_LIVE_DATABRICKS_CHAT_MODEL", "databricks-meta-llama-3-3-70b-instruct"
)
EMBEDDING_MODEL = os.environ.get(
    "TENETRAG_LIVE_DATABRICKS_EMBEDDING_MODEL", "databricks-qwen3-embedding-0-6b"
)

pytestmark = [
    pytest.mark.live,
    pytest.mark.enable_socket,
    pytest.mark.skipif(not PROFILE, reason="set TENETRAG_LIVE_DATABRICKS_PROFILE to run"),
]

CITY = {
    "type": "object",
    "properties": {"city": {"type": "string"}},
    "required": ["city"],
    "additionalProperties": False,
}


def source() -> CliProfileSource:
    return CliProfileSource(kind="cli_profile", name=PROFILE)


def test_chat_with_a_small_schema():
    settings = ChatModelSettings(
        provider="databricks", model=CHAT_MODEL, credential=source(), max_output_tokens=200
    )
    model = chat_model_from_settings(settings, target_name="live.chat")
    question = Message("user", "Which city is the capital of Vietnam? Reply with its name.")
    result = model.generate([question], schema=CITY)
    assert isinstance(result.data, dict)
    assert result.data["city"]
    assert result.finish_reason == "stop"


def test_embedding_dimension_matches_the_shipped_profile():
    settings = EmbeddingModelSettings(
        provider="databricks", model=EMBEDDING_MODEL, credential=source()
    )
    model = embedding_model_from_settings(settings, target_name="live.embedding")
    vectors = model.embed_documents(["Hà Nội là thủ đô của Việt Nam."])
    shipped = capability_profile("databricks", EMBEDDING_MODEL).embedding_dimensions
    assert [len(vector) for vector in vectors] == [shipped]


def test_sdk_environment_warning(monkeypatch, caplog):
    # DATABRICKS_HOST is set to the profile's own host, so the login is unchanged.
    host = Credentials.cli_profile(PROFILE)._host
    assert host is not None
    monkeypatch.setenv("DATABRICKS_HOST", host)
    monkeypatch.setattr(databricks_auth, "_env_warning_logged", False)
    with caplog.at_level(logging.WARNING, logger="tenetrag"):
        Credentials.cli_profile(PROFILE)
    assert "DATABRICKS_HOST" in caplog.text
