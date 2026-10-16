"""Identity cases: load a case file and check it against its stack (data-model §8, research R11).

Contract: specs/002-packs-and-corpus/contracts/identity-cases.md. A case
file is read like a pack file (safe YAML, repeated keys, NFC, unknown fields
refused) and gives the same file.* rule ids. `check_cases` runs no
resolver: it checks that every name a case uses exists in the case's own
stack, that outcomes fit, and that the cases cover each shipped pack's
identity elements (FR-031, FR-032). Feature 004 runs the cases through the
resolver.
"""

from __future__ import annotations

import datetime
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from importlib.resources.abc import Traversable
from pathlib import Path
from types import MappingProxyType
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict, Field, ValidationError
from pydantic_core import PydanticCustomError

from tenetrag.packs.format import (
    LOWER_NAME,
    RECURSIVE_ALIAS,
    RELATION_NAME,
    LowerName,
    RecursiveDataError,
    RelationName,
    Text,
    TypeName,
    name_checker,
    normalized,
    validation_problems,
)
from tenetrag.packs.loading import FileKind, load_pack, read_mapping, shipped_directory
from tenetrag.packs.problems import PackProblem, config_error
from tenetrag.packs.stack import Attribute, EntityType, PackStack

# The rule ids check_cases gives (data-model §8). Each has a small case file
# in tests/unit/packs/test_cases.py, and a test checks both ways.
CASE_RULES: frozenset[str] = frozenset(
    {
        "case.duplicate-id",
        "case.unknown-entity",
        "case.unknown-type",
        "case.unknown-attribute",
        "case.unknown-relation",
        "case.unknown-element",
        "case.outcome",
        "case.blocked-by",
        "case.coverage-type",
        "case.coverage-element",
    }
)

ENTITY_ID = re.compile(r"[a-z][a-z0-9]*(?:[.-][a-z0-9]+)*")
CASE_ID = re.compile(r"[A-Z]+-[0-9]+")
_ISO_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_SUFFIX = ".cases.yaml"

_CASE_FILE = FileKind(
    empty="the file is empty; write identity cases in it",
    not_mapping="a case file is a mapping of fields such as `pack:`, `entities:` and `cases:`",
)


def _iso(value: object) -> object:
    """A date YAML read unquoted, as the text a quoted one gives."""
    return value.isoformat() if isinstance(value, datetime.date) else value


def _date(value: str) -> str:
    try:
        datetime.date.fromisoformat(value)
    except ValueError:
        raise PydanticCustomError("bad_date", "not an ISO date") from None
    if _ISO_DATE.fullmatch(value) is None:
        raise PydanticCustomError("bad_date", "not an ISO date")
    return value


EntityId = Annotated[str, AfterValidator(name_checker(ENTITY_ID, "alpha.tc"))]
CaseId = Annotated[str, AfterValidator(name_checker(CASE_ID, "PER-5"))]
IsoDate = Annotated[str, BeforeValidator(_iso), AfterValidator(_date)]
# An attribute's value is text; a date written unquoted reads as one.
Value = Annotated[str, BeforeValidator(_iso), Field(min_length=1)]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class Quoted(_Model):
    """An attribute value with the quote that states it, as the compiled schema extracts it."""

    value: Value
    quote: Text


class CaseRelation(_Model):
    type: RelationName
    to: EntityId
    attributes: dict[LowerName, Quoted] = Field(default_factory=dict)
    valid_from: IsoDate | None = None
    valid_to: IsoDate | None = None


class FormerName(_Model):
    name: Text
    quote: Text


class _Described(_Model):
    """What an existing entity and a mention both state: the fields of data-model §8."""

    type: TypeName
    name: Text
    scope: EntityId | None = None
    attributes: dict[LowerName, Quoted] = Field(default_factory=dict)
    relations: list[CaseRelation] = Field(default_factory=list)
    former_names: list[FormerName] = Field(default_factory=list)


class CaseEntity(_Described):
    """An entity already in the graph before a case's mention arrives."""

    aliases: list[Text] = Field(default_factory=list)


class CitingDocument(_Model):
    issuer: EntityId | None = None
    date: IsoDate
    language: Literal["vi", "en"]


class Mention(_Described):
    """The new mention. `scope_source: document` means its scope came from the document."""

    scope_source: Literal["text", "document"] = "text"
    translation: Text | None = None
    document: CitingDocument


class Outcome(_Model):
    """What the resolver must do; which ids each kind names is checked by check_cases."""

    kind: Literal["merge", "new", "same_as", "confirm"]
    into: EntityId | None = None
    links: list[EntityId] = Field(default_factory=list)
    candidates: list[EntityId] = Field(default_factory=list)
    right: EntityId | None = None


class Case(_Model):
    id: CaseId
    origin: Literal["design", "added"]
    expect: Literal["merge", "apart"]
    title: Text
    existing: list[EntityId] = Field(min_length=1)
    mention: Mention
    outcome: Outcome
    # Elements such as `veto:code`; their grammar is checked against the stack.
    depends_on: list[Text] = Field(min_length=1)
    blocked_by: LowerName | None = None


class _CaseFile(_Model):
    pack: Text
    entities: dict[EntityId, CaseEntity]
    cases: list[Case] = Field(min_length=1)


@dataclass(frozen=True, slots=True)
class CaseSet:
    """One loaded case file. `source` is a shipped file's name, else the file's absolute path."""

    source: str
    stack: PackStack
    entities: Mapping[str, CaseEntity]
    cases: tuple[Case, ...]


def load_cases(path: str | os.PathLike[str]) -> CaseSet:
    """Read one case file and load the stack its `pack` names.

    A relative `pack` path resolves against the case file. Raises
    `ConfigError` for a shape problem, with the file.* rule ids of a pack
    file, or for a stack that fails to load.
    """
    resolved = Path(path).resolve()
    return _load(resolved, str(resolved), resolved.parent)


def shipped_cases() -> tuple[CaseSet, ...]:
    """The identity case files shipped beside the packs, sorted by name."""
    entries = [entry for entry in shipped_directory().iterdir() if entry.name.endswith(_SUFFIX)]
    return tuple(_load(entry, entry.name, None) for entry in sorted(entries, key=_entry_name))


def _entry_name(entry: Traversable) -> str:
    return entry.name


def _load(source: Path | Traversable, label: str, base_dir: Path | None) -> CaseSet:
    data, problems = read_mapping(source, label, _CASE_FILE)
    case_file = None
    if data is not None:
        try:
            nfc_data = normalized(data)
        except RecursiveDataError:
            problems.append(PackProblem("file.yaml", label, "", RECURSIVE_ALIAS, "error"))
        else:
            try:
                case_file = _CaseFile.model_validate(nfc_data)
            except ValidationError as exc:
                problems.extend(validation_problems(exc, label, "", nfc_data))
    if problems or case_file is None:
        raise config_error(problems, subject="The case file")
    stack = load_pack(case_file.pack, base_dir=base_dir)
    return CaseSet(label, stack, MappingProxyType(case_file.entities), tuple(case_file.cases))


def check_cases(*case_sets: CaseSet) -> tuple[PackProblem, ...]:
    """Every problem of the case sets, in order; empty when everything holds.

    Each set is checked against its own stack: entities first, then cases
    in file order, then FR-031 coverage, sorted by path, when the set's top
    pack is shipped. An id two cases share is reported at the later one.
    Pure: no I/O, no resolver.
    """
    problems: list[PackProblem] = []
    first_source: dict[str, str] = {}
    for case_set in case_sets:
        checker = _Checker(case_set)
        for entity_id, entity in case_set.entities.items():
            checker.described(entity, f"entities.{entity_id}")
        for case in case_set.cases:
            if case.id in first_source:
                other = first_source[case.id]
                where = "this file" if other == case_set.source else other
                checker.problem(
                    "case.duplicate-id",
                    f"cases[{case.id}]",
                    f"`{case.id}` is also a case in {where}; give each case its own id",
                )
            else:
                first_source[case.id] = case_set.source
            checker.case(case)
        problems += checker.problems
        problems += sorted(_coverage(case_set), key=lambda problem: problem.path)
    return tuple(problems)


# The fields each outcome kind names, and the `expect` it fits (data-model §8, ADR 0023).
_OUTCOME_FIELDS: dict[str, frozenset[str]] = {
    "merge": frozenset({"into"}),
    "confirm": frozenset({"candidates", "right"}),
    "new": frozenset(),
    "same_as": frozenset({"links"}),
}
_OUTCOME_SHAPES = {
    "merge": "a `merge` outcome names `into` and nothing else",
    "confirm": "a `confirm` outcome names `candidates` and `right` and nothing else",
    "new": "a `new` outcome names no entity",
    "same_as": "a `same_as` outcome names `links` and nothing else",
}
_OUTCOME_FITS = {
    "merge": ("merge",),
    "confirm": ("merge",),
    "new": ("apart",),
    "same_as": ("merge", "apart"),
}

_KEY_ARGUMENT = re.compile(r"[a-z][a-z0-9_]*(\+[a-z][a-z0-9_]*)*")
_ELEMENT_ARGUMENTS = {
    "key": _KEY_ARGUMENT,
    "veto": LOWER_NAME,
    "names": LOWER_NAME,
    "unique": LOWER_NAME,
    "corroborate": RELATION_NAME,
}
_BAD_ELEMENT = (
    "not an element; write `scope`, `key:<a>+<b>`, `veto:<a>`, `names:<rule>`, "
    "`unique:<a>` or `corroborate:<RELATION>`"
)


class _Checker:
    """The consistency checks of one case set against its own stack (FR-032)."""

    def __init__(self, case_set: CaseSet) -> None:
        self.case_set = case_set
        self.stack = case_set.stack
        self.problems: list[PackProblem] = []

    def problem(self, rule: str, path: str, message: str) -> None:
        self.problems.append(PackProblem(rule, self.case_set.source, path, message, "error"))

    def entity(self, entity_id: str, path: str) -> CaseEntity | None:
        entity = self.case_set.entities.get(entity_id)
        if entity is None:
            self.problem(
                "case.unknown-entity",
                path,
                f"no entity `{entity_id}` under `entities`; define it, or use an id defined there",
            )
        return entity

    def described(self, described: _Described, path: str) -> None:
        entity_type = self.stack.entities.get(described.type)
        if entity_type is None:
            self.problem(
                "case.unknown-type",
                f"{path}.type",
                f"no entity type `{described.type}` under `{self.stack.name}`; "
                "use one of the stack's types",
            )
            return
        if described.scope is not None:
            self.scope(entity_type, described.scope, f"{path}.scope")
        for name, quoted in described.attributes.items():
            self.attribute(
                entity_type.name,
                entity_type.attributes,
                name,
                quoted.value,
                f"{path}.attributes.{name}",
            )
        for index, relation in enumerate(described.relations):
            self.relation(entity_type, relation, f"{path}.relations[{index}]")

    def scope(self, entity_type: EntityType, scope_id: str, path: str) -> None:
        scope = entity_type.scope
        if scope is None:
            self.problem(
                "case.unknown-element",
                path,
                f"`{entity_type.name}` has no scope under `{self.stack.name}`; leave `scope` out",
            )
            return
        target = self.entity(scope_id, path)
        if target is not None and target.type not in scope.to:
            self.problem(
                "case.unknown-element",
                path,
                f"`{entity_type.name}` is scoped by {_either(scope.to)} under "
                f"`{self.stack.name}`; use an entity of that type",
            )

    def attribute(
        self, owner: str, attributes: Mapping[str, Attribute], name: str, value: str, path: str
    ) -> None:
        attribute = attributes.get(name)
        if attribute is None:
            self.problem(
                "case.unknown-attribute",
                path,
                f"`{owner}` has no attribute `{name}` under `{self.stack.name}`",
            )
            return
        values = self.stack.enums.get(attribute.range)
        if values is not None and value not in values:
            self.problem(
                "case.unknown-attribute",
                path,
                f"the value is not in `{attribute.range}` under `{self.stack.name}`; "
                f"use one of {', '.join(values)}",
            )

    def relation(self, entity_type: EntityType, relation: CaseRelation, path: str) -> None:
        relation_type = self.stack.relations.get(relation.type)
        if relation_type is None:
            self.problem(
                "case.unknown-relation",
                f"{path}.type",
                f"no relation `{relation.type}` under `{self.stack.name}`; "
                "use one of the stack's relations",
            )
            return
        target = self.entity(relation.to, f"{path}.to")
        if target is not None and target.type in self.stack.entities:
            fits = (
                entity_type.name in relation_type.from_types
                and target.type in relation_type.to_types
            )
            if not fits:
                self.problem(
                    "case.unknown-relation",
                    path,
                    f"`{relation.type}` runs from {_either(relation_type.from_types)} to "
                    f"{_either(relation_type.to_types)} under `{self.stack.name}`, "
                    f"not from `{entity_type.name}` to `{target.type}`",
                )
        for name, quoted in relation.attributes.items():
            self.attribute(
                relation.type,
                relation_type.attributes,
                name,
                quoted.value,
                f"{path}.attributes.{name}",
            )

    def case(self, case: Case) -> None:
        path = f"cases[{case.id}]"
        for index, entity_id in enumerate(case.existing):
            self.entity(entity_id, f"{path}.existing[{index}]")
        mention = case.mention
        self.described(mention, f"{path}.mention")
        if mention.document.issuer is not None:
            self.entity(mention.document.issuer, f"{path}.mention.document.issuer")
        self.outcome(case, path)
        entity_type = self.stack.entities.get(mention.type)
        if entity_type is not None:
            for index, element in enumerate(case.depends_on):
                self.element(entity_type, element, f"{path}.depends_on[{index}]")
        self.blocked_by(case, path)

    def outcome(self, case: Case, path: str) -> None:
        outcome = case.outcome
        named = {
            name
            for name in ("into", "links", "candidates", "right")
            if getattr(outcome, name) not in (None, [])
        }
        if named != _OUTCOME_FIELDS[outcome.kind]:
            self.problem(
                "case.outcome",
                f"{path}.outcome",
                f"{_OUTCOME_SHAPES[outcome.kind]}; fix the fields",
            )
            return
        fits = _OUTCOME_FITS[outcome.kind]
        if case.expect not in fits:
            allowed = " or ".join(f"`expect: {expect}`" for expect in fits)
            self.problem(
                "case.outcome",
                f"{path}.outcome.kind",
                f"a `{outcome.kind}` outcome goes with {allowed}; change the kind or `expect`",
            )
            return
        ids = [(f"{path}.outcome.into", outcome.into)] if outcome.into is not None else []
        ids += [(f"{path}.outcome.links[{i}]", link) for i, link in enumerate(outcome.links)]
        ids += [(f"{path}.outcome.candidates[{i}]", c) for i, c in enumerate(outcome.candidates)]
        for id_path, entity_id in ids:
            if self.entity(entity_id, id_path) is not None and entity_id not in case.existing:
                self.problem(
                    "case.outcome",
                    id_path,
                    f"`{entity_id}` is not in the case's `existing`; name an existing entity",
                )
        if outcome.right is not None and outcome.right not in outcome.candidates:
            self.problem(
                "case.outcome",
                f"{path}.outcome.right",
                f"`{outcome.right}` is not one of the `candidates`; name one of them",
            )

    def element(self, entity_type: EntityType, element: str, path: str) -> None:
        kind, colon, argument = element.partition(":")
        if element == "scope":
            if entity_type.scope is None:
                self.unknown_element(path, f"`{entity_type.name}` has no scope")
            return
        form = _ELEMENT_ARGUMENTS.get(kind)
        if not colon or form is None or form.fullmatch(argument) is None:
            self.problem("case.unknown-element", path, _BAD_ELEMENT)
            return
        name = entity_type.name
        if kind == "key":
            keys = [key.attributes for key in entity_type.identity]
            if tuple(argument.split("+")) not in keys:
                self.unknown_element(
                    path,
                    f"`{name}` has no key `{argument}`",
                    "write a key's attributes in its declared order",
                )
        elif kind == "veto":
            if argument not in entity_type.vetoes:
                self.unknown_element(path, f"`{name}` has no veto `{argument}`")
        elif kind == "names":
            if argument != entity_type.names.value:
                self.unknown_element(
                    path, f"`{name}` has `names: {entity_type.names.value}`, not `{argument}`,"
                )
        elif kind == "unique":
            attribute = entity_type.attributes.get(argument)
            if attribute is None or attribute.unique == "scope":
                self.unknown_element(
                    path, f"`{name}` has no attribute `{argument}` with a non-default `unique`"
                )
        elif argument not in entity_type.corroborate:
            self.unknown_element(path, f"`{name}` does not corroborate by `{argument}`")

    def unknown_element(self, path: str, what: str, advice: str | None = None) -> None:
        message = f"{what} under `{self.stack.name}`"
        self.problem("case.unknown-element", path, f"{message}; {advice}" if advice else message)

    def blocked_by(self, case: Case, path: str) -> None:
        vetoes = {
            element.removeprefix("veto:")
            for element in case.depends_on
            if element.startswith("veto:")
        }
        if case.blocked_by is not None and case.blocked_by not in vetoes:
            self.problem(
                "case.blocked-by",
                f"{path}.blocked_by",
                f"`depends_on` has no `veto:{case.blocked_by}`; add it, or name a veto it has",
            )
        elif case.blocked_by is None and case.outcome.kind == "new" and vetoes:
            self.problem(
                "case.blocked-by",
                path,
                "a `new` outcome that depends on a veto names it in `blocked_by`; add it",
            )


# The parts of an entity type that decide its identity, as `origins` paths name them.
_IDENTITY_PARTS = ("scope", "identity[", "vetoes[", "names", "corroborate[")
_ELEMENT_PATH = re.compile(r"(identity|vetoes)\[([^\]]+)\]")


def _coverage(case_set: CaseSet) -> list[PackProblem]:
    """FR-031 for a set whose top pack is shipped: each identity part the top pack gives is tested.

    A type the top pack defines with an identity field, or whose identity
    fields it changes, needs a case that must merge and one that must stay
    apart; each key and veto the top pack declares needs a case naming it.
    """
    stack = case_set.stack
    top = stack.packs[-1]
    if top.source != "shipped":
        return []
    types: set[str] = set()
    elements: dict[str, tuple[str, str]] = {}
    for path, owner in stack.origins.items():
        if owner != top.name or not path.startswith("entities."):
            continue
        type_name, _, part = path.removeprefix("entities.").partition(".")
        entity_type = stack.entities[type_name]
        if entity_type.scope is None and not entity_type.identity and not entity_type.vetoes:
            continue
        if not part or part.startswith(_IDENTITY_PARTS):
            types.add(type_name)
        match = _ELEMENT_PATH.fullmatch(part)
        if match is not None:
            kind = "key" if match[1] == "identity" else "veto"
            elements[path] = (type_name, f"{kind}:{match[2]}")
    expects: dict[str, set[str]] = {}
    named: set[tuple[str, str]] = set()
    for case in case_set.cases:
        expects.setdefault(case.mention.type, set()).add(case.expect)
        named |= {(case.mention.type, element) for element in case.depends_on}
    problems = []
    for type_name in types:
        missing = [
            words
            for expect, words in (("merge", "must merge"), ("apart", "must stay apart"))
            if expect not in expects.get(type_name, set())
        ]
        if missing:
            each = "one of each" if len(missing) == 2 else "one"
            problems.append(
                PackProblem(
                    "case.coverage-type",
                    case_set.source,
                    f"entities.{type_name}",
                    f"no case of `{type_name}` {' or '.join(missing)} under `{top.name}`; "
                    f"add {each}",
                    "error",
                )
            )
    for path, (type_name, element) in elements.items():
        if (type_name, element) not in named:
            does = "this key merges" if element.startswith("key:") else "this veto keeps apart"
            problems.append(
                PackProblem(
                    "case.coverage-element",
                    case_set.source,
                    path,
                    f"no case depends on `{element}`; add one that {does}",
                    "error",
                )
            )
    return problems


def _either(names: tuple[str, ...]) -> str:
    return " or ".join(f"`{name}`" for name in names)
