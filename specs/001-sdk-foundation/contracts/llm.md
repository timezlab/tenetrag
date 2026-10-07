# Contract: `tenetrag.protocols` (models) and `tenetrag.llm`

## Protocols

These live in `tenetrag.protocols` and import only the standard library.
They follow
[engine brief §6.4](../../../docs/product/engine-brief.md#64-model-protocols),
with the additive result fields of
[data-model.md §9](../data-model.md#9-model-results).

```python
class ChatModel(Protocol):
    @property
    def model_id(self) -> str: ...
    def generate(self, messages: Sequence[Message], *, schema: Mapping[str, Any] | None = None,
                 max_output_tokens: int | None = None,
                 temperature: float | None = None) -> ChatResult: ...
        # None: the settings' max_output_tokens and temperature

class EmbeddingModel(Protocol):
    @property
    def model_id(self) -> str: ...
    @property
    def dimensions(self) -> int: ...
    @property
    def max_input_tokens(self) -> int: ...
    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...
    def embed_queries(self, texts: Sequence[str]) -> list[list[float]]: ...
    def count_tokens(self, text: str) -> int | None: ...
```

The attributes are read-only properties, so a plain attribute or a
property satisfies them. `max_input_tokens` is a required protocol attribute. It comes from the
shipped capability profile, or from `capabilities.max_input_tokens` in the
settings. When neither gives it, model creation raises `ConfigError`
asking for it. Without
a limit, over-long texts could not be rejected before the call
(FR-024, edge cases).

## Factories and classes (`tenetrag.llm`)

Imports allowed: the standard library, `tenetrag.protocols`,
`tenetrag.config`, `tenetrag.auth`, `tenetrag._retry`, jsonschema, and
`openai` behind the `openai` or `databricks` extra, imported lazily.

```python
def chat_model_from_settings(settings: ChatModelSettings, *, target_name: str,
                             credential: Credential | None = None,
                             http_client: httpx2.Client | None = None,
                             fake_responses: Sequence[ScriptItem] = ()) -> ChatModel: ...
def embedding_model_from_settings(settings: EmbeddingModelSettings, *, target_name: str,
                                  credential: Credential | None = None,
                                  http_client: httpx2.Client | None = None) -> EmbeddingModel: ...
    # Pick the class by `provider`; resolve the credential (auth contract);
    # raise MissingExtraError when `openai` is not installed.
    # `http_client` and `fake_responses` are test seams: the first reaches the
    # HTTP providers, the second the fake; each provider ignores the other.

class OpenAICompatibleChatModel: ...      # ChatModel
class OpenAICompatibleEmbeddingModel: ... # EmbeddingModel
    # Both: (settings, *, credential, capabilities, http_client=None,
    #        sleep=time.sleep, clock=time.monotonic); the credential is used as given.
class DatabricksChatModel(OpenAICompatibleChatModel): ...      # base_url = {workspace}/serving-endpoints
class DatabricksEmbeddingModel(OpenAICompatibleEmbeddingModel): ...
class FakeChatModel: ...                  # data-model §10
class FakeEmbeddingModel: ...

class Strategy(StrEnum): NATIVE_SCHEMA, TOOL_CALL, JSON_MODE, PROMPT_PARSE  # the fixed order
@dataclass(frozen=True)
class CapabilityProfile: ...              # data-model §5
def capability_profile(provider: str, model: str,
                       overrides: CapabilityOverrides | None = None) -> CapabilityProfile: ...
```

## Request rules

The rules run in this order on every call:
1. Empty texts, or texts over `max_input_tokens` (when `count_tokens`
   knows), raise `UnsupportedRequestError` with their positions.
2. Schema keywords in `forbidden_schema_keywords`, or more properties
   than `max_schema_properties`, raise `UnsupportedRequestError` naming
   the first offender.
3. Parameters the profile does not accept are dropped, such as
   `temperature` on `claude-sonnet-5`.
4. The strategy is the first one in the fixed order that the profile
   lists (research R9 has the request shapes).
5. The call runs under the retry policy (research R10).
6. `finish_reason == "length"` raises `OutputTruncatedError`.
7. The parsed output is validated with jsonschema. On failure the class
   re-asks up to `parse_retries`, appending the validation error, and
   then raises `StructuredOutputError(strategy, attempts)`.
8. Embeddings are reordered by response index. Their dimension must equal
   `dimensions`, else `ResponseError`.

## Behaviour pinned by tests

Unit tests run with `MockTransport` from `httpx2`, passed as
`http_client`, with no network.

| Test | Asserts |
|---|---|
| `test_same_code_three_providers` | one calling function works against fake, OpenAI-compatible (mock) and Databricks (mock) chat and embedding (SC-009) |
| `test_strategy_order` | a profile without `native_schema` sends `tool_call`; `ChatResult.strategy` says so |
| `test_parse_retry_then_error` | invalid JSON twice, then valid: success after 3 attempts; always invalid: `StructuredOutputError(attempts=3)` |
| `test_truncation` | `finish_reason: length` raises `OutputTruncatedError` |
| `test_rate_limit_retry_after` | 429 with `retry-after: 1` is retried after about 1 s, then succeeds; budget exhausted raises `ModelUnavailableError` |
| `test_auth_fails_fast` | 401 on an `api_key` credential raises `CredentialRejectedError` after one request |
| `test_reauth_once` | 401 on a refreshable credential invalidates and retries once |
| `test_temperature_dropped` | the request body has no `temperature` when the profile says so |
| `test_forbidden_schema` | `anyOf` on a Databricks model raises before any request |
| `test_usage_unknown_not_zero` | missing `cached_tokens` gives `None` |
| `test_embedding_order_and_dimension` | shuffled indexes are reordered; a wrong dimension raises `ResponseError`; `[]` makes no request |
| `test_prefixes` | query and passage prefixes are applied |
| `test_openai_env_not_used_for_key` | with `OPENAI_API_KEY` and `OPENAI_BASE_URL` set, requests carry our key and URL |
| `test_openai_env_warning` | `OPENAI_ORG_ID` set logs one warning naming it |
| `test_fake_deterministic` | the same inputs give identical outputs; an exhausted script raises `AssertionError` |
| `test_custom_headers_cannot_replace_our_token` | an `Authorization` line in `OPENAI_CUSTOM_HEADERS` never replaces the credential's token, and `none` sends no header |
| `test_bad_request_names_status_and_message` | a 400 raises `LLMError` with the status and the server's message, with no chained SDK exception |
| `test_model_errors_never_leak` (SC-006) | 401, 429, 5xx, 400 and unreadable answers, with the server echoing the key, leave no planted secret in errors, logs or `repr` |
