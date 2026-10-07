# Contract: `tenetrag.auth`

Imports allowed: the standard library, `tenetrag.config`,
`tenetrag.protocols`, and `databricks-sdk` only behind the `databricks`
extra, imported lazily. Shapes are in
[data-model.md §3 and §4](../data-model.md#4-credentials-in-code). ADR
0003 left the constructor names to M0. These are those names.

```python
class Secret:
    def __init__(self, value: str) -> None: ...      # empty value -> CredentialSourceError
    @classmethod
    def from_env(cls, name: str) -> Secret: ...      # unset or empty -> CredentialSourceError naming `name`
    def reveal(self) -> str: ...
    # __repr__ and __str__ -> "Secret('***')"; no __eq__ on the value

class Credentials:                                   # constructors only
    # any target
    @staticmethod
    def none() -> Credential: ...
    # OpenAI-compatible
    @staticmethod
    def api_key(key: Secret) -> Credential: ...
    # Neo4j, Postgres
    @staticmethod
    def basic(user: str, password: Secret) -> Credential: ...
    @staticmethod
    def token_provider(user: str, mint: Callable[[], AccessToken], *, identity: str) -> Credential: ...
    # Databricks
    @staticmethod
    def pat(host: str, token: Secret) -> Credential: ...
    @staticmethod
    def obo(host: str, token: Secret) -> Credential: ...
    @staticmethod
    def oauth_m2m(host: str, client_id: str, client_secret: Secret) -> Credential: ...
    @staticmethod
    def oauth_u2m(host: str) -> Credential: ...            # terminal only
    @staticmethod
    def cli_profile(name: str, *, config_file: str | None = None) -> Credential: ...
    @staticmethod
    def runtime() -> Credential: ...
    @staticmethod
    def workspace_client(client: "databricks.sdk.WorkspaceClient") -> Credential: ...

@dataclass(frozen=True, slots=True)
class AccessToken:
    value: Secret
    expires_at: datetime | None

@dataclass(frozen=True)
class Credential:
    kind: CredentialKind
    identity: str          # non-secret label; pools are keyed by it
    source: str            # "code", "env:NAME", "cli_profile:NAME", "runtime"
    refreshable: bool
    # private: _token_source for bearer kinds, _user/_password for basic

class TargetKind(Enum): NEO4J, POSTGRES, OPENAI_COMPATIBLE, DATABRICKS_MODEL

def resolve_credential(
    target: TargetKind,
    target_name: str,                        # dotted profile path, used in errors
    source: CredentialSource | None,         # from the profile
    override: Credential | None = None,      # from code; wins
    *,
    workspace_url: str | None = None,        # the model's; pat, oauth_m2m and oauth_u2m sources need it
) -> Credential: ...
    # MissingCredentialError, CredentialSourceError or CredentialMismatchError
```

Accepted kinds per target:

| Target | Kinds |
|---|---|
| Neo4j | `basic`, `none` |
| Postgres | `basic`, `token_provider` |
| OpenAI-compatible | `api_key`, `none` |
| Databricks model | `pat`, `obo`, `oauth_m2m`, `oauth_u2m`, `cli_profile`, `runtime`, `workspace_client` |

**Delegated kinds.** The kinds that delegate to the Databricks SDK
(`oauth_m2m`, `oauth_u2m`, `cli_profile`, `runtime`, `workspace_client`)
log one warning per process when any `DATABRICKS_*`, `ARM_*` or
`GOOGLE_CREDENTIALS` variable is set. The warning names the variables,
never their values (ADR 0018).

## Behaviour pinned by tests

| Test | Asserts |
|---|---|
| `test_missing_credential` | no source and no override raises `MissingCredentialError` naming target and kinds; no socket opened |
| `test_ambient_vars_never_read` | with `DATABRICKS_TOKEN`, `OPENAI_API_KEY`, `NEO4J_PASSWORD` and `PGPASSWORD` set and no source named, every target raises `MissingCredentialError` |
| `test_named_env_unset` | `password_env: X` with `X` unset raises `CredentialSourceError` naming `X` |
| `test_override_wins` | a code credential beats the profile source |
| `test_mismatch` | `obo` for Neo4j raises `CredentialMismatchError` |
| `test_refresh_same_identity` | a fake refreshable source refreshes once under the same `identity`; a second rejection raises `CredentialRejectedError` |
| `test_obo_not_refreshed` | an expired OBO rejection raises at once |
| `test_runtime_outside_databricks` | `runtime()` with no `DATABRICKS_RUNTIME_VERSION` raises `CredentialSourceError` without network |
| `test_u2m_needs_terminal` | `oauth_u2m` with no terminal raises `CredentialSourceError` that points to `cli_profile` |
| `test_databricks_env_warning` | a delegated kind with `DATABRICKS_HOST` set logs one warning naming it and not its value |
| `test_secrets_never_leak` | planted secrets never appear in `repr`, `str`, logs or exception chains (SC-006) |
