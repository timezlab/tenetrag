"""Unit-test fixtures shared across packages."""

import pytest

# urllib3, under the Databricks SDK, opens a local IPv6 socket when first imported
# to probe support. Importing it here, before pytest-socket blocks sockets for each
# test, keeps that probe from showing up as a blocked network call.
import urllib3  # noqa: F401 - imported for its side effect only

from tests.support.fake_databricks import FakeSdk


@pytest.fixture
def fake_sdk(monkeypatch: pytest.MonkeyPatch) -> FakeSdk:
    """Swap the Databricks SDK's `Config` for a fake, and reset the once-per-process warning."""
    from tenetrag.auth import databricks

    sdk = FakeSdk()
    monkeypatch.setattr(databricks, "_new_config", sdk)
    monkeypatch.setattr(databricks, "_env_warning_logged", False)
    return sdk
