"""Loading a profile from YAML or a dict (contracts/config.md, data-model §2, FR-010)."""

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from tenetrag import ConfigError
from tenetrag.config import Profile, load_profile, profile_from_dict, profile_from_yaml
from tests.support.secrets import PLANTED, assert_exception_clean

PROFILES = Path(__file__).parents[2] / "fixtures" / "profiles"
FIXTURES = sorted(PROFILES.glob("*.yaml"))
NEO4J_PASSWORD_PLANTED = PLANTED[1]


def config_error(text: str) -> ConfigError:
    with pytest.raises(ConfigError) as caught:
        profile_from_yaml(text)
    return caught.value


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.stem)
def test_fixture_profiles_load(path):
    assert isinstance(load_profile(path), Profile)


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.stem)
def test_yaml_and_dict_give_equal_profiles(path):
    text = path.read_text(encoding="utf-8")
    assert profile_from_dict(yaml.safe_load(text)) == profile_from_yaml(text)


def test_load_profile_accepts_str_path():
    path = PROFILES / "minimal_fake.yaml"
    assert load_profile(str(path)) == load_profile(path)


# Duplicate keys


def test_duplicate_key_rejected():
    error = config_error("a: 1\na: 2\n")
    assert "'a'" in str(error)
    assert "line 2" in str(error)


def test_duplicate_nested_key_rejected():
    text = (
        "models:\n  answer: {provider: fake, model: one}\n  answer: {provider: fake, model: two}\n"
    )
    error = config_error(text)
    assert "'answer'" in str(error)
    assert "line 3" in str(error)


def test_every_duplicate_key_reported_together():
    error = config_error("language: vi\nlanguage: en\nmodels: {}\nmodels: {}\n")
    assert "line 2" in str(error)
    assert "line 4" in str(error)


def test_yaml_merge_key_override_is_not_a_duplicate():
    text = (
        "base: &base {provider: fake, model: fake-chat}\n"
        "models:\n"
        "  answer: {<<: *base, model: other}\n"
    )
    # Only the unknown top-level `base` is reported, not the merge override.
    error = config_error(text)
    assert "base" in str(error)
    assert "duplicate" not in str(error)


# Every problem at once


def test_unknown_and_invalid_reported_together():
    text = (
        "models:\n  answer: {provider: fake, model: fake-chat, timeout_seconds: -1}\nlangauge: vi\n"
    )
    message = str(config_error(text))
    assert "langauge" in message
    assert "unknown field" in message
    assert "models.answer.timeout_seconds" in message


@pytest.mark.parametrize("key", ["password", "token", "api_key", "secret", "client_secret"])
def test_secret_like_key_hint(key):
    text = (
        "connections:\n"
        "  graph:\n"
        "    kind: neo4j\n"
        "    uri: bolt://localhost:7687\n"
        f"    {key}: {NEO4J_PASSWORD_PLANTED}\n"
    )
    error = config_error(text)
    assert f"connections.graph.{key}" in str(error)
    assert "named as a source under `credential`" in str(error)
    assert_exception_clean(error)


def test_secret_like_key_under_a_model_gets_the_hint():
    text = f"models:\n  answer: {{provider: fake, model: fake-chat, api_key: {PLANTED[0]}}}\n"
    error = config_error(text)
    assert "models.answer.api_key" in str(error)
    assert "named as a source under `credential`" in str(error)
    assert_exception_clean(error)


def test_ordinary_unknown_key_gets_no_credential_hint():
    error = config_error("langauge: vi\n")
    assert "credential" not in str(error)


def test_dict_input_errors_never_echo_values():
    data = {"connections": {"graph": {"kind": "neo4j", "uri": 5, "password": PLANTED[1]}}}
    with pytest.raises(ConfigError) as caught:
        profile_from_dict(data)
    assert "connections.graph.uri" in str(caught.value)
    assert_exception_clean(caught.value)


# Malformed documents


@pytest.mark.parametrize("text", ["", "# only a comment\n", "---\n", "null\n"])
def test_empty_document_rejected(text):
    assert "empty" in str(config_error(text))


@pytest.mark.parametrize("text", ["- a\n- b\n", "just text\n", "42\n"])
def test_non_mapping_document_rejected(text):
    assert "mapping" in str(config_error(text))


@pytest.mark.parametrize(
    "text",
    [
        "language: !!python/object/apply:os.system ['true']\n",
        "language: !!python/name:os.system\n",
        "!!python/object:tenetrag.config.Profile {}\n",
    ],
)
def test_object_building_tags_rejected(text):
    assert "python/" in str(config_error(text))


# PyYAML quotes about 35 characters on each side of the error mark, so the
# secret sits right next to it.
@pytest.mark.parametrize(
    "text",
    [
        f"connections:\n  graph:\n    password: {PLANTED[1]}: extra\n",
        f"connections:\n  graph:\n    password: [{PLANTED[1]}\n",
    ],
)
def test_yaml_syntax_error_does_not_echo_the_line(text):
    error = config_error(text)
    assert "line" in str(error)
    assert_exception_clean(error)


def test_non_mapping_dict_input_rejected():
    with pytest.raises(ConfigError):
        profile_from_dict(["not", "a", "mapping"])


# Files


def test_unreadable_path_names_the_path(tmp_path):
    missing = tmp_path / "missing.yaml"
    with pytest.raises(ConfigError) as caught:
        load_profile(missing)
    assert str(missing) in str(caught.value)


def test_directory_path_names_the_path(tmp_path):
    with pytest.raises(ConfigError) as caught:
        load_profile(tmp_path)
    assert str(tmp_path) in str(caught.value)


def test_errors_from_a_file_name_the_file(tmp_path):
    path = tmp_path / "profile.yaml"
    path.write_text("language: vi\nlanguage: en\n", encoding="utf-8")
    with pytest.raises(ConfigError) as caught:
        load_profile(path)
    assert str(path) in str(caught.value)


def test_non_utf8_file_rejected(tmp_path):
    path = tmp_path / "profile.yaml"
    path.write_bytes(b"language: \xff\n")
    with pytest.raises(ConfigError) as caught:
        load_profile(path)
    assert str(path) in str(caught.value)


# The loaded profile


def test_loaded_profile_is_frozen():
    profile = load_profile(PROFILES / "minimal_fake.yaml")
    with pytest.raises(ValidationError):
        profile.language = "vi"
    assert profile.models.answer is not None
    with pytest.raises(ValidationError):
        profile.models.answer.model = "other"
