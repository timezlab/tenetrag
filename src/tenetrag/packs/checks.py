"""Checks over the merged stack (data-model §1, research R5).

Private to `tenetrag.packs`. References are checked once the whole stack
is merged, since any pack in it may define a name. Each file's own
definitions are checked against the merged stack, so a problem names the
file and the place in it that holds the reference. A name whose
definition was set aside for a file problem still counts as defined, so a
misspelt field does not also report every reference to that type
(research R4).
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Collection, Iterable, Iterator, Mapping, Sequence

from pydantic import BaseModel

from tenetrag.packs.coverage import check_coverage
from tenetrag.packs.format import (
    BUILTIN_RANGES,
    AttributeDef,
    EntityDef,
    EventDef,
    FactDef,
    ParsedPack,
    RelationDef,
)
from tenetrag.packs.problems import PackProblem, Severity
from tenetrag.packs.stack import Attribute, EventType, Mode, NameRule
from tenetrag.packs.stacking import KINDS, PackFile, Stacked, owner_of, question_path

# Text that reads like an instruction to the model (research R5), matched
# after NFC and case folding. Whole words only, and no generic call syntax,
# which would flag "customer(s)".
_INSTRUCTION = re.compile(
    r"(?<!\w)(?:ignore|disregard|you\s+must|you\s+should|you\s+are|system\s+prompt"
    r"|previous\s+instructions|bỏ\s+qua|bạn\s+phải|bạn\s+là"
    r"|describe_schema|find_entities|get_entity|get_neighbors|get_sources)(?!\w)"
    r"|(?<!\w)retrieve\("
    r"|(?<![\w.+-])[a-z][a-z0-9+.-]*://"
    r"|(?<!\w)www\."
)

_VETO_RANGES = frozenset({"str", "date", "int"})
_NAME_ATTRIBUTES = frozenset({"name", "title"})
_NOUNS = {
    "entities": "entity type",
    "relations": "relation",
    "events": "event type",
    "facts": "fact type",
    "enums": "enum",
}


def check_stack(stacked: Stacked, files: Sequence[PackFile]) -> list[PackProblem]:
    """Every problem the merged stack has; warnings have severity "warning"."""
    checker = _Checker(stacked, files)
    for file in files:
        checker.file(file)
    checker.kind_clashes()
    checker.is_a()
    checker.identity()
    checker.glossary()
    checker.coverage()
    return checker.problems


class _Checker:
    def __init__(self, stacked: Stacked, files: Sequence[PackFile]) -> None:
        self.stack = stacked.stack
        self.owners = stacked.owners
        self.files = files
        self.label = ""
        self.problems: list[PackProblem] = []
        self.set_aside = {
            kind: set().union(*(file.parsed.set_aside.get(kind, set()) for file in files))
            for kind in _NOUNS
        }

    def problem(
        self,
        rule: str,
        path: str,
        message: str,
        *,
        label: str | None = None,
        severity: Severity = "error",
    ) -> None:
        self.problems.append(PackProblem(rule, label or self.label, path, message, severity))

    def label_of(self, path: str) -> str:
        """The file that added the element at `path`, or the nearest one enclosing it."""
        return self.files[owner_of(self.owners, path)].label

    def defined(self, kind: str, name: str) -> bool:
        return name in getattr(self.stack, kind) or name in self.set_aside[kind]

    def unknown(self, path: str, message: str) -> None:
        self.problem("ref.unknown", path, message)

    # One file's references

    def file(self, file: PackFile) -> None:
        self.label = file.label
        parsed = file.parsed
        for name, entity in parsed.entities.items():
            if entity is not None and name in self.stack.entities:
                self.entity(name, entity, parsed.listed_keys.get(name, ()))
        for name, relation in parsed.relations.items():
            if relation is not None and name in self.stack.relations:
                self.relation(name, relation)
        for name, event in parsed.events.items():
            if event is not None and name in self.stack.events:
                self.event(name, event)
        for name, fact in parsed.facts.items():
            if fact is not None and name in self.stack.facts:
                self.fact(name, fact)
        for position, entry in parsed.glossary:
            self.type_ref(f"glossary[{position}].type", entry.type, ("entities",))
        if parsed.retrieval is not None:
            for index, name in enumerate(parsed.retrieval.hub_penalty or ()):
                self.type_ref(f"retrieval.hub_penalty[{index}]", name, ("entities",))
            for index, name in enumerate(parsed.retrieval.context_relations or ()):
                self.type_ref(f"retrieval.context_relations[{index}]", name, ("relations",))
        self.texts(parsed)

    def type_ref(self, path: str, name: str, kinds: tuple[str, ...]) -> None:
        if not any(self.defined(kind, name) for kind in kinds):
            noun = " or ".join(_NOUNS[kind] for kind in kinds)
            self.unknown(path, f"no {noun} `{name}`; define it or use one of the stack's")

    def ranges(self, path: str, attributes: dict[str, AttributeDef] | None) -> None:
        for name, attribute in (attributes or {}).items():
            if attribute.range is not None:
                self.range_ref(f"{path}.attributes.{name}.range", attribute.range)

    def range_ref(self, path: str, range_: str) -> None:
        if range_ not in BUILTIN_RANGES and not self.defined("enums", range_):
            self.unknown(path, f"no enum `{range_}`; use a built-in range or define the enum")

    def names(
        self, path: str, names: Sequence[str] | None, allowed: Collection[str], what: str
    ) -> None:
        """Report each of `names` that `allowed` lacks, at `path[i]`."""
        for index, name in enumerate(names or ()):
            if name not in allowed:
                self.unknown(f"{path}[{index}]", f"no {what} `{name}` on this type")

    def enum_values(
        self, path: str, attribute: Attribute | None, name: str, values: Sequence[str]
    ) -> None:
        """A condition on an enum attribute: it exists, is an enum, and has the values."""
        if attribute is None:
            self.unknown(path, f"no attribute `{name}` on this type")
        elif attribute.range not in self.stack.enums:
            if attribute.range not in self.set_aside["enums"]:
                self.problem(
                    "ref.where-not-enum",
                    path,
                    "a condition needs an attribute whose range is an enum",
                )
        else:
            self.names(path, values, self.stack.enums[attribute.range], "enum value")

    def entity(self, name: str, definition: EntityDef, listed: tuple[bool, ...]) -> None:
        path = f"entities.{name}"
        merged = self.stack.entities[name]
        attributes = merged.attributes
        self.ranges(path, definition.attributes)
        if definition.scope is not None:
            for index, target in enumerate(definition.scope.to or ()):
                self.type_ref(f"{path}.scope.to[{index}]", target, ("entities",))
            for attribute, values in (definition.scope.when or {}).items():
                where = f"{path}.scope.when.{attribute}"
                self.enum_values(where, attributes.get(attribute), attribute, values)
        for index, key in enumerate(definition.identity or ()):
            is_listed = listed[index] if index < len(listed) else True
            key_path = f"{path}.identity[{index}]" + ("" if is_listed else ".key")
            for position, part in enumerate(key.key):
                if part == "scope" and merged.scope is None:
                    self.unknown(
                        f"{key_path}[{position}]",
                        "`scope` stands for the type's scope, and this type has none",
                    )
                elif part != "scope" and part not in attributes:
                    self.unknown(f"{key_path}[{position}]", f"no attribute `{part}` on this type")
            self.names(f"{path}.identity[{index}].during", key.during, attributes, "attribute")
        for field in ("vetoes", "version_start", "document_link", "required"):
            self.names(f"{path}.{field}", getattr(definition, field), attributes, "attribute")
        for index, relation in enumerate(definition.corroborate or ()):
            self.type_ref(f"{path}.corroborate[{index}]", relation, ("relations",))

    def relation(self, name: str, definition: RelationDef) -> None:
        path = f"relations.{name}"
        merged = self.stack.relations[name]
        for end, types in (("from", definition.from_), ("to", definition.to)):
            for index, target in enumerate(types or ()):
                self.type_ref(f"{path}.{end}[{index}]", target, ("entities",))
        self.ranges(path, definition.attributes)
        if definition.value is not None:
            self.range_ref(f"{path}.value", definition.value)
        if definition.where is not None:
            ends = (
                ("from", definition.where.from_, merged.from_types),
                ("to", definition.where.to, merged.to_types),
            )
            for end, conditions, end_types in ends:
                for attribute, values in (conditions or {}).items():
                    self.where(f"{path}.where.{end}.{attribute}", attribute, values, end_types)
        if definition.cardinality is not None:
            self.names(
                f"{path}.cardinality.one_at_a_time",
                definition.cardinality.one_at_a_time,
                ("subject", "object"),
                "end (use subject or object)",
            )
        self.names(f"{path}.required", definition.required, merged.attributes, "attribute")

    def where(self, path: str, attribute: str, values: Sequence[str], types: Sequence[str]) -> None:
        """A `where` attribute must be an enum on every type its endpoint allows."""
        enums = set()
        for type_name in types:
            entity = self.stack.entities.get(type_name)
            if entity is None:
                continue  # set aside, or reported as unknown
            found = entity.attributes.get(attribute)
            if found is None or found.range not in self.stack.enums:
                self.problem(
                    "ref.where-not-enum",
                    path,
                    "a `where` attribute must be an enum on every type this end allows",
                )
                return
            enums.add(found.range)
        for index, value in enumerate(values):
            if any(value not in self.stack.enums[enum] for enum in enums):
                self.unknown(
                    f"{path}[{index}]", f"`{value}` is not a value of the attribute's enum"
                )

    def event(self, name: str, definition: EventDef) -> None:
        path = f"events.{name}"
        merged = self.stack.events[name]
        self.roles(path, definition.roles)
        self.ranges(path, definition.attributes)
        parts = {"time", *merged.roles, *merged.attributes}
        for index, entry in enumerate(definition.identity or ()):
            self.names(f"{path}.identity[{index}]", entry, parts, "role or attribute")
        self.names(f"{path}.required", definition.required, parts - {"time"}, "role or attribute")

    def fact(self, name: str, definition: FactDef) -> None:
        path = f"facts.{name}"
        merged = self.stack.facts[name]
        self.roles(path, definition.roles)
        self.ranges(path, definition.attributes)
        parts = {*merged.roles, *merged.attributes}
        self.names(
            f"{path}.version_key", definition.version_key, parts | {"issuer"}, "role or attribute"
        )
        self.names(f"{path}.required", definition.required, parts, "role or attribute")

    def roles(self, path: str, roles: dict[str, list[str]] | None) -> None:
        for role, types in (roles or {}).items():
            for index, target in enumerate(types):
                self.type_ref(f"{path}.roles.{role}[{index}]", target, ("entities", "events"))

    def texts(self, parsed: ParsedPack) -> None:
        severity: Severity = "error" if self.stack.mode is Mode.STRICT else "warning"
        for path, text in _texts(parsed):
            folded = unicodedata.normalize("NFC", text).casefold()
            if _INSTRUCTION.search(folded):
                self.problem(
                    "text.instruction",
                    path,
                    "reads like an instruction to the model; describe the type instead",
                    severity=severity,
                )

    # The merged stack

    def kind_clashes(self) -> None:
        """One name, two kinds: reported on the one added later."""
        order = {kind: position for position, kind in enumerate(_NOUNS)}
        added = sorted(
            (self.owners[f"{kind}.{name}"], order[kind], kind, name)
            for kind in _NOUNS
            for name in getattr(self.stack, kind)
        )
        first: dict[str, tuple[str, int]] = {}
        for owner, _, kind, name in added:
            if name not in first:
                first[name] = (kind, owner)
                continue
            other_kind, other_owner = first[name]
            pack = self.files[other_owner].info.name
            self.problem(
                "ref.kind-clash",
                f"{kind}.{name}",
                f"the name is already the {_NOUNS[other_kind]} of pack `{pack}`; pick another",
                label=self.files[owner].label,
            )

    def is_a(self) -> None:
        events = self.stack.events
        for name, event in events.items():
            parent = event.is_a
            if parent is None or (parent not in events and parent in self.set_aside["events"]):
                continue
            path = f"events.{name}.is_a"
            if parent not in events:
                message = "names no event type; use an event type such as `Event`"
            elif _loops(name, events):
                message = "`is_a` comes back to this type; break the loop"
            else:
                continue
            self.problem("ref.is-a", path, message, label=self.label_of(path))

    def identity(self) -> None:
        """The identity lint of ADR 0016 over every merged entity type."""
        for name, entity in self.stack.entities.items():
            path = f"entities.{name}"
            attributes = entity.attributes
            for key in entity.identity:
                key_path = f"{path}.identity[{'+'.join(key.attributes)}]"
                if (
                    entity.scope is not None
                    and "scope" not in key.attributes
                    and any(
                        attributes[part].unique == "scope"
                        for part in key.attributes
                        if part in attributes
                    )
                ):
                    self.lint(
                        "identity.key-needs-scope",
                        key_path,
                        "the key holds an attribute unique only within a scope; add `scope` to it",
                    )
                if any(
                    other.during is None and set(other.attributes) < set(key.attributes)
                    for other in entity.identity
                ):
                    self.lint(
                        "identity.key-not-minimal",
                        key_path,
                        "the key contains another key of this type; drop it or the extra parts",
                    )
            for veto in entity.vetoes:
                self.veto(f"{path}.vetoes[{veto}]", veto, attributes.get(veto))
            if entity.names is NameRule.VERSIONED and not entity.version_start:
                self.lint(
                    "identity.versioned-needs-start",
                    f"{path}.names",
                    "`names: versioned` needs `version_start`, "
                    "the date attributes a version starts on",
                )
            if entity.names is NameRule.EVIDENCE and not entity.corroborate:
                self.lint(
                    "identity.evidence-without-corroborate",
                    f"{path}.names",
                    "`names: evidence` has no `corroborate`, "
                    "so every shared name goes to the model",
                    severity="warning",
                )

    def veto(self, path: str, name: str, attribute: Attribute | None) -> None:
        if attribute is None:
            return  # reported as unknown where the veto is written
        if name in _NAME_ATTRIBUTES:
            rule, message = "identity.veto-is-name", "a name never vetoes a merge; veto on a key"
        elif attribute.multivalued:
            rule, message = "identity.veto-multivalued", "a veto needs a single-valued attribute"
        elif attribute.range not in _VETO_RANGES:
            rule, message = "identity.veto-range", "a veto's range must be str, date or int"
        else:
            return
        self.lint(rule, path, message)

    def lint(self, rule: str, path: str, message: str, *, severity: Severity = "error") -> None:
        self.problem(rule, path, message, label=self.label_of(path), severity=severity)

    def glossary(self) -> None:
        """An alias maps to at most one glossary entry of a type (FR-012)."""
        first: dict[tuple[str, str], int] = {}
        number = 0
        for file in self.files:
            for position, entry in file.parsed.glossary:
                number += 1
                texts = [(f"glossary[{position}].name", entry.name)]
                texts += [
                    (f"glossary[{position}].aliases[{index}]", alias)
                    for index, alias in enumerate(entry.aliases or ())
                ]
                for path, text in texts:
                    key = (entry.type, unicodedata.normalize("NFC", text).casefold())
                    if first.setdefault(key, number) != number:
                        self.problem(
                            "glossary.alias-clash",
                            path,
                            "another glossary entry of this type already has this name or alias; "
                            "keep it on one entry",
                            label=file.label,
                        )

    def coverage(self) -> None:
        """A competency question the stack cannot answer warns once (FR-026, research R9).

        The warning sits at the question, in the file that holds it, and names
        what it lacks but not its text, as no message repeats a file's text.
        """
        for question in check_coverage(self.stack).questions:
            if question.passed:
                continue
            lacks, fixes = [], []
            if question.missing:
                lacks.append(f"no pack defines {_listed(question.missing)}")
                fixes.append("define the missing names")
            if question.not_extracted:
                lacks.append(f"`extract: false` on {_listed(question.not_extracted)}")
                fixes.append("set `extract: true` in a child pack")
            path = question_path(question.id)
            self.problem(
                "coverage.unmet",
                path,
                f"the stack cannot answer this question: {'; '.join(lacks)}; "
                f"{' or '.join(fixes)}, or change its `needs`",
                label=self.label_of(path),
                severity="warning",
            )


def _listed(names: Iterable[str]) -> str:
    return ", ".join(f"`{name}`" for name in names)


def _loops(name: str, events: Mapping[str, EventType]) -> bool:
    seen = {name}
    current = events[name].is_a
    while current is not None and current in events:
        if current in seen:
            return current == name
        seen.add(current)
        current = events[current].is_a
    return False


def _texts(parsed: ParsedPack) -> Iterator[tuple[str, str]]:
    """Every text of one file a model sees, with its path."""
    for kind in KINDS:
        definitions: dict[str, BaseModel | None] = getattr(parsed, kind)
        for name, definition in definitions.items():
            if definition is None:
                continue
            path = f"{kind}.{name}"
            description = getattr(definition, "description", None)
            if description:
                yield f"{path}.description", description
            for field in ("examples", "aliases"):
                for index, text in enumerate(getattr(definition, field, None) or ()):
                    yield f"{path}.{field}[{index}]", text
            attributes: dict[str, AttributeDef] = getattr(definition, "attributes", None) or {}
            for attribute, value in attributes.items():
                if value.description:
                    yield f"{path}.attributes.{attribute}.description", value.description
    for _, question in parsed.questions:
        yield f"competency_questions[{question.id}].text", question.text
    for position, entry in parsed.glossary:
        yield f"glossary[{position}].name", entry.name
        for index, alias in enumerate(entry.aliases or ()):
            yield f"glossary[{position}].aliases[{index}]", alias
        if entry.note:
            yield f"glossary[{position}].note", entry.note
