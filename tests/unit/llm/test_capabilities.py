"""Shipped capability profiles, lookup and overrides (data-model §5, T038).

Behaviours:
1. Every Databricks endpoint gets the structured-output limits of the platform.
2. Claude on Databricks has no JSON mode; databricks-claude-sonnet-5 drops
   temperature and top_p, and the longer sonnet-5-5 name does not inherit that.
3. The OpenAI families send native schema first; the first gpt-4o snapshot
   cannot, and the reasoning families drop temperature.
4. An unknown model gets prompt_parse only, with no schema limits.
5. Overrides replace single fields; the strategy is the first in the fixed order.
6. An embedding model needs a known max_input_tokens and dimension.
7. config's StrategyName lists exactly the Strategy values.
"""

from typing import get_args

import pytest

from tenetrag import ConfigError
from tenetrag.config import CapabilityOverrides, EmbeddingModelSettings, NoneSource
from tenetrag.config.profile import StrategyName
from tenetrag.llm import Strategy, capability_profile, embedding_model_from_settings

ALL_FOUR = (Strategy.NATIVE_SCHEMA, Strategy.TOOL_CALL, Strategy.JSON_MODE, Strategy.PROMPT_PARSE)
DATABRICKS_FORBIDDEN = {"$ref", "anyOf", "oneOf", "allOf", "pattern", "prefixItems"}


@pytest.mark.parametrize(
    "model", ["databricks-meta-llama-3-3-70b-instruct", "databricks-gpt-5", "my-own-endpoint"]
)
def test_databricks_endpoints_get_the_platform_limits(model):
    profile = capability_profile("databricks", model)
    assert set(profile.forbidden_schema_keywords) == DATABRICKS_FORBIDDEN
    assert profile.max_schema_properties == 64
    assert profile.strategies == ALL_FOUR
    assert profile.strategy is Strategy.NATIVE_SCHEMA


@pytest.mark.parametrize(
    "model",
    ["databricks-claude-opus-5", "databricks-claude-sonnet-5", "databricks-claude-haiku-4-5"],
)
def test_claude_on_databricks_has_no_json_mode(model):
    profile = capability_profile("databricks", model)
    assert Strategy.JSON_MODE not in profile.strategies
    assert profile.strategy is Strategy.NATIVE_SCHEMA
    assert set(profile.forbidden_schema_keywords) == DATABRICKS_FORBIDDEN


def test_claude_sonnet_5_drops_temperature():
    profile = capability_profile("databricks", "databricks-claude-sonnet-5")
    assert not profile.accepts_temperature
    assert not profile.accepts_top_p


def test_claude_sonnet_5_5_keeps_temperature():
    # Its name starts with databricks-claude-sonnet-5, but the restriction is documented
    # for Sonnet 5 only.
    profile = capability_profile("databricks", "databricks-claude-sonnet-5-5")
    assert profile.accepts_temperature
    assert profile.accepts_top_p


@pytest.mark.parametrize(
    "model", ["gpt-4o", "gpt-4o-mini", "gpt-4o-2024-08-06", "gpt-4.1", "gpt-4.1-mini", "gpt-5"]
)
def test_openai_families_send_native_schema_first(model):
    profile = capability_profile("openai_compatible", model)
    assert profile.strategies == ALL_FOUR
    assert profile.strategy is Strategy.NATIVE_SCHEMA


def test_first_gpt_4o_snapshot_has_no_native_schema():
    profile = capability_profile("openai_compatible", "gpt-4o-2024-05-13")
    assert Strategy.NATIVE_SCHEMA not in profile.strategies
    assert profile.strategy is Strategy.TOOL_CALL


@pytest.mark.parametrize(
    ("model", "accepts"),
    [("gpt-5", False), ("gpt-5.5", False), ("gpt-6-astra", False), ("gpt-4o", True)],
)
def test_reasoning_gpt_families_drop_temperature(model, accepts):
    profile = capability_profile("openai_compatible", model)
    assert profile.accepts_temperature is accepts
    assert profile.accepts_top_p is accepts


@pytest.mark.parametrize(
    ("provider", "model"),
    [
        ("openai_compatible", "qwen3-32b"),
        ("openai_compatible", "llama-gpt-4o-ft"),
        # Starts with the gpt-4o family's name, but not at a boundary (-, ., :, _).
        ("openai_compatible", "gpt-4omni-ft"),
    ],
)
def test_unknown_model_gets_prompt_parse_only(provider, model):
    profile = capability_profile(provider, model)
    assert profile.strategies == (Strategy.PROMPT_PARSE,)
    assert profile.forbidden_schema_keywords == ()
    assert profile.max_schema_properties is None
    assert profile.max_input_tokens is None
    assert profile.accepts_temperature
    assert profile.parse_retries == 2


def test_qwen3_embedding_on_databricks():
    profile = capability_profile("databricks", "databricks-qwen3-embedding-0-6b")
    assert profile.embedding_dimensions == 1024
    assert profile.max_input_tokens is not None


def test_overrides_replace_single_fields():
    overrides = CapabilityOverrides(
        strategies=("json_mode", "prompt_parse"), max_schema_properties=10
    )
    profile = capability_profile("databricks", "databricks-gpt-5", overrides)
    assert profile.strategies == (Strategy.JSON_MODE, Strategy.PROMPT_PARSE)
    assert profile.max_schema_properties == 10
    assert set(profile.forbidden_schema_keywords) == DATABRICKS_FORBIDDEN


def test_overrides_widen_an_unknown_model():
    overrides = CapabilityOverrides(
        strategies=("native_schema",), forbidden_schema_keywords=(), max_input_tokens=8192
    )
    profile = capability_profile("openai_compatible", "qwen3-32b", overrides)
    assert profile.strategy is Strategy.NATIVE_SCHEMA
    assert profile.max_input_tokens == 8192


def test_strategy_is_the_first_in_the_fixed_order():
    overrides = CapabilityOverrides(strategies=("prompt_parse", "json_mode"))
    profile = capability_profile("openai_compatible", "qwen3-32b", overrides)
    assert profile.strategy is Strategy.JSON_MODE


def embedding_settings(**fields) -> EmbeddingModelSettings:
    values = {
        "provider": "openai_compatible",
        "base_url": "http://localhost:4000/v1",
        "model": "bge-m3",
        "credential": NoneSource(kind="none"),
        **fields,
    }
    return EmbeddingModelSettings(**values)


def test_embedding_model_needs_max_input_tokens():
    with pytest.raises(ConfigError, match="max_input_tokens") as caught:
        embedding_model_from_settings(
            embedding_settings(dimensions=1024), target_name="models.embedding"
        )
    assert "models.embedding" in str(caught.value)


def test_embedding_model_needs_a_dimension():
    settings = embedding_settings(capabilities=CapabilityOverrides(max_input_tokens=8192))
    with pytest.raises(ConfigError, match="dimensions"):
        embedding_model_from_settings(settings, target_name="models.embedding")


def test_embedding_model_with_both_is_created():
    settings = embedding_settings(
        dimensions=1024, capabilities=CapabilityOverrides(max_input_tokens=8192)
    )
    model = embedding_model_from_settings(settings, target_name="models.embedding")
    assert (model.model_id, model.dimensions, model.max_input_tokens) == ("bge-m3", 1024, 8192)


def test_strategy_names_match_config():
    # config cannot import llm, so the names are written in both places.
    assert get_args(StrategyName) == tuple(strategy.value for strategy in Strategy)
