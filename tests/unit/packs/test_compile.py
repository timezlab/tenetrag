"""Compiled extraction schemas (data-model §6, research R6, FR-020 to FR-022, US2-1 to US2-4).

Behaviours:
1. Every shipped stack, the finance stacks and the example pack compile to the
   fixed 52-property shape, which the Databricks profile accepts (SC-002).
2. Every object requires all its properties and allows no other; every enum
   is sorted; no value can be null.
3. A subset gives enums of its names only, and a part with no names is left out.
4. An unknown name, an `extract: false` type or an empty subset raises
   ConfigError, as does a schema past max_properties, listing its parts by size.
5. The same stack gives the same bytes, pinned for core; the schema handed
   out is a fresh plain copy.
"""

from __future__ import annotations

import dataclasses
import json
import re
from collections.abc import Iterator
from typing import Any

import pytest

from tenetrag import ConfigError, UnsupportedRequestError
from tenetrag.llm.capabilities import capability_profile
from tenetrag.llm.structured import check_schema
from tenetrag.packs import CompiledSchema, compile_schema, load_pack
from tests.support.packs import FINANCE_DRAFT, PACK_FIXTURES, write_pack

MODEL = "databricks-claude-sonnet-5"
DATABRICKS = capability_profile("databricks", MODEL)
VALID = PACK_FIXTURES / "valid"
GOLDEN_CORE = PACK_FIXTURES / "compiled" / "core.json"

STACKS = {
    "core": "core",
    "enterprise-docs": "enterprise-docs",
    "finance": FINANCE_DRAFT,
    "enterprise-docs+finance": VALID / "shared-ancestor.yaml",
    "alpha-ops": VALID / "alpha-ops.yaml",
}

# The parts of research R6, keyed by the array properties that lead to them.
SHAPE = {
    (): {"entities", "relations", "events", "facts"},
    ("entities",): {
        "id",
        "type",
        "surface",
        "is_name",
        "name",
        "translation",
        "ref",
        "scope",
        "former_names",
        "attributes",
    },
    ("entities", "former_names"): {"name", "quote"},
    ("entities", "attributes"): {"name", "value", "quote"},
    ("relations",): {"type", "from", "to", "attributes", "valid_from", "valid_to", "quote"},
    ("relations", "attributes"): {"name", "value", "quote"},
    ("events",): {"id", "type", "roles", "attributes", "valid_from", "valid_to", "quote"},
    ("events", "roles"): {"role", "ref"},
    ("events", "attributes"): {"name", "value", "quote"},
    ("facts",): {"type", "roles", "attributes", "valid_from", "valid_to", "quote"},
    ("facts", "roles"): {"role", "ref"},
    ("facts", "attributes"): {"name", "value", "quote"},
}

CORE_ENTITY_TYPES = ["Concept", "Metric", "Organization", "Person", "Place", "Product", "Work"]


def parts(
    schema: dict[str, Any], path: tuple[str, ...] = ()
) -> Iterator[tuple[tuple[str, ...], dict]]:
    """Each object schema, keyed by the array properties that lead to it."""
    yield path, schema
    for name, child in schema["properties"].items():
        if child["type"] == "array":
            yield from parts(child["items"], (*path, name))


def shape(compiled: CompiledSchema) -> dict[tuple[str, ...], set[str]]:
    return {path: set(part["properties"]) for path, part in parts(compiled.schema)}


def part(compiled: CompiledSchema, *path: str) -> dict[str, Any]:
    return dict(parts(compiled.schema))[path]


def enum(compiled: CompiledSchema, *path: str) -> list[str]:
    *where, field = path
    return part(compiled, *where)["properties"][field]["enum"]


def nodes(value: Any) -> Iterator[Any]:
    yield value
    if isinstance(value, dict):
        for item in value.values():
            yield from nodes(item)
    elif isinstance(value, list):
        for item in value:
            yield from nodes(item)


def generated_pack(count: int) -> str:
    lines = ["pack: many-types", "version: 1", "extends: core", "entities:"]
    for number in range(1, count + 1):
        lines += [
            f"  Generated{number:02d}:",
            f"    description: Generated entity type number {number}.",
            f"    examples: [Example {number}]",
            "    attributes:",
            f"      code_{number:02d}: {{range: str, compare: code, unique: global}}",
            f"    identity: [[code_{number:02d}]]",
        ]
    return "\n".join(lines) + "\n"


# Fits the providers (US2-1, SC-002)


@pytest.mark.parametrize("reference", STACKS.values(), ids=STACKS.keys())
def test_compiled_fits_providers(reference):
    compiled = compile_schema(load_pack(reference))
    check_schema(compiled.schema, DATABRICKS, MODEL)
    assert compiled.property_count == 52
    assert shape(compiled) == SHAPE


def test_many_types_fit(tmp_path):
    stack = load_pack(write_pack(tmp_path, "many.yaml", generated_pack(60)))
    compiled = compile_schema(stack)
    check_schema(compiled.schema, DATABRICKS, MODEL)
    assert compiled.property_count == 52
    assert len(enum(compiled, "entities", "type")) == len(CORE_ENTITY_TYPES) + 60


def test_property_count_is_what_check_schema_counts():
    compiled = compile_schema(load_pack("enterprise-docs"))
    exact = dataclasses.replace(DATABRICKS, max_schema_properties=compiled.property_count)
    check_schema(compiled.schema, exact, MODEL)
    one_less = dataclasses.replace(exact, max_schema_properties=compiled.property_count - 1)
    with pytest.raises(UnsupportedRequestError, match=f"has {compiled.property_count} properties"):
        check_schema(compiled.schema, one_less, MODEL)


# The shape


@pytest.mark.parametrize("reference", STACKS.values(), ids=STACKS.keys())
def test_every_property_required_and_no_other(reference):
    compiled = compile_schema(load_pack(reference))
    for _, object_schema in parts(compiled.schema):
        assert object_schema["type"] == "object"
        assert object_schema["additionalProperties"] is False
        assert object_schema["required"] == sorted(object_schema["properties"])


@pytest.mark.parametrize("reference", STACKS.values(), ids=STACKS.keys())
def test_every_enum_sorted(reference):
    compiled = compile_schema(load_pack(reference))
    enums = [
        node["enum"] for node in nodes(compiled.schema) if isinstance(node, dict) and "enum" in node
    ]
    assert enums
    for values in enums:
        assert values == sorted(set(values))


def test_values_are_text_never_null():
    compiled = compile_schema(load_pack("core"))
    leaves = {
        (path, name): child["type"]
        for path, object_schema in parts(compiled.schema)
        for name, child in object_schema["properties"].items()
        if child["type"] not in ("array", "object")
    }
    assert leaves.pop((("entities",), "is_name")) == "boolean"
    assert set(leaves.values()) == {"string"}
    assert "null" not in compiled.to_json()


def test_core_enums():
    compiled = compile_schema(load_pack("core"))
    assert enum(compiled, "entities", "type") == CORE_ENTITY_TYPES
    assert enum(compiled, "entities", "attributes", "name") == [
        "born_on",
        "category",
        "code",
        "email",
        "established_on",
        "issued_on",
        "kind",
        "registration_id",
        "title",
        "unit",
    ]
    assert enum(compiled, "relations", "attributes", "name") == ["title"]
    assert enum(compiled, "events", "roles", "role") == ["location", "participant"]
    assert enum(compiled, "facts", "type") == ["Definition", "ReportedFigure"]
    assert compiled.types == tuple(sorted(compiled.types))
    assert "Statement" not in compiled.types


def test_relation_value_is_an_attribute_name():
    # finance's OWNS_STAKE declares `value: percentage` and no attribute.
    compiled = compile_schema(load_pack(FINANCE_DRAFT), ["OWNS_STAKE"])
    assert enum(compiled, "relations", "attributes", "name") == ["value"]


# Subsets (US2-3, US2-4)


def test_compile_subset():
    compiled = compile_schema(load_pack("core"), ["Person", "MEMBER_OF"])
    assert compiled.types == ("MEMBER_OF", "Person")
    assert enum(compiled, "entities", "type") == ["Person"]
    assert enum(compiled, "entities", "attributes", "name") == ["born_on", "email"]
    assert enum(compiled, "relations", "type") == ["MEMBER_OF"]
    # MEMBER_OF has no attribute, and no event or fact type is selected.
    assert set(part(compiled)["properties"]) == {"entities", "relations"}
    assert "attributes" not in part(compiled, "relations")["properties"]


def test_compile_empty_parts_left_out():
    compiled = compile_schema(load_pack("core"), ["Concept"])
    assert shape(compiled) == {
        (): {"entities"},
        ("entities",): SHAPE[("entities",)] - {"attributes"},
        ("entities", "former_names"): {"name", "quote"},
    }
    assert compiled.property_count == 1 + 9 + 2


@pytest.mark.parametrize(
    ("types", "named"),
    [
        (["Person", "Vendor"], "Vendor"),
        (["Statement"], "Statement"),
        ([], "no type"),
    ],
)
def test_compile_rejects_bad_subset(types, named):
    with pytest.raises(ConfigError, match=named):
        compile_schema(load_pack("core"), types)


def test_extract_false_left_out(tmp_path):
    core = compile_schema(load_pack("core"))
    assert "Statement" not in enum(core, "facts", "type")
    child = write_pack(
        tmp_path,
        "statements.yaml",
        """\
        pack: statements
        version: 1
        extends: core
        facts:
          Statement: {extract: true}
        """,
    )
    compiled = compile_schema(load_pack(child))
    assert "Statement" in enum(compiled, "facts", "type")
    assert {"about", "speaker"} <= set(enum(compiled, "facts", "roles", "role"))


# The limit (US2-2)


def test_compile_limit():
    with pytest.raises(ConfigError) as caught:
        compile_schema(load_pack("core"), max_properties=40)
    message = str(caught.value)
    assert "52" in message
    assert "40" in message
    sizes = [int(size) for _, size in re.findall(r"([a-z][a-z ]*) \((\d+)\)", message)]
    assert len(sizes) == len(SHAPE)
    assert sum(sizes) == 52
    assert sizes == sorted(sizes, reverse=True)


def test_compile_at_the_limit():
    assert compile_schema(load_pack("core"), max_properties=52).property_count == 52


# Bytes and copies (FR-022)


def test_compile_golden():
    compiled = compile_schema(load_pack("core"))
    assert (compiled.to_json() + "\n").encode("utf-8") == GOLDEN_CORE.read_bytes()


def test_compile_deterministic():
    stack = load_pack("enterprise-docs")
    first, second = compile_schema(stack), compile_schema(load_pack("enterprise-docs"))
    assert first.to_json() == second.to_json()
    assert first.to_json() == json.dumps(
        first.schema, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )


def test_schema_is_a_fresh_plain_copy():
    compiled = compile_schema(load_pack("core"))
    schema = compiled.schema
    assert all(type(node) in (dict, list, str, bool) for node in nodes(schema))
    schema["properties"].clear()
    assert compiled.schema["properties"]
    assert compiled.property_count == 52
