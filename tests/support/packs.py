"""Paths and helpers for the pack tests (specs/002-packs-and-corpus)."""

from __future__ import annotations

import re
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PACK_FIXTURES = REPO_ROOT / "tests" / "fixtures" / "packs"
# Stays a draft until M4; tests stack it on the shipped packs (FR-019).
FINANCE_DRAFT = REPO_ROOT / "docs" / "product" / "packs" / "finance.yaml"

# One error line of a pack ConfigError (data-model §1). A path holds no
# space, so the first ": " after it ends the path, whatever the message holds.
_PROBLEM_LINE = re.compile(r"  - (?P<file>.+?): (?P<path>\S*): .* \[(?P<rule>[a-z0-9.-]+)\]")


def write_pack(directory: Path, name: str, text: str) -> Path:
    """Write `text`, dedented, as UTF-8 with LF line endings, and return the file's path."""
    path = directory / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(textwrap.dedent(text).encode("utf-8"))
    return path


def problem_lines(exc: BaseException) -> list[tuple[str, str, str]]:
    """The (file, path, rule) of each error line, in order.

    A line that does not parse fails the test, so that a changed format can
    never make an assertion pass on an empty list.
    """
    first, *lines = str(exc).split("\n")
    count = re.fullmatch(r"The pack stack has (\d+) problems?:", first)
    assert count, f"not a pack stack error: {first!r}"
    assert int(count[1]) == len(lines), f"{first!r} over {len(lines)} lines"
    parsed = []
    for line in lines:
        match = _PROBLEM_LINE.fullmatch(line)
        assert match, f"not a pack problem line: {line!r}"
        parsed.append((match["file"], match["path"], match["rule"]))
    return parsed
