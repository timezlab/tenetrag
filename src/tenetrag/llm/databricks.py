"""Databricks serving endpoints through the OpenAI-compatible classes (research R9).

The endpoints live at `{workspace}/serving-endpoints`, and `model` is the
endpoint name. The workspace comes from `workspace_url`, or from a
credential that names its own (cli_profile, runtime, workspace_client).
"""

from __future__ import annotations

from urllib.parse import urlsplit

from tenetrag.auth.credentials import Credential
from tenetrag.config import ChatModelSettings, EmbeddingModelSettings
from tenetrag.llm.openai_compatible import OpenAICompatibleChatModel, OpenAICompatibleEmbeddingModel
from tenetrag.protocols.errors import ConfigError


class DatabricksChatModel(OpenAICompatibleChatModel):
    # Foundation Model APIs take the output limit as max_tokens.
    _max_tokens_field = "max_tokens"

    def _base_url(self, settings: ChatModelSettings, credential: Credential) -> str:
        return serving_endpoints_url(settings.workspace_url, credential)


class DatabricksEmbeddingModel(OpenAICompatibleEmbeddingModel):
    def _base_url(self, settings: EmbeddingModelSettings, credential: Credential) -> str:
        return serving_endpoints_url(settings.workspace_url, credential)


def serving_endpoints_url(workspace_url: str | None, credential: Credential) -> str:
    """`{workspace}/serving-endpoints`. Settings and credential must agree on the workspace."""
    host = credential._host
    if workspace_url is not None and host is not None and _origin(workspace_url) != _origin(host):
        raise ConfigError(
            f"workspace_url is {workspace_url}, but the credential {credential.identity} belongs "
            f"to {host}. Use one workspace for both, or leave workspace_url unset."
        )
    url = workspace_url or host
    if url is None:
        raise ConfigError(
            "A Databricks model needs its workspace: set `workspace_url` on the model, or use a "
            "credential that names one (cli_profile, runtime, or a configured WorkspaceClient)."
        )
    return f"{url.rstrip('/')}/serving-endpoints"


def _origin(url: str) -> tuple[str, str]:
    parts = urlsplit(url)
    return parts.scheme.lower(), parts.netloc.lower()
