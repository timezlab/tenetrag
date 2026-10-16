# Contract: `tenetrag.config` and `tenetrag._yaml` (changes from M0)

This feature changes M0's
[config contract](../../001-sdk-foundation/contracts/config.md) in three
places. Everything not listed here stays as M0 states it. The field is in
[data-model.md §7](../data-model.md#7-profile-field-delta-to-m0-data-model-2).

## 1. The `pack` field

```python
class Profile(BaseModel):          # frozen, extra="forbid", as in M0
    ...
    pack: Annotated[PackReference, Operational()] = "core"
        # A value ending in .yaml or .yml is a path. Anything else must match
        # ^[a-z][a-z0-9]*(-[a-z0-9]+)*$. Whether a named pack exists is
        # checked by tenetrag.packs.load_pack, not by the profile.
```

- `load_profile(path)` makes a relative pack path absolute against the
  profile file's directory, so a profile and its pack can move together.
- `profile_from_yaml` and `profile_from_dict` keep the value as written;
  a relative path then resolves against the caller's working directory.
- `field_phases()` resolves `pack` to `(Phase.QUERY, None)`, like every
  other operational leaf.

```yaml
# profiles/alpha.yaml
pack: packs/alpha-ops.yaml        # becomes /…/profiles/packs/alpha-ops.yaml
models: { … }
```

## 2. `stage_hashes` takes the pack's index hash

```python
def stage_hashes(profile: Profile, *, pack_hash: str) -> dict[Stage, str]: ...
    # pack_hash is PackStack.index_hash. It enters the fields of Stage.EXTRACT
    # and Stage.RESOLVE under the name "pack". The other stages are unchanged.
    # Raises ValueError when pack_hash is not "sha256:" followed by 64 hex digits:
    # a caller bug, not a profile problem.
```

The caller loads the pack the profile names and passes its hash:

```python
from tenetrag.config import load_profile
from tenetrag.config.hashing import stage_hashes
from tenetrag.packs import load_pack

profile = load_profile("profiles/alpha.yaml")
stack = load_pack(profile.pack)
hashes = stage_hashes(profile, pack_hash=stack.index_hash)
```

`_FORMAT` stays 1. The extract and resolve fields now always hold
`pack`, so no hash computed before this change can equal one computed
after it.

## 3. `tenetrag._yaml`

A private module in the bottom layer, beside `protocols` and `_retry`.
Its code moves unchanged from `tenetrag/config/loading.py`, with
public names inside the private module:

```python
class DuplicateKeyLoader(yaml.SafeLoader): ...
    # Was _ProfileLoader. Records each repeated key with both lines in
    # .duplicates instead of keeping the last value. Merge keys are skipped.

def parse_yaml(text: str) -> tuple[object, list[DuplicateKey]]: ...
    # Was _parse. Returns the data and the duplicate keys. Raises
    # yaml.YAMLError, including for a tag that would build an object.

class DuplicateKey: path: str; key: Hashable; line: int; first_line: int
    # Added in T019: `path` is the mapping's dotted path ("", `entities`,
    # `qs[1]`), which file.duplicate-key reports. str() gives the text the
    # profile loader printed before, so its message is unchanged.

def yaml_problem(exc: yaml.YAMLError) -> str: ...
    # Was _yaml_problem. The problem and its line and column, never the
    # offending text, which may hold a secret.
```

`config.loading` and `packs.loading` both import it. Neither keeps a
copy.

## Behaviour pinned by tests

| Test | Asserts |
|---|---|
| `test_pack_default` | a profile with no `pack` has `pack == "core"` (FR-001) |
| `test_pack_name_or_path` | `enterprise-docs`, `a/b.yaml` and `c.yml` are accepted; `Core`, `core_v2` and `a/b.json` fail with a hint naming both forms |
| `test_pack_path_relative_to_profile` | `load_profile` turns `packs/x.yaml` into an absolute path under the profile's directory; `profile_from_yaml` keeps it as written |
| `test_pack_is_operational` | `field_phases()["pack"] == (Phase.QUERY, None)` |
| `test_hash_needs_pack_hash` | calling `stage_hashes(profile)` without `pack_hash` is a `TypeError`; a malformed hash is a `ValueError` |
| `test_hash_pack_extract_and_resolve_only` | two pack hashes change `Stage.EXTRACT` and `Stage.RESOLVE` and leave the other four equal (FR-025) |
| `test_hash_pack_path_ignored` | the same pack loaded from two paths gives equal stage hashes |
| `test_hash_retrieval_and_glossary_ignored` | a user pack that changes only `retrieval`, or only its glossary, gives equal stage hashes (US2-6, SC-004) |
| `test_hash_golden` | M0's two fixture profiles, with the `core` index hash, give new pinned values for `extract` and `resolve` and M0's values for the rest |
| `test_yaml_moved` (`tests/unit/test_yaml.py`) | M0's duplicate-key, merge-key, bad-tag and no-echo tests run against `tenetrag._yaml` directly |
