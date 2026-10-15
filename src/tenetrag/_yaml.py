"""The safe YAML loader shared by profiles and packs.

PyYAML only (contracts/config.md §3, research R1). Moved unchanged from
`tenetrag.config.loading` so that `config` and `packs`, which are siblings,
read YAML the same way: no tag that builds an object, every repeated key
reported, and no error text that repeats the input.
"""

from __future__ import annotations

from collections.abc import Hashable
from typing import Any

import yaml

_MERGE_TAG = "tag:yaml.org,2002:merge"


class DuplicateKeyLoader(yaml.SafeLoader):
    """PyYAML's safe loader, recording duplicate keys instead of keeping the last one."""

    def __init__(self, stream: str) -> None:
        super().__init__(stream)
        self.duplicates: list[str] = []

    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict[Hashable, Any]:
        first_lines: dict[Any, int] = {}
        for key_node, _ in node.value:
            # A merge key (`<<`) may be overridden by design; only explicit keys count.
            if key_node.tag == _MERGE_TAG:
                continue
            key = self.construct_object(key_node, deep=deep)
            line = key_node.start_mark.line + 1
            try:
                seen = key in first_lines
            except TypeError:
                continue  # unhashable; the base class reports it
            if seen:
                self.duplicates.append(f"{key!r} at line {line} (first at line {first_lines[key]})")
            else:
                first_lines[key] = line
        return super().construct_mapping(node, deep=deep)


def parse_yaml(text: str) -> tuple[object, list[str]]:
    """Return the data and the duplicate-key descriptions. Raises `yaml.YAMLError`."""
    # The constructor already reads the text, and can raise a ReaderError.
    loader = DuplicateKeyLoader(text)
    try:
        return loader.get_single_data(), loader.duplicates
    finally:
        loader.dispose()


def yaml_problem(exc: yaml.YAMLError) -> str:
    """The problem and its position, never the offending text."""
    # str(exc) quotes the offending line, which may hold a secret.
    if isinstance(exc, yaml.MarkedYAMLError):
        problem = exc.problem or exc.context or "not valid YAML"
        mark = exc.problem_mark or exc.context_mark
        if mark is None:
            return problem
        return f"{problem} at line {mark.line + 1}, column {mark.column + 1}"
    return "the text has characters YAML does not accept"
