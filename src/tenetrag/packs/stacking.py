"""Stacking pack files into one merged stack (data-model §4, research R3).

Private to `tenetrag.packs`. Files come in linear order, core first, and
each is a delta over the files before it. A definition new to the stack is
taken whole; one already in it may only add, as R3's "Allowed change"
table says, and every other field it states must equal the stack's value.
The merge records which file added each element, so a conflict names the
pack that set the value, and is `stack.parents-conflict` when that pack is
not an ancestor of the file that differs.

The working state is plain dicts and sets, frozen into the classes of
`stack.py` at the end: defaults filled in, `is_a` resolved, sets sorted.
A part with a problem keeps a placeholder, since the stack is then
discarded and only the problems are reported.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, TypeVar

from pydantic import BaseModel

from tenetrag.packs.format import (
    AttributeDef,
    CardinalityDef,
    EntityDef,
    EventDef,
    FactDef,
    ParsedPack,
    RelationDef,
    ScopeDef,
    WhereDef,
)
from tenetrag.packs.problems import PackProblem
from tenetrag.packs.stack import (
    Attribute,
    CompetencyQuestion,
    EntityType,
    EventType,
    FactType,
    GlossaryEntry,
    Key,
    Mode,
    NameRule,
    PackInfo,
    PackStack,
    RelationType,
    Retrieval,
    Scope,
    Stamp,
)

KINDS = ("entities", "relations", "events", "facts")

_T = TypeVar("_T")

_EMPTY: dict[str, BaseModel] = {
    "entities": EntityDef(),
    "relations": RelationDef(),
    "events": EventDef(),
    "facts": FactDef(),
}

# Fields that must equal the inherited value, and the rule when they differ.
_SAME = {
    "description": "stack.changed-description",
    "examples": "stack.changed",
    "aliases": "stack.changed",
    "is_a": "stack.changed",
    "time": "stack.changed-time",
    "value": "stack.changed-range",
    "names": "stack.changed-identity",
    "version_start": "stack.changed-identity",
    "document_link": "stack.changed",
    "cardinality": "stack.changed",
    "agent_visible": "stack.changed",
    "deprecated": "stack.changed",
    "renamed_from": "stack.changed",
}
# Fields a later pack may add values to; the merged stack sorts them.
_ADDED = frozenset({"from", "to", "vetoes", "exact_mappings", "version_key"})
# Of those, the fields whose values `origins` records one by one.
_OWNED_VALUES = frozenset({"from", "to", "vetoes", "version_key"})
_SETS = _ADDED | {"corroborate", "document_link", "required"}

_ATTRIBUTE_DEFAULTS: dict[str, Any] = {
    "range": "",  # a placeholder: a new attribute without a range is a problem
    "required": False,
    "multivalued": False,
    "unit": None,
    "description": None,
    "compare": "text",
    "unique": "scope",
}
_ATTRIBUTE_RULES = {
    "range": "stack.changed-range",
    "multivalued": "stack.changed",
    "unit": "stack.changed",
    "description": "stack.changed-description",
    "compare": "stack.changed-identity",
    "unique": "stack.changed-identity",
}

_MESSAGES = {
    "stack.changed-range": "the range differs from the one pack `{pack}` set; "
    "an inherited attribute keeps its range, so add a new attribute instead",
    "stack.changed-time": "the time differs from the one pack `{pack}` set; "
    "an inherited type keeps its time",
    "stack.changed-description": "the description differs from the one pack `{pack}` wrote; "
    "restate it word for word or leave it out",
    "stack.changed-identity": "this differs from what pack `{pack}` set; "
    "a later pack cannot change how a type is identified",
    "stack.changed": "this differs from what pack `{pack}` set; "
    "a later pack can only add to an inherited definition",
    "stack.parents-conflict": "this differs from what parent pack `{pack}` defines; "
    "make the two parents agree",
}


@dataclass(frozen=True, slots=True)
class PackFile:
    """One file of the stack. `ancestors` holds the linear indices of every pack it extends."""

    label: str
    parsed: ParsedPack
    info: PackInfo
    ancestors: frozenset[int]


@dataclass(frozen=True, slots=True)
class Stacked:
    """The merged stack, the file index that added each element path, and the problems."""

    stack: PackStack
    owners: Mapping[str, int]
    problems: list[PackProblem]


def stack_files(files: Sequence[PackFile]) -> Stacked:
    """Merge `files`, given in linear order with the top pack last."""
    merger = _Merger(files)
    for index, file in enumerate(files):
        merger.apply(index, file.parsed)
    merger.resolve_is_a()
    return Stacked(merger.freeze(), MappingProxyType(dict(merger.owners)), merger.problems)


def question_path(question_id: str) -> str:
    """A competency question's element path, keyed by id as `origins` and warnings give it."""
    return f"competency_questions[{question_id}]"


def owner_of(owners: Mapping[str, int], path: str) -> int:
    """The file that added the element at `path`, or its nearest enclosing element."""
    while path not in owners:
        cut = max(path.rfind("."), path.rfind("["))
        if cut < 0:
            raise KeyError(path)
        path = path[:cut]
    return owners[path]


def _new_state(kind: str) -> dict[str, Any]:
    """A definition with every default of data-model §2 filled in."""
    state: dict[str, Any] = {
        "description": None,
        "attributes": {},
        "required": set(),
        "extract": True,
        "exact_mappings": set(),
        "deprecated": False,
        "renamed_from": None,
    }
    if kind != "relations":
        state |= {"examples": (), "aliases": (), "agent_visible": False}
    if kind == "entities":
        state |= {
            "scope": None,
            "identity": [],
            "vetoes": set(),
            "names": "key",
            "corroborate": set(),
            "version_start": (),
            "document_link": set(),
        }
    elif kind == "relations":
        state |= {
            "from": set(),
            "to": set(),
            "where": {},
            "time": None,
            "value": None,
            "cardinality": None,
        }
    elif kind == "events":
        # `time` stays None until `is_a` is resolved, unless the type states it.
        state |= {"is_a": None, "roles": {}, "time": None, "identity": []}
    else:
        state |= {"roles": {}, "time": "interval", "version_key": set()}
    return state


def _is_empty(value: object) -> bool:
    return value is None or (isinstance(value, (list, tuple, set, dict)) and not value)


def _stored(key: str, value: object) -> object:
    """A field's value as the working state holds it."""
    if isinstance(value, CardinalityDef):
        return set(value.one_at_a_time or ())
    if isinstance(value, list):
        return set(value) if key in _SETS else tuple(value)
    return value


def _stated(model: BaseModel) -> list[tuple[str, Any]]:
    """The (key, value) of each field the file wrote, in the model's order."""
    return [
        ("from" if name == "from_" else name, getattr(model, name))
        for name in type(model).model_fields
        if name in model.model_fields_set
    ]


class _Merger:
    def __init__(self, files: Sequence[PackFile]) -> None:
        self.files = files
        self.index = 0
        self.problems: list[PackProblem] = []
        self.owners: dict[str, int] = {}
        self.definitions: dict[str, dict[str, dict[str, Any]]] = {kind: {} for kind in KINDS}
        self.enums: dict[str, set[str]] = {}
        self.not_entities: set[str] = set()
        self.retrieval: dict[str, Any] = {
            "hub_penalty": set(),
            "max_hops": None,
            "context_relations": set(),
        }
        self.glossary: list[GlossaryEntry] = []
        self.questions: dict[str, tuple[CompetencyQuestion, int]] = {}
        self.mode = Mode.STRICT

    # Problems and origins

    def problem(self, rule: str, path: str, message: str, index: int | None = None) -> None:
        label = self.files[self.index if index is None else index].label
        self.problems.append(PackProblem(rule, label, path, message, "error"))

    def own(self, path: str) -> None:
        self.owners.setdefault(path, self.index)

    def differs(self, rule: str, path: str) -> None:
        """Report a field that must equal its inherited value, naming the pack that set it."""
        owner = owner_of(self.owners, path)
        if owner not in self.files[self.index].ancestors:
            rule = "stack.parents-conflict"
        pack = self.files[owner].info.name
        self.problem(rule, path, _MESSAGES[rule].format(pack=pack))

    def removed(self, path: str) -> None:
        self.problem(
            "stack.removed",
            path,
            "a null or empty value would remove an inherited element; leave the field out",
        )

    # Applying one file

    def apply(self, index: int, parsed: ParsedPack) -> None:
        self.index = index
        if parsed.mode is not None:
            self.mode = parsed.mode
        for kind in KINDS:
            definitions: Mapping[str, BaseModel | None] = getattr(parsed, kind)
            for name, definition in definitions.items():
                self.definition(kind, name, definition)
        self.apply_enums(parsed.enums)
        self.not_entities |= set(parsed.not_entities)
        if parsed.retrieval is not None:
            # Query-time hints: a later pack replaces each one it states (research R3).
            for key, value in _stated(parsed.retrieval):
                if key == "max_hops":
                    self.retrieval[key] = value
                else:
                    self.retrieval[key] = set(value or ())
        self.glossary.extend(
            GlossaryEntry(entry.name, entry.type, tuple(entry.aliases or ()), entry.note)
            for _, entry in parsed.glossary
        )
        for position, question in parsed.questions:
            self.question(position, question.id, question.text, tuple(question.needs))

    def definition(self, kind: str, name: str, definition: BaseModel | None) -> None:
        path = f"{kind}.{name}"
        state = self.definitions[kind].get(name)
        if state is None:
            self.create(kind, path, name, definition or _EMPTY[kind])
        elif definition is None:
            self.removed(path)
        else:
            self.change(kind, path, state, definition, is_new=False)

    def create(self, kind: str, path: str, name: str, model: BaseModel) -> None:
        self.own(path)
        state = _new_state(kind)
        self.definitions[kind][name] = state
        stated = dict(_stated(model))
        if kind != "relations" and stated.get("description") is None:
            self.problem(
                "stack.missing-description",
                f"{path}.description",
                "a new type needs a description; say what the type is",
            )
        if kind == "relations":
            for key in ("from", "to", "time"):
                if stated.get(key) is None:
                    self.problem(
                        "file.invalid-value",
                        f"{path}.{key}",
                        f"a new relation needs `{key}`; add it",
                    )
            state["time"] = "none"  # replaced below when stated
        if kind == "events" and stated.get("is_a") is None and stated.get("time") is None:
            self.problem(
                "file.invalid-value",
                f"{path}.time",
                "an event type with no `is_a` needs a time: none, point or interval",
            )
        self.change(kind, path, state, model, is_new=True)

    def change(
        self, kind: str, path: str, state: dict[str, Any], model: BaseModel, *, is_new: bool
    ) -> None:
        for key, value in _stated(model):
            where = f"{path}.{key}"
            if _is_empty(value) and key not in ("identity", "required"):
                if not is_new and not _is_empty(state[key]) and state[key] != _new_state(kind)[key]:
                    self.removed(where)
                continue
            if key == "attributes":
                self.attributes(where, state["attributes"], value, is_new)
            elif key == "roles":
                self.roles(where, state["roles"], value, is_new)
            elif key == "scope":
                self.scope(where, state, value)
            elif key == "identity":
                self.identity(kind, where, state, value, is_new)
            elif key == "where":
                self.where(where, state["where"], value, is_new)
            elif key == "required":
                self.required(where, state, value, is_new)
            elif key == "corroborate":
                self.corroborate(where, state, value, is_new)
            elif key in _ADDED:
                for item in value:
                    if key in _OWNED_VALUES:
                        self.own(f"{where}[{item}]")
                    state[key].add(item)
            elif key == "extract" or is_new or (key == "time" and state["time"] is None):
                state[key] = _stored(key, value)
            elif _stored(key, value) != state[key]:
                self.differs(_SAME[key], where)

    # The fields with their own rules

    def attributes(
        self,
        path: str,
        attributes: dict[str, dict[str, Any]],
        stated: dict[str, AttributeDef],
        is_new: bool,
    ) -> None:
        for name, definition in stated.items():
            where = f"{path}.{name}"
            current = attributes.get(name)
            if current is None:
                attributes[name] = self.new_attribute(where, definition, inherited=not is_new)
                self.own(where)
            else:
                self.change_attribute(where, current, definition)

    def new_attribute(
        self, path: str, definition: AttributeDef, *, inherited: bool
    ) -> dict[str, Any]:
        attribute = dict(_ATTRIBUTE_DEFAULTS)
        attribute.update((key, value) for key, value in _stated(definition) if value is not None)
        if definition.range is None:
            self.problem(
                "file.invalid-value", f"{path}.range", "a new attribute needs a range; add one"
            )
        if inherited and attribute["required"]:
            self.required_on_inherited(f"{path}.required")
            attribute["required"] = False
        return attribute

    def change_attribute(
        self, path: str, current: dict[str, Any], definition: AttributeDef
    ) -> None:
        for key, value in _stated(definition):
            where = f"{path}.{key}"
            if value is None:
                if current[key] != _ATTRIBUTE_DEFAULTS[key]:
                    self.removed(where)
            elif key == "required":
                if value and not current["required"]:
                    self.required_on_inherited(where)
                elif not value and current["required"]:
                    self.differs("stack.changed", where)
            elif value != current[key]:
                self.differs(_ATTRIBUTE_RULES[key], where)

    def required_on_inherited(self, path: str) -> None:
        self.problem(
            "stack.required-on-inherited",
            path,
            "a pack cannot make a field required on a type another pack defined; "
            "leave `required` out",
        )

    def roles(
        self, path: str, roles: dict[str, set[str]], stated: dict[str, list[str]], is_new: bool
    ) -> None:
        for role, types in stated.items():
            where = f"{path}.{role}"
            if role not in roles:
                roles[role] = set(types)
                self.own(where)
            elif not types and not is_new:
                self.removed(where)
            else:
                roles[role] |= set(types)

    def scope(self, path: str, state: dict[str, Any], stated: ScopeDef) -> None:
        scope = state["scope"]
        if scope is None:
            # A scope added to an inherited type that had none only keeps more entities
            # apart, so it is taken whole, as on a new type (ADR 0023).
            for key in ("role", "to"):
                if getattr(stated, key) is None:
                    self.problem(
                        "file.invalid-value", f"{path}.{key}", f"a new scope needs `{key}`; add it"
                    )
            state["scope"] = {
                "role": stated.role or "",
                "to": set(stated.to or ()),
                "inherit": stated.inherit or "none",
                "when": {},
            }
            self.own(path)
            self.own(f"{path}.inherit")
            for attribute, values in (stated.when or {}).items():
                self.when_values(
                    f"{path}.when.{attribute}", state["scope"]["when"], attribute, values
                )
            return
        for key, value in _stated(stated):
            where = f"{path}.{key}"
            if key == "when":
                self.when(where, scope["when"], value)
            elif _is_empty(value):
                if key != "inherit" or scope["inherit"] != "none":
                    self.removed(where)
            elif key == "to":
                if set(value) != scope["to"]:
                    self.differs("stack.changed-identity", where)
            elif key == "inherit" and value == "document" and scope["inherit"] == "none":
                scope["inherit"] = value
                self.owners[where] = self.index
            elif value != scope[key]:
                self.differs("stack.changed-identity", where)

    def when(
        self, path: str, when: dict[str, set[str]], stated: dict[str, list[str]] | None
    ) -> None:
        if not stated:
            if when:
                self.removed(path)
            return
        if not when:
            self.added_identity(path)
            return
        for attribute, values in stated.items():
            where = f"{path}.{attribute}"
            if attribute not in when:
                self.added_identity(where)
            elif not values:
                self.removed(where)
            else:
                self.when_values(where, when, attribute, values)

    def when_values(
        self, path: str, when: dict[str, set[str]], attribute: str, values: list[str]
    ) -> None:
        self.own(path)
        for value in values:
            self.own(f"{path}[{value}]")
        when.setdefault(attribute, set()).update(values)

    def where(
        self, path: str, where: dict[str, dict[str, set[str]]], stated: WhereDef, is_new: bool
    ) -> None:
        if not where and not is_new:
            self.added_identity(path)
            return
        for end, attributes in _stated(stated):
            end_path = f"{path}.{end}"
            if not attributes:
                if where.get(end) and not is_new:
                    self.removed(end_path)
                continue
            if end not in where and not is_new:
                self.added_identity(end_path)
                continue
            current = where.setdefault(end, {})
            for attribute, values in attributes.items():
                where_path = f"{end_path}.{attribute}"
                if attribute not in current and not is_new:
                    self.added_identity(where_path)
                elif not values and not is_new:
                    self.removed(where_path)
                else:
                    self.own(where_path)
                    for value in values:
                        self.own(f"{where_path}[{value}]")
                    current.setdefault(attribute, set()).update(values)

    def added_identity(self, path: str) -> None:
        self.problem(
            "stack.added-identity",
            path,
            "a later pack cannot add an identity constraint to an inherited definition "
            "that had none; leave it out",
        )

    def identity(
        self, kind: str, path: str, state: dict[str, Any], stated: list[Any] | None, is_new: bool
    ) -> None:
        keys: list[Key] = []
        for entry in stated or ():
            if kind == "entities":
                during = (entry.during[0], entry.during[1]) if entry.during else None
                key = Key(tuple(entry.key), during)
            else:
                key = Key(tuple(sorted(entry)))
            if key not in keys and key not in state["identity"]:
                keys.append(key)
                self.own(f"{path}[{'+'.join(key.attributes)}]")
        if not stated and state["identity"] and not is_new:
            self.removed(path)
        # A later pack's keys are tried before the inherited ones (research R3).
        state["identity"] = keys + state["identity"]

    def required(
        self, path: str, state: dict[str, Any], stated: list[str] | None, is_new: bool
    ) -> None:
        if is_new:
            state["required"] = set(stated or ())
            return
        if not stated:
            if state["required"]:
                self.removed(path)
            return
        attributes = state["attributes"]
        already = state["required"] | {name for name in attributes if attributes[name]["required"]}
        for position, name in enumerate(stated):
            if name not in already:
                self.required_on_inherited(f"{path}[{position}]")

    def corroborate(
        self, path: str, state: dict[str, Any], stated: list[str], is_new: bool
    ) -> None:
        if is_new:
            state["corroborate"] = set(stated)
            for relation in stated:
                self.own(f"{path}[{relation}]")
        elif not state["corroborate"]:
            self.added_identity(path)
        elif set(stated) != state["corroborate"]:
            self.differs("stack.changed-identity", path)

    # The rest of a file

    def apply_enums(self, enums: Mapping[str, list[str] | None]) -> None:
        for name, values in enums.items():
            path = f"enums.{name}"
            current = self.enums.get(name)
            if current is None:
                if not values:
                    self.problem(
                        "file.invalid-value", path, "a new enum needs at least one value; add some"
                    )
                current = self.enums[name] = set()
                self.own(path)
            elif not values:
                self.removed(path)
                continue
            for value in values or ():
                self.own(f"{path}[{value}]")
                current.add(value)

    def question(self, position: int, question_id: str, text: str, needs: tuple[str, ...]) -> None:
        question = CompetencyQuestion(question_id, text, needs)
        known = self.questions.get(question_id)
        if known is None:
            self.questions[question_id] = (question, self.index)
            self.own(question_path(question_id))
        elif known[0] != question:
            pack = self.files[known[1]].info.name
            self.problem(
                "stack.duplicate-question",
                f"competency_questions[{position}]",
                f"pack `{pack}` has a different question with the id `{question_id}`; "
                "pick another id",
            )

    # After the last file

    def resolve_is_a(self) -> None:
        """Copy each `is_a` parent's roles, attributes and, unless stated, time; parents first."""
        events = self.definitions["events"]
        resolved: set[str] = set()

        def resolve(name: str, path: tuple[str, ...]) -> None:
            if name in resolved:
                return
            resolved.add(name)
            parent_name = events[name]["is_a"]
            # A missing parent or a loop is reported by the checks (ref.is-a).
            if parent_name not in events or parent_name in path:
                return
            resolve(parent_name, (*path, name))
            self.inherit(name, events[name], events[parent_name])

        for name in events:
            resolve(name, ())

    def inherit(self, name: str, child: dict[str, Any], parent: dict[str, Any]) -> None:
        path = f"events.{name}"
        for role, types in parent["roles"].items():
            child["roles"][role] = child["roles"].get(role, set()) | types
        for attribute_name, attribute in parent["attributes"].items():
            mine = child["attributes"].get(attribute_name)
            if mine is None:
                # is_a does not pass on `required` (research R3).
                child["attributes"][attribute_name] = {**attribute, "required": False}
                continue
            where = f"{path}.attributes.{attribute_name}"
            for key, rule in _ATTRIBUTE_RULES.items():
                if mine[key] != attribute[key]:
                    self.problem(
                        rule,
                        f"{where}.{key}",
                        f"this differs from the parent type `{child['is_a']}`; "
                        "restate the parent's attribute word for word or leave it out",
                        owner_of(self.owners, where),
                    )
                    break
        # A subtype may state its own time: a conference runs for days under a point-time
        # Event (ADR 0023).
        if child["time"] is None:
            child["time"] = parent["time"]

    def freeze(self) -> PackStack:
        top = self.files[-1].info
        questions = tuple(question for question, _ in self.questions.values())
        retrieval = self.retrieval
        return PackStack(
            name=top.name,
            version=top.version,
            mode=self.mode,
            # load_pack hashes the stack once it is checked (hashing.stamped).
            stamp=Stamp(top.name, top.version, ""),
            index_hash="",
            glossary_hash="",
            packs=tuple(file.info for file in self.files),
            entities=_frozen_map(self.definitions["entities"], _entity),
            relations=_frozen_map(self.definitions["relations"], _relation),
            events=_frozen_map(self.definitions["events"], _event),
            facts=_frozen_map(self.definitions["facts"], _fact),
            enums=MappingProxyType(
                {name: tuple(sorted(self.enums[name])) for name in sorted(self.enums)}
            ),
            not_entities=tuple(sorted(self.not_entities)),
            retrieval=Retrieval(
                hub_penalty=tuple(sorted(retrieval["hub_penalty"])),
                max_hops=retrieval["max_hops"],
                context_relations=tuple(sorted(retrieval["context_relations"])),
            ),
            glossary=tuple(self.glossary),
            competency_questions=questions,
            origins=MappingProxyType(
                {path: self.files[self.owners[path]].info.name for path in sorted(self.owners)}
            ),
        )


def _frozen_map(
    definitions: dict[str, dict[str, Any]], freeze: Callable[[str, dict[str, Any]], _T]
) -> Mapping[str, _T]:
    return MappingProxyType({name: freeze(name, definitions[name]) for name in sorted(definitions)})


def _attributes(state: dict[str, Any]) -> Mapping[str, Attribute]:
    attributes = state["attributes"]
    return MappingProxyType(
        {
            name: Attribute(
                name=name,
                range=attributes[name]["range"],
                multivalued=attributes[name]["multivalued"],
                unit=attributes[name]["unit"],
                description=attributes[name]["description"],
                compare=attributes[name]["compare"],
                unique=attributes[name]["unique"],
            )
            for name in sorted(attributes)
        }
    )


def _required(state: dict[str, Any]) -> tuple[str, ...]:
    attributes = state["attributes"]
    marked = {name for name in attributes if attributes[name]["required"]}
    return tuple(sorted(state["required"] | marked))


def _types(roles: dict[str, set[str]]) -> Mapping[str, tuple[str, ...]]:
    return MappingProxyType({name: tuple(sorted(roles[name])) for name in sorted(roles)})


def _shared(state: dict[str, Any]) -> dict[str, Any]:
    """The fields every kind but relations has, frozen."""
    return {
        "description": state["description"] or "",
        "examples": state["examples"],
        "aliases": state["aliases"],
        "attributes": _attributes(state),
        "required": _required(state),
        "extract": state["extract"],
        "agent_visible": state["agent_visible"],
        "exact_mappings": tuple(sorted(state["exact_mappings"])),
        "deprecated": state["deprecated"],
        "renamed_from": state["renamed_from"],
    }


def _entity(name: str, state: dict[str, Any]) -> EntityType:
    scope = state["scope"]
    return EntityType(
        name=name,
        scope=None
        if scope is None
        else Scope(
            role=scope["role"],
            to=tuple(sorted(scope["to"])),
            inherit=scope["inherit"],
            when=_types(scope["when"]),
        ),
        identity=tuple(state["identity"]),
        vetoes=tuple(sorted(state["vetoes"])),
        names=NameRule(state["names"]),
        corroborate=tuple(sorted(state["corroborate"])),
        version_start=state["version_start"],
        document_link=tuple(sorted(state["document_link"])),
        **_shared(state),
    )


def _relation(name: str, state: dict[str, Any]) -> RelationType:
    cardinality = state["cardinality"]
    return RelationType(
        name=name,
        description=state["description"],
        from_types=tuple(sorted(state["from"])),
        to_types=tuple(sorted(state["to"])),
        where=MappingProxyType(
            {end: _types(state["where"][end]) for end in sorted(state["where"])}
        ),
        time=state["time"],
        attributes=_attributes(state),
        value=state["value"],
        cardinality=None if cardinality is None else tuple(sorted(cardinality)),
        required=_required(state),
        extract=state["extract"],
        exact_mappings=tuple(sorted(state["exact_mappings"])),
        deprecated=state["deprecated"],
        renamed_from=state["renamed_from"],
    )


def _event(name: str, state: dict[str, Any]) -> EventType:
    return EventType(
        name=name,
        is_a=state["is_a"],
        roles=_types(state["roles"]),
        time=state["time"] or "none",
        identity=tuple(state["identity"]),
        **_shared(state),
    )


def _fact(name: str, state: dict[str, Any]) -> FactType:
    return FactType(
        name=name,
        roles=_types(state["roles"]),
        time=state["time"],
        version_key=tuple(sorted(state["version_key"])),
        **_shared(state),
    )
