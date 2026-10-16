"""The compiled extraction schema (data-model §6, research R6).

One fixed shape whatever the stack: type, attribute and role names grow
enums, never properties, so the schema keeps 52 properties and fits
providers that cap the count (Databricks: 64). Strict structured output
needs every property required and no other allowed, and `anyOf` is
forbidden, so a value the text does not state is `""` rather than null.
A part whose names would be empty is left out: an empty enum means
nothing, and `maxItems: 0` is not known to work on every provider.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from tenetrag.packs.stack import Attribute, PackStack
from tenetrag.protocols.errors import ConfigError

_KINDS = ("entities", "relations", "events", "facts")
_KIND_LABELS = {"entities": "entity", "relations": "relation", "events": "event", "facts": "fact"}
_PART_LABELS = {"former_names": "former name", "attributes": "attribute", "roles": "role"}


@dataclass(frozen=True, slots=True)
class CompiledSchema:
    """A compiled schema and the sorted types it covers.

    `property_count` is the sum of every `properties` map's size, as M0's
    `check_schema` counts it.
    """

    types: tuple[str, ...]
    property_count: int
    _json: str = field(repr=False)

    @property
    def schema(self) -> dict[str, Any]:
        """The JSON Schema, a fresh copy in plain dicts and lists on each read.

        `check_schema` refuses a read-only mapping, and a copy leaves this
        object unchanged whatever the caller does with it.
        """
        schema: dict[str, Any] = json.loads(self._json)
        return schema

    def to_json(self) -> str:
        """Sorted keys, compact separators and text as written: the same stack, the same bytes."""
        return self._json


def compile_schema(
    stack: PackStack,
    types: Sequence[str] | None = None,
    *,
    max_properties: int = 64,
) -> CompiledSchema:
    """The extraction schema for `types`, or for every type with `extract: true`.

    Raises `ConfigError` for a name the stack lacks, a type with
    `extract: false`, a selection with no type, or a schema with more than
    `max_properties` properties.
    """
    selected = _selected(stack, types)
    builder = _Builder()
    root: dict[str, Any] = {}
    if selected["entities"]:
        root["entities"] = _array(_entity(builder, selected["entities"]))
    if selected["relations"]:
        root["relations"] = _array(_relation(builder, selected["relations"]))
    if selected["events"]:
        root["events"] = _array(_event(builder, "events", selected["events"]))
    if selected["facts"]:
        root["facts"] = _array(_event(builder, "facts", selected["facts"]))
    schema = builder.object((), root)
    count = sum(size for _, size in builder.parts)
    if count > max_properties:
        by_size = sorted(builder.parts, key=lambda part: part[1], reverse=True)
        listed = ", ".join(f"{label} ({size})" for label, size in by_size)
        raise ConfigError(
            f"The schema compiled from `{stack.name}` has {count} properties, more than "
            f"max_properties={max_properties}. Its parts by size: {listed}. Compile one kind "
            "at a time with `types`, which leaves the other kinds' parts out, or raise "
            "max_properties if the provider accepts more."
        )
    names = sorted(name for kind in _KINDS for name in selected[kind])
    text = json.dumps(schema, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return CompiledSchema(tuple(names), count, text)


def _selected(stack: PackStack, types: Sequence[str] | None) -> dict[str, Mapping[str, Any]]:
    """The selected types of each kind, by name, in stack order; `_enum` sorts the names."""
    every: dict[str, Mapping[str, Any]] = {kind: getattr(stack, kind) for kind in _KINDS}
    if types is None:
        wanted = {name for kind in _KINDS for name, item in every[kind].items() if item.extract}
    else:
        wanted = set(types)
        known = {name for kind in _KINDS for name in every[kind]}
        unknown = sorted(wanted - known)
        skipped = sorted(
            name
            for kind in _KINDS
            for name, item in every[kind].items()
            if name in wanted and not item.extract
        )
        problems = []
        if unknown:
            problems.append(
                f"the stack has no type {_names(unknown)}; use the names its packs define"
            )
        if skipped:
            problems.append(
                f"`extract: false` on {_names(skipped)}; leave such types out, or set "
                "`extract: true` in a child pack"
            )
        if problems:
            raise ConfigError(f"Cannot compile `{stack.name}`: {'; and '.join(problems)}.")
    if not wanted:
        raise ConfigError(
            f"Cannot compile `{stack.name}`: the selection names no type. Name at least one, "
            "or pass types=None for every type with `extract: true`."
        )
    return {
        kind: {name: item for name, item in every[kind].items() if name in wanted}
        for kind in _KINDS
    }


def _names(names: Iterable[str]) -> str:
    return ", ".join(f"`{name}`" for name in names)


class _Builder:
    """Builds object schemas and records each part's label and property count."""

    def __init__(self) -> None:
        self.parts: list[tuple[str, int]] = []

    def object(self, path: tuple[str, ...], properties: dict[str, Any]) -> dict[str, Any]:
        self.parts.append((_label(path), len(properties)))
        return {
            "type": "object",
            "additionalProperties": False,
            "required": sorted(properties),
            "properties": properties,
        }

    def attributes(self, path: tuple[str, ...], names: set[str]) -> dict[str, Any]:
        return _array(self.object(path, {"name": _enum(names), "value": _text(), "quote": _text()}))

    def roles(self, path: tuple[str, ...], names: set[str]) -> dict[str, Any]:
        return _array(self.object(path, {"role": _enum(names), "ref": _text()}))


def _entity(builder: _Builder, entities: Mapping[str, Any]) -> dict[str, Any]:
    former_name = builder.object(("entities", "former_names"), {"name": _text(), "quote": _text()})
    properties: dict[str, Any] = {
        "id": _text(),
        "type": _enum(entities),
        "surface": _text(),
        "is_name": {"type": "boolean"},
        "name": _text(),
        "translation": _text(),
        "ref": _text(),
        "scope": _text(),
        "former_names": _array(former_name),
    }
    names = _attribute_names(entity.attributes for entity in entities.values())
    if names:
        properties["attributes"] = builder.attributes(("entities", "attributes"), names)
    return builder.object(("entities",), properties)


def _relation(builder: _Builder, relations: Mapping[str, Any]) -> dict[str, Any]:
    properties: dict[str, Any] = {
        "type": _enum(relations),
        "from": _text(),
        "to": _text(),
        "valid_from": _text(),
        "valid_to": _text(),
        "quote": _text(),
    }
    names = _attribute_names(relation.attributes for relation in relations.values())
    # A relation's main value is the attribute named `value` (research R6).
    if any(relation.value is not None for relation in relations.values()):
        names.add("value")
    if names:
        properties["attributes"] = builder.attributes(("relations", "attributes"), names)
    return builder.object(("relations",), properties)


def _event(builder: _Builder, kind: str, types: Mapping[str, Any]) -> dict[str, Any]:
    """An event or fact item; only events carry an `id`, since a role may point to an event."""
    properties: dict[str, Any] = {
        "type": _enum(types),
        "valid_from": _text(),
        "valid_to": _text(),
        "quote": _text(),
    }
    if kind == "events":
        properties["id"] = _text()
    roles = {role for item in types.values() for role in item.roles}
    if roles:
        properties["roles"] = builder.roles((kind, "roles"), roles)
    names = _attribute_names(item.attributes for item in types.values())
    if names:
        properties["attributes"] = builder.attributes((kind, "attributes"), names)
    return builder.object((kind,), properties)


def _attribute_names(attributes: Iterable[Mapping[str, Attribute]]) -> set[str]:
    return {name for mapping in attributes for name in mapping}


def _label(path: tuple[str, ...]) -> str:
    if not path:
        return "root"
    kind, *rest = path
    return " ".join([_KIND_LABELS[kind], *(_PART_LABELS[part] for part in rest)])


def _array(items: dict[str, Any]) -> dict[str, Any]:
    return {"type": "array", "items": items}


def _enum(names: Iterable[str]) -> dict[str, Any]:
    return {"type": "string", "enum": sorted(names)}


def _text() -> dict[str, Any]:
    return {"type": "string"}
