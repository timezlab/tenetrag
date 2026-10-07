"""Secret and AccessToken hide their values (data-model §4, contracts/auth.md)."""

from datetime import UTC, datetime

import pytest

from tenetrag import ConfigError, CredentialSourceError
from tenetrag.auth import AccessToken, Credentials, Secret
from tests.support.secrets import PLANTED, assert_exception_clean, assert_no_secret

VALUE = PLANTED[1]


def test_repr_and_str_are_masked():
    secret = Secret(VALUE)
    assert repr(secret) == "Secret('***')"
    assert str(secret) == "Secret('***')"
    assert_no_secret(f"{secret}", f"{secret!r}")


def test_reveal_returns_the_value():
    assert Secret(VALUE).reveal() == VALUE


def test_equality_is_not_by_value():
    assert Secret(VALUE) != Secret(VALUE)


def test_empty_value_rejected():
    with pytest.raises(CredentialSourceError):
        Secret("")


def test_from_env_reads_the_named_variable(monkeypatch):
    monkeypatch.setenv("APP_DB_PASSWORD", VALUE)
    assert Secret.from_env("APP_DB_PASSWORD").reveal() == VALUE


@pytest.mark.parametrize("value", [None, ""])
def test_from_env_unset_or_empty_names_the_variable(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("APP_DB_PASSWORD", raising=False)
    else:
        monkeypatch.setenv("APP_DB_PASSWORD", value)
    with pytest.raises(CredentialSourceError) as caught:
        Secret.from_env("APP_DB_PASSWORD")
    assert "APP_DB_PASSWORD" in str(caught.value)
    assert_exception_clean(caught.value)


def test_access_token_repr_is_masked():
    token = AccessToken(Secret(VALUE), expires_at=datetime(2026, 10, 6, 12, tzinfo=UTC))
    assert_no_secret(repr(token), str(token))


def test_access_token_expiry_must_carry_a_time_zone():
    # A naive time cannot be compared with the clock, so refresh would fail later.
    with pytest.raises(ConfigError, match="time zone"):
        AccessToken(Secret(VALUE), expires_at=datetime(2026, 10, 6, 12))


# Workspace URLs in code constructors


@pytest.mark.parametrize(
    "host",
    [
        "http://adb-1.example.net",
        "adb-1.example.net",
        f"https://token:{VALUE}@adb-1.example.net",
        "https://",
    ],
)
@pytest.mark.parametrize("build", [Credentials.pat, Credentials.obo], ids=["pat", "obo"])
def test_workspace_url_must_be_https_without_user(build, host):
    with pytest.raises(ConfigError) as caught:
        build(host, Secret("t"))
    assert_exception_clean(caught.value)


def test_workspace_url_keeps_the_port():
    credential = Credentials.pat("https://adb-1.example.net:8443/", Secret("t"))
    assert credential._host == "https://adb-1.example.net:8443"
    assert credential.identity == "pat:adb-1.example.net"
