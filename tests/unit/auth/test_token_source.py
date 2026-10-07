"""Bearer tokens: cached, refreshed for the same identity, one reauth (data-model §4)."""

import threading
import time
from datetime import UTC, datetime, timedelta

import pytest

from tenetrag import CredentialRejectedError
from tenetrag.auth import AccessToken, Credentials, Secret
from tenetrag.auth.credentials import _TokenSource
from tests.support.secrets import assert_exception_clean

START = datetime(2026, 10, 6, 12, tzinfo=UTC)
HOST = "https://adb-1.example.net"


class Clock:
    def __init__(self) -> None:
        self.now = START

    def __call__(self) -> datetime:
        return self.now


class Mint:
    """Hands out tok-1, tok-2, ... each valid for `lifetime` from the clock's time."""

    def __init__(self, clock: Clock | None = None, lifetime: timedelta | None = None) -> None:
        self.calls = 0
        self.clock = clock
        self.lifetime = lifetime

    def __call__(self) -> AccessToken:
        self.calls += 1
        expires_at = None
        if self.clock is not None and self.lifetime is not None:
            expires_at = self.clock() + self.lifetime
        return AccessToken(Secret(f"tok-{self.calls}"), expires_at=expires_at)


def source(mint, *, refreshable=True, clock=None) -> _TokenSource:
    return _TokenSource(mint, identity="test:app", refreshable=refreshable, now=clock or Clock())


def value(token: AccessToken) -> str:
    return token.value.reveal()


def test_token_is_cached():
    mint = Mint()
    tokens = source(mint)
    assert tokens.token() is tokens.token()
    assert mint.calls == 1


def test_refresh_same_identity():
    mint = Mint()
    credential = Credentials.token_provider("app", mint, identity="lakebase:app")
    tokens = credential._token_source
    first = tokens.token()
    tokens.invalidate(first)
    second = tokens.token()
    assert (value(first), value(second)) == ("tok-1", "tok-2")
    assert mint.calls == 2
    assert credential.identity == "token_provider:lakebase:app"
    assert credential.refreshable
    with pytest.raises(CredentialRejectedError) as caught:
        tokens.invalidate(second)
    assert "token_provider:lakebase:app" in str(caught.value)


def test_invalidate_then_rejection_raises():
    tokens = source(Mint())
    tokens.invalidate(tokens.token())
    with pytest.raises(CredentialRejectedError) as caught:
        tokens.invalidate(tokens.token())
    assert "test:app" in str(caught.value)
    assert_exception_clean(caught.value)


def test_refresh_happens_once_across_threads():
    calls = 0

    def slow_mint() -> AccessToken:
        nonlocal calls
        calls += 1
        time.sleep(0.05)  # keeps the refresh open while the other threads arrive
        return AccessToken(Secret(f"tok-{calls}"), expires_at=None)

    tokens = source(slow_mint)
    start = threading.Barrier(8)
    seen: list[str] = []

    def ask() -> None:
        start.wait()
        seen.append(value(tokens.token()))

    threads = [threading.Thread(target=ask) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert calls == 1
    assert seen == ["tok-1"] * 8


def test_rejection_reported_twice_refreshes_once():
    # Two requests failed on the same token; the second report must not count
    # as a rejection of the token the first report fetched.
    mint = Mint()
    tokens = source(mint)
    first = tokens.token()
    tokens.invalidate(first)
    second = tokens.token()
    tokens.invalidate(first)
    assert tokens.token() is second
    assert mint.calls == 2


@pytest.mark.parametrize(
    "build",
    [
        lambda: Credentials.obo(HOST, Secret("obo-token")),
        lambda: Credentials.pat(HOST, Secret("pat-token")),
        lambda: Credentials.api_key(Secret("api-key")),
    ],
    ids=["obo", "pat", "api_key"],
)
def test_obo_not_refreshed(build):
    credential = build()
    assert not credential.refreshable
    tokens = credential._token_source
    with pytest.raises(CredentialRejectedError) as caught:
        tokens.invalidate(tokens.token())
    assert credential.identity in str(caught.value)


def test_token_near_expiry_is_refreshed_before_use():
    clock = Clock()
    mint = Mint(clock, lifetime=timedelta(seconds=120))
    tokens = source(mint, clock=clock)
    assert value(tokens.token()) == "tok-1"
    clock.now = START + timedelta(seconds=59)  # 61 s left: still used
    assert value(tokens.token()) == "tok-1"
    clock.now = START + timedelta(seconds=61)  # 59 s left: inside the 60 s margin
    assert value(tokens.token()) == "tok-2"


def test_token_without_expiry_is_kept_until_rejected():
    clock = Clock()
    mint = Mint()
    tokens = source(mint, clock=clock)
    tokens.token()
    clock.now = START + timedelta(days=30)
    tokens.token()
    assert mint.calls == 1


def test_scheduled_refresh_restores_the_reauth():
    # A token that expires on schedule is not a rejection, so the next rejection
    # gets its own refresh.
    clock = Clock()
    mint = Mint(clock, lifetime=timedelta(minutes=10))
    tokens = source(mint, clock=clock)
    tokens.invalidate(tokens.token())
    tokens.token()  # tok-2, fetched after the rejection
    clock.now = START + timedelta(minutes=10)
    third = tokens.token()
    assert value(third) == "tok-3"
    tokens.invalidate(third)
    assert value(tokens.token()) == "tok-4"


def test_late_rejection_of_a_replaced_token_is_ignored():
    # A request that used the token fetched after a rejection fails after that
    # token was already replaced on schedule: the fresh token stands.
    clock = Clock()
    mint = Mint(clock, lifetime=timedelta(minutes=10))
    tokens = source(mint, clock=clock)
    tokens.invalidate(tokens.token())
    second = tokens.token()
    clock.now = START + timedelta(minutes=10)
    tokens.token()
    tokens.invalidate(second)
    assert value(tokens.token()) == "tok-3"
