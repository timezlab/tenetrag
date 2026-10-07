"""Planted secrets never reach repr, str, logs or exception chains (SC-006).

Part 1 covers credentials, part 2 models and part 3 store connections.
"""

import logging
import sys

import httpx2
import neo4j
import pytest

from tenetrag import AuthError, CredentialRejectedError, CredentialSourceError, TenetRAGError
from tenetrag.auth import (
    AccessToken,
    Credential,
    CredentialKind,
    Credentials,
    Secret,
    TargetKind,
    resolve_credential,
)
from tenetrag.config import (
    ApiKeySource,
    BasicSource,
    CapabilityOverrides,
    ChatModelSettings,
    EmbeddingModelSettings,
    ModelRetrySettings,
    Neo4jSettings,
    OAuthM2MSource,
    PatSource,
    PostgresSettings,
    StoreRetrySettings,
)
from tenetrag.llm import (
    DatabricksChatModel,
    OpenAICompatibleChatModel,
    OpenAICompatibleEmbeddingModel,
    capability_profile,
)
from tenetrag.protocols import Message
from tenetrag.storage import Neo4jConnection, PostgresConnection
from tests.support.fake_databricks import HOST, FakeConfig, FakeWorkspaceClient
from tests.support.fake_openai import FakeServer, error_reply
from tests.support.fake_stores import (
    FakeNeo4j,
    FakePostgres,
    install_fake_postgres,
    neo4j_error,
    refused,
)
from tests.support.secrets import (
    PLANTED,
    assert_exception_clean,
    assert_logs_clean,
    assert_no_secret,
)

logger = logging.getLogger("tests.leak")

API_KEY, PASSWORD, TOKEN, PAT, CLIENT_SECRET = PLANTED


class Terminal:
    def isatty(self) -> bool:
        return True


def build(kind: CredentialKind, monkeypatch, fake_sdk) -> Credential:
    """A credential of `kind` holding planted values; Databricks tokens are planted too."""
    fake_sdk.tokens = [TOKEN, TOKEN, TOKEN]
    match kind:
        case CredentialKind.NONE:
            return Credentials.none()
        case CredentialKind.API_KEY:
            return Credentials.api_key(Secret(API_KEY))
        case CredentialKind.BASIC:
            return Credentials.basic("neo4j", Secret(PASSWORD))
        case CredentialKind.TOKEN_PROVIDER:
            return Credentials.token_provider(
                "app", lambda: AccessToken(Secret(TOKEN), expires_at=None), identity="app"
            )
        case CredentialKind.PAT:
            return Credentials.pat(HOST, Secret(PAT))
        case CredentialKind.OBO:
            return Credentials.obo(HOST, Secret(TOKEN))
        case CredentialKind.OAUTH_M2M:
            return Credentials.oauth_m2m(HOST, "sp-1", Secret(CLIENT_SECRET))
        case CredentialKind.OAUTH_U2M:
            with monkeypatch.context() as patch:  # only while building: print needs stdout
                patch.setattr(sys, "stdin", Terminal())
                patch.setattr(sys, "stdout", Terminal())
                return Credentials.oauth_u2m(HOST)
        case CredentialKind.CLI_PROFILE:
            return Credentials.cli_profile("dev")
        case CredentialKind.RUNTIME:
            monkeypatch.setenv("DATABRICKS_RUNTIME_VERSION", "17.3")
            return Credentials.runtime()
        case CredentialKind.WORKSPACE_CLIENT:
            return Credentials.workspace_client(FakeWorkspaceClient(FakeConfig(TOKEN)))
    raise AssertionError(kind)


def a_target_refusing(kind: CredentialKind) -> TargetKind:
    if kind is CredentialKind.NONE:
        return TargetKind.POSTGRES
    if kind in (CredentialKind.BASIC, CredentialKind.TOKEN_PROVIDER):
        return TargetKind.OPENAI_COMPATIBLE
    return TargetKind.NEO4J


def errors_from(credential: Credential) -> list[AuthError]:
    """Every auth error this credential can cause: a mismatch, and a rejected token."""
    errors: list[AuthError] = []
    try:
        resolve_credential(
            a_target_refusing(credential.kind), "connections.graph", None, credential
        )
    except AuthError as exc:
        errors.append(exc)
    tokens = credential._token_source
    if tokens is not None:
        try:
            for _ in range(3):
                tokens.invalidate(tokens.token())
        except CredentialRejectedError as exc:
            errors.append(exc)
    return errors


@pytest.mark.parametrize("kind", list(CredentialKind))
def test_secrets_never_leak(kind, monkeypatch, fake_sdk, capsys, caplog):
    monkeypatch.setenv("DATABRICKS_HOST", HOST)  # so the SDK environment warning is logged too
    with caplog.at_level(logging.DEBUG):
        credential = build(kind, monkeypatch, fake_sdk)
        tokens = credential._token_source
        printed = [credential]
        if tokens is not None:
            printed += [tokens, tokens.token(), tokens.token().value]
        for item in printed:
            print(item, repr(item))
            logger.debug("credential %s %r", item, item)
        errors = errors_from(credential)
    assert len(errors) == (2 if tokens is not None else 1)
    for error in errors:
        assert_exception_clean(error)
    assert_logs_clean(caplog)
    captured = capsys.readouterr()
    assert_no_secret(captured.out, captured.err)


def test_profile_sources_never_leak(monkeypatch, fake_sdk, caplog):
    monkeypatch.setenv("LLM_KEY", API_KEY)
    monkeypatch.setenv("GRAPH_PASSWORD", PASSWORD)
    monkeypatch.setenv("DBX_TOKEN", PAT)
    monkeypatch.setenv("SP_SECRET", CLIENT_SECRET)
    sources = [
        (TargetKind.OPENAI_COMPATIBLE, ApiKeySource(kind="api_key", env="LLM_KEY")),
        (TargetKind.NEO4J, BasicSource(kind="basic", user="neo4j", password_env="GRAPH_PASSWORD")),
        (TargetKind.DATABRICKS_MODEL, PatSource(kind="pat", token_env="DBX_TOKEN")),
        (
            TargetKind.DATABRICKS_MODEL,
            OAuthM2MSource(kind="oauth_m2m", client_id="sp-1", client_secret_env="SP_SECRET"),
        ),
    ]
    with caplog.at_level(logging.DEBUG):
        for target, source in sources:
            credential = resolve_credential(target, "t", source, workspace_url=HOST)
            logger.debug("%s %r", credential, credential)
            assert_no_secret(str(credential), repr(credential))
    assert_logs_clean(caplog)


def test_unset_source_variable_never_leaks_others(monkeypatch):
    monkeypatch.setenv("OTHER_SECRET", PASSWORD)
    monkeypatch.delenv("GRAPH_PASSWORD", raising=False)
    source = BasicSource(kind="basic", user="neo4j", password_env="GRAPH_PASSWORD")
    with pytest.raises(CredentialSourceError) as caught:
        resolve_credential(TargetKind.NEO4J, "connections.graph", source)
    assert_exception_clean(caught.value)


# Part 2: models. The server echoes the key, as some proxies and servers do.

BASE_URL = "https://llm.example.net/v1"
ASK = [Message("user", "Which city?")]
ECHO = f"Incorrect API key provided: {API_KEY}."
NO_CHOICES = {"id": "c", "object": "chat.completion", "created": 1, "choices": [], "note": ECHO}

FAILURES = {
    "rejected": [error_reply(401, ECHO)],
    "rate_limited": [error_reply(429, ECHO), error_reply(429, ECHO)],
    "server_error": [error_reply(500, ECHO), error_reply(500, ECHO)],
    "bad_request": [error_reply(400, ECHO)],
    "not_json": [httpx2.Response(200, text=f"<html>proxy error for {API_KEY}</html>")],
    "no_choices": [httpx2.Response(200, json=NO_CHOICES)],
}


def openai_chat(server: FakeServer) -> OpenAICompatibleChatModel:
    settings = ChatModelSettings(
        provider="openai_compatible",
        base_url=BASE_URL,
        model="gpt-4o",
        log_content=True,
        retry=ModelRetrySettings(max_attempts=2),
    )
    return OpenAICompatibleChatModel(
        settings,
        credential=Credentials.api_key(Secret(API_KEY)),
        capabilities=capability_profile("openai_compatible", "gpt-4o"),
        http_client=server.client(),
        sleep=lambda seconds: None,
    )


@pytest.fixture
def openai_env(monkeypatch):
    """A planted admin key the SDK would read, and a variable that makes the client warn."""
    monkeypatch.setenv("OPENAI_ADMIN_KEY", CLIENT_SECRET)
    monkeypatch.setenv("OPENAI_ORG_ID", "org-test")


@pytest.mark.parametrize("failure", list(FAILURES))
def test_model_errors_never_leak(failure, openai_env, caplog):
    server = FakeServer(*FAILURES[failure])
    with caplog.at_level(logging.DEBUG):
        model = openai_chat(server)
        logger.debug("model %s %r", model, model)
        with pytest.raises(TenetRAGError) as caught:  # AuthError on 401, LLMError otherwise
            model.generate(ASK)
    assert server.last.headers["authorization"] == f"Bearer {API_KEY}"  # so a leak was possible
    assert all(CLIENT_SECRET not in str(request.headers) for request in server.requests)
    assert_exception_clean(caught.value)
    assert_logs_clean(caplog)
    assert_no_secret(str(model), repr(model))


def test_embedding_errors_never_leak(openai_env, caplog):
    server = FakeServer(error_reply(401, ECHO))
    settings = EmbeddingModelSettings(
        provider="openai_compatible", base_url=BASE_URL, model="bge-m3", dimensions=4
    )
    with caplog.at_level(logging.DEBUG):
        model = OpenAICompatibleEmbeddingModel(
            settings,
            credential=Credentials.api_key(Secret(API_KEY)),
            capabilities=capability_profile(
                "openai_compatible", "bge-m3", CapabilityOverrides(max_input_tokens=512)
            ),
            http_client=server.client(),
        )
        logger.debug("model %s %r", model, model)
        with pytest.raises(CredentialRejectedError) as caught:
            model.embed_documents(["Huế"])
    assert_exception_clean(caught.value)
    assert_logs_clean(caplog)
    assert_no_secret(str(model), repr(model))


@pytest.mark.parametrize("kind", [CredentialKind.PAT, CredentialKind.CLI_PROFILE])
def test_databricks_model_errors_never_leak(kind, fake_sdk, caplog):
    fake_sdk.tokens = [TOKEN, TOKEN]
    echo = f"Invalid token {PAT} or {TOKEN}."
    server = FakeServer(error_reply(401, echo), error_reply(401, echo))
    settings = ChatModelSettings(
        provider="databricks", model="databricks-gpt-5", workspace_url=HOST
    )
    with caplog.at_level(logging.DEBUG):
        model = DatabricksChatModel(
            settings,
            credential=build(kind, None, fake_sdk),
            capabilities=capability_profile("databricks", "databricks-gpt-5"),
            http_client=server.client(),
        )
        logger.debug("model %s %r", model, model)
        with pytest.raises(CredentialRejectedError) as caught:
            model.generate(ASK)
    assert_exception_clean(caught.value)
    assert_logs_clean(caplog)
    assert_no_secret(str(model), repr(model))


# Part 3: store connections. Server messages here echo the secret sent, which no
# real server is known to do, so masking is checked as well as dropping pgconn.

POSTGRES_FAILURES = {
    "rejected": ['FATAL:  password authentication failed for user "app" {secret}'] * 2,
    "missing database": ['FATAL:  database "graph" does not exist {secret}'],
    "unreachable": ["Connection refused {secret}"] * 2,
}


def postgres_credential(kind: CredentialKind) -> Credential:
    if kind is CredentialKind.BASIC:
        return Credentials.basic("app", Secret(PASSWORD))
    return Credentials.token_provider(
        "app", lambda: AccessToken(Secret(TOKEN), expires_at=None), identity="app"
    )


@pytest.mark.parametrize("failure", list(POSTGRES_FAILURES))
@pytest.mark.parametrize("kind", [CredentialKind.BASIC, CredentialKind.TOKEN_PROVIDER])
def test_postgres_errors_never_leak(kind, failure, monkeypatch, caplog):
    secret = PASSWORD if kind is CredentialKind.BASIC else TOKEN
    reasons = [reason.format(secret=secret) for reason in POSTGRES_FAILURES[failure]]
    server = FakePostgres(refusals=[refused("db.example.com", reason) for reason in reasons])
    install_fake_postgres(monkeypatch, server)
    settings = PostgresSettings(
        kind="postgres",
        host="db.example.com",
        database="graph",
        retry=StoreRetrySettings(max_attempts=2),
    )
    with caplog.at_level(logging.DEBUG), pytest.raises(TenetRAGError) as caught:
        PostgresConnection(
            settings, name="vectors", credential=postgres_credential(kind), sleep=lambda s: None
        )
    assert server.passwords[0] == secret  # so a leak was possible
    assert_exception_clean(caught.value)
    assert_logs_clean(caplog)


def test_postgres_connection_never_leaks(monkeypatch, caplog):
    install_fake_postgres(monkeypatch, FakePostgres())
    settings = PostgresSettings(kind="postgres", host="db.example.com", database="graph")
    with caplog.at_level(logging.DEBUG):
        connection = PostgresConnection(
            settings, name="vectors", credential=postgres_credential(CredentialKind.BASIC)
        )
        logger.debug("connection %s %r", connection, connection)
    assert_logs_clean(caplog)
    assert_no_secret(str(connection), repr(connection))


def test_neo4j_errors_never_leak(monkeypatch, caplog):
    fake = FakeNeo4j()
    monkeypatch.setattr(neo4j.GraphDatabase, "driver", fake)
    settings = Neo4jSettings(kind="neo4j", uri="neo4j+s://graph.example.com")
    with caplog.at_level(logging.DEBUG):
        connection = Neo4jConnection(
            settings, name="graph", credential=Credentials.basic("neo4j", Secret(PASSWORD))
        )
        logger.debug("connection %s %r", connection, connection)
        rejected = neo4j_error("Neo.ClientError.Security.Unauthorized", f"no {PASSWORD}")
        fake.last.failures = [rejected]
        with pytest.raises(CredentialRejectedError) as caught:
            connection.read(lambda tx: None)
    assert fake.last.auth.credentials == PASSWORD  # so a leak was possible
    assert_exception_clean(caught.value)
    assert_logs_clean(caplog)
    assert_no_secret(str(connection), repr(connection))
