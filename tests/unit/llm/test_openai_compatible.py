"""The OpenAI-compatible chat model on a scripted server (contracts/llm.md, research R9, T040).

Behaviours:
1. Each strategy sends the request shape of research R9, and the result says
   which strategy ran.
2. Invalid output is re-asked; truncated output raises OutputTruncatedError at once.
3. 429 and 5xx are retried, honouring retry-after, until the budget runs out.
4. 401 on a key that cannot refresh fails after one request.
5. Temperature is sent unless the profile drops it.
6. A forbidden schema keyword is refused before any request.
7. Unreported usage is None, never zero; usage adds up over re-asks.
8. The key and URL come from the settings and credential, never from OPENAI_*
   variables; OPENAI_CUSTOM_HEADERS cannot replace the Authorization header;
   `none` sends no Authorization header.
9. OPENAI_ORG_ID, OPENAI_PROJECT_ID or OPENAI_CUSTOM_HEADERS log one warning per process.
10. Other 4xx answers raise LLMError with the status and the server's message.
11. Prompt and response text are logged only with log_content.
"""

import json
import logging
import sys

import pytest

from tenetrag import (
    CredentialRejectedError,
    LLMError,
    MissingExtraError,
    ModelUnavailableError,
    OutputTruncatedError,
    StructuredOutputError,
    UnsupportedRequestError,
)
from tenetrag.auth import Credentials, Secret
from tenetrag.config import CapabilityOverrides, ChatModelSettings, ModelRetrySettings
from tenetrag.llm import OpenAICompatibleChatModel, Strategy, capability_profile
from tenetrag.llm import openai_compatible as module
from tenetrag.protocols import Message
from tests.support.fake_openai import (
    FakeServer,
    chat_reply,
    error_reply,
    json_reply,
    messages_of,
)

BASE_URL = "https://llm.example.net/v1"
KEY = "sk-test-key-1"
ASK = [Message("user", "Which city?")]
CITY = {
    "type": "object",
    "properties": {"city": {"type": "string"}},
    "required": ["city"],
    "additionalProperties": False,
}
HUE = {"city": "Huế"}


class FakeTime:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


@pytest.fixture(autouse=True)
def _reset_env_warning(monkeypatch):
    monkeypatch.setattr(module, "_env_warning_logged", False)


def chat(
    server,
    *,
    credential=None,
    capabilities=None,
    fake_time=None,
    model="gpt-4o",
    **settings,
) -> OpenAICompatibleChatModel:
    values = {"provider": "openai_compatible", "base_url": BASE_URL, "model": model, **settings}
    fake_time = fake_time or FakeTime()
    return OpenAICompatibleChatModel(
        ChatModelSettings(**values),
        credential=credential or Credentials.api_key(Secret(KEY)),
        capabilities=capabilities or capability_profile("openai_compatible", model),
        http_client=server.client(),
        sleep=fake_time.sleep,
        clock=fake_time.clock,
    )


def strategies(*names):
    return capability_profile(
        "openai_compatible", "qwen3-32b", CapabilityOverrides(strategies=names)
    )


# Request shapes (research R9)


def test_native_schema_request():
    server = FakeServer(json_reply(HUE))
    result = chat(server).generate(ASK, schema=CITY)
    body = server.last.body
    assert body["response_format"] == {
        "type": "json_schema",
        "json_schema": {"name": "output", "schema": CITY, "strict": True},
    }
    assert "tools" not in body
    assert messages_of(server.last) == [{"role": "user", "content": "Which city?"}]
    assert (result.strategy, result.data, result.finish_reason) == (
        Strategy.NATIVE_SCHEMA,
        HUE,
        "stop",
    )
    assert server.last.path == "/v1/chat/completions"
    assert body["model"] == "gpt-4o"


def test_strategy_order():
    # A profile without native_schema sends tool_call, and the result says so.
    server = FakeServer(chat_reply(None, tool_args=json.dumps(HUE)))
    result = chat(server, capabilities=strategies("tool_call", "json_mode")).generate(
        ASK, schema=CITY
    )
    body = server.last.body
    assert body["tools"] == [
        {
            "type": "function",
            "function": {
                "name": "output",
                "description": "Return the answer as this function's arguments.",
                "parameters": CITY,
            },
        }
    ]
    assert body["tool_choice"] == {"type": "function", "function": {"name": "output"}}
    assert "response_format" not in body
    assert (result.strategy, result.data) == (Strategy.TOOL_CALL, HUE)


@pytest.mark.parametrize(
    ("strategy", "response_format"),
    [("json_mode", {"type": "json_object"}), ("prompt_parse", None)],
)
def test_schema_in_the_system_message(strategy, response_format):
    server = FakeServer(json_reply(HUE))
    result = chat(server, capabilities=strategies(strategy)).generate(ASK, schema=CITY)
    body = server.last.body
    assert body.get("response_format") == response_format
    assert "tools" not in body
    first, *rest = messages_of(server.last)
    assert first["role"] == "system"
    assert json.dumps(CITY, ensure_ascii=False, sort_keys=True) in first["content"]
    assert rest == [{"role": "user", "content": "Which city?"}]
    assert result.strategy == strategy


def test_caller_system_message_is_kept_first():
    server = FakeServer(json_reply(HUE))
    messages = [Message("system", "Answer briefly."), *ASK]
    chat(server, capabilities=strategies("json_mode")).generate(messages, schema=CITY)
    sent = messages_of(server.last)
    assert [message["role"] for message in sent] == ["system", "user"]
    assert sent[0]["content"].startswith("Answer briefly.")
    assert '"city"' in sent[0]["content"]


def test_plain_text_without_schema():
    server = FakeServer(chat_reply("Huế"))
    result = chat(server).generate(ASK)
    assert (result.text, result.data, result.strategy) == ("Huế", None, None)
    assert "response_format" not in server.last.body


# Validation and truncation


def test_parse_retry_then_error():
    server = FakeServer(json_reply({"city": 1}), chat_reply("not json"), json_reply(HUE))
    result = chat(server).generate(ASK, schema=CITY)
    assert result.data == HUE
    assert len(server.requests) == 3
    last_messages = messages_of(server.requests[2])
    assert last_messages[-1]["role"] == "user"
    assert "not valid JSON" in last_messages[-1]["content"]

    failing = FakeServer(*(json_reply({"city": n}) for n in range(3)))
    with pytest.raises(StructuredOutputError) as caught:
        chat(failing).generate(ASK, schema=CITY)
    assert (caught.value.strategy, caught.value.attempts) == ("native_schema", 3)
    assert len(failing.requests) == 3


def test_truncation():
    server = FakeServer(chat_reply('{"city": "Hu', finish_reason="length"))
    with pytest.raises(OutputTruncatedError, match="max_output_tokens"):
        chat(server).generate(ASK, schema=CITY)
    assert len(server.requests) == 1


def test_missing_tool_call_is_reasked():
    server = FakeServer(chat_reply("Huế"), chat_reply(None, tool_args=json.dumps(HUE)))
    result = chat(server, capabilities=strategies("tool_call")).generate(ASK, schema=CITY)
    assert result.data == HUE
    assert len(server.requests) == 2


# Retries


def test_rate_limit_retry_after():
    fake_time = FakeTime()
    server = FakeServer(error_reply(429, headers={"retry-after": "1"}), json_reply(HUE))
    result = chat(server, fake_time=fake_time).generate(ASK, schema=CITY)
    assert result.data == HUE
    assert fake_time.sleeps == [1.0]
    assert len(server.requests) == 2


def test_rate_limit_budget_exhausted():
    server = FakeServer(error_reply(429), error_reply(429))
    model = chat(server, retry=ModelRetrySettings(max_attempts=2))
    with pytest.raises(ModelUnavailableError) as caught:
        model.generate(ASK, schema=CITY)
    assert "gpt-4o" in str(caught.value)
    assert "429" in str(caught.value)
    assert len(server.requests) == 2


def test_server_error_is_retried():
    server = FakeServer(error_reply(503), json_reply(HUE))
    assert chat(server).generate(ASK, schema=CITY).data == HUE
    assert len(server.requests) == 2


def test_auth_fails_fast():
    server = FakeServer(error_reply(401, "bad key"), json_reply(HUE))
    with pytest.raises(CredentialRejectedError, match="api_key"):
        chat(server).generate(ASK, schema=CITY)
    assert len(server.requests) == 1


def test_permission_denied_fails_fast():
    server = FakeServer(error_reply(403, "no access"))
    with pytest.raises(CredentialRejectedError):
        chat(server).generate(ASK)
    assert len(server.requests) == 1


def test_bad_request_names_status_and_message():
    server = FakeServer(error_reply(400, "Unsupported parameter: 'seed'."))
    with pytest.raises(LLMError) as caught:
        chat(server).generate(ASK)
    assert type(caught.value) is LLMError
    assert "400" in str(caught.value)
    assert "Unsupported parameter: 'seed'." in str(caught.value)
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    assert len(server.requests) == 1


# Parameters


def test_temperature_dropped():
    server = FakeServer(chat_reply("a"), chat_reply("b"), chat_reply("c"))
    model = chat(server, model="gpt-5")  # the profile drops temperature
    model.generate(ASK)
    assert "temperature" not in server.last.body
    kept = chat(server, temperature=0.3)
    kept.generate(ASK)
    assert server.last.body["temperature"] == 0.3
    kept.generate(ASK, temperature=0.9)
    assert server.last.body["temperature"] == 0.9


def test_max_output_tokens_from_settings_or_call():
    server = FakeServer(chat_reply("a"), chat_reply("b"), chat_reply("c"))
    chat(server).generate(ASK)
    assert "max_completion_tokens" not in server.last.body
    model = chat(server, max_output_tokens=500)
    model.generate(ASK)
    assert server.last.body["max_completion_tokens"] == 500
    model.generate(ASK, max_output_tokens=50)
    assert server.last.body["max_completion_tokens"] == 50


def test_forbidden_schema():
    server = FakeServer()
    capabilities = capability_profile("databricks", "databricks-gpt-5")
    schema = {"type": "object", "properties": {"x": {"anyOf": [{"type": "string"}]}}}
    with pytest.raises(UnsupportedRequestError, match="anyOf"):
        chat(server, capabilities=capabilities).generate(ASK, schema=schema)
    assert server.requests == []


# Usage


def test_usage_unknown_not_zero():
    server = FakeServer(chat_reply("a"), chat_reply("b", usage=None))
    usage = chat(server).generate(ASK).usage
    assert (usage.input_tokens, usage.output_tokens, usage.cached_input_tokens) == (11, 7, None)
    usage = chat(server).generate(ASK).usage
    assert (usage.input_tokens, usage.output_tokens, usage.cached_input_tokens) == (
        None,
        None,
        None,
    )


def test_cached_tokens_are_read():
    usage = {
        "prompt_tokens": 100,
        "completion_tokens": 5,
        "total_tokens": 105,
        "prompt_tokens_details": {"cached_tokens": 64},
    }
    server = FakeServer(chat_reply("a", usage=usage))
    assert chat(server).generate(ASK).usage.cached_input_tokens == 64


def test_usage_adds_up_over_reasks():
    server = FakeServer(json_reply({"city": 1}), json_reply(HUE))
    usage = chat(server).generate(ASK, schema=CITY).usage
    assert (usage.input_tokens, usage.output_tokens) == (22, 14)


# The environment


def test_openai_env_not_used_for_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-from-env")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://env.example.org/v1")
    server = FakeServer(chat_reply("a"))
    chat(server).generate(ASK)
    assert server.last.url.startswith(BASE_URL)
    assert server.last.headers["authorization"] == f"Bearer {KEY}"


def test_custom_headers_cannot_replace_our_token(monkeypatch):
    monkeypatch.setenv("OPENAI_CUSTOM_HEADERS", "Authorization: Bearer ambient-token")
    server = FakeServer(chat_reply("a"), chat_reply("b"))
    chat(server).generate(ASK)
    assert server.last.headers["authorization"] == f"Bearer {KEY}"
    chat(server, credential=Credentials.none()).generate(ASK)
    assert "authorization" not in server.last.headers


def test_none_credential_sends_no_authorization():
    server = FakeServer(chat_reply("a"))
    chat(server, credential=Credentials.none()).generate(ASK)
    assert "authorization" not in server.last.headers


@pytest.mark.parametrize("name", ["OPENAI_ORG_ID", "OPENAI_PROJECT_ID", "OPENAI_CUSTOM_HEADERS"])
def test_openai_env_warning(monkeypatch, caplog, name):
    monkeypatch.setenv(name, "X-Team: value-not-logged")
    server = FakeServer()
    with caplog.at_level(logging.WARNING, logger="tenetrag"):
        chat(server)
        chat(server)
    warnings = [record for record in caplog.records if record.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert name in warnings[0].getMessage()
    assert "value-not-logged" not in caplog.text


def test_no_warning_without_openai_env(caplog):
    with caplog.at_level(logging.WARNING, logger="tenetrag"):
        chat(FakeServer())
    assert caplog.records == []


def test_missing_openai_extra(monkeypatch):
    monkeypatch.setitem(sys.modules, "openai", None)
    with pytest.raises(MissingExtraError) as caught:
        chat(FakeServer())
    assert caught.value.extra == "openai"


# Logging


def test_content_is_not_logged_by_default(caplog):
    server = FakeServer(chat_reply("the answer text"))
    with caplog.at_level(logging.DEBUG, logger="tenetrag"):
        chat(server).generate([Message("user", "the prompt text")])
    assert "the prompt text" not in caplog.text
    assert "the answer text" not in caplog.text


def test_content_is_logged_with_log_content(caplog):
    server = FakeServer(chat_reply("the answer text"))
    with caplog.at_level(logging.DEBUG, logger="tenetrag"):
        chat(server, log_content=True).generate([Message("user", "the prompt text")])
    assert "the prompt text" in caplog.text
    assert "the answer text" in caplog.text
