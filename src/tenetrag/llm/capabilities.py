"""Capability profiles: what a model accepts, shipped only for documented facts (data-model §5).

A profile is built in layers, each replacing single fields: the provider's
base, then the longest matching model family, then an exact model name, then
the `capabilities` overrides of the settings. An unknown model gets
`prompt_parse` only and no schema limits, which works on every server; the
profile widens it once the server is known to support more. The class never
switches strategy after an error, so a run is reproducible.
"""

from __future__ import annotations

import dataclasses
import enum
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from tenetrag.config import CapabilityOverrides


class Strategy(enum.StrEnum):
    """Structured-output strategies, in the fixed order of preference (research R9).

    config.profile.StrategyName lists the same names, since config cannot import llm.
    """

    NATIVE_SCHEMA = "native_schema"
    TOOL_CALL = "tool_call"
    JSON_MODE = "json_mode"
    PROMPT_PARSE = "prompt_parse"


@dataclass(frozen=True, slots=True)
class CapabilityProfile:
    """What one model accepts. `strategies` is kept in the fixed order of `Strategy`."""

    strategies: tuple[Strategy, ...] = (Strategy.PROMPT_PARSE,)
    accepts_temperature: bool = True
    accepts_top_p: bool = True
    forbidden_schema_keywords: tuple[str, ...] = ()
    max_schema_properties: int | None = None
    max_input_tokens: int | None = None
    max_output_tokens: int | None = None
    embedding_dimensions: int | None = None
    query_prefix: str = ""
    passage_prefix: str = ""
    parse_retries: int = 2

    @property
    def strategy(self) -> Strategy:
        """The strategy the class uses: the first the profile lists, in the fixed order."""
        return self.strategies[0]


_ALL = tuple(Strategy)
_NO_SAMPLING = MappingProxyType({"accepts_temperature": False, "accepts_top_p": False})

# Every Databricks serving endpoint. Source: docs/reference/databricks-platform.md, Models;
# https://docs.databricks.com/aws/en/machine-learning/model-serving/structured-outputs
# (prefixItems added from the same page on 2026-10-07).
_DATABRICKS: Mapping[str, Any] = MappingProxyType(
    {
        "strategies": _ALL,
        "forbidden_schema_keywords": ("$ref", "anyOf", "oneOf", "allOf", "pattern", "prefixItems"),
        "max_schema_properties": 64,
    }
)

_PROVIDERS: Mapping[str, Mapping[str, Any]] = MappingProxyType(
    {
        "databricks": _DATABRICKS,
        "openai_compatible": MappingProxyType({}),
        # The fakes answer any request, so every strategy can be exercised against them.
        "fake": MappingProxyType({"strategies": _ALL}),
    }
)

# Model families, matched by name prefix up to a boundary (`-`, `.`, `:`, `_` or the end).
_FAMILIES: Mapping[str, Mapping[str, Mapping[str, Any]]] = MappingProxyType(
    {
        "openai_compatible": MappingProxyType(
            {
                # json_schema response_format: gpt-4o-mini, gpt-4o-2024-08-06 and later.
                # https://platform.openai.com/docs/guides/structured-outputs
                "gpt-4o": MappingProxyType({"strategies": _ALL}),
                "gpt-4.1": MappingProxyType({"strategies": _ALL}),
                # Reasoning models refuse temperature and top_p (gpt-5 accepts only 1, per
                # community reports [inferred]; GPT-6: "remove temperature, top_p" when
                # reasoning is on). https://developers.openai.com/api/docs/guides/latest-model
                "gpt-5": MappingProxyType({"strategies": _ALL, **_NO_SAMPLING}),
                "gpt-6": MappingProxyType({"strategies": _ALL, **_NO_SAMPLING}),
            }
        ),
        "databricks": MappingProxyType(
            {
                # Claude takes json_schema but not json_object.
                # https://docs.databricks.com/aws/en/machine-learning/model-serving/structured-outputs
                "databricks-claude": MappingProxyType(
                    {
                        "strategies": (
                            Strategy.NATIVE_SCHEMA,
                            Strategy.TOOL_CALL,
                            Strategy.PROMPT_PARSE,
                        )
                    }
                ),
            }
        ),
    }
)

# Exact model names, for facts documented for one model only.
_EXACT: Mapping[str, Mapping[str, Mapping[str, Any]]] = MappingProxyType(
    {
        "openai_compatible": MappingProxyType(
            {
                # The first gpt-4o snapshot predates json_schema; JSON mode or tools only.
                # https://platform.openai.com/docs/guides/structured-outputs
                "gpt-4o-2024-05-13": MappingProxyType(
                    {"strategies": (Strategy.TOOL_CALL, Strategy.JSON_MODE, Strategy.PROMPT_PARSE)}
                ),
            }
        ),
        "databricks": MappingProxyType(
            {
                # HTTP 400 on temperature, top_p or top_k. Documented for Sonnet 5 only, so
                # databricks-claude-sonnet-5-5 does not inherit it.
                # docs/reference/databricks-platform.md, Models
                "databricks-claude-sonnet-5": _NO_SAMPLING,
                # Unverified until the live test (T044) confirms the dimension. "Configurable
                # dimensionality up to 1024", context "~32K tokens", rounded down here.
                # https://learn.microsoft.com/en-us/azure/databricks/machine-learning/foundation-models/supported-models
                "databricks-qwen3-embedding-0-6b": MappingProxyType(
                    {"embedding_dimensions": 1024, "max_input_tokens": 32_000}
                ),
            }
        ),
    }
)

_BOUNDARIES = frozenset("-.:_")


def capability_profile(
    provider: str, model: str, overrides: CapabilityOverrides | None = None
) -> CapabilityProfile:
    """The profile of `model` on `provider`, with the settings' overrides applied last."""
    fields: dict[str, Any] = dict(_PROVIDERS.get(provider, {}))
    family = _longest_family(_FAMILIES.get(provider, {}), model)
    if family is not None:
        fields.update(family)
    fields.update(_EXACT.get(provider, {}).get(model, {}))
    if overrides is not None:
        fields.update(overrides.model_dump(exclude_none=True))
    if "strategies" in fields:
        listed = {Strategy(name) for name in fields["strategies"]}
        fields["strategies"] = tuple(strategy for strategy in Strategy if strategy in listed)
    return dataclasses.replace(CapabilityProfile(), **fields)


def _longest_family(
    families: Mapping[str, Mapping[str, Any]], model: str
) -> Mapping[str, Any] | None:
    matches = [
        prefix
        for prefix in families
        if model == prefix or (model.startswith(prefix) and model[len(prefix)] in _BOUNDARIES)
    ]
    return families[max(matches, key=len)] if matches else None
