"""Every profile field declares its phase (data-model §8, FR-012, SC-003)."""

from collections.abc import Mapping
from pathlib import Path
from typing import Annotated

import pytest
import yaml
from pydantic import BaseModel

from tenetrag import ConfigError
from tenetrag.config import (
    Content,
    IndexTime,
    Operational,
    Phase,
    QueryTime,
    Stage,
    field_phases,
    profile_from_dict,
)

PROFILES = Path(__file__).parents[2] / "fixtures" / "profiles"
QUERY = (Phase.QUERY, None)

CAPABILITY_FIELDS = (
    "strategies",
    "accepts_temperature",
    "accepts_top_p",
    "forbidden_schema_keywords",
    "max_schema_properties",
    "max_input_tokens",
    "max_output_tokens",
    "embedding_dimensions",
    "query_prefix",
    "passage_prefix",
    "parse_retries",
)

# The whole index-time field set of M0. Changing it changes stage hashes, so
# it changes here, visibly.
EXPECTED_INDEX_TIME = {
    "language": Stage.EXTRACT,
    "models.extraction.provider": Stage.EXTRACT,
    "models.extraction.model": Stage.EXTRACT,
    "models.extraction.temperature": Stage.EXTRACT,
    "models.extraction.max_output_tokens": Stage.EXTRACT,
    **{f"models.extraction.capabilities.{name}": Stage.EXTRACT for name in CAPABILITY_FIELDS},
    "models.embedding.provider": Stage.EMBED,
    "models.embedding.model": Stage.EMBED,
    "models.embedding.dimensions": Stage.EMBED,
    **{f"models.embedding.capabilities.{name}": Stage.EMBED for name in CAPABILITY_FIELDS},
}


def leaf_paths(data: Mapping, prefix: str = "") -> set[str]:
    """Dotted paths of the leaves of a dumped profile, with `*` for connection names."""
    paths: set[str] = set()
    for key, value in data.items():
        path = f"{prefix}{key}"
        if path == "connections":
            for connection in value.values():
                paths |= leaf_paths(connection, "connections.*.")
        elif isinstance(value, Mapping):
            paths |= leaf_paths(value, f"{path}.")
        else:
            paths.add(path)
    return paths


# The Profile


def test_every_leaf_has_phase():
    phases = field_phases()
    full = yaml.safe_load((PROFILES / "selfhosted.yaml").read_text(encoding="utf-8"))
    full["connections"]["pg"] = {
        "kind": "postgres",
        "host": "localhost",
        "database": "graph",
        "credential": {"kind": "basic", "user": "app", "password_env": "PG_APP_PASSWORD"},
    }
    # Every section is present, so each None in the dump is a real leaf.
    dumped = profile_from_dict(full).model_dump()
    missing = leaf_paths(dumped) - phases.keys()
    assert missing == set()


def test_default_argument_is_the_profile():
    from tenetrag.config import Profile

    assert field_phases() == field_phases(Profile)


def test_index_time_field_set_is_pinned():
    index_time = {
        path: stage for path, (phase, stage) in field_phases().items() if phase is Phase.INDEX
    }
    assert index_time == EXPECTED_INDEX_TIME


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("models.answer.model", QUERY),
        ("models.answer.temperature", QUERY),
        ("models.answer.capabilities.strategies", QUERY),
        ("models.extraction.model", (Phase.INDEX, Stage.EXTRACT)),
        ("models.extraction.base_url", QUERY),
        ("models.extraction.timeout_seconds", QUERY),
        ("models.extraction.retry.max_attempts", QUERY),
        ("models.extraction.credential.kind", QUERY),
        ("models.extraction.log_content", QUERY),
        ("models.embedding.batch_size", QUERY),
        ("connections.*.uri", QUERY),
        ("connections.*.host", QUERY),
        ("connections.*.pool.min_size", QUERY),
    ],
)
def test_resolved_phases(path, expected):
    assert field_phases()[path] == expected


# The rules, on synthetic models


class Leafy(BaseModel):
    content: Annotated[int, Content()] = 0
    operational: Annotated[int, Operational()] = 0


def test_leaf_with_no_marker_fails_naming_its_path():
    class Inner(BaseModel):
        marked: Annotated[int, Operational()] = 0
        unmarked: int = 0

    class Outer(BaseModel):
        inner: Annotated[Inner, QueryTime()]

    with pytest.raises(ConfigError, match=r"inner\.unmarked"):
        field_phases(Outer)


def test_content_leaf_with_no_phased_ancestor_fails():
    class Orphan(BaseModel):
        value: Annotated[int, Content()] = 0

    with pytest.raises(ConfigError, match="value"):
        field_phases(Orphan)


def test_every_bad_path_is_named_in_one_error():
    class Bad(BaseModel):
        first: int = 0
        second: Annotated[int, Content()] = 0

    with pytest.raises(ConfigError) as caught:
        field_phases(Bad)
    assert "first" in str(caught.value)
    assert "second" in str(caught.value)


def test_two_markers_on_one_leaf_fail():
    class Twice(BaseModel):
        value: Annotated[int, Operational(), QueryTime()] = 0

    with pytest.raises(ConfigError, match="value"):
        field_phases(Twice)


@pytest.mark.parametrize("marker", [Content(), Operational()])
def test_leaf_markers_on_a_section_fail(marker):
    class Section(BaseModel):
        leaf: Annotated[int, QueryTime()] = 0

    class Holder(BaseModel):
        section: Annotated[Section, marker]

    with pytest.raises(ConfigError, match="section"):
        field_phases(Holder)


def test_operational_under_index_time_resolves_to_query_time():
    class Holder(BaseModel):
        section: Annotated[Leafy, IndexTime(Stage.EMBED)]

    phases = field_phases(Holder)
    assert phases["section.content"] == (Phase.INDEX, Stage.EMBED)
    assert phases["section.operational"] == QUERY


def test_content_under_query_time_is_query_time():
    class Holder(BaseModel):
        section: Annotated[Leafy, QueryTime()]

    assert field_phases(Holder)["section.content"] == QUERY


def test_nearest_phased_ancestor_wins():
    class Middle(BaseModel):
        leafy: Annotated[Leafy, QueryTime()]

    class Outer(BaseModel):
        middle: Annotated[Middle, IndexTime(Stage.EXTRACT)]

    assert field_phases(Outer)["middle.leafy.content"] == QUERY


def test_a_leaf_marker_overrides_its_ancestors():
    class Section(BaseModel):
        pinned: Annotated[int, QueryTime()] = 0

    class Holder(BaseModel):
        section: Annotated[Section, IndexTime(Stage.EXTRACT)]

    assert field_phases(Holder)["section.pinned"] == QUERY


def test_optional_section_is_walked():
    class Holder(BaseModel):
        section: Annotated[Leafy | None, IndexTime(Stage.CHUNK)] = None

    assert field_phases(Holder)["section.content"] == (Phase.INDEX, Stage.CHUNK)


def test_mapping_of_sections_uses_a_star():
    class Holder(BaseModel):
        named: Annotated[Mapping[str, Leafy], QueryTime()] = {}

    assert field_phases(Holder)["named.*.content"] == QUERY


def test_union_variants_are_merged():
    class A(BaseModel):
        shared: Annotated[int, Operational()] = 0
        only_a: Annotated[int, Content()] = 0

    class B(BaseModel):
        shared: Annotated[int, Operational()] = 0

    class Holder(BaseModel):
        either: Annotated[A | B, IndexTime(Stage.RESOLVE)]

    phases = field_phases(Holder)
    assert phases["either.shared"] == QUERY
    assert phases["either.only_a"] == (Phase.INDEX, Stage.RESOLVE)


def test_union_variants_that_disagree_fail():
    class A(BaseModel):
        value: Annotated[int, Operational()] = 0

    class B(BaseModel):
        value: Annotated[int, Content()] = 0

    class Holder(BaseModel):
        either: Annotated[A | B, IndexTime(Stage.RESOLVE)]

    with pytest.raises(ConfigError, match=r"either\.value"):
        field_phases(Holder)


def test_stage_values_are_the_lower_case_names():
    assert [stage.value for stage in Stage] == [
        "chunk",
        "extract",
        "resolve",
        "embed",
        "cluster",
        "reports",
    ]
    assert [phase.value for phase in Phase] == ["index", "query"]
