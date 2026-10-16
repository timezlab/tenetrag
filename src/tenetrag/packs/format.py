"""The pydantic models of one pack file, and the problems they find (data-model §2, research R2).

Private to `tenetrag.packs`. A file is validated alone, before any merge:
every string is normalized to NFC first, unknown fields are refused, and
types are strict. Whether an entry is a new type or a change to an
inherited one is known only after stacking, so every field of a definition
is optional here. Each definition, enum, glossary entry and question is
validated on its own: a bad one is set aside, its name still counts as
defined, and the rest of the file stacks (research R4).

A message never repeats the file's text, so pydantic's own messages, which
may quote the input, are replaced by the ones below.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Annotated, Any, Literal, TypeVar, cast

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    ValidationError,
    model_validator,
)
from pydantic_core import ErrorDetails, PydanticCustomError

from tenetrag.packs.problems import PackProblem
from tenetrag.packs.stack import Mode

PACK_NAME = re.compile(r"[a-z][a-z0-9]*(-[a-z0-9]+)*")
TYPE_NAME = re.compile(r"[A-Z][A-Za-z0-9]*")
RELATION_NAME = re.compile(r"[A-Z][A-Z0-9]*(_[A-Z0-9]+)*")
LOWER_NAME = re.compile(r"[a-z][a-z0-9]*(_[a-z0-9]+)*")

BUILTIN_RANGES = frozenset({"str", "date", "money", "percentage", "int", "float", "bool"})

UNKNOWN_FIELD = "unknown field; remove it or use a field of the pack format"


def name_checker(pattern: re.Pattern[str], example: str) -> Callable[[str], str]:
    """A validator refusing a name `pattern` does not match, with `example` for the message."""

    def check(value: str) -> str:
        if pattern.fullmatch(value) is None:
            raise PydanticCustomError("bad_name", "not a valid name", {"example": example})
        return value

    return check


def _needed(value: str) -> str:
    if TYPE_NAME.fullmatch(value) is None and RELATION_NAME.fullmatch(value) is None:
        raise PydanticCustomError("bad_name", "not a valid name", {"example": "Vendor or SUPPLIES"})
    return value


def _range(value: str) -> str:
    if value not in BUILTIN_RANGES and TYPE_NAME.fullmatch(value) is None:
        raise PydanticCustomError("bad_range", "not a range")
    return value


PackName = Annotated[str, AfterValidator(name_checker(PACK_NAME, "alpha-ops"))]
QuestionId = Annotated[str, AfterValidator(name_checker(PACK_NAME, "alpha-ops-1"))]
TypeName = Annotated[str, AfterValidator(name_checker(TYPE_NAME, "VendorDesk"))]
RelationName = Annotated[str, AfterValidator(name_checker(RELATION_NAME, "REPORTS_TO"))]
LowerName = Annotated[str, AfterValidator(name_checker(LOWER_NAME, "tax_code"))]
Needed = Annotated[str, AfterValidator(_needed)]
Range = Annotated[str, AfterValidator(_range)]
Text = Annotated[str, Field(min_length=1)]
Time = Literal["none", "point", "interval"]
Names = Literal["key", "evidence", "versioned", "none"]
Compare = Literal["text", "code", "digits", "lower", "upper", "date"]
Unique = Literal["scope", "global", "self_scoped"]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class AttributeDef(_Model):
    range: Range | None = None
    required: bool | None = None
    multivalued: bool | None = None
    unit: Text | None = None
    description: Text | None = None
    compare: Compare | None = None
    unique: Unique | None = None


class ScopeDef(_Model):
    role: LowerName | None = None
    to: list[TypeName] | None = None
    inherit: Literal["none", "document"] | None = None
    when: dict[LowerName, list[LowerName]] | None = None


class KeyDef(_Model):
    """An identity key: `[a, b]`, or `{key: [a, b], during: [start, end]}`."""

    key: Annotated[list[LowerName], Field(min_length=1)]
    during: Annotated[list[LowerName], Field(min_length=2, max_length=2)] | None = None

    @model_validator(mode="before")
    @classmethod
    def _from_list(cls, data: object) -> object:
        if isinstance(data, list):
            return {"key": data}
        if isinstance(data, dict):
            return data
        raise PydanticCustomError("bad_key", "not a key")


class _TypeDef(_Model):
    """The fields entity, event and fact types share."""

    description: Text | None = None
    examples: list[Text] | None = None
    aliases: list[Text] | None = None
    attributes: dict[LowerName, AttributeDef] | None = None
    required: list[LowerName] | None = None
    extract: bool | None = None
    agent_visible: bool | None = None
    exact_mappings: list[Text] | None = None
    deprecated: bool | None = None
    renamed_from: TypeName | None = None


class EntityDef(_TypeDef):
    scope: ScopeDef | None = None
    identity: list[KeyDef] | None = None
    vetoes: list[LowerName] | None = None
    names: Names | None = None
    corroborate: list[RelationName] | None = None
    version_start: list[LowerName] | None = None
    document_link: list[LowerName] | None = None


class EventDef(_TypeDef):
    is_a: TypeName | None = None
    roles: dict[LowerName, list[TypeName]] | None = None
    time: Time | None = None
    identity: list[Annotated[list[LowerName], Field(min_length=1)]] | None = None


class FactDef(_TypeDef):
    roles: dict[LowerName, list[TypeName]] | None = None
    time: Time | None = None
    version_key: list[LowerName] | None = None


class WhereDef(_Model):
    from_: dict[LowerName, list[LowerName]] | None = Field(default=None, alias="from")
    to: dict[LowerName, list[LowerName]] | None = None


class CardinalityDef(_Model):
    one_at_a_time: Annotated[list[LowerName], Field(min_length=1)]


class RelationDef(_Model):
    description: Text | None = None
    from_: list[TypeName] | None = Field(default=None, alias="from")
    to: list[TypeName] | None = None
    where: WhereDef | None = None
    time: Time | None = None
    attributes: dict[LowerName, AttributeDef] | None = None
    value: Range | None = None
    cardinality: CardinalityDef | None = None
    required: list[LowerName] | None = None
    extract: bool | None = None
    exact_mappings: list[Text] | None = None
    deprecated: bool | None = None
    renamed_from: RelationName | None = None


class RetrievalDef(_Model):
    hub_penalty: list[TypeName] | None = None
    max_hops: Annotated[int, Field(ge=1)] | None = None
    context_relations: list[RelationName] | None = None


class GlossaryDef(_Model):
    name: Text
    type: TypeName
    aliases: list[Text] | None = None
    note: Text | None = None


class QuestionDef(_Model):
    id: QuestionId
    text: Text
    needs: Annotated[list[Needed], Field(min_length=1)]


Definition = EntityDef | RelationDef | EventDef | FactDef

_STRICT = ConfigDict(strict=True)
_PACK_NAME: TypeAdapter[str] = TypeAdapter(PackName, config=_STRICT)
_VERSION: TypeAdapter[int] = TypeAdapter(Annotated[int, Field(ge=1)], config=_STRICT)
_MODE: TypeAdapter[str] = TypeAdapter(Literal["strict", "discovery"], config=_STRICT)
_LOWER_NAMES: TypeAdapter[list[str]] = TypeAdapter(list[LowerName], config=_STRICT)

_TOP_FIELDS = frozenset(
    {
        "pack",
        "version",
        "extends",
        "mode",
        "entities",
        "relations",
        "events",
        "facts",
        "enums",
        "not_entities",
        "retrieval",
        "glossary",
        "competency_questions",
    }
)

# The words of the identity and version-key grammars, by kind (research R2).
_RESERVED: dict[str, tuple[tuple[str, ...], str, str]] = {
    "entities": (("attributes",), "scope", "an entity's scope in identity keys"),
    "events": (("roles", "attributes"), "time", "an event's time in identity entries"),
    "facts": (("roles", "attributes"), "issuer", "a fact's issuer in version keys"),
}

_EXPECTED = {
    "string_type": "a text",
    "int_type": "a whole number",
    "bool_type": "true or false",
    "list_type": "a list",
    "dict_type": "a mapping",
    "model_type": "a mapping of fields",
}

_T = TypeVar("_T")


@dataclass
class ParsedPack:
    """One file's validated content. `extends` holds (reference, path) pairs."""

    name: str | None
    version: int | None
    extends: list[tuple[str, str]]
    has_extends: bool
    mode: Mode | None
    entities: dict[str, EntityDef | None] = field(default_factory=dict)
    relations: dict[str, RelationDef | None] = field(default_factory=dict)
    events: dict[str, EventDef | None] = field(default_factory=dict)
    facts: dict[str, FactDef | None] = field(default_factory=dict)
    enums: dict[str, list[str] | None] = field(default_factory=dict)
    not_entities: list[str] = field(default_factory=list)
    retrieval: RetrievalDef | None = None
    glossary: list[tuple[int, GlossaryDef]] = field(default_factory=list)
    questions: list[tuple[int, QuestionDef]] = field(default_factory=list)
    # Per entity, whether each identity key was written as a list, for problem paths.
    listed_keys: dict[str, tuple[bool, ...]] = field(default_factory=dict)
    # Names whose definition has a problem, by kind: still defined for references.
    set_aside: dict[str, set[str]] = field(default_factory=dict)


def parse_pack(data: Mapping[object, object], label: str) -> tuple[ParsedPack, list[PackProblem]]:
    """Validate one file's data. `label` names the file in the problems."""
    parser = _Parser(label)
    try:
        nfc_data = normalized(data)
    except RecursiveDataError:
        parser.problem("file.yaml", "", RECURSIVE_ALIAS)
        return ParsedPack(None, None, [], True, None), parser.problems
    # normalized returns a dict for a dict.
    return parser.parse(cast("dict[Any, Any]", nfc_data)), parser.problems


class RecursiveDataError(Exception):
    """An alias that contains itself, which no pack or case field can hold."""


RECURSIVE_ALIAS = "an alias refers to itself; remove the loop"


def normalized(data: object) -> object:
    """`data` with every string in NFC. Raises `RecursiveDataError` for an alias holding itself."""
    return _nfc(data, {})


def validation_problems(
    exc: ValidationError, label: str, path: str, raw: object
) -> list[PackProblem]:
    """One file.* problem for each pydantic error, at its path under `path` in `raw`."""
    problems = []
    for detail in exc.errors(include_url=False, include_input=False):
        rule, message = _describe(detail)
        problems.append(PackProblem(rule, label, _path(path, detail["loc"], raw), message, "error"))
    return problems


_IN_PROGRESS = object()


def _nfc(value: object, done: dict[int, object]) -> object:
    """`value` with every string, key or value, in NFC.

    `done` maps each list or dict already normalized to its result, so a
    subtree that aliases share is walked once, however often it is named.
    """
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if not isinstance(value, (list, dict)):
        return value
    seen = done.get(id(value))
    if seen is _IN_PROGRESS:
        raise RecursiveDataError
    if seen is not None:
        return seen
    done[id(value)] = _IN_PROGRESS
    result: object
    if isinstance(value, list):
        result = [_nfc(item, done) for item in value]
    else:
        result = {_nfc(key, done): _nfc(item, done) for key, item in value.items()}
    done[id(value)] = result
    return result


class _Parser:
    def __init__(self, label: str) -> None:
        self.label = label
        self.problems: list[PackProblem] = []
        self.set_aside: dict[str, set[str]] = {
            kind: set() for kind in ("entities", "relations", "events", "facts", "enums")
        }

    def problem(self, rule: str, path: str, message: str) -> None:
        self.problems.append(PackProblem(rule, self.label, path, message, "error"))

    def parse(self, data: dict[Any, Any]) -> ParsedPack:
        for key in data:
            if key not in _TOP_FIELDS:
                self.problem("file.unknown-field", str(key), UNKNOWN_FIELD)
        mode = data.get("mode")
        parsed = ParsedPack(
            name=self._required(data, "pack", _PACK_NAME),
            version=self._required(data, "version", _VERSION),
            extends=self._extends(data.get("extends")),
            has_extends=data.get("extends") not in (None, []),
            mode=None if mode is None else _mode(self._valid(_MODE, mode, "mode")),
            entities=self._definitions("entities", data.get("entities"), EntityDef),
            relations=self._definitions("relations", data.get("relations"), RelationDef),
            events=self._definitions("events", data.get("events"), EventDef),
            facts=self._definitions("facts", data.get("facts"), FactDef),
            enums=self._enums(data.get("enums")),
            set_aside=self.set_aside,
        )
        if data.get("not_entities") is not None:
            parsed.not_entities = (
                self._valid(_LOWER_NAMES, data["not_entities"], "not_entities") or []
            )
        if data.get("retrieval") is not None:
            parsed.retrieval = self._model(RetrievalDef, data["retrieval"], "retrieval")
        parsed.glossary = self._items("glossary", data.get("glossary"), GlossaryDef)
        parsed.questions = self._items(
            "competency_questions", data.get("competency_questions"), QuestionDef
        )
        for name, entity in parsed.entities.items():
            if entity is not None and entity.identity is not None:
                raw_keys = data["entities"][name]["identity"]
                parsed.listed_keys[name] = tuple(isinstance(key, list) for key in raw_keys)
        return parsed

    def _required(self, data: dict[Any, Any], name: str, adapter: TypeAdapter[_T]) -> _T | None:
        if name not in data:
            self.problem("file.invalid-value", name, "required field is missing; add it")
            return None
        return self._valid(adapter, data[name], name)

    def _extends(self, value: object) -> list[tuple[str, str]]:
        if value is None:
            return []
        if isinstance(value, str):
            return [(value, "extends")]
        if not isinstance(value, list):
            self.problem("file.invalid-value", "extends", _EXTENDS)
            return []
        references = []
        for index, item in enumerate(value):
            if isinstance(item, str):
                references.append((item, f"extends[{index}]"))
            else:
                self.problem("file.invalid-value", f"extends[{index}]", _EXTENDS)
        return references

    def _definitions(
        self, kind: str, value: object, model: type[_DefinitionT]
    ) -> dict[str, _DefinitionT | None]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            self.problem("file.invalid-value", kind, "expected a mapping of names to definitions")
            return {}
        pattern, example = (
            (RELATION_NAME, "REPORTS_TO") if kind == "relations" else (TYPE_NAME, "VendorDesk")
        )
        definitions: dict[str, _DefinitionT | None] = {}
        for name, raw in value.items():
            path = f"{kind}.{name}"
            if not isinstance(name, str) or pattern.fullmatch(name) is None:
                self.problem("file.bad-name", path, _bad_name(example))
                continue
            if raw is None:
                definitions[name] = None
                continue
            reserved_clear = self._reserved_clear(kind, path, raw)
            definition = self._model(model, raw, path)
            if definition is None or not reserved_clear:
                self.set_aside[kind].add(name)
            else:
                definitions[name] = definition
        return definitions

    def _reserved_clear(self, kind: str, path: str, raw: object) -> bool:
        if kind not in _RESERVED or not isinstance(raw, dict):
            return True
        fields, word, meaning = _RESERVED[kind]
        clear = True
        for name in fields:
            names = raw.get(name)
            if isinstance(names, dict) and word in names:
                self.problem(
                    "file.reserved-name",
                    f"{path}.{name}.{word}",
                    f"`{word}` is reserved: it stands for {meaning}; rename this one",
                )
                clear = False
        return clear

    def _enums(self, value: object) -> dict[str, list[str] | None]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            self.problem("file.invalid-value", "enums", "expected a mapping of names to values")
            return {}
        enums: dict[str, list[str] | None] = {}
        for name, raw in value.items():
            path = f"enums.{name}"
            if not isinstance(name, str) or TYPE_NAME.fullmatch(name) is None:
                self.problem("file.bad-name", path, _bad_name("DeskTier"))
                continue
            if raw is None:
                enums[name] = None
                continue
            values = self._valid(_LOWER_NAMES, raw, path)
            if values is None:
                self.set_aside["enums"].add(name)
                continue
            repeated = [index for index, item in enumerate(values) if item in values[:index]]
            for index in repeated:
                self.problem(
                    "file.invalid-value", f"{path}[{index}]", "a value appears twice; write it once"
                )
            if repeated:
                self.set_aside["enums"].add(name)
            else:
                enums[name] = values
        return enums

    def _items(self, kind: str, value: object, model: type[_ItemT]) -> list[tuple[int, _ItemT]]:
        if value is None:
            return []
        if not isinstance(value, list):
            self.problem("file.invalid-value", kind, "expected a list")
            return []
        items = []
        for index, raw in enumerate(value):
            item = self._model(model, raw, f"{kind}[{index}]")
            if item is not None:
                items.append((index, item))
        return items

    def _model(self, model: type[_ModelT], value: object, path: str) -> _ModelT | None:
        try:
            return model.model_validate(value)
        except ValidationError as exc:
            self._report(exc, path, value)
            return None

    def _valid(self, adapter: TypeAdapter[_T], value: object, path: str) -> _T | None:
        """The validated value, or None after reporting each problem at its path."""
        try:
            return adapter.validate_python(value)
        except ValidationError as exc:
            self._report(exc, path, value)
            return None

    def _report(self, exc: ValidationError, path: str, value: object) -> None:
        self.problems.extend(validation_problems(exc, self.label, path, value))


_ModelT = TypeVar("_ModelT", bound=BaseModel)
_DefinitionT = TypeVar("_DefinitionT", EntityDef, RelationDef, EventDef, FactDef)
_ItemT = TypeVar("_ItemT", GlossaryDef, QuestionDef)

_EXTENDS = "expected a pack name or a path ending in .yaml or .yml"


def _mode(value: str | None) -> Mode | None:
    return None if value is None else Mode(value)


def _bad_name(example: str) -> str:
    return f"not a valid name; write it like `{example}`"


def _describe(detail: ErrorDetails) -> tuple[str, str]:
    """The rule and a message for one pydantic error, never quoting the input."""
    kind = detail["type"]
    context = detail.get("ctx", {})
    if kind == "extra_forbidden":
        return "file.unknown-field", UNKNOWN_FIELD
    if kind == "bad_name":
        return "file.bad-name", _bad_name(context["example"])
    if kind == "missing":
        message = "required field is missing; add it"
    elif kind == "bad_range":
        message = "not a range; use str, date, money, percentage, int, float, bool or an enum name"
    elif kind == "bad_key":
        message = "expected a list of attributes, or a mapping with `key` and `during`"
    elif kind == "bad_date":
        message = "expected an ISO date such as 2025-06-10"
    elif kind == "literal_error":
        message = f"not one of the allowed values; use {context['expected']}"
    elif kind == "string_too_short":
        message = "must not be empty"
    elif kind == "too_short":
        message = f"list at least {context['min_length']} item(s)"
    elif kind == "too_long":
        message = f"list at most {context['max_length']} item(s)"
    elif kind == "greater_than_equal":
        message = f"must be at least {context['ge']}"
    elif kind in _EXPECTED:
        message = f"expected {_EXPECTED[kind]}"
    else:
        message = "not a valid value; see the pack format in docs/product/domain-packs.md"
    return "file.invalid-value", message


def _path(prefix: str, loc: tuple[int | str, ...], raw: object) -> str:
    """The dotted path of a pydantic error location, with `[n]` for list items."""
    path, node = prefix, raw
    for part in loc:
        if part == "[key]":
            continue
        if isinstance(part, int) and isinstance(node, list):
            path += f"[{part}]"
            node = node[part] if part < len(node) else None
        elif isinstance(node, list):
            continue  # `key`, which wraps an identity key written as a list
        else:
            path = f"{path}.{part}" if path else str(part)
            node = node.get(part) if isinstance(node, dict) else None
    return path
