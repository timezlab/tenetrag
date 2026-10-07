"""Databricks credentials through the SDK, with no SDK network (research R11, ADR 0018).

The `fake_sdk` fixture (tests/unit/conftest.py) replaces the SDK's `Config`.
"""

import logging
import subprocess
import sys

import pytest

from tenetrag import CredentialRejectedError, CredentialSourceError, MissingExtraError
from tenetrag.auth import CredentialKind, Credentials, Secret
from tests.support.fake_databricks import HOST, FakeConfig, FakeWorkspaceClient
from tests.support.secrets import PLANTED, assert_exception_clean, assert_logs_clean


class Stream:
    def __init__(self, is_terminal: bool) -> None:
        self.is_terminal = is_terminal

    def isatty(self) -> bool:
        return self.is_terminal


def terminal(monkeypatch, stdin: bool, stdout: bool) -> None:
    monkeypatch.setattr(sys, "stdin", Stream(stdin))
    monkeypatch.setattr(sys, "stdout", Stream(stdout))


def token_of(credential) -> str:
    return credential._token_source.token().value.reveal()


# What each kind asks the SDK for


def test_oauth_m2m_fixes_the_auth_type(fake_sdk):
    credential = Credentials.oauth_m2m(HOST, "sp-1", Secret(PLANTED[4]))
    assert fake_sdk.calls == [
        {"host": HOST, "client_id": "sp-1", "client_secret": PLANTED[4], "auth_type": "oauth-m2m"}
    ]
    assert credential.kind is CredentialKind.OAUTH_M2M
    assert credential.identity == "oauth_m2m:sp-1@adb-1.example.net"
    assert credential.refreshable
    assert credential._host == HOST
    assert token_of(credential) == "tok-1"


def test_cli_profile_fixes_the_auth_type(fake_sdk):
    credential = Credentials.cli_profile("dev")
    assert fake_sdk.calls == [{"profile": "dev", "auth_type": "databricks-cli"}]
    assert credential.identity == "cli_profile:dev"
    assert credential.source == "cli_profile:dev"
    assert credential.refreshable


def test_cli_profile_passes_the_config_file(fake_sdk):
    Credentials.cli_profile("dev", config_file="/etc/databricks/cfg")
    assert fake_sdk.calls[-1]["config_file"] == "/etc/databricks/cfg"


def test_runtime_outside_databricks(fake_sdk):
    with pytest.raises(CredentialSourceError) as caught:
        Credentials.runtime()
    assert "DATABRICKS_RUNTIME_VERSION" in str(caught.value)
    assert fake_sdk.calls == []


def test_runtime_inside_databricks(monkeypatch, fake_sdk):
    monkeypatch.setenv("DATABRICKS_RUNTIME_VERSION", "17.3")
    credential = Credentials.runtime()
    assert fake_sdk.calls == [{"auth_type": "runtime"}]
    assert credential.kind is CredentialKind.RUNTIME
    assert credential.source == "runtime"
    assert credential.refreshable


@pytest.mark.parametrize(("stdin", "stdout"), [(False, False), (True, False), (False, True)])
def test_u2m_needs_terminal(monkeypatch, fake_sdk, stdin, stdout):
    terminal(monkeypatch, stdin, stdout)
    with pytest.raises(CredentialSourceError) as caught:
        Credentials.oauth_u2m(HOST)
    assert "cli_profile" in str(caught.value)
    assert fake_sdk.calls == []


def test_u2m_with_no_stdin_needs_terminal(monkeypatch, fake_sdk):
    monkeypatch.setattr(sys, "stdin", None)
    monkeypatch.setattr(sys, "stdout", Stream(True))
    with pytest.raises(CredentialSourceError):
        Credentials.oauth_u2m(HOST)


def test_u2m_in_a_terminal(monkeypatch, fake_sdk):
    terminal(monkeypatch, True, True)
    credential = Credentials.oauth_u2m(HOST)
    assert fake_sdk.calls == [{"host": HOST, "auth_type": "external-browser"}]
    assert credential.identity == "oauth_u2m:adb-1.example.net"


def test_workspace_client_uses_the_client_headers(fake_sdk):
    client = FakeWorkspaceClient(FakeConfig("ws-token"))
    credential = Credentials.workspace_client(client)
    assert token_of(credential) == "ws-token"
    assert credential.kind is CredentialKind.WORKSPACE_CLIENT
    assert credential.identity == "workspace_client:adb-1.example.net"
    assert fake_sdk.calls == []


def test_non_bearer_header_rejected(fake_sdk):
    client = FakeWorkspaceClient(FakeConfig("unused"))
    client.config.header = "Basic dXNlcjpwYXNz"
    credential = Credentials.workspace_client(client)
    with pytest.raises(CredentialSourceError, match="bearer"):
        credential._token_source.token()


# SDK failures


def test_missing_cli_profile(fake_sdk):
    fake_sdk.error = ValueError("resolve: ~/.databrickscfg has no dev profile configured")
    with pytest.raises(CredentialSourceError) as caught:
        Credentials.cli_profile("dev")
    message = str(caught.value)
    assert "cli_profile:dev" in message
    assert "databricks auth login --profile dev" in message
    assert isinstance(caught.value.__cause__, ValueError)


def test_expired_cli_login_during_use(fake_sdk):
    credential = Credentials.cli_profile("dev")
    fake_sdk.configs[-1].error = ValueError("databricks-cli auth: refresh token is invalid")
    with pytest.raises(CredentialSourceError) as caught:
        credential._token_source.token()
    assert "databricks auth login --profile dev" in str(caught.value)


# When `databricks auth token` fails, as for an expired login, the SDK raises
# IOError("cannot get access token: ...") at build and at refresh, not ValueError.
def test_failed_cli_command_at_build(fake_sdk):
    fake_sdk.error = OSError("cannot get access token: refresh token is invalid")
    with pytest.raises(CredentialSourceError) as caught:
        Credentials.cli_profile("dev")
    assert "databricks auth login --profile dev" in str(caught.value)
    assert isinstance(caught.value.__cause__, OSError)


def test_failed_cli_command_during_use(fake_sdk):
    credential = Credentials.cli_profile("dev")
    fake_sdk.configs[-1].error = OSError("cannot get access token: refresh token is invalid")
    with pytest.raises(CredentialSourceError) as caught:
        credential._token_source.token()
    assert "databricks auth login --profile dev" in str(caught.value)


def test_reauth_builds_a_new_config_once(fake_sdk):
    credential = Credentials.oauth_m2m(HOST, "sp-1", Secret(PLANTED[4]))
    tokens = credential._token_source
    first = tokens.token()
    tokens.invalidate(first)
    second = tokens.token()
    assert second.value.reveal() == "tok-2"
    assert len(fake_sdk.calls) == 2
    tokens.invalidate(first)  # a late report of the same rejection changes nothing
    assert len(fake_sdk.calls) == 2
    with pytest.raises(CredentialRejectedError) as caught:
        tokens.invalidate(second)
    assert "oauth_m2m:sp-1@adb-1.example.net" in str(caught.value)
    assert_exception_clean(caught.value)


def test_workspace_client_reauth_retries_once(fake_sdk):
    client = FakeWorkspaceClient(FakeConfig("ws-token"))
    tokens = Credentials.workspace_client(client)._token_source
    first = tokens.token()
    client.config.token = "ws-token-2"  # the SDK refreshed it meanwhile
    tokens.invalidate(first)
    second = tokens.token()
    assert second.value.reveal() == "ws-token-2"
    with pytest.raises(CredentialRejectedError):
        tokens.invalidate(second)


def test_missing_sdk_raises_missing_extra(monkeypatch):
    for name in ("databricks", "databricks.sdk", "databricks.sdk.core", "databricks.sdk.config"):
        monkeypatch.setitem(sys.modules, name, None)
    with pytest.raises(MissingExtraError) as caught:
        Credentials.cli_profile("dev")
    assert caught.value.extra == "databricks"


def test_missing_extra_is_not_reported_as_a_credential_problem(monkeypatch, fake_sdk):
    # MissingExtraError is also a ValueError, which the SDK error mapping catches.
    def no_sdk(**settings):
        raise MissingExtraError("databricks")

    monkeypatch.setattr("tenetrag.auth.databricks._new_config", no_sdk)
    with pytest.raises(MissingExtraError):
        Credentials.cli_profile("dev")


def test_pat_and_obo_never_import_databricks_sdk():
    # A fresh interpreter, so modules the test session already imported do not count.
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys\n"
            "from tenetrag.auth import Credentials, Secret\n"
            "Credentials.pat('https://adb-1.example.net', Secret('t'))._token_source.token()\n"
            "Credentials.obo('https://adb-1.example.net', Secret('t'))._token_source.token()\n"
            "print('databricks' in {name.partition('.')[0] for name in sys.modules})\n",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "False"


# The SDK's own environment reads (ADR 0018)


def test_databricks_env_warning(monkeypatch, caplog, fake_sdk):
    monkeypatch.setenv("DATABRICKS_HOST", PLANTED[3])
    with caplog.at_level(logging.WARNING, logger="tenetrag"):
        Credentials.cli_profile("dev")
        Credentials.cli_profile("prod")
    warnings = [record for record in caplog.records if record.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "DATABRICKS_HOST" in warnings[0].getMessage()
    assert_logs_clean(caplog)


def test_databricks_env_warning_names_every_variable_read(monkeypatch, caplog, fake_sdk):
    monkeypatch.setenv("DATABRICKS_CLIENT_ID", "sp-other")
    monkeypatch.setenv("ARM_TENANT_ID", "tenant")
    monkeypatch.setenv("GOOGLE_CREDENTIALS", PLANTED[0])
    monkeypatch.setenv("DATABRICKS_RUNTIME_VERSION", "17.3")  # a runtime marker the SDK never reads
    with caplog.at_level(logging.WARNING, logger="tenetrag"):
        Credentials.runtime()
    message = caplog.records[0].getMessage()
    for name in ("DATABRICKS_CLIENT_ID", "ARM_TENANT_ID", "GOOGLE_CREDENTIALS"):
        assert name in message
    assert "DATABRICKS_RUNTIME_VERSION" not in message
    assert_logs_clean(caplog)


def test_no_warning_without_databricks_env(caplog, fake_sdk):
    with caplog.at_level(logging.WARNING, logger="tenetrag"):
        Credentials.cli_profile("dev")
    assert caplog.records == []


def test_pat_logs_no_env_warning(monkeypatch, caplog, fake_sdk):
    # pat needs no SDK, so the SDK's environment reads do not apply.
    monkeypatch.setenv("DATABRICKS_HOST", HOST)
    with caplog.at_level(logging.WARNING, logger="tenetrag"):
        Credentials.pat(HOST, Secret(PLANTED[3]))
    assert caplog.records == []
