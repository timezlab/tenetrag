"""The database images the Docker suites pin, and the Docker check they share.

`tests/integration/conftest.py` and the contract suite's Docker parameters
both start containers from these digests, and `tests/unit/test_local_stack.py`
checks that `deploy/compose.yaml` uses the same ones.
"""

import pytest

# Multi-arch index digests, resolved 2026-10-06 from Docker Hub. The neo4j tag
# was re-pushed that morning, so this pins the previous build (2026-10-02, per
# docker-library/repo-info) to respect the 24-hour rule of the dependency gate.
NEO4J_IMAGE = (
    "neo4j:2026.09.0-community"
    "@sha256:0dfcadbd51e1d2e5a0cf86d054a0bb537a4bce212796d967cbd88445aaf3fbf3"
)
PGVECTOR_IMAGES = {
    "pg16": (
        "pgvector/pgvector:0.8.7-pg16"
        "@sha256:7b822b0aac60967beb1ea5e576b8602c94c300a157d187f385ae3e0da199b90a"
    ),
    "pg17": (
        "pgvector/pgvector:0.8.7-pg17"
        "@sha256:ac08538c6f8b9904c33c8224c5e5706dbe760aca29db1d096972b4052c22a75d"
    ),
}


def require_docker() -> None:
    """Skip the calling test or fixture when no Docker daemon answers."""
    import docker  # dev-only, installed with testcontainers

    try:
        docker.from_env().ping()
    except docker.errors.DockerException:
        pytest.skip("Docker not available")
