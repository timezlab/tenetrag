"""A stand-in for the Databricks SDK's `Config`, so auth tests make no SDK network call."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

HOST = "https://adb-1.example.net"


class FakeConfig:
    """Answers `authenticate()` the way the SDK does: one Authorization header."""

    def __init__(self, token: str, host: str | None = HOST) -> None:
        self.host = host
        self.token = token
        self.header: str | None = None  # replaces the whole header value when set
        self.error: Exception | None = None  # raised by authenticate(), as an expired login

    def authenticate(self) -> dict[str, str]:
        if self.error is not None:
            raise self.error
        return {"Authorization": self.header or f"Bearer {self.token}"}


class FakeWorkspaceClient:
    def __init__(self, config: FakeConfig) -> None:
        self.config = config


@dataclass
class FakeSdk:
    """Replaces `tenetrag.auth.databricks._new_config`, recording each call's settings.

    The n-th config hands out `tokens[n]`. `error` makes every call raise, as the
    SDK does for a missing CLI profile.
    """

    tokens: list[str] = field(default_factory=lambda: ["tok-1", "tok-2", "tok-3", "tok-4"])
    error: Exception | None = None
    calls: list[dict[str, Any]] = field(default_factory=list)
    configs: list[FakeConfig] = field(default_factory=list)

    def __call__(self, **settings: Any) -> FakeConfig:
        self.calls.append(settings)
        if self.error is not None:
            raise self.error
        config = FakeConfig(self.tokens[len(self.configs)], host=settings.get("host", HOST))
        self.configs.append(config)
        return config
