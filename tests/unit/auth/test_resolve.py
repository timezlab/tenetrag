"""Resolving a credential: code, then the profile's named source, else fail (contracts/auth.md)."""

import pytest

from tenetrag import (
    ConfigError,
    CredentialMismatchError,
    CredentialSourceError,
    MissingCredentialError,
)
from tenetrag.auth import (
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
    CliProfileSource,
    NoneSource,
    OAuthM2MSource,
    OAuthU2MSource,
    PatSource,
    RuntimeSource,
)
from tests.support.secrets import PLANTED, assert_exception_clean

WORKSPACE = "https://adb-1.example.net"

# The accepted-kinds table of contracts/auth.md, written out independently.
ACCEPTED = {
    TargetKind.NEO4J: {"basic", "none"},
    TargetKind.POSTGRES: {"basic", "token_provider"},
    TargetKind.OPENAI_COMPATIBLE: {"api_key", "none"},
    TargetKind.DATABRICKS_MODEL: {
        "pat",
        "obo",
        "oauth_m2m",
        "oauth_u2m",
        "cli_profile",
        "runtime",
        "workspace_client",
    },
}


def credential_of(kind: CredentialKind) -> Credential:
    return Credential(kind=kind, identity=f"{kind.value}:test", source="code", refreshable=False)


# No credential


@pytest.mark.parametrize("target", list(TargetKind))
def test_missing_credential(target):
    with pytest.raises(MissingCredentialError) as caught:
        resolve_credential(target, "models.extraction", None)
    message = str(caught.value)
    assert "models.extraction" in message
    for kind in ACCEPTED[target]:
        assert kind in message


@pytest.mark.parametrize("target", list(TargetKind))
def test_ambient_vars_never_read(monkeypatch, target):
    for name, secret in zip(
        ("DATABRICKS_TOKEN", "OPENAI_API_KEY", "NEO4J_PASSWORD", "PGPASSWORD"),
        PLANTED,
        strict=False,
    ):
        monkeypatch.setenv(name, secret)
    monkeypatch.setenv("DATABRICKS_HOST", WORKSPACE)
    with pytest.raises(MissingCredentialError) as caught:
        resolve_credential(target, "connections.graph", None, workspace_url=WORKSPACE)
    assert_exception_clean(caught.value)


# Code and profile


def test_override_wins(monkeypatch):
    monkeypatch.delenv("GRAPH_PASSWORD", raising=False)
    override = Credentials.basic("app", Secret(PLANTED[1]))
    source = BasicSource(kind="basic", user="neo4j", password_env="GRAPH_PASSWORD")
    assert resolve_credential(TargetKind.NEO4J, "connections.graph", source, override) is override


def test_named_env_unset(monkeypatch):
    monkeypatch.delenv("GRAPH_PASSWORD", raising=False)
    source = BasicSource(kind="basic", user="neo4j", password_env="GRAPH_PASSWORD")
    with pytest.raises(CredentialSourceError) as caught:
        resolve_credential(TargetKind.NEO4J, "connections.graph", source)
    assert "GRAPH_PASSWORD" in str(caught.value)
    assert "connections.graph" in " ".join(getattr(caught.value, "__notes__", []))


def test_mismatch():
    obo = Credentials.obo(WORKSPACE, Secret(PLANTED[2]))
    with pytest.raises(CredentialMismatchError) as caught:
        resolve_credential(TargetKind.NEO4J, "connections.graph", None, obo)
    message = str(caught.value)
    assert "obo" in message
    assert "connections.graph" in message
    assert_exception_clean(caught.value)


@pytest.mark.parametrize("kind", list(CredentialKind))
@pytest.mark.parametrize("target", list(TargetKind))
def test_accepted_kinds(target, kind):
    credential = credential_of(kind)
    if kind.value in ACCEPTED[target]:
        assert resolve_credential(target, "t", None, credential) is credential
    else:
        with pytest.raises(CredentialMismatchError):
            resolve_credential(target, "t", None, credential)


def test_profile_kind_checked_before_reading_its_variable(monkeypatch):
    monkeypatch.delenv("DBX_TOKEN", raising=False)
    source = PatSource(kind="pat", token_env="DBX_TOKEN")
    with pytest.raises(CredentialMismatchError):
        resolve_credential(TargetKind.NEO4J, "connections.graph", source)


# Profile sources become credentials


def test_basic_from_profile(monkeypatch):
    monkeypatch.setenv("GRAPH_PASSWORD", PLANTED[1])
    source = BasicSource(kind="basic", user="neo4j", password_env="GRAPH_PASSWORD")
    credential = resolve_credential(TargetKind.NEO4J, "connections.graph", source)
    assert credential.kind is CredentialKind.BASIC
    assert credential.identity == "basic:neo4j"
    assert credential.source == "env:GRAPH_PASSWORD"
    assert not credential.refreshable


def test_api_key_from_profile(monkeypatch):
    monkeypatch.setenv("LLM_KEY", PLANTED[0])
    source = ApiKeySource(kind="api_key", env="LLM_KEY")
    credential = resolve_credential(TargetKind.OPENAI_COMPATIBLE, "models.answer", source)
    assert credential.kind is CredentialKind.API_KEY
    assert credential.source == "env:LLM_KEY"
    assert credential._token_source.token().value.reveal() == PLANTED[0]


def test_none_from_profile():
    credential = resolve_credential(TargetKind.NEO4J, "connections.graph", NoneSource(kind="none"))
    assert credential.kind is CredentialKind.NONE


def test_pat_from_profile(monkeypatch):
    monkeypatch.setenv("DBX_TOKEN", PLANTED[3])
    source = PatSource(kind="pat", token_env="DBX_TOKEN")
    credential = resolve_credential(
        TargetKind.DATABRICKS_MODEL, "models.extraction", source, workspace_url=WORKSPACE
    )
    assert credential.kind is CredentialKind.PAT
    assert credential.identity == "pat:adb-1.example.net"
    assert credential.source == "env:DBX_TOKEN"


@pytest.mark.parametrize(
    "source",
    [
        PatSource(kind="pat", token_env="DBX_TOKEN"),
        OAuthM2MSource(kind="oauth_m2m", client_id="sp-1", client_secret_env="SP_SECRET"),
        OAuthU2MSource(kind="oauth_u2m"),
    ],
    ids=["pat", "oauth_m2m", "oauth_u2m"],
)
def test_workspace_url_needed_for_host_kinds(monkeypatch, source):
    monkeypatch.setenv("DBX_TOKEN", PLANTED[3])
    monkeypatch.setenv("SP_SECRET", PLANTED[4])
    with pytest.raises(ConfigError, match="workspace_url") as caught:
        resolve_credential(TargetKind.DATABRICKS_MODEL, "models.extraction", source)
    assert "models.extraction" in str(caught.value)


def test_oauth_m2m_from_profile(monkeypatch, fake_sdk):
    monkeypatch.setenv("SP_SECRET", PLANTED[4])
    source = OAuthM2MSource(kind="oauth_m2m", client_id="sp-1", client_secret_env="SP_SECRET")
    credential = resolve_credential(
        TargetKind.DATABRICKS_MODEL, "models.extraction", source, workspace_url=WORKSPACE
    )
    assert credential.kind is CredentialKind.OAUTH_M2M
    assert credential.source == "env:SP_SECRET"
    assert fake_sdk.calls[-1]["client_secret"] == PLANTED[4]


def test_cli_profile_from_profile(fake_sdk):
    source = CliProfileSource(kind="cli_profile", name="dev", config_file="/etc/databricks/cfg")
    credential = resolve_credential(TargetKind.DATABRICKS_MODEL, "models.extraction", source)
    assert credential.identity == "cli_profile:dev"
    assert credential.source == "cli_profile:dev"
    assert fake_sdk.calls[-1]["config_file"] == "/etc/databricks/cfg"


def test_runtime_from_profile(monkeypatch, fake_sdk):
    monkeypatch.setenv("DATABRICKS_RUNTIME_VERSION", "17.3")
    source = RuntimeSource(kind="runtime")
    credential = resolve_credential(TargetKind.DATABRICKS_MODEL, "models.extraction", source)
    assert credential.kind is CredentialKind.RUNTIME
    assert credential.source == "runtime"
