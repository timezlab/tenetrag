"""The graph results a correct engine derives (contracts/corpus.md, engine brief §3.1 and §3.2).

- Mentions with one world id are one entity.
- A relation type with `one_at_a_time` groups by the ends it lists, and a
  fact type with `version_key` groups by the parts of that key.
- A member starts at its `valid_from`, else the document's
  `effective_from`, else the document date (`issued_on`, then `held_on`).
- Inside a group, the newest start is `current` and each older member is
  `superseded`, closed at the next start unless it states its own end;
  members sharing the newest start are all `conflicting`.
"""

from __future__ import annotations

from typing import Any, NamedTuple

from tenetrag.packs import PackStack
from tests.support.corpus.checks import refs
from tests.support.corpus.facts import (
    Document,
    EntityItem,
    FactTable,
    RelationItem,
    StatementItem,
)
from tests.support.corpus.problems import Problem

Item = EntityItem | RelationItem | StatementItem
# Relation ends as `one_at_a_time` names them (domain-packs.md).
_ENDS = ("subject", "object")


class Member(NamedTuple):
    item: str
    document: str
    start: str
    states_end: bool


def position(item_id: str) -> tuple[int, int]:
    """`D2.10` after `D2.9`, and `D10.1` after `D9.1`."""
    document, number = item_id[1:].split(".")
    return int(document), int(number)


def start_of(item: RelationItem | StatementItem, document: Document) -> str | None:
    dates = document.dates
    return (
        item.valid_from
        or dates.get("effective_from")
        or dates.get("issued_on")
        or dates.get("held_on")
    )


def issuer_of(
    table: FactTable, document: Document, item: StatementItem, world_of: dict[str, str]
) -> str:
    """The scope of the entity in the `source` role, else the document's issuer (§3.2)."""
    source = item.roles.get("source")
    if source is not None:
        world_id = world_of.get(refs(source)[0])
        scope = table.world.entities[world_id].scope if world_id is not None else None
        if scope is not None:
            return scope
    return document.issuer


def group_of(
    table: FactTable,
    document: Document,
    item: Item,
    world_of: dict[str, str],
    stack: PackStack,
) -> str | None:
    """The version group id: the type, then each key part as `name=value`, joined by `;`."""
    if isinstance(item, RelationItem):
        cardinality = stack.relations[item.type].cardinality
        if cardinality is None:
            return None
        ends = dict(zip(_ENDS, (world_of[item.from_], world_of[item.to]), strict=True))
        return f"{item.type}:" + ";".join(f"{end}={ends[end]}" for end in cardinality)
    if not isinstance(item, StatementItem) or item.kind != "fact":
        return None
    parts = []
    for name in stack.facts[item.type].version_key:
        if name == "issuer":
            value = issuer_of(table, document, item, world_of)
        elif name in item.roles:
            value = ",".join(sorted(world_of.get(ref, ref) for ref in refs(item.roles[name])))
        elif name in item.attributes:
            value = item.attributes[name].value
        else:
            continue
        parts.append(f"{name}={value}")
    return f"{item.type}:" + ";".join(parts) if parts else None


def statuses(members: list[Member]) -> list[dict[str, str]]:
    ordered = sorted(members, key=lambda member: (member.start, position(member.item)))
    if not ordered:
        return []
    newest = ordered[-1].start
    shared = sum(1 for member in ordered if member.start == newest) > 1
    result = []
    for member in ordered:
        if member.start == newest:
            status, closed_at = ("conflicting" if shared else "current"), ""
        else:
            status = "superseded"
            later = next(other.start for other in ordered if other.start > member.start)
            closed_at = "" if member.states_end else later
        result.append({"closed_at": closed_at, "item": member.item, "status": status})
    return result


def world_ids(table: FactTable) -> dict[str, str]:
    """Each entity item's world id."""
    return {
        item.id: item.world
        for document in table.documents
        for item in document.items
        if isinstance(item, EntityItem)
    }


def derive(table: FactTable, stack: PackStack) -> tuple[dict[str, Any], list[Problem]]:
    """graph.json's content, and the problems that keep a member from having a start."""
    world_of = world_ids(table)
    entities: dict[str, list[str]] = {}
    members: dict[str, list[Member]] = {}
    supersedes = []
    problems = []
    for document in table.documents:
        for item in document.items:
            if isinstance(item, EntityItem):
                entities.setdefault(item.world, []).append(item.id)
                continue
            if item.type == "SUPERSEDES" and isinstance(item, RelationItem):
                supersedes.append(
                    {"from": world_of[item.from_], "item": item.id, "to": world_of[item.to]}
                )
            group = group_of(table, document, item, world_of, stack)
            if group is None:
                continue
            start = start_of(item, document)
            if start is None:
                problems.append(
                    Problem(
                        f"documents/{document.id}.yaml",
                        f"items[{item.id}]",
                        "a version needs a start: state `valid_from` or a document date",
                    )
                )
                continue
            member = Member(item.id, document.id, start, item.valid_to is not None)
            members.setdefault(group, []).append(member)

    versions = {group: statuses(group_members) for group, group_members in members.items()}
    deletions = {}
    for document_id in table.graph.deletions:
        changed = {}
        for group, group_members in members.items():
            remaining = [member for member in group_members if member.document != document_id]
            if len(remaining) == len(group_members):
                continue
            kept = {member.item for member in remaining}
            after = statuses(remaining)
            if not remaining or after != [m for m in versions[group] if m["item"] in kept]:
                changed[group] = after
        deletions[document_id] = {"versions": changed}
    graph = {
        "deletions": deletions,
        "entities": entities,
        "supersedes": supersedes,
        "text_in": [link.model_dump() for link in table.graph.text_in],
        "versions": versions,
    }
    return graph, problems
