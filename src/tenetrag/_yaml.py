"""The safe YAML loader shared by profiles and packs.

PyYAML only (contracts/config.md §3, research R1). Moved unchanged from
`tenetrag.config.loading` so that `config` and `packs`, which are siblings,
read YAML the same way: no tag that builds an object, every repeated key
reported, and no error text that repeats the input.

Each duplicate also carries the dotted path of its mapping, which the pack
loader reports (specs/002-packs-and-corpus T019); the profile loader prints
only the key and both lines, as before.
"""

from __future__ import annotations

from collections.abc import Hashable
from dataclasses import dataclass
from typing import Any

import yaml

_MERGE_TAG = "tag:yaml.org,2002:merge"


@dataclass(frozen=True, slots=True)
class DuplicateKey:
    """A key its mapping repeats: the mapping's dotted path, the key and both lines.

    `path` is "" for the top-level mapping, `entities.Vendor` for a nested
    one and `qs[1]` for one inside a list.
    """

    path: str
    key: Hashable
    line: int
    first_line: int

    def __str__(self) -> str:
        return f"{self.key!r} at line {self.line} (first at line {self.first_line})"


class DuplicateKeyLoader(yaml.SafeLoader):
    """PyYAML's safe loader, recording duplicate keys instead of keeping the last one."""

    def __init__(self, stream: str) -> None:
        super().__init__(stream)
        self.duplicates: list[DuplicateKey] = []
        self._mapping_paths: dict[int, str] = {}

    def construct_document(self, node: yaml.Node) -> object:
        self._mapping_paths = _mapping_paths(node)
        return super().construct_document(node)

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
                path = self._mapping_paths.get(id(node), "")
                self.duplicates.append(DuplicateKey(path, key, line, first_lines[key]))
            else:
                first_lines[key] = line
        return super().construct_mapping(node, deep=deep)


def _mapping_paths(root: yaml.Node) -> dict[int, str]:
    """The dotted path of each mapping node under `root`, by node id."""
    paths: dict[int, str] = {}
    pending: list[tuple[yaml.Node, str]] = [(root, "")]
    visited: set[int] = set()
    while pending:
        node, path = pending.pop()
        # An alias shares its anchor's node, and an anchor can hold itself.
        if id(node) in visited:
            continue
        visited.add(id(node))
        if isinstance(node, yaml.MappingNode):
            paths[id(node)] = path
            for key_node, value_node in node.value:
                key = key_node.value if isinstance(key_node, yaml.ScalarNode) else "?"
                pending.append((value_node, f"{path}.{key}" if path else str(key)))
        elif isinstance(node, yaml.SequenceNode):
            pending.extend((item, f"{path}[{index}]") for index, item in enumerate(node.value))
    return paths


def parse_yaml(text: str) -> tuple[object, list[DuplicateKey]]:
    """Return the data and the duplicate keys, in document order. Raises `yaml.YAMLError`."""
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
