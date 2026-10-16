"""Checks over a fact table that read well (contracts/corpus.md, research R12, FR-039).

Every quote must occur in its document's rendered text, every ref and world
id must resolve, and every item must fit the shipped stack. The fit check
is small and local to the generator; feature 004's validator may replace
it. Each check collects problems and never stops at the first.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from datetime import date
from typing import Any

from tenetrag.packs import PackStack
from tests.support.corpus.facts import (
    Document,
    EntityItem,
    FactTable,
    RelationItem,
    StatementItem,
)
from tests.support.corpus.problems import Problem

STACK_NAME = "enterprise-docs"


def refs(value: str | list[str]) -> list[str]:
    return [value] if isinstance(value, str) else value


def lineage(stack: PackStack, type_name: str) -> set[str]:
    """The type and every event type it is a kind of."""
    names = {type_name}
    event = stack.events.get(type_name)
    while event is not None and event.is_a is not None and event.is_a not in names:
        names.add(event.is_a)
        event = stack.events.get(event.is_a)
    return names


def company(table: FactTable, world_id: str) -> str:
    """The top of a world entity's scope chain."""
    seen = {world_id}
    entities = table.world.entities
    while world_id in entities and entities[world_id].scope not in (None, *seen):
        world_id = entities[world_id].scope or world_id
        seen.add(world_id)
    return world_id


def check(table: FactTable, rendered: dict[str, str], stack: PackStack) -> list[Problem]:
    problems = list(_world_problems(table, stack))
    for document in table.documents:
        problems += _document_problems(table, document, rendered[document.id], stack)
    problems += _graph_problems(table, stack)
    problems += _golden_problems(table, stack)
    return problems


def _world_problems(table: FactTable, stack: PackStack) -> Iterator[Problem]:
    for world_id, entity in table.world.entities.items():
        where = f"entities[{world_id}]"
        definition = stack.entities.get(entity.type)
        if definition is None:
            yield Problem("world.yaml", f"{where}.type", f"`{entity.type}` is not an entity type")
            continue
        for name, value in entity.attributes.items():
            message = _attribute_problem(stack, entity.type, definition.attributes, name, value)
            if message:
                yield Problem("world.yaml", f"{where}.attributes.{name}", message)
        if entity.scope is None:
            continue
        if definition.scope is None:
            yield Problem("world.yaml", f"{where}.scope", f"`{entity.type}` has no scope")
            continue
        target = table.world.entities.get(entity.scope)
        if target is None:
            yield Problem("world.yaml", f"{where}.scope", f"`{entity.scope}` is not in world.yaml")
        elif target.type not in definition.scope.to:
            yield Problem(
                "world.yaml",
                f"{where}.scope",
                f"the scope of `{entity.type}` is a {' or '.join(definition.scope.to)}, "
                f"not a `{target.type}`",
            )


def _attribute_problem(
    stack: PackStack, owner: str, attributes: Mapping[str, Any], name: str, value: str
) -> str | None:
    attribute = attributes.get(name)
    if attribute is None:
        return f"`{owner}` has no attribute `{name}`"
    values = stack.enums.get(attribute.range)
    if values is not None and value not in values:
        return f"`{value}` is not a value of `{attribute.range}`"
    if attribute.range == "date":
        try:
            date.fromisoformat(value)
        except ValueError:
            return f"`{value}` is not an ISO date"
    return None


def _quotes(item: EntityItem | RelationItem | StatementItem) -> Iterator[tuple[str, str]]:
    """Each (path, text) the document's text must hold."""
    if isinstance(item, EntityItem):
        yield "surface", item.surface
        for index, former in enumerate(item.former_names):
            yield f"former_names[{index}].quote", former.quote
    else:
        yield "quote", item.quote
    for name, attribute in item.attributes.items():
        yield f"attributes.{name}.quote", attribute.quote


def _document_problems(
    table: FactTable, document: Document, text: str, stack: PackStack
) -> list[Problem]:
    file = f"documents/{document.id}.yaml"
    problems: list[Problem] = []

    def problem(path: str, message: str) -> None:
        problems.append(Problem(file, path, message))

    issuer = table.world.entities.get(document.issuer)
    if issuer is None:
        problem("issuer", f"`{document.issuer}` is not in world.yaml")
    elif issuer.type != "Organization":
        problem("issuer", f"`{document.issuer}` is a `{issuer.type}`, not an `Organization`")
    items: dict[str, EntityItem | RelationItem | StatementItem] = {}
    for number, item in enumerate(document.items, 1):
        # Numbered in order, so ids are unique and an item is easy to find by hand.
        if item.id != f"{document.id}.{number}":
            problem(
                f"items[{item.id}].id",
                f"items are numbered in order; expected `{document.id}.{number}`",
            )
        items[item.id] = item
    for item in document.items:
        where = f"items[{item.id}]"
        for path, quote in _quotes(item):
            if quote not in text:
                problem(f"{where}.{path}", f"not in the rendered text of {document.id}")
        for path, message in _item_problems(table, document, item, items, stack):
            problem(f"{where}{path}", message)
    return problems


def _item_problems(
    table: FactTable,
    document: Document,
    item: EntityItem | RelationItem | StatementItem,
    items: dict[str, EntityItem | RelationItem | StatementItem],
    stack: PackStack,
) -> Iterator[tuple[str, str]]:
    """Each (path below the item, message) that keeps the item from fitting the stack."""
    kind = item.kind
    definitions = {
        "entity": stack.entities,
        "relation": stack.relations,
        "event": stack.events,
        "fact": stack.facts,
    }[kind]
    definition = definitions.get(item.type)
    if definition is None:
        yield ".type", f"`{item.type}` is not an {kind} type of `{STACK_NAME}`"
        return
    if not definition.extract:
        yield ".type", f"`{item.type}` is not extracted under `{STACK_NAME}`"
    for name, attribute in item.attributes.items():
        message = _attribute_problem(stack, item.type, definition.attributes, name, attribute.value)
        if message:
            yield f".attributes.{name}", message

    if isinstance(item, EntityItem):
        entity = table.world.entities.get(item.world)
        if entity is None:
            yield ".world", f"`{item.world}` is not in world.yaml"
        elif entity.type != item.type:
            yield ".world", f"`{item.world}` is a `{entity.type}` in world.yaml"
        return

    if item.valid_from and item.valid_to and item.valid_to < item.valid_from:
        yield ".valid_to", "is before `valid_from`"

    if isinstance(item, RelationItem):
        for end, ref, allowed in (
            ("from", item.from_, definition.from_types),
            ("to", item.to, definition.to_types),
        ):
            target = items.get(ref)
            if target is None:
                yield f".{end}", f"`{ref}` is not an item of {document.id}"
            elif not isinstance(target, EntityItem):
                yield f".{end}", f"`{ref}` is not an entity"
            elif target.type not in allowed:
                yield f".{end}", f"`{item.type}` cannot have a `{target.type}` at its {end} end"
        for name in definition.required:
            if name not in item.attributes:
                yield "", f"`{item.type}` needs `{name}`"
        return

    roles = definition.roles
    for role, value in item.roles.items():
        if role not in roles:
            yield f".roles.{role}", f"`{item.type}` has no role `{role}`"
            continue
        for ref in refs(value):
            target = items.get(ref)
            if target is None:
                yield f".roles.{role}", f"`{ref}` is not an item of {document.id}"
            elif isinstance(target, RelationItem) or target.kind == "fact":
                yield f".roles.{role}", f"`{ref}` is not an entity or an event"
            elif not lineage(stack, target.type) & set(roles[role]):
                yield (
                    f".roles.{role}",
                    f"role `{role}` of `{item.type}` cannot hold a `{target.type}`",
                )
    for name in definition.required:
        if name not in item.roles and name not in item.attributes:
            yield "", f"`{item.type}` needs `{name}`"


def _graph_problems(table: FactTable, stack: PackStack) -> Iterator[Problem]:
    documents = {document.id: document for document in table.documents}
    for index, document_id in enumerate(table.graph.deletions):
        if document_id not in documents:
            yield Problem("graph.yaml", f"deletions[{index}]", f"`{document_id}` is not a document")
    for index, link in enumerate(table.graph.text_in):
        where = f"text_in[{index}]"
        entity = table.world.entities.get(link.entity)
        document = documents.get(link.document)
        if entity is None:
            yield Problem("graph.yaml", f"{where}.entity", f"`{link.entity}` is not in world.yaml")
        if document is None:
            yield Problem("graph.yaml", f"{where}.document", f"`{link.document}` is not a document")
        if entity is None or document is None:
            continue
        definition = stack.entities.get(entity.type)
        if definition is None or not definition.document_link:
            yield Problem("graph.yaml", f"{where}.entity", f"`{entity.type}` has no document link")
            continue
        title = entity.attributes.get("title", "")
        if title.casefold() != document.title.casefold():
            yield Problem(
                "graph.yaml",
                f"{where}.entity",
                f"the title of `{link.entity}` is not the title of {document.id}",
            )
        if entity.scope is not None and company(table, link.entity) != company(
            table, document.issuer
        ):
            yield Problem(
                "graph.yaml",
                f"{where}.entity",
                f"the scope of `{link.entity}` conflicts with the issuer of {document.id}",
            )


def _golden_problems(table: FactTable, stack: PackStack) -> Iterator[Problem]:
    documents = {document.id for document in table.documents}
    competency = {question.id for question in stack.competency_questions}
    seen: set[str] = set()
    for question in table.golden.questions:
        where = f"questions[{question.id}]"
        if question.id in seen:
            yield Problem("golden.yaml", f"{where}.id", "appears twice")
        seen.add(question.id)
        for source in question.expected_sources:
            if source not in documents:
                yield Problem(
                    "golden.yaml", f"{where}.expected_sources", f"`{source}` is not a document"
                )
        for cq in question.cq:
            if cq not in competency:
                yield Problem("golden.yaml", f"{where}.cq", f"`{cq}` is not a competency question")
        if (question.as_of is not None) != (question.qtype == "as_of"):
            yield Problem("golden.yaml", f"{where}.as_of", "is given for `as_of` questions only")
