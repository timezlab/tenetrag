"""Paths and helpers for the pack tests (specs/002-packs-and-corpus)."""

from __future__ import annotations

import re
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PACK_FIXTURES = REPO_ROOT / "tests" / "fixtures" / "packs"
# Stays a draft until M4; tests stack it on the shipped packs (FR-019).
FINANCE_DRAFT = REPO_ROOT / "docs" / "product" / "packs" / "finance.yaml"
# The shipped identity case files as checked out, for tests that copy and edit them.
SHIPPED_DIR = REPO_ROOT / "src" / "tenetrag" / "packs" / "shipped"
FINANCE_CASES = REPO_ROOT / "tests" / "fixtures" / "identity" / "finance.cases.yaml"
# The 60 design cases of ADR 0016, recovered for feature 002 (research R0).
DESIGN_SNAPSHOT = (
    REPO_ROOT / "specs" / "002-packs-and-corpus" / "research" / "identity-design-cases.json"
)

# One error line of a pack ConfigError (data-model §1). A path holds no
# space, so the first ": " after it ends the path, whatever the message holds.
_PROBLEM_LINE = re.compile(
    r"  - (?P<file>.+?): (?P<path>\S*): (?P<message>.*) \[(?P<rule>[a-z0-9.-]+)\]"
)

# Every Tripwire built, so a test can show that a pack load built none.
BUILT: list[object] = []


class Tripwire:
    """A class a `!!python/object` tag in a test pack names."""

    def __new__(cls) -> Tripwire:
        instance = super().__new__(cls)
        BUILT.append(instance)
        return instance


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
    return [(match["file"], match["path"], match["rule"]) for match in _matches(exc)]


def problem_messages(exc: BaseException) -> list[str]:
    """The message of each error line, in order, parsed as strictly as `problem_lines`."""
    return [match["message"] for match in _matches(exc)]


def _matches(exc: BaseException) -> list[re.Match[str]]:
    first, *lines = str(exc).split("\n")
    count = re.fullmatch(r"The (?:pack stack|case file) has (\d+) problems?:", first)
    assert count, f"not a pack stack or case file error: {first!r}"
    assert int(count[1]) == len(lines), f"{first!r} over {len(lines)} lines"
    matches = []
    for line in lines:
        match = _PROBLEM_LINE.fullmatch(line)
        assert match, f"not a pack problem line: {line!r}"
        matches.append(match)
    return matches
