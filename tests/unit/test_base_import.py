"""A bare `import tenetrag` loads no optional package (FR-004, SC-008)."""

import subprocess
import sys

OPTIONAL_PACKAGES = ("openai", "httpx2", "httpx", "databricks", "neo4j", "psycopg", "psycopg_pool")


def test_base_import_loads_no_optional_package():
    # A fresh interpreter, so modules the test session already imported do not count.
    result = subprocess.run(
        [sys.executable, "-c", "import sys, tenetrag; print('\\n'.join(sys.modules))"],
        capture_output=True,
        text=True,
        check=True,
    )
    top_level = {name.partition(".")[0] for name in result.stdout.splitlines()}
    assert "tenetrag" in top_level
    assert sorted(top_level.intersection(OPTIONAL_PACKAGES)) == []
