"""Docker integration tests: network allowed, skipped without Docker, images pinned by digest."""

from pathlib import Path

import pytest

from tests.support.containers import NEO4J_IMAGE, PGVECTOR_IMAGES, require_docker

_INTEGRATION_DIR = Path(__file__).parent


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    # This hook sees the whole session, so mark only the tests under this directory.
    for item in items:
        if item.path.is_relative_to(_INTEGRATION_DIR):
            item.add_marker(pytest.mark.enable_socket)
            item.add_marker(pytest.mark.docker)


@pytest.fixture(scope="session", autouse=True)
def _require_docker() -> None:
    require_docker()


@pytest.fixture(scope="session")
def neo4j_image() -> str:
    return NEO4J_IMAGE


@pytest.fixture(scope="session", params=sorted(PGVECTOR_IMAGES))
def pgvector_image(request: pytest.FixtureRequest) -> str:
    return PGVECTOR_IMAGES[request.param]
