# Contract: `tenetrag.config`

Imports allowed: the standard library, pydantic, PyYAML and
`tenetrag.protocols` (for errors). Shapes and defaults are in
[data-model.md §2 and §8](../data-model.md#2-profile).

```python
from collections.abc import Mapping
from os import PathLike
from typing import Any

def load_profile(path: str | PathLike[str]) -> Profile: ...
def profile_from_yaml(text: str) -> Profile: ...
def profile_from_dict(data: Mapping[str, Any]) -> Profile: ...
    # All three raise ConfigError listing every problem with its dotted path.
    # load_profile also raises ConfigError for an unreadable file, naming the path.

class Profile(BaseModel):          # frozen, extra="forbid"
    connections: Mapping[str, Neo4jSettings | PostgresSettings]
    models: ModelsSettings         # extraction, answer, embedding
    language: str

class Phase(Enum): INDEX = "index"; QUERY = "query"
class Stage(Enum): CHUNK, EXTRACT, RESOLVE, EMBED, CLUSTER, REPORTS   # values are the lower-case names

# Field markers, used in Annotated[...] metadata on every leaf field
class IndexTime:   def __init__(self, stage: Stage) -> None: ...
class QueryTime:   ...
class Content:     ...   # inherits the nearest phased ancestor
class Operational: ...   # always query-time

def field_phases(model: type[BaseModel] = Profile) -> dict[str, tuple[Phase, Stage | None]]: ...
    # Dotted path -> resolved phase. Raises ConfigError naming any leaf with
    # no marker, or a Content leaf with no phased ancestor.
```

`tenetrag.config.hashing` is the one module of ADR 0005:

```python
def stage_hashes(profile: Profile) -> dict[Stage, str]: ...
    # {Stage.EXTRACT: "sha256:…", …} for every Stage. Index-time leaves only.
```

## Example profile (self-hosted)

```yaml
connections:
  graph:
    kind: neo4j
    uri: bolt://localhost:7687
    credential: {kind: basic, user: neo4j, password_env: NEO4J_PASSWORD}
models:
  extraction:
    provider: openai_compatible
    base_url: http://localhost:11434/v1     # Ollama
    model: qwen3
    credential: {kind: none}
    capabilities: {strategies: [json_mode, prompt_parse]}
  answer:
    provider: openai_compatible
    base_url: http://localhost:11434/v1
    model: qwen3
    credential: {kind: none}
  embedding:
    provider: openai_compatible
    base_url: http://localhost:11434/v1
    model: bge-m3
    dimensions: 1024
    credential: {kind: none}
    capabilities: {max_input_tokens: 8192}  # no shipped profile for bge-m3
language: vi
```

## Example profile (Databricks, from a laptop)

```yaml
models:
  extraction:
    provider: databricks
    model: databricks-claude-sonnet-5
    credential: {kind: cli_profile, name: dev}
  embedding:
    provider: databricks
    model: databricks-qwen3-embedding-0-6b
    dimensions: 1024          # checked by the live smoke test
    credential: {kind: cli_profile, name: dev}
```

## Behaviour pinned by tests

| Test | Asserts |
|---|---|
| `test_duplicate_key_rejected` | `a: 1\na: 2` raises `ConfigError` naming `a` and the line |
| `test_unknown_and_invalid_reported_together` | a misspelled field and a negative timeout appear in one error |
| `test_secret_like_key_hint` | `password:` under a connection is rejected with the credential hint |
| `test_every_leaf_has_phase` | `field_phases()` succeeds and covers every leaf |
| `test_hash_ignores_query_time` | changing `models.answer` or any connection leaves every hash equal |
| `test_hash_embedding_only` | changing `models.embedding.model` changes only `Stage.EMBED` |
| `test_hash_extraction_only` | changing `models.extraction.model` changes only `Stage.EXTRACT` |
| `test_hash_default_equals_omitted` | `temperature: 0.0` written out equals leaving it out |
| `test_hash_golden` | two fixture profiles give pinned hash strings on every CI Python |
