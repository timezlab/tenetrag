"""Stage hashes: the one module of ADR 0005 that computes them (data-model §8).

Each stage's hash covers that stage's index-time leaves only, after defaults
are filled in, so changing a query-time field changes no hash and changing the
embedding model changes only the `embed` hash.
"""

from __future__ import annotations

import enum
import hashlib
import json
import unicodedata
from collections.abc import Iterator, Mapping
from typing import TypeAlias

from pydantic import BaseModel

from tenetrag.config.phases import Phase, Resolved, Stage, field_phases
from tenetrag.config.profile import Profile

_Json: TypeAlias = bool | int | float | str | list["_Json"] | dict[str, "_Json"] | None

# Bump with any change to the canonical form below, so old and new hashes never collide.
_FORMAT = 1


def stage_hashes(profile: Profile) -> dict[Stage, str]:
    """`{stage: "sha256:<hex>"}` for every stage; a stage with no fields hashes an empty set."""
    phases = field_phases(type(profile))
    fields: dict[Stage, dict[str, _Json]] = {stage: {} for stage in Stage}
    for pattern, path, value in _leaves(profile, phases, "", ""):
        phase, stage = phases[pattern]
        if phase is Phase.INDEX and stage is not None:
            fields[stage][path] = _canonical(value)
    return {stage: _digest(stage, stage_fields) for stage, stage_fields in fields.items()}


def _leaves(
    model: BaseModel, phases: Mapping[str, Resolved], pattern_prefix: str, path_prefix: str
) -> Iterator[tuple[str, str, object]]:
    """Yield (pattern path, concrete path, value) for each leaf the profile holds."""
    for name in type(model).model_fields:
        value = getattr(model, name)
        pattern = f"{pattern_prefix}{name}"
        path = f"{path_prefix}{name}"
        if pattern in phases:
            yield pattern, path, value
        elif isinstance(value, BaseModel):
            yield from _leaves(value, phases, f"{pattern}.", f"{path}.")
        elif isinstance(value, Mapping):
            for key, item in value.items():
                yield from _leaves(item, phases, f"{pattern}.*.", f"{path}.{key}.")
        elif value is not None:
            # field_phases names every leaf, so only an absent section gets here.
            raise TypeError(f"{path} is neither a leaf nor a section")


def _canonical(value: object) -> _Json:
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, enum.Enum):
        return _canonical(value.value)
    if value is None or isinstance(value, bool | int | float):
        return value
    if isinstance(value, list | tuple):
        return [_canonical(item) for item in value]
    if isinstance(value, Mapping):
        return {
            unicodedata.normalize("NFC", str(key)): _canonical(item) for key, item in value.items()
        }
    raise TypeError(f"no canonical form for a {type(value).__name__} value")


def _digest(stage: Stage, fields: dict[str, _Json]) -> str:
    document = {"format": _FORMAT, "stage": stage.value, "fields": fields}
    text = json.dumps(
        document, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()
