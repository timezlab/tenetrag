"""Phase markers for profile fields, and their resolution (data-model §8, ADR 0005).

Every leaf field carries exactly one marker in its `Annotated` metadata. A
section (a field holding models) may carry `IndexTime` or `QueryTime`, which
its `Content()` leaves inherit from the nearest such ancestor.
"""

from __future__ import annotations

import enum
import types
import typing
from collections.abc import Iterator, Mapping
from dataclasses import dataclass

from pydantic import BaseModel

from tenetrag.protocols.errors import ConfigError


class Phase(enum.Enum):
    INDEX = "index"
    QUERY = "query"


class Stage(enum.Enum):
    """Pipeline stages of engine brief §9. M0 has fields in `extract` and `embed` only."""

    CHUNK = "chunk"
    EXTRACT = "extract"
    RESOLVE = "resolve"
    EMBED = "embed"
    CLUSTER = "cluster"
    REPORTS = "reports"


@dataclass(frozen=True, slots=True)
class IndexTime:
    """Changes graph contents, in this stage."""

    stage: Stage


@dataclass(frozen=True, slots=True)
class QueryTime:
    """Changes only how the graph is read."""


@dataclass(frozen=True, slots=True)
class Content:
    """Takes the phase of the nearest ancestor section marked IndexTime or QueryTime."""


@dataclass(frozen=True, slots=True)
class Operational:
    """Always query-time, even inside an index-time section (FR-012)."""


Marker = IndexTime | QueryTime | Content | Operational
Resolved = tuple[Phase, Stage | None]

_QUERY: Resolved = (Phase.QUERY, None)


def field_phases(model: type[BaseModel] | None = None) -> dict[str, Resolved]:
    """Map each leaf's dotted path to its resolved phase; `*` stands for a mapping key.

    Defaults to `Profile`. Raises `ConfigError` naming every leaf with no marker or
    more than one, every `Content()` leaf with no phased ancestor, and every section
    marked `Content()` or `Operational()`.
    """
    if model is None:
        # Imported here because profile.py imports the markers from this module.
        from tenetrag.config.profile import Profile

        model = Profile
    phases: dict[str, Resolved] = {}
    problems: list[str] = []
    for path, resolved in _walk(model, "", None, problems):
        if phases.setdefault(path, resolved) != resolved:
            problems.append(f"{path}: union variants resolve to different phases")
    if problems:
        listed = "\n".join(f"  - {problem}" for problem in dict.fromkeys(problems))
        raise ConfigError(f"Profile fields with a bad phase marker:\n{listed}")
    return phases


def _walk(
    model: type[BaseModel], prefix: str, inherited: Resolved | None, problems: list[str]
) -> Iterator[tuple[str, Resolved]]:
    for name, field in model.model_fields.items():
        path = f"{prefix}{name}"
        markers = [item for item in field.metadata if isinstance(item, Marker)]
        sections = list(_sections(field.annotation, path))
        if len(markers) > 1:
            problems.append(f"{path}: more than one phase marker")
            continue
        marker = markers[0] if markers else None
        if sections:
            if isinstance(marker, Content | Operational):
                problems.append(
                    f"{path}: a section takes IndexTime or QueryTime; "
                    "Content() and Operational() go on leaf fields"
                )
                continue
            section_phase = _resolve(marker, inherited) if marker else inherited
            for section_path, section_model in sections:
                yield from _walk(section_model, f"{section_path}.", section_phase, problems)
            continue
        if marker is None:
            problems.append(
                f"{path}: no phase marker; add IndexTime(stage), QueryTime(), "
                "Content() or Operational()"
            )
        elif isinstance(marker, Content) and inherited is None:
            problems.append(f"{path}: Content() needs an ancestor marked IndexTime or QueryTime")
        else:
            yield path, _resolve(marker, inherited)


def _resolve(marker: Marker, inherited: Resolved | None) -> Resolved:
    if isinstance(marker, IndexTime):
        return (Phase.INDEX, marker.stage)
    if isinstance(marker, Content) and inherited is not None:
        return inherited
    return _QUERY


def _sections(annotation: object, path: str) -> Iterator[tuple[str, type[BaseModel]]]:
    """The models a field holds, directly, in a union, or as mapping values."""
    origin = typing.get_origin(annotation)
    if origin is typing.Annotated:
        yield from _sections(typing.get_args(annotation)[0], path)
    elif origin is typing.Union or origin is types.UnionType:
        for member in typing.get_args(annotation):
            yield from _sections(member, path)
    elif origin is not None and _is_mapping(origin):
        yield from _sections(typing.get_args(annotation)[1], f"{path}.*")
    elif isinstance(annotation, type) and issubclass(annotation, BaseModel):
        yield path, annotation


def _is_mapping(origin: object) -> bool:
    return isinstance(origin, type) and issubclass(origin, Mapping)
