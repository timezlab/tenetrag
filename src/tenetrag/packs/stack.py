"""The merged, read-only pack stack that `load_pack` returns (data-model §3).

Standard library and `tenetrag.packs.problems` only. Every value is
resolved: defaults are filled in and `is_a` parents' roles, attributes and
time are copied into each child. Mappings are `MappingProxyType` and
sequences tuples, so no caller can change a stack another caller shares.
A list whose order means nothing is sorted; one whose order matters keeps
it (data-model §3, "Order").
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Literal, NamedTuple

from tenetrag.packs.problems import PackProblem

Time = Literal["none", "point", "interval"]
Compare = Literal["text", "code", "digits", "lower", "upper", "date"]
Unique = Literal["scope", "global", "self_scoped"]
Inherit = Literal["none", "document"]


def _no_mapping() -> Mapping[str, tuple[str, ...]]:
    return MappingProxyType({})


class Mode(Enum):
    """How the text lint treats instruction-like text: fail, or warn."""

    STRICT = "strict"
    DISCOVERY = "discovery"


class NameRule(Enum):
    """What a shared name proves for an entity type (ADR 0016)."""

    KEY = "key"
    EVIDENCE = "evidence"
    VERSIONED = "versioned"
    NONE = "none"


class ShippedPack(NamedTuple):
    name: str
    version: int


@dataclass(frozen=True, slots=True)
class PackInfo:
    """One pack of the stack. `source` is "shipped" or the file's absolute path."""

    name: str
    version: int
    source: str


@dataclass(frozen=True, slots=True)
class Scope:
    """An entity type's scope. An empty `when` means the scope always applies."""

    role: str
    to: tuple[str, ...]
    inherit: Inherit = "none"
    when: Mapping[str, tuple[str, ...]] = field(default_factory=_no_mapping)


@dataclass(frozen=True, slots=True)
class Key:
    """One identity key, its attributes as written; `during` holds two date attributes."""

    attributes: tuple[str, ...]
    during: tuple[str, str] | None = None


@dataclass(frozen=True, slots=True)
class Attribute:
    name: str
    range: str
    multivalued: bool = False
    unit: str | None = None
    description: str | None = None
    compare: Compare = "text"
    unique: Unique = "scope"


@dataclass(frozen=True, slots=True)
class EntityType:
    """An entity type. `required` holds the `required` list and the attributes marked required."""

    name: str
    description: str
    examples: tuple[str, ...]
    aliases: tuple[str, ...]
    attributes: Mapping[str, Attribute]
    scope: Scope | None
    identity: tuple[Key, ...]
    vetoes: tuple[str, ...]
    names: NameRule
    corroborate: tuple[str, ...]
    version_start: tuple[str, ...]
    document_link: tuple[str, ...]
    required: tuple[str, ...]
    extract: bool
    agent_visible: bool
    exact_mappings: tuple[str, ...]
    deprecated: bool
    renamed_from: str | None


@dataclass(frozen=True, slots=True)
class RelationType:
    """A relation type. `where` maps "from" or "to" to attribute → allowed enum values."""

    name: str
    description: str | None
    from_types: tuple[str, ...]
    to_types: tuple[str, ...]
    where: Mapping[str, Mapping[str, tuple[str, ...]]]
    time: Time
    attributes: Mapping[str, Attribute]
    value: str | None
    cardinality: tuple[str, ...] | None
    required: tuple[str, ...]
    extract: bool
    exact_mappings: tuple[str, ...]
    deprecated: bool
    renamed_from: str | None


@dataclass(frozen=True, slots=True)
class EventType:
    """An event type. Each identity entry's names are sorted, since they are a set."""

    name: str
    description: str
    examples: tuple[str, ...]
    aliases: tuple[str, ...]
    is_a: str | None
    roles: Mapping[str, tuple[str, ...]]
    attributes: Mapping[str, Attribute]
    time: Time
    identity: tuple[Key, ...]
    required: tuple[str, ...]
    extract: bool
    agent_visible: bool
    exact_mappings: tuple[str, ...]
    deprecated: bool
    renamed_from: str | None


@dataclass(frozen=True, slots=True)
class FactType:
    name: str
    description: str
    examples: tuple[str, ...]
    aliases: tuple[str, ...]
    roles: Mapping[str, tuple[str, ...]]
    attributes: Mapping[str, Attribute]
    time: Time
    required: tuple[str, ...]
    version_key: tuple[str, ...]
    extract: bool
    agent_visible: bool
    exact_mappings: tuple[str, ...]
    deprecated: bool
    renamed_from: str | None


@dataclass(frozen=True, slots=True)
class Retrieval:
    """Query-time hints: changing them never asks for a re-index."""

    hub_penalty: tuple[str, ...] = ()
    max_hops: int | None = None
    context_relations: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class GlossaryEntry:
    name: str
    type: str
    aliases: tuple[str, ...] = ()
    note: str | None = None


@dataclass(frozen=True, slots=True)
class CompetencyQuestion:
    """A question the stack must answer. `needs` keeps the order written."""

    id: str
    text: str
    needs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PackStack:
    """The merged stack. `origins` maps each element path to the pack that added it."""

    name: str
    version: int
    mode: Mode
    packs: tuple[PackInfo, ...]
    entities: Mapping[str, EntityType]
    relations: Mapping[str, RelationType]
    events: Mapping[str, EventType]
    facts: Mapping[str, FactType]
    enums: Mapping[str, tuple[str, ...]]
    not_entities: tuple[str, ...]
    retrieval: Retrieval
    glossary: tuple[GlossaryEntry, ...]
    competency_questions: tuple[CompetencyQuestion, ...]
    origins: Mapping[str, str]
    warnings: tuple[PackProblem, ...] = ()
