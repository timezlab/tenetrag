"""The problems a fact table can have, and the error that lists them (contracts/corpus.md)."""

from __future__ import annotations

from collections.abc import Iterable
from typing import NamedTuple


class Problem(NamedTuple):
    """One fact table problem: the file under `facts/`, the path inside it, and what is wrong."""

    file: str
    path: str
    message: str

    def __str__(self) -> str:
        return f"{self.file}: {self.path}: {self.message}"


class CorpusError(Exception):
    """The fact table has problems. One line per problem, in the order they were found."""

    def __init__(self, problems: Iterable[Problem]) -> None:
        self.problems = tuple(problems)
        super().__init__("\n".join(str(problem) for problem in self.problems))
