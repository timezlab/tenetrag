"""The local stack in deploy/ (docs/guides/local-stack.md).

Behaviours:
1. Neo4j and Postgres run the images the integration tests pin
   (test_images_match_the_tested_pins).
2. Every published port binds to 127.0.0.1 (test_ports_bind_to_loopback).
3. No compose file holds a password: each password setting reads a required
   variable or a secret file (test_passwords_come_from_variables_or_secret_files).
4. Neo4j sends no usage reports (test_neo4j_usage_report_is_off).
"""

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from tests.integration.conftest import NEO4J_IMAGE, PGVECTOR_IMAGES

ROOT = Path(__file__).parents[2]
DEPLOY = ROOT / "deploy"
FILES = ["compose.yaml", "compose.dev.yaml", "compose.prod.yaml"]

pytestmark = pytest.mark.skipif(
    not (ROOT / ".git").exists(), reason="deploy/ ships in git, not in the sdist"
)


def services(name: str) -> dict[str, Any]:
    return yaml.safe_load((DEPLOY / name).read_text())["services"]


def test_images_match_the_tested_pins():
    base = services("compose.yaml")
    assert base["neo4j"]["image"] == NEO4J_IMAGE
    assert base["postgres"]["image"] == PGVECTOR_IMAGES["pg17"]


@pytest.mark.parametrize("name", FILES)
def test_ports_bind_to_loopback(name):
    ports = [port for service in services(name).values() for port in service.get("ports", [])]
    assert all(str(port).startswith("127.0.0.1:") for port in ports), ports


@pytest.mark.parametrize("name", FILES)
def test_passwords_come_from_variables_or_secret_files(name):
    for service in services(name).values():
        for key, value in service.get("environment", {}).items():
            if key.endswith("_FILE"):
                assert value.startswith("/run/secrets/"), (key, value)
            elif "AUTH" in key or "PASSWORD" in key:
                assert re.search(r"\$\{\w+:\?[^}]+\}", value), (key, value)


def test_neo4j_usage_report_is_off():
    environment = services("compose.yaml")["neo4j"]["environment"]
    assert environment["NEO4J_dbms_usage__report_enabled"] == "false"
