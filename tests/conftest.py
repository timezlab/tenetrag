"""Shared test setup. Markers and socket blocking are configured in pyproject.toml."""

import os

import pytest

# Credential variables, and the ones the official SDKs read on their own (ADR 0018).
AMBIENT_PREFIXES = ("OPENAI_", "DATABRICKS_", "ARM_", "NEO4J_", "PG")
AMBIENT_NAMES = frozenset({"GOOGLE_CREDENTIALS"})


@pytest.fixture(autouse=True)
def _clear_ambient_credentials(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Hide ambient credentials from every test, so none can pass by reading them.

    Live tests are the exception: they run against the real environment by design.
    """
    if request.node.get_closest_marker("live"):
        return
    for name in list(os.environ):
        if name.startswith(AMBIENT_PREFIXES) or name in AMBIENT_NAMES:
            monkeypatch.delenv(name)
