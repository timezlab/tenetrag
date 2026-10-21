"""Store protocols and the store schema (contracts/protocols.md §2 to §4, data-model §5).

Behaviours:
1. Importing tenetrag.protocols loads only the standard library and tenetrag.
2. GraphStore has the methods of engine brief §6.1 less the six community
   methods, plus renew_writer and release_writer; VectorStore those of §6.2.
3. HopSpec limits run from 1 to 1,000, with defaults 20 and 50.
4. StoreSchema refuses a name that breaks its pattern, a name two kinds
   share and a reserved name, naming it; a type may equal its own kind's
   base label.
5. StoreSchema keeps sorted tuples without repeats, and merged() is the union.
6. The name patterns equal those of the pack format.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

from tenetrag.packs import format as pack_format
from tenetrag.protocols import (
    RELATION_NAME,
    TYPE_NAME,
    ConfigError,
    GraphStore,
    HopSpec,
    StoreSchema,
    VectorStore,
)

GRAPH_METHODS = {
    "ensure_schema",
    "acquire_writer",
    "renew_writer",
    "release_writer",
    "begin_run",
    "finish_run",
    "get_runs",
    "document_states",
    "get_cached_extractions",
    "put_cached_extractions",
    "get_resolution_decisions",
    "put_resolution_decisions",
    "find_by_identity",
    "find_events",
    "match_names",
    "search_names",
    "match_document_links",
    "get_version_groups",
    "get_document_version_keys",
    "write_documents",
    "delete_documents",
    "refresh_degrees",
    "entities_in_chunks",
    "hop",
    "get_entities",
    "get_items",
    "get_chunks",
    "get_documents",
}
VECTOR_METHODS = {
    "ensure_collections",
    "upsert",
    "delete",
    "delete_documents",
    "search",
    "search_text",
    "get_vectors",
}


def _methods(protocol: type) -> set[str]:
    return {
        name
        for name, value in vars(protocol).items()
        if callable(value) and not name.startswith("_")
    }


def test_protocols_stdlib_only():
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            "import sys; before = set(sys.modules); import tenetrag.protocols; "
            "print('\\n'.join(sorted(set(sys.modules) - before)))",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    added = {name.partition(".")[0] for name in result.stdout.splitlines()}

    assert "tenetrag" in added
    assert sorted(added - set(sys.stdlib_module_names) - {"tenetrag"}) == []


def test_protocol_methods():
    assert _methods(GraphStore) == GRAPH_METHODS
    assert _methods(VectorStore) == VECTOR_METHODS
    assert "capabilities" in VectorStore.__annotations__


def test_hop_spec_limits():
    spec = HopSpec()

    assert (spec.neighbour_limit, spec.item_limit) == (20, 50)
    assert HopSpec(neighbour_limit=1, item_limit=1000).item_limit == 1000
    for limits in ({"neighbour_limit": 0}, {"neighbour_limit": 1001}, {"item_limit": 0}):
        with pytest.raises(ValueError, match=next(iter(limits))):
            HopSpec(**limits)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="item_limit"):
        HopSpec(item_limit=1001)


@pytest.mark.parametrize(
    ("kinds", "name"),
    [
        ({"entity_types": ("policy",)}, "policy"),
        ({"relation_types": ("OWNER-OF",)}, "OWNER-OF"),
        ({"relation_types": ("Owner_Of",)}, "Owner_Of"),
        ({"entity_types": ("Meeting",), "event_types": ("Meeting",)}, "Meeting"),
        ({"fact_types": ("Owns",), "entity_types": ("Owns",)}, "Owns"),
    ],
)
def test_store_schema_patterns(kinds: dict[str, tuple[str, ...]], name: str):
    with pytest.raises(ConfigError, match=name):
        StoreSchema(**kinds)


@pytest.mark.parametrize(
    ("kinds", "name"),
    [
        ({"entity_types": ("Chunk",)}, "Chunk"),
        ({"entity_types": ("Event",)}, "Event"),
        ({"fact_types": ("Entity",)}, "Entity"),
        ({"event_types": ("WriterLease",)}, "WriterLease"),
        ({"relation_types": ("IN_DOCUMENT",)}, "IN_DOCUMENT"),
        ({"relation_types": ("SAME_AS",)}, "SAME_AS"),
    ],
)
def test_store_schema_reserved(kinds: dict[str, tuple[str, ...]], name: str):
    with pytest.raises(ConfigError, match=name):
        StoreSchema(**kinds)


def test_store_schema_own_base_label_allowed():
    schema = StoreSchema(entity_types=("Entity",), event_types=("Event",), fact_types=("Fact",))

    assert schema.event_types == ("Event",)


def test_store_schema_merged():
    first = StoreSchema(entity_types=("Policy", "Person"), relation_types=("OWNER_OF",))
    second = StoreSchema(
        entity_types=("Person", "Metric"), event_types=("Meeting",), relation_types=("PART_OF",)
    )

    merged = first.merged(second)

    assert first.entity_types == ("Person", "Policy")
    assert merged.entity_types == ("Metric", "Person", "Policy")
    assert merged.event_types == ("Meeting",)
    assert merged.fact_types == ()
    assert merged.relation_types == ("OWNER_OF", "PART_OF")
    assert StoreSchema(entity_types=("Policy", "Policy")).entity_types == ("Policy",)


def test_name_patterns_match_packs():
    assert TYPE_NAME.pattern == pack_format.TYPE_NAME.pattern
    assert RELATION_NAME.pattern == pack_format.RELATION_NAME.pattern
