"""Chat and embedding models behind one interface (contracts/llm.md).

`chat_model_from_settings` and `embedding_model_from_settings` pick the class
by `provider` and resolve the credential with the target's name. `openai` is
needed only by the OpenAI-compatible and Databricks classes, and is imported
when one is built.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from tenetrag.auth import Credential, TargetKind, resolve_credential
from tenetrag.config import ChatModelSettings, EmbeddingModelSettings
from tenetrag.llm.capabilities import CapabilityProfile, Strategy, capability_profile
from tenetrag.llm.databricks import DatabricksChatModel, DatabricksEmbeddingModel
from tenetrag.llm.fake import FakeChatModel, FakeEmbeddingModel, ScriptItem
from tenetrag.llm.openai_compatible import (
    OpenAICompatibleChatModel,
    OpenAICompatibleEmbeddingModel,
    embedding_limits,
)
from tenetrag.protocols.models import ChatModel, EmbeddingModel

if TYPE_CHECKING:
    import httpx2

__all__ = [
    "CapabilityProfile",
    "DatabricksChatModel",
    "DatabricksEmbeddingModel",
    "FakeChatModel",
    "FakeEmbeddingModel",
    "OpenAICompatibleChatModel",
    "OpenAICompatibleEmbeddingModel",
    "Strategy",
    "capability_profile",
    "chat_model_from_settings",
    "embedding_model_from_settings",
]


def chat_model_from_settings(
    settings: ChatModelSettings,
    *,
    target_name: str,
    credential: Credential | None = None,
    http_client: httpx2.Client | None = None,
    fake_responses: Sequence[ScriptItem] = (),
) -> ChatModel:
    """The chat model the settings describe. `target_name` is its profile path, for errors.

    `http_client` (an `httpx2.Client`) and `fake_responses` are test seams: the
    first reaches the HTTP providers, the second the fake; each provider ignores
    the other.
    """
    capabilities = capability_profile(settings.provider, settings.model, settings.capabilities)
    if settings.provider == "fake":
        return FakeChatModel(fake_responses, model_id=settings.model, capabilities=capabilities)
    resolved = _credential(settings, target_name, credential)
    cls = DatabricksChatModel if settings.provider == "databricks" else OpenAICompatibleChatModel
    return cls(settings, credential=resolved, capabilities=capabilities, http_client=http_client)


def embedding_model_from_settings(
    settings: EmbeddingModelSettings,
    *,
    target_name: str,
    credential: Credential | None = None,
    http_client: httpx2.Client | None = None,
) -> EmbeddingModel:
    """The embedding model the settings describe. `target_name` is its profile path, for errors.

    Its dimension and input limit must be known, from the settings or the
    shipped profile; otherwise `ConfigError` names the target.
    """
    capabilities = capability_profile(settings.provider, settings.model, settings.capabilities)
    if settings.provider == "fake":
        dimensions = settings.dimensions or capabilities.embedding_dimensions or 8
        return FakeEmbeddingModel(
            dimensions,
            model_id=settings.model,
            max_input_tokens=capabilities.max_input_tokens or 8192,
        )
    embedding_limits(settings, capabilities, label=target_name)
    resolved = _credential(settings, target_name, credential)
    cls = (
        DatabricksEmbeddingModel
        if settings.provider == "databricks"
        else OpenAICompatibleEmbeddingModel
    )
    return cls(settings, credential=resolved, capabilities=capabilities, http_client=http_client)


def _credential(
    settings: ChatModelSettings | EmbeddingModelSettings,
    target_name: str,
    credential: Credential | None,
) -> Credential:
    target = (
        TargetKind.DATABRICKS_MODEL
        if settings.provider == "databricks"
        else TargetKind.OPENAI_COMPATIBLE
    )
    return resolve_credential(
        target, target_name, settings.credential, credential, workspace_url=settings.workspace_url
    )
