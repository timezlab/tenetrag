"""Planted secrets never reach repr, str, logs or exception chains (SC-006).

Part 1 covers credentials; the model and store parts follow with US4 and US5.
"""

import logging
import sys

import pytest

from tenetrag import AuthError, CredentialRejectedError, CredentialSourceError
from tenetrag.auth import (
    AccessToken,
    Credential,
    CredentialKind,
    Credentials,
    Secret,
    TargetKind,
    resolve_credential,
)
from tenetrag.config import ApiKeySource, BasicSource, OAuthM2MSource, PatSource
from tests.support.fake_databricks import HOST, FakeConfig, FakeWorkspaceClient
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
