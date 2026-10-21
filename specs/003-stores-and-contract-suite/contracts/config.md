# Contract: `tenetrag.config` (changes from M0 and 002)

This feature adds the profile's index section and `text_languages` to M0's
[config contract](../../001-sdk-foundation/contracts/config.md), as
changed by [002](../../002-packs-and-corpus/contracts/config.md).
Everything not listed here stays as those state it. The shapes are in
[data-model.md §8](../data-model.md#8-profile-index-section-delta-to-m0-data-model-2).

## 1. The `index` section

```python
IndexId = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,39}$")]

class IndexSettings(_Settings):    # frozen, extra="forbid"
    id: Annotated[IndexId, Operational()]
    graph: Annotated[ConnectionName, Operational()]
    vectors: Annotated[ConnectionName | None, Operational()] = None
        # None: the graph connection. Read it through vector_connection.

    @property
    def vector_connection(self) -> str: ...    # vectors or graph

class Profile(_Settings):
    ...
    index: Annotated[IndexSettings | None, Operational()] = None

VECTOR_MAX_DIMENSIONS: Mapping[str, int]       # {"postgres": 2000, "neo4j": 4096}
```

- The index id becomes the Postgres schema `tenetrag_<id>` and the Neo4j
  `index_id` property. The pattern keeps the schema name under 63 bytes
  with no quoting (research R5).
- Every field is operational: moving an index to another connection or
  id changes no stage hash, since the stored content is the same.
  `field_phases()` resolves each to `(Phase.QUERY, None)`.
- A profile with no `index` still loads: M0's model tests and 002's
  pack checks need none. `open_stores` refuses it (stores.md §5).
- `IndexSettings` and `VECTOR_MAX_DIMENSIONS` are exported from
  `tenetrag.config`.

## 1b. `text_languages`

```python
LanguageCode = Annotated[str, Field(pattern=r"^[a-z]{2,3}$")]

class Profile(_Settings):
    ...
    text_languages: Annotated[
        tuple[LanguageCode, ...], AfterValidator(_language_set), IndexTime(Stage.CHUNK)
    ] = ()
```

- The corpus's languages. `norm` runs the extra rules of each, at index
  and query time alike ([text.md](text.md),
  [ADR 0025](../../../docs/decisions/0025-normalize-text-by-the-languages-the-profile-names.md)).
  A language with no rules adds nothing, so `en` is accepted and changes
  nothing today.
- Codes are ISO 639 codes with no region: `vi`, `en`, `fil`. `VI`,
  `vi-VN` and `Vietnamese` fail with the field named.
- Sorted and without repeats, so `[vi, en, vi]` loads as `("en", "vi")`
  and the order written changes no hash.
- Index-time in the chunk stage, the first stage that writes a `_norm`
  field. Adding the field gave every profile a new chunk stage hash
  (`text_languages: []` in the chunk fields); M0's golden hashes were
  pinned again in 003 phase 2.

## 2. Checks at load

A `Profile` model validator, so `load_profile`, `profile_from_yaml` and
`profile_from_dict` all raise `ConfigError` through M0's load errors,
with every problem listed (FR-039):

| Check | Message names |
|---|---|
| `index.graph` is a key of `connections` | the missing name and the connections that exist |
| `index.vectors`, when set, is a key of `connections` | the same |
| each connection's kind serves its role | the connection and its kind; both kinds serve both roles today, so this fails only for a kind added later without a store |
| the stated embedding dimensions fit | the dimensions, the vector connection, its kind and its maximum, and that the model or the vector connection must change |

- The stated dimensions are `models.embedding.dimensions`, else
  `models.embedding.capabilities.embedding_dimensions`. When neither is
  set, the shipped capability profile decides at model creation, and
  `ensure_collections` refuses a size above `max_dimensions` with the
  same message (stores.md §1).
- No check needs a server.

```yaml
# profiles/local.yaml
connections:
  pg:    {kind: postgres, host: localhost, database: tenetrag, credential: {kind: basic, user: tenetrag, password_env: TENETRAG_PG_PASSWORD}}
  graph: {kind: neo4j, uri: bolt://localhost:7687, credential: {kind: none}}
models:
  embedding: {provider: fake, model: fake-embed, dimensions: 768}
index:
  id: alpha
  graph: graph        # Neo4j holds the graph
  vectors: pg         # Postgres holds the vectors: a split pairing
```

```text
ConfigError: The profile has 2 problems:
  - index.vectors: no connection `pgvector`; use one of: graph, pg
  - models.embedding.dimensions: 3072 dimensions exceed the 2000 that connection `pg` (postgres) can index; choose a smaller embedding model or another vector connection
```

## Behaviour pinned by tests

`tests/unit/config/test_index.py`:

| Test | Asserts |
|---|---|
| `test_index_optional` | a profile with no `index` loads, and `profile.index is None` |
| `test_index_id_pattern` | `alpha` and `a_1` load; `Alpha`, `1a`, `a-b` and 41 characters fail with the pattern in the message (FR-038) |
| `test_vectors_default_to_graph` | `index: {id: a, graph: pg}` gives `vector_connection == "pg"` |
| `test_unknown_connection` | a graph or vector name with no connection fails, naming it and the ones that exist (FR-039) |
| `test_dimensions_over_maximum` | 2001 dimensions with a Postgres vector connection fail; 2001 with Neo4j load; 4097 with Neo4j fail |
| `test_capability_override_dimensions` | the same limit applies to `capabilities.embedding_dimensions` when `dimensions` is unset |
| `test_problems_listed_together` | an unknown connection and too many dimensions give one error with both lines |
| `test_index_is_operational` | `field_phases()` gives `(Phase.QUERY, None)` for `index.id`, `index.graph` and `index.vectors` |
| `test_index_moves_no_hash` | two profiles that differ only in `index` give equal stage hashes |
| `test_extra_field_refused` | `index.writer: x` fails as an unknown field |

`tests/unit/config/test_profile.py`, `test_phases.py` and
`test_hashing.py` (§1b):

| Test | Asserts |
|---|---|
| `test_empty_mapping_gives_all_defaults` | `text_languages == ()` |
| `test_text_languages_accepted` | `[vi]`, `[en, vi]` and `[fil]` load |
| `test_text_languages_rejected` | `VI`, `Vietnamese`, `vi-VN`, `e` and `""` fail, naming `text_languages` |
| `test_text_languages_sorted_without_repeats` | `[vi, en, vi]` gives `("en", "vi")` |
| `test_index_time_field_set_is_pinned` | `text_languages` resolves to the chunk stage |
| `test_hash_follows_the_spec_recipe` | the chunk hash of `text_languages: [vi]` follows the data-model §8 recipe of M0 |
| `test_hash_chunk_only` | changing `text_languages` changes only the chunk hash; `[vi, en]` and `[en, vi]` hash alike |
| `test_hash_default_equals_omitted` | `text_languages: []` hashes as when it is left out |
