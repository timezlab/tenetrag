"""Stage hashes from index-time fields and the pack's index hash.

M0 data-model §8, ADR 0005, FR-013, SC-004; the pack hash is 002's
contracts/config.md §2 (FR-025, US2-6).
"""

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
from tenetrag.packs import load_pack
from tests.support.packs import write_pack
from tests.unit.config.test_phases import CAPABILITY_FIELDS

PROFILES = Path(__file__).parents[2] / "fixtures" / "profiles"
# A well-formed pack index hash, for tests about the profile's own fields.
PACK_HASH = "sha256:" + hashlib.sha256(b"a pack").hexdigest()
OTHER_PACK_HASH = "sha256:" + hashlib.sha256(b"another pack").hexdigest()

# A user pack on core, for the tests that load one.
USER_PACK = """\
    pack: alpha
    version: 1
    extends: core
    entities:
      Vendor:
        description: A company that supplies goods or services to the organization.
        examples: [Công ty TNHH Gamma]
        attributes:
          tax_code: {range: str, compare: digits, unique: global}
        identity: [[tax_code]]
    retrieval:
      max_hops: 2
    glossary:
      - {name: Công ty TNHH Gamma, type: Vendor, aliases: [Gamma]}
    """

# Pinned after the first green run. A change here is a change of the hash
# format or of the index-time field set, and needs a reason in the commit.
# Changed in M0 phase 6: three request-check capability fields left the
# index-time set (T038).
# Changed in 002 phase 4: extract and resolve hold the pack's index hash, here
# that of `core`, the default pack (002 contracts/config.md §2).
# Changed in 003 phase 2: chunk holds `text_languages`, empty by default (ADR 0025).
GOLDEN = {
    "selfhosted": {
        Stage.CHUNK: "sha256:b869850816f2e408fd5ed189536f1ac98506cfd7f62bc474a05fbebafcfc7a3e",
        Stage.EXTRACT: "sha256:ed4364bc17b0e5ee407c3204497d9d22a8e849e9d870a80d387207dae66cddb3",
        Stage.RESOLVE: "sha256:ab4ca86d9c3ce68184a4b46ccf48f66b5eb99e94a1b3e7429dd068ec35c99156",
        Stage.EMBED: "sha256:a4849b4634d4a777cdf6a2851265d518a9a166af28a9ba65c56f6293150c6981",
        Stage.CLUSTER: "sha256:0888af2dead1f985b5c81b551d3ff2559307afecac5c98b3830863b4a305d061",
        Stage.REPORTS: "sha256:5f774d41c2a014c20f214e9ae4160410dbf2479402f0c3241c3478fa23d76f2a",
    },
    "databricks": {
        Stage.CHUNK: "sha256:b869850816f2e408fd5ed189536f1ac98506cfd7f62bc474a05fbebafcfc7a3e",
        Stage.EXTRACT: "sha256:672d0d48132cec17df2301c6692631ba93f25f03e65a1695d64a93ae646b0893",
        Stage.RESOLVE: "sha256:ab4ca86d9c3ce68184a4b46ccf48f66b5eb99e94a1b3e7429dd068ec35c99156",
        Stage.EMBED: "sha256:59e8aa17e178a1f7979ba5462149f21b67588ea8540b99f2018e866a40d5c973",
        Stage.CLUSTER: "sha256:0888af2dead1f985b5c81b551d3ff2559307afecac5c98b3830863b4a305d061",
        Stage.REPORTS: "sha256:5f774d41c2a014c20f214e9ae4160410dbf2479402f0c3241c3478fa23d76f2a",
    },
}


def fixture_dict(name: str) -> dict[str, Any]:
    return yaml.safe_load((PROFILES / f"{name}.yaml").read_text(encoding="utf-8"))


def hashes(data: dict[str, Any], pack_hash: str = PACK_HASH) -> dict[Stage, str]:
    return stage_hashes(profile_from_dict(data), pack_hash=pack_hash)


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
    # Enough of JSON for these tests: text without quotes or backslashes, ints, lists and null.
    if value is None:
        return "null"
    if isinstance(value, str):
        return f'"{value}"'
    if isinstance(value, list):
        return "[" + ",".join(json_value(item) for item in value) + "]"
    return str(value)


# Shape


def test_every_stage_has_a_hash():
    result = stage_hashes(load_profile(PROFILES / "minimal_fake.yaml"), pack_hash=PACK_HASH)
    assert set(result) == set(Stage)
    for value in result.values():
        assert re.fullmatch(r"sha256:[0-9a-f]{64}", value)


def test_hash_follows_the_spec_recipe():
    result = hashes({"language": "vi", "text_languages": ["vi"]})
    assert result[Stage.CHUNK] == spec_hash("chunk", {"text_languages": ["vi"]})
    assert result[Stage.EMBED] == spec_hash("embed", {})
    assert result[Stage.EXTRACT] == spec_hash("extract", {"language": "vi", "pack": PACK_HASH})
    assert result[Stage.RESOLVE] == spec_hash("resolve", {"pack": PACK_HASH})


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
    profile = load_profile(PROFILES / f"{name}.yaml")
    assert stage_hashes(profile, pack_hash=load_pack(profile.pack).index_hash) == GOLDEN[name]


# Input form


def reverse_keys(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: reverse_keys(value[key]) for key in reversed(list(value))}
    return value


@pytest.mark.parametrize("name", ["selfhosted", "databricks", "minimal_fake"])
def test_yaml_dict_and_key_order_give_equal_hashes(name):
    text = (PROFILES / f"{name}.yaml").read_text(encoding="utf-8")
    from_yaml = stage_hashes(profile_from_yaml(text), pack_hash=PACK_HASH)
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
        # The pack enters through pack_hash; naming it another way changes nothing.
        ("pack", "enterprise-docs"),
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


def test_hash_chunk_only():
    base = fixture_dict("selfhosted")
    changed = variant(base, "text_languages", ["vi"])
    assert changed_stages(hashes(base), hashes(changed)) == {Stage.CHUNK}
    # The profile sorts the list, so the order it is written in changes nothing.
    assert hashes(variant(base, "text_languages", ["vi", "en"])) == hashes(
        variant(base, "text_languages", ["en", "vi"])
    )


@pytest.mark.parametrize(
    ("dotted", "value"),
    [
        ("text_languages", []),
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


# The pack's index hash (002 contracts/config.md §2)


def test_hash_needs_pack_hash():
    profile = profile_from_dict({})
    with pytest.raises(TypeError):
        stage_hashes(profile)  # type: ignore[call-arg]  # the missing argument is the test


@pytest.mark.parametrize(
    "malformed",
    [
        "",
        "sha256:",
        "sha256:abc",
        PACK_HASH.upper(),
        PACK_HASH.replace("sha256:", "md5:"),
        PACK_HASH + "0",
        PACK_HASH + "\n",
        PACK_HASH.removeprefix("sha256:"),
    ],
)
def test_hash_rejects_malformed_pack_hash(malformed):
    with pytest.raises(ValueError, match="pack_hash"):
        stage_hashes(profile_from_dict({}), pack_hash=malformed)


def test_hash_pack_extract_and_resolve_only():
    base = fixture_dict("selfhosted")
    a = hashes(base, PACK_HASH)
    b = hashes(base, OTHER_PACK_HASH)
    assert changed_stages(a, b) == {Stage.EXTRACT, Stage.RESOLVE}


def stage_hashes_for(tmp_path: Path, name: str, pack_text: str) -> dict[Stage, str]:
    """Write the pack and a profile naming it, load both, and hash the stages."""
    write_pack(tmp_path / name, "pack.yaml", pack_text)
    profile_path = tmp_path / name / "profile.yaml"
    profile_path.write_text("pack: pack.yaml\n", encoding="utf-8")
    profile = load_profile(profile_path)
    return stage_hashes(profile, pack_hash=load_pack(profile.pack).index_hash)


def test_hash_pack_path_ignored(tmp_path):
    a = stage_hashes_for(tmp_path, "a", USER_PACK)
    b = stage_hashes_for(tmp_path, "b", USER_PACK)
    assert a == b


@pytest.mark.parametrize(
    ("old", "new", "expected"),
    [
        ("max_hops: 2", "max_hops: 3", set()),
        ("aliases: [Gamma]", "aliases: [Gamma, GMA]", set()),
        ("goods or services", "services", {Stage.EXTRACT, Stage.RESOLVE}),
    ],
    ids=["retrieval", "glossary", "description"],
)
def test_hash_retrieval_and_glossary_ignored(tmp_path, old, new, expected):
    assert USER_PACK.count(old) == 1
    base = stage_hashes_for(tmp_path, "base", USER_PACK)
    other = stage_hashes_for(tmp_path, "other", USER_PACK.replace(old, new))
    assert changed_stages(base, other) == expected
