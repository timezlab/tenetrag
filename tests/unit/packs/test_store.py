"""The store schema built from a pack stack (contracts/protocols.md §4, data-model §5.1).

Behaviours:
1. `core`, `enterprise-docs` and the `finance` draft each build a schema.
2. It holds every entity, event, fact and relation type of the stack,
   `extract: false` types included.
"""

from __future__ import annotations

import pytest

from tenetrag.packs import load_pack, store_schema
from tests.support.packs import FINANCE_DRAFT


@pytest.mark.parametrize("reference", ["core", "enterprise-docs", FINANCE_DRAFT])
def test_store_schema_shipped(reference: object):
    stack = load_pack(reference)  # type: ignore[arg-type]

    schema = store_schema(stack)

    assert schema.entity_types == tuple(sorted(stack.entities))
    assert schema.event_types == tuple(sorted(stack.events))
    assert schema.fact_types == tuple(sorted(stack.facts))
    assert schema.relation_types == tuple(sorted(stack.relations))


def test_store_schema_core():
    stack = load_pack("core")

    schema = store_schema(stack)

    assert "PART_OF" in schema.relation_types
    assert "Event" in schema.event_types
    assert stack.facts["Statement"].extract is False
    assert "Statement" in schema.fact_types
