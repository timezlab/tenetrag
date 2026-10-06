"""Load a profile from a YAML file, a YAML string or a dict (data-model §2, research R7).

Every failure is one `ConfigError` listing each problem with its dotted path.
Messages never repeat input values, since a mistaken profile may hold a secret:
YAML errors keep only the problem and its position, and the errors of pydantic
and the decoder are never chained, because their `str` or `repr` carry the input.
"""

from __future__ import annotations

import os
from collections.abc import Hashable, Mapping
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError
from pydantic_core import ErrorDetails

from tenetrag.config.profile import Profile
from tenetrag.protocols.errors import ConfigError

_SECRET_WORDS = ("password", "passwd", "secret", "token", "api_key", "apikey")
_CREDENTIAL_HINT = "credentials are passed in code, or named as a source under `credential`"
_MERGE_TAG = "tag:yaml.org,2002:merge"


def load_profile(path: str | os.PathLike[str]) -> Profile:
    """Load a profile file. An unreadable or non-UTF-8 file raises `ConfigError` naming it."""
    source = os.fspath(path)
    try:
        data = Path(path).read_bytes()
    except OSError as exc:
        reason = exc.strerror or type(exc).__name__
        raise ConfigError(
            f"Cannot read the profile file {source}: {reason}. "
            "Check that the path names a readable file."
        ) from exc
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        position = exc.start
    else:
        return _from_yaml(text, f" in {source}")
    raise ConfigError(
        f"The profile file {source} is not UTF-8 text (byte {position}). Save it as UTF-8."
    )


def profile_from_yaml(text: str) -> Profile:
    return _from_yaml(text, "")


def profile_from_dict(data: Mapping[str, Any]) -> Profile:
    if not isinstance(data, Mapping):
        raise ConfigError(
            f"A profile is a mapping of sections such as `models:`, not a {type(data).__name__}."
        )
    return _validate(data, "")


class _ProfileLoader(yaml.SafeLoader):
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


def _parse(text: str) -> tuple[object, list[str]]:
    # The constructor already reads the text, and can raise a ReaderError.
    loader = _ProfileLoader(text)
    try:
        return loader.get_single_data(), loader.duplicates
    finally:
        loader.dispose()


def _from_yaml(text: str, where: str) -> Profile:
    try:
        data, duplicates = _parse(text)
    except yaml.YAMLError as exc:
        problem = _yaml_problem(exc)
    else:
        return _checked(data, duplicates, where)
    raise ConfigError(
        f"Invalid YAML{where}: {problem}. Fix the syntax; tags that build "
        "Python objects are not allowed."
    )


def _checked(data: object, duplicates: list[str], where: str) -> Profile:
    if duplicates:
        listed = "\n".join(f"  - {duplicate}" for duplicate in duplicates)
        raise ConfigError(f"Duplicate keys{where}; write each key once per mapping:\n{listed}")
    if data is None:
        raise ConfigError(
            f"The profile{where} is empty. Write at least one section, such as `models:`."
        )
    if not isinstance(data, Mapping):
        raise ConfigError(
            f"The profile{where} must be a mapping of sections such as `models:`, "
            f"not a {type(data).__name__}."
        )
    return _validate(data, where)


def _yaml_problem(exc: yaml.YAMLError) -> str:
    # str(exc) quotes the offending line, which may hold a secret.
    if isinstance(exc, yaml.MarkedYAMLError):
        problem = exc.problem or exc.context or "not valid YAML"
        mark = exc.problem_mark or exc.context_mark
        if mark is None:
            return problem
        return f"{problem} at line {mark.line + 1}, column {mark.column + 1}"
    return "the text has characters YAML does not accept"


def _validate(data: Mapping[str, Any], where: str) -> Profile:
    try:
        return Profile.model_validate(data)
    except ValidationError as exc:
        problems = [_describe(error, data) for error in exc.errors(include_input=False)]
    # Raised here, outside the handler, so the ValidationError is neither the
    # cause nor the context: its str holds the input values.
    listed = "\n".join(f"  - {problem}" for problem in problems)
    raise ConfigError(
        f"Invalid profile{where}, {len(problems)} problem(s). Fix each field below:\n{listed}"
    )


def _describe(error: ErrorDetails, data: Mapping[str, Any]) -> str:
    path = _dotted_path(error["loc"], data)
    if error["type"] != "extra_forbidden":
        return f"{path}: {error['msg'].removeprefix('Value error, ')}"
    name = str(error["loc"][-1]).lower()
    if any(word in name for word in _SECRET_WORDS):
        return f"{path}: unknown field; {_CREDENTIAL_HINT}"
    return f"{path}: unknown field"


def _dotted_path(loc: tuple[int | str, ...], data: object) -> str:
    """Join an error location as written in the profile, without pydantic's own segments."""
    parts: list[str] = []
    node: object = data
    for segment in loc:
        if segment == "[key]":
            continue  # the problem is in the mapping key, already the last part
        if isinstance(node, Mapping) and segment not in node and segment == node.get("kind"):
            continue  # the tag of a discriminated union, not a key of the input
        if isinstance(segment, int):
            parts.append(f"[{segment}]")
        else:
            parts.append(f".{segment}" if parts else segment)
        node = _child(node, segment)
    return "".join(parts) or "(profile)"


def _child(node: object, segment: int | str) -> object:
    if isinstance(node, Mapping):
        return node.get(segment)
    if isinstance(node, list | tuple) and isinstance(segment, int) and 0 <= segment < len(node):
        return node[segment]
    return None
