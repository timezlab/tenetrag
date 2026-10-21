"""The store schema of a pack stack (specs/003-stores-and-contract-suite, protocols.md §4)."""

from __future__ import annotations

from tenetrag.packs.stack import PackStack
from tenetrag.protocols.stores import StoreSchema


def store_schema(stack: PackStack) -> StoreSchema:
    """Every type of the stack, `extract: false` included.

    A later pack version may extract a type the store must already hold.
    StoreSchema raises ConfigError when it refuses a name.
    """
    return StoreSchema(
        entity_types=tuple(stack.entities),
        event_types=tuple(stack.events),
        fact_types=tuple(stack.facts),
        relation_types=tuple(stack.relations),
    )
