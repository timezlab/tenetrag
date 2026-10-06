"""Unit tests never see ambient credential variables (root conftest fixture).

Meaningful only when run with such variables exported, e.g.
`OPENAI_API_KEY=x PGPASSWORD=y uv run pytest tests/unit/test_env_isolation.py`.
"""

import os

AMBIENT_PREFIXES = ("OPENAI_", "DATABRICKS_", "ARM_", "NEO4J_", "PG")
AMBIENT_NAMES = ("GOOGLE_CREDENTIALS",)


def test_ambient_credential_variables_are_cleared():
    leaked = sorted(
        name for name in os.environ if name.startswith(AMBIENT_PREFIXES) or name in AMBIENT_NAMES
    )
    assert leaked == []
