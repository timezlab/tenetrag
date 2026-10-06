"""Profile fields, defaults and per-provider rules (data-model §2, §3, §5 to §7)."""

import math
from pathlib import Path

import pytest

from tenetrag import ConfigError
from tenetrag.config import (
    Neo4jSettings,
    PostgresSettings,
    TlsMode,
    load_profile,
    profile_from_dict,
)
from tests.support.secrets import PLANTED, assert_exception_clean

PROFILES = Path(__file__).parents[2] / "fixtures" / "profiles"


def problems(data: dict) -> str:
    with pytest.raises(ConfigError) as caught:
        profile_from_dict(data)
    return str(caught.value)


def chat(**fields) -> dict:
    return {"provider": "fake", "model": "fake-chat", **fields}


def neo4j(**fields) -> dict:
    return {"kind": "neo4j", "uri": "bolt://localhost:7687", **fields}


def postgres(**fields) -> dict:
    return {"kind": "postgres", "host": "localhost", "database": "graph", **fields}


# Defaults


def test_empty_mapping_gives_all_defaults():
    profile = profile_from_dict({})
    assert profile.connections == {}
    assert profile.models.extraction is None
    assert profile.models.answer is None
    assert profile.models.embedding is None
    assert profile.language == "en"


def test_chat_model_defaults():
    answer = profile_from_dict({"models": {"answer": chat()}}).models.answer
    assert answer is not None
    assert answer.temperature == 0.0
    assert answer.max_output_tokens is None
    assert answer.timeout_seconds == 120
    assert answer.log_content is False
    assert answer.credential is None
    retry = answer.retry
    assert (retry.max_attempts, retry.max_total_seconds) == (5, 60)
    assert (retry.initial_backoff_seconds, retry.max_backoff_seconds) == (0.5, 8)


def test_embedding_model_defaults():
    embedding = profile_from_dict(
        {"models": {"embedding": {"provider": "fake", "model": "fake-embed"}}}
    ).models.embedding
    assert embedding is not None
    assert embedding.dimensions is None
    assert embedding.batch_size == 64
    assert embedding.timeout_seconds == 60


def test_neo4j_defaults():
    graph = profile_from_dict({"connections": {"graph": neo4j()}}).connections["graph"]
    assert isinstance(graph, Neo4jSettings)
    assert graph.database == "neo4j"
    assert graph.tls is TlsMode.AUTO
    assert graph.connect_timeout_seconds == 15
    assert (graph.pool.max_size, graph.pool.max_age_seconds) == (8, 43200)
    assert graph.pool.acquire_timeout_seconds == 30
    assert (graph.retry.max_attempts, graph.retry.max_total_seconds) == (5, 30)
    assert (graph.retry.initial_backoff_seconds, graph.retry.max_backoff_seconds) == (0.2, 4)


def test_postgres_defaults():
    store = profile_from_dict({"connections": {"pg": postgres()}}).connections["pg"]
    assert isinstance(store, PostgresSettings)
    assert store.port == 5432
    assert store.tls is TlsMode.AUTO
    assert (store.pool.min_size, store.pool.max_size) == (1, 8)
    assert store.retry.max_total_seconds == 30


def test_partial_store_retry_keeps_store_defaults():
    graph = profile_from_dict(
        {"connections": {"graph": neo4j(retry={"max_attempts": 3})}}
    ).connections["graph"]
    assert graph.retry.max_attempts == 3
    assert graph.retry.max_total_seconds == 30
    assert graph.retry.max_backoff_seconds == 4


def test_selfhosted_fixture_values():
    profile = load_profile(PROFILES / "selfhosted.yaml")
    assert profile.language == "vi"
    graph = profile.connections["graph"]
    assert isinstance(graph, Neo4jSettings)
    assert graph.credential is not None
    assert graph.credential.kind == "basic"
    extraction = profile.models.extraction
    assert extraction is not None
    assert extraction.capabilities.strategies == ("json_mode", "prompt_parse")


# Connections


def test_connection_kind_selects_the_settings():
    profile = profile_from_dict({"connections": {"graph": neo4j(), "pg": postgres()}})
    assert isinstance(profile.connections["graph"], Neo4jSettings)
    assert isinstance(profile.connections["pg"], PostgresSettings)


def test_unknown_connection_kind_rejected():
    assert "connections.graph" in problems({"connections": {"graph": {"kind": "mysql"}}})


@pytest.mark.parametrize(
    "uri", ["neo4j://db:7687", "neo4j+s://db.example.com", "bolt://127.0.0.1", "bolt+s://db"]
)
def test_neo4j_uri_schemes_accepted(uri):
    profile_from_dict({"connections": {"graph": neo4j(uri=uri)}})


@pytest.mark.parametrize("uri", ["http://db:7474", "db:7687", "bolt://", "neo4j+ssc://db"])
def test_neo4j_uri_rejected(uri):
    assert "connections.graph.uri" in problems({"connections": {"graph": neo4j(uri=uri)}})


def test_neo4j_uri_with_a_password_rejected_without_echoing_it():
    uri = f"bolt://neo4j:{PLANTED[1]}@localhost:7687"
    with pytest.raises(ConfigError) as caught:
        profile_from_dict({"connections": {"graph": neo4j(uri=uri)}})
    assert "connections.graph.uri" in str(caught.value)
    assert "credential" in str(caught.value)
    assert_exception_clean(caught.value)


@pytest.mark.parametrize("port", [0, 65536, -1])
def test_postgres_port_range(port):
    assert "connections.pg.port" in problems({"connections": {"pg": postgres(port=port)}})


def test_postgres_requires_host_and_database():
    message = problems({"connections": {"pg": {"kind": "postgres"}}})
    assert "connections.pg.host" in message
    assert "connections.pg.database" in message


def test_pool_min_size_above_max_size_rejected():
    data = {"connections": {"pg": postgres(pool={"min_size": 9, "max_size": 8})}}
    assert "connections.pg.pool" in problems(data)


@pytest.mark.parametrize("tls", ["auto", "require", "verify", "off"])
def test_tls_modes(tls):
    graph = profile_from_dict({"connections": {"graph": neo4j(tls=tls)}}).connections["graph"]
    assert graph.tls is TlsMode(tls)


def test_unknown_tls_mode_rejected():
    assert "connections.graph.tls" in problems({"connections": {"graph": neo4j(tls="maybe")}})


@pytest.mark.parametrize("name", ["graph.main", "", "a b"])
def test_connection_names_are_plain_identifiers(name):
    assert "connections" in problems({"connections": {name: neo4j()}})


# Credential sources


@pytest.mark.parametrize(
    "credential",
    [
        {"kind": "none"},
        {"kind": "api_key", "env": "OPENAI_API_KEY"},
        {"kind": "basic", "user": "neo4j", "password_env": "NEO4J_PASSWORD"},
        {"kind": "pat", "token_env": "DATABRICKS_TOKEN"},
        {"kind": "oauth_m2m", "client_id": "app-1", "client_secret_env": "SP_SECRET"},
        {"kind": "oauth_u2m"},
        {"kind": "cli_profile", "name": "dev"},
        {"kind": "cli_profile", "name": "dev", "config_file": "/etc/databrickscfg"},
        {"kind": "runtime"},
    ],
    ids=lambda c: c["kind"] + ("+file" if "config_file" in c else ""),
)
def test_credential_source_kinds(credential):
    graph = profile_from_dict({"connections": {"graph": neo4j(credential=credential)}}).connections[
        "graph"
    ]
    assert graph.credential is not None
    assert graph.credential.kind == credential["kind"]


@pytest.mark.parametrize("env", ["1ABC", "MY-VAR", "has space", ""])
def test_env_var_names_validated(env):
    data = {"connections": {"graph": neo4j(credential={"kind": "api_key", "env": env})}}
    assert "connections.graph.credential.env" in problems(data)


def test_unknown_credential_kind_rejected():
    data = {"connections": {"graph": neo4j(credential={"kind": "password"})}}
    assert "connections.graph.credential" in problems(data)


def test_credential_source_rejects_a_value_field():
    credential = {"kind": "basic", "user": "neo4j", "password": PLANTED[1]}
    with pytest.raises(ConfigError) as caught:
        profile_from_dict({"connections": {"graph": neo4j(credential=credential)}})
    assert "connections.graph.credential.password" in str(caught.value)
    assert_exception_clean(caught.value)


# Model providers


def test_openai_compatible_requires_base_url():
    data = {"models": {"answer": {"provider": "openai_compatible", "model": "qwen3"}}}
    message = problems(data)
    assert "models.answer" in message
    assert "base_url" in message


def test_databricks_requires_workspace_url_for_pat():
    data = {
        "models": {
            "answer": {
                "provider": "databricks",
                "model": "databricks-claude-sonnet-5",
                "credential": {"kind": "pat", "token_env": "DATABRICKS_TOKEN"},
            }
        }
    }
    assert "workspace_url" in problems(data)


@pytest.mark.parametrize("kind", ["cli_profile", "runtime"])
def test_databricks_workspace_url_optional_when_the_credential_carries_the_host(kind):
    credential = {"kind": kind, "name": "dev"} if kind == "cli_profile" else {"kind": kind}
    data = {
        "models": {"answer": {"provider": "databricks", "model": "m", "credential": credential}}
    }
    assert profile_from_dict(data).models.answer is not None


@pytest.mark.parametrize(
    ("fields", "named"),
    [
        ({"provider": "fake", "base_url": "http://localhost:4000"}, "base_url"),
        (
            {"provider": "fake", "workspace_url": "https://adb-1.azuredatabricks.net"},
            "workspace_url",
        ),
        ({"provider": "fake", "credential": {"kind": "none"}}, "credential"),
        (
            {"provider": "databricks", "base_url": "http://x", "credential": {"kind": "runtime"}},
            "base_url",
        ),
        (
            {
                "provider": "openai_compatible",
                "base_url": "http://localhost:4000",
                "workspace_url": "https://adb-1.azuredatabricks.net",
            },
            "workspace_url",
        ),
    ],
)
def test_fields_that_do_not_apply_to_the_provider_rejected(fields, named):
    message = problems({"models": {"answer": {"model": "m", **fields}}})
    assert "models.answer" in message
    assert named in message


def test_unknown_provider_rejected():
    assert "models.answer.provider" in problems({"models": {"answer": chat(provider="acme")}})


@pytest.mark.parametrize("url", ["ftp://host", "localhost:4000", "http://"])
def test_base_url_must_be_http(url):
    data = {"models": {"answer": {"provider": "openai_compatible", "model": "m", "base_url": url}}}
    assert "models.answer.base_url" in problems(data)


def test_workspace_url_must_be_https():
    data = {
        "models": {
            "answer": {
                "provider": "databricks",
                "model": "m",
                "workspace_url": "http://adb-1.azuredatabricks.net",
                "credential": {"kind": "oauth_u2m"},
            }
        }
    }
    assert "models.answer.workspace_url" in problems(data)


def test_base_url_with_a_password_rejected_without_echoing_it():
    url = f"http://user:{PLANTED[0]}@localhost:4000"
    data = {"models": {"answer": {"provider": "openai_compatible", "model": "m", "base_url": url}}}
    with pytest.raises(ConfigError) as caught:
        profile_from_dict(data)
    assert "models.answer.base_url" in str(caught.value)
    assert_exception_clean(caught.value)


@pytest.mark.parametrize(
    ("fields", "path"),
    [
        ({"temperature": -0.1}, "models.answer.temperature"),
        ({"max_output_tokens": 0}, "models.answer.max_output_tokens"),
        ({"timeout_seconds": 0}, "models.answer.timeout_seconds"),
        ({"model": ""}, "models.answer.model"),
        ({"retry": {"max_attempts": 0}}, "models.answer.retry.max_attempts"),
        ({"retry": {"max_total_seconds": -1}}, "models.answer.retry.max_total_seconds"),
        ({"capabilities": {"strategies": []}}, "models.answer.capabilities.strategies"),
        ({"capabilities": {"strategies": ["guess"]}}, "models.answer.capabilities.strategies"),
        ({"capabilities": {"parse_retries": -1}}, "models.answer.capabilities.parse_retries"),
    ],
)
def test_chat_field_bounds(fields, path):
    assert path in problems({"models": {"answer": chat(**fields)}})


# JSON has no infinity or NaN, so a stage hash could not cover such a value.
@pytest.mark.parametrize("value", [math.inf, -math.inf, math.nan])
@pytest.mark.parametrize("field", ["temperature", "timeout_seconds"])
def test_chat_numbers_must_be_finite(field, value):
    assert f"models.answer.{field}" in problems({"models": {"answer": chat(**{field: value})}})


@pytest.mark.parametrize("value", [math.inf, math.nan])
def test_store_seconds_must_be_finite(value):
    data = {"connections": {"graph": neo4j(connect_timeout_seconds=value)}}
    assert "connections.graph.connect_timeout_seconds" in problems(data)


def test_retry_initial_backoff_above_max_backoff_rejected():
    retry = {"initial_backoff_seconds": 10, "max_backoff_seconds": 1}
    assert "models.answer.retry" in problems({"models": {"answer": chat(retry=retry)}})


@pytest.mark.parametrize(("field", "value"), [("dimensions", 0), ("batch_size", 0)])
def test_embedding_field_bounds(field, value):
    data = {"models": {"embedding": {"provider": "fake", "model": "e", field: value}}}
    assert f"models.embedding.{field}" in problems(data)


def test_capability_overrides_default_to_empty():
    answer = profile_from_dict({"models": {"answer": chat()}}).models.answer
    assert answer is not None
    assert answer.capabilities.strategies is None
    assert answer.capabilities.max_input_tokens is None


# Language


@pytest.mark.parametrize("language", ["vi", "en", "fil", "pt-BR"])
def test_language_codes_accepted(language):
    assert profile_from_dict({"language": language}).language == language


@pytest.mark.parametrize("language", ["Vietnamese", "VI", "pt-br", "e", ""])
def test_language_codes_rejected(language):
    assert "language" in problems({"language": language})
