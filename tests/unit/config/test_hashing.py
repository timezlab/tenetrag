"""Stage hashes from index-time fields only (data-model §8, ADR 0005, FR-013, SC-004)."""

import copy
import hashlib
import re
import unicodedata
from pathlib import Path
from typing import Any

import pytest
import yaml

from tenetrag.config import Stage, load_profile, profile_from_dict, profile_from_yaml
from tenetrag.config.hashing import stage_hashes
from tests.unit.config.test_phases import CAPABILITY_FIELDS

PROFILES = Path(__file__).parents[2] / "fixtures" / "profiles"

# Pinned after the first green run. A change here is a change of the hash
# format or of the index-time field set, and needs a reason in the commit.
# Changed in M0 phase 6: three request-check capability fields left the
# index-time set (T038).
GOLDEN = {
    "selfhosted": {
        Stage.CHUNK: "sha256:e72a5a7b71ba5db66ef0080ca76119a05e659d9352a883461b587ed8cc12cd47",
        Stage.EXTRACT: "sha256:7efe7333d88b6b0b3803f2c2082114de15c2e2df975c36de4244cb0b9691fcaa",
        Stage.RESOLVE: "sha256:af9279ee7fff762692097bad083c2278bed82bf9d84cf7b3dbdf2ab789859a38",
        Stage.EMBED: "sha256:a4849b4634d4a777cdf6a2851265d518a9a166af28a9ba65c56f6293150c6981",
        Stage.CLUSTER: "sha256:0888af2dead1f985b5c81b551d3ff2559307afecac5c98b3830863b4a305d061",
        Stage.REPORTS: "sha256:5f774d41c2a014c20f214e9ae4160410dbf2479402f0c3241c3478fa23d76f2a",
    },
    "databricks": {
        Stage.CHUNK: "sha256:e72a5a7b71ba5db66ef0080ca76119a05e659d9352a883461b587ed8cc12cd47",
        Stage.EXTRACT: "sha256:7693dc4cb7bc18fcb4fc6f53749cf63832a602e7a4cc94602ee023b2147f2014",
        Stage.RESOLVE: "sha256:af9279ee7fff762692097bad083c2278bed82bf9d84cf7b3dbdf2ab789859a38",
        Stage.EMBED: "sha256:59e8aa17e178a1f7979ba5462149f21b67588ea8540b99f2018e866a40d5c973",
        Stage.CLUSTER: "sha256:0888af2dead1f985b5c81b551d3ff2559307afecac5c98b3830863b4a305d061",
        Stage.REPORTS: "sha256:5f774d41c2a014c20f214e9ae4160410dbf2479402f0c3241c3478fa23d76f2a",
    },
}


def fixture_dict(name: str) -> dict[str, Any]:
    return yaml.safe_load((PROFILES / f"{name}.yaml").read_text(encoding="utf-8"))


def hashes(data: dict[str, Any]) -> dict[Stage, str]:
    return stage_hashes(profile_from_dict(data))


def variant(data: dict[str, Any], dotted: str, value: Any) -> dict[str, Any]:
    changed = copy.deepcopy(data)
    *parents, last = dotted.split(".")
    node = changed
    for key in parents:
        node = node.setdefault(key, {})
    node[last] = value
    return changed


def changed_stages(a: dict[Stage, str], b: dict[Stage, str]) -> set[Stage]:
    return {stage for stage in Stage if a[stage] != b[stage]}


def spec_hash(stage: str, fields: dict[str, Any]) -> str:
    """The data-model §8 recipe, written out independently of the implementation."""
    document = f'{{"fields":{fields_json(fields)},"format":1,"stage":"{stage}"}}'
    return "sha256:" + hashlib.sha256(document.encode("utf-8")).hexdigest()


def fields_json(fields: dict[str, Any]) -> str:
    items = ",".join(f'"{key}":{json_value(fields[key])}' for key in sorted(fields))
    return "{" + items + "}"


def json_value(value: Any) -> str:
    # Enough of JSON for these tests: text without quotes or backslashes, ints and null.
    if value is None:
        return "null"
    if isinstance(value, str):
        return f'"{value}"'
    return str(value)


# Shape


def test_every_stage_has_a_hash():
    result = stage_hashes(load_profile(PROFILES / "minimal_fake.yaml"))
    assert set(result) == set(Stage)
    for value in result.values():
        assert re.fullmatch(r"sha256:[0-9a-f]{64}", value)


def test_hash_follows_the_spec_recipe():
    result = hashes({"language": "vi"})
    assert result[Stage.CHUNK] == spec_hash("chunk", {})
    assert result[Stage.EMBED] == spec_hash("embed", {})
    assert result[Stage.EXTRACT] == spec_hash("extract", {"language": "vi"})


def test_hash_keeps_non_ascii_text_as_is():
    model = unicodedata.normalize("NFC", "mô-hình-nhúng")
    data = {"models": {"embedding": {"provider": "fake", "model": model, "dimensions": 8}}}
    expected = {
        "models.embedding.provider": "fake",
        "models.embedding.model": model,
        "models.embedding.dimensions": 8,
        **{f"models.embedding.capabilities.{name}": None for name in CAPABILITY_FIELDS},
    }
    assert hashes(data)[Stage.EMBED] == spec_hash("embed", expected)


@pytest.mark.parametrize("name", ["selfhosted", "databricks"])
def test_hash_golden(name):
    assert stage_hashes(load_profile(PROFILES / f"{name}.yaml")) == GOLDEN[name]


# Input form


def reverse_keys(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: reverse_keys(value[key]) for key in reversed(list(value))}
    return value


@pytest.mark.parametrize("name", ["selfhosted", "databricks", "minimal_fake"])
def test_yaml_dict_and_key_order_give_equal_hashes(name):
    text = (PROFILES / f"{name}.yaml").read_text(encoding="utf-8")
    from_yaml = stage_hashes(profile_from_yaml(text))
    assert hashes(fixture_dict(name)) == from_yaml
    assert hashes(reverse_keys(fixture_dict(name))) == from_yaml


def test_strings_are_compared_in_nfc():
    composed = unicodedata.normalize("NFC", "mô-hình-việt")
    decomposed = unicodedata.normalize("NFD", composed)
    assert composed != decomposed
    base = {"models": {"extraction": {"provider": "fake"}}}
    a = hashes(variant(base, "models.extraction.model", composed))
    b = hashes(variant(base, "models.extraction.model", decomposed))
    assert a == b


# What changes which hash


@pytest.mark.parametrize(
    ("dotted", "value"),
    [
        ("models.answer.model", "other"),
        ("models.answer.temperature", 0.7),
        ("connections.graph.uri", "bolt://db.internal:7687"),
        ("connections.graph.pool", {"max_size": 2}),
        ("connections.pg", {"kind": "postgres", "host": "db", "database": "graph"}),
        ("models.extraction.base_url", "http://gpu-box:11434/v1"),
        ("models.extraction.timeout_seconds", 30),
        ("models.extraction.credential", {"kind": "api_key", "env": "LLM_KEY"}),
        ("models.extraction.retry", {"max_attempts": 2}),
        ("models.extraction.log_content", True),
        ("models.embedding.batch_size", 16),
        ("models.embedding.timeout_seconds", 5),
        # Leaf paths, so the fixture's other capabilities (its strategies) stay as they are.
        ("models.extraction.capabilities.forbidden_schema_keywords", ["anyOf"]),
        ("models.extraction.capabilities.max_schema_properties", 10),
        ("models.extraction.capabilities.max_input_tokens", 1000),
        ("models.embedding.capabilities.max_input_tokens", 512),
    ],
)
def test_hash_ignores_query_time(dotted, value):
    base = fixture_dict("selfhosted")
    assert changed_stages(hashes(base), hashes(variant(base, dotted, value))) == set()


def test_removing_the_answer_model_changes_no_hash():
    base = fixture_dict("selfhosted")
    without = copy.deepcopy(base)
    del without["models"]["answer"]
    assert changed_stages(hashes(base), hashes(without)) == set()


@pytest.mark.parametrize(
    ("dotted", "value"),
    [
        ("models.embedding.model", "nomic-embed-text"),
        ("models.embedding.dimensions", 768),
        ("models.embedding.capabilities", {"query_prefix": "query: "}),
    ],
)
def test_hash_embedding_only(dotted, value):
    base = fixture_dict("selfhosted")
    assert changed_stages(hashes(base), hashes(variant(base, dotted, value))) == {Stage.EMBED}


@pytest.mark.parametrize(
    ("dotted", "value"),
    [
        ("models.extraction.model", "llama4"),
        ("models.extraction.temperature", 0.2),
        ("models.extraction.max_output_tokens", 4096),
        ("models.extraction.capabilities", {"strategies": ["prompt_parse"]}),
        ("language", "en"),
    ],
)
def test_hash_extraction_only(dotted, value):
    base = fixture_dict("selfhosted")
    assert changed_stages(hashes(base), hashes(variant(base, dotted, value))) == {Stage.EXTRACT}


@pytest.mark.parametrize(
    ("dotted", "value"),
    [
        ("models.extraction.temperature", 0.0),
        ("models.extraction.temperature", 0),
        ("models.extraction.max_output_tokens", None),
        ("models.extraction.capabilities", {}),
        ("language", "en"),
    ],
)
def test_hash_default_equals_omitted(dotted, value):
    base = {"models": {"extraction": {"provider": "fake", "model": "fake-chat"}}}
    assert hashes(variant(base, dotted, value)) == hashes(base)
