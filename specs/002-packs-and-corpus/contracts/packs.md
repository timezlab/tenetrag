# Contract: `tenetrag.packs`

Imports allowed: the standard library, pydantic, PyYAML,
`tenetrag.protocols` (for `ConfigError`) and `tenetrag._yaml`. Shapes are
in [data-model.md §1 to §6](../data-model.md#1-problems-and-rule-ids).
The identity cases are in [identity-cases.md](identity-cases.md).

```python
from collections.abc import Mapping, Sequence
from os import PathLike

def shipped_packs() -> tuple[ShippedPack, ...]: ...
    # Sorted by name: (ShippedPack("core", 1), ShippedPack("enterprise-docs", 1)).
    # Reads package data through importlib.resources; works with no extra installed.

def load_pack(
    reference: str | PathLike[str],
    *,
    base_dir: str | PathLike[str] | None = None,
) -> PackStack: ...
    # reference: a shipped pack name, or a path ending in .yaml or .yml.
    # A relative path resolves against base_dir, else the working directory.
    # A path in `extends` resolves against the file that holds it.
    # Raises ConfigError listing every error (data model §1). Warnings are
    # returned on PackStack.warnings and logged once by the "tenetrag.packs" logger.

def compile_schema(
    stack: PackStack,
    types: Sequence[str] | None = None,
    *,
    max_properties: int = 64,
) -> CompiledSchema: ...
    # types=None: every type with extract: true. Otherwise the named types only.
    # Raises ConfigError for a name the stack lacks, a type with extract: false,
    # a selection with no type, or a schema with more than max_properties
    # properties (the message gives the count and the parts by size).

def check_coverage(stack: PackStack) -> CoverageReport: ...
    # Pure: no I/O, no model call.

class ShippedPack(NamedTuple): name: str; version: int
class Stamp(NamedTuple):       name: str; version: int; content_hash: str
class Mode(Enum):              STRICT = "strict"; DISCOVERY = "discovery"

# Frozen, read-only (data model §3 and §6):
class PackStack: ...
class PackProblem: ...
class CompiledSchema: ...
class CoverageReport: ...
```

The names above are exported from `tenetrag.packs`. The parts of a
stack (`EntityType`, `Attribute`, `Key`, `Scope`, `RelationType`,
`EventType`, `FactType` and the others of data model §3) are exported
too, so that the engine can type its arguments. The pydantic models of a
pack file stay private to `tenetrag.packs.format`.

## Example: a user pack on `enterprise-docs`

```yaml
# packs/alpha-ops.yaml, named in the profile as  pack: packs/alpha-ops.yaml
pack: alpha-ops
version: 1
extends: enterprise-docs
entities:
  Vendor:
    description: A company that supplies goods or services to the organization under a contract.
    examples: [Công ty TNHH Gamma]
    attributes:
      tax_code: {range: str, compare: digits, unique: global}
    identity: [[tax_code]]
    vetoes: [tax_code]
relations:
  SUPPLIES:
    from: [Vendor]
    to: [Organization]
    time: interval
enums:
  OrgCategory: [vendor_desk]          # adds one value to core's enum
competency_questions:
  - {id: alpha-ops-1, text: "Which vendors supplied unit U in year Y?", needs: [Vendor, SUPPLIES]}
```

```python
from tenetrag.packs import load_pack, compile_schema, check_coverage

stack = load_pack("packs/alpha-ops.yaml")
stack.stamp                  # Stamp(name='alpha-ops', version=1, content_hash='sha256:…')
[p.name for p in stack.packs]  # ['core', 'enterprise-docs', 'alpha-ops']
stack.entities["Person"].identity[0].attributes   # ('scope', 'employee_id')
compiled = compile_schema(stack)
compiled.property_count      # 52, whatever the number of types
check_coverage(stack).passed # True: 15 questions, 6 + 8 + 1
```

## Example: a failed load

```text
ConfigError: The pack stack has 3 problems:
  - packs/alpha-ops.yaml: entities.Vendor.vetos: unknown field; remove it or use a field of the pack format [file.unknown-field]
  - packs/alpha-ops.yaml: entities: `Vendor` appears twice, at line 12 (first at line 5) [file.duplicate-key]
  - packs/alpha-ops.yaml: relations.SUPPLIES.to[0]: no entity type `Organisation`; define it or use one of the stack's types [ref.unknown]
```

## Behaviour pinned by tests

Loading and stacking (`test_format.py`, `test_stacking.py`,
`test_checks.py`):

| Test | Asserts |
|---|---|
| `test_enterprise_docs_merged` | `Organization.scope.when["category"]` holds `unit` and the five categories of `enterprise-docs`; `Person.identity` is `[[scope, employee_id], [email]]` (US1-1) |
| `test_user_pack_additions` | the example pack's type, relation and enum value are in the stack, and its question is checked (US1-2, SC-005) |
| `test_broken_pack` | parametrized over `tests/fixtures/packs/broken/<rule>/`: loading fails, and the error names the rule, the file and the path; for the three warning rules, the pack loads with that warning (SC-003) |
| `test_every_rule_has_a_broken_pack` | the rule ids the module defines equal the fixture directory names, both ways |
| `test_conflict_names_both_packs` | a changed range names the parent and the child pack (US1-3) |
| `test_parents_identical_merge`, `test_parents_conflict` | two parents with one identical attribute load silently; with two ranges, both packs are named (US1-4) |
| `test_problems_reported_together` | `vetos`, a duplicate type and an unknown endpoint give one error with three lines (US1-5) |
| `test_evidence_without_corroborate_warns` | the pack loads, with one warning naming the type (US1-6) |
| `test_instruction_text_by_mode` | the same description fails in `strict` and warns in `discovery`; the word "customer(s)" passes (US1-7) |
| `test_yaml_tag_refused` | a `!!python/object` tag fails with `file.yaml`, and no object is built (US1-8) |
| `test_cycle_named` | `a → b → a` fails, and the message lists the cycle (US1-9) |
| `test_shared_ancestor_once` | a user pack on `[enterprise-docs, finance]` lists `core` once, in linear order `core, enterprise-docs, finance, user` |
| `test_stack_read_only` | setting an attribute or a mapping item of the stack raises (FR-013) |
| `test_nfc` | a pack written in NFD loads equal to its NFC form (FR-011) |
| `test_text_never_echoed` | a broken file holding a secret-shaped value never shows it in the error |

Shipped packs and hashes (`test_shipped.py`, `test_hashing.py`):

| Test | Asserts |
|---|---|
| `test_shipped_listed` | `shipped_packs()` returns `core` 1 and `enterprise-docs` 1 (FR-018) |
| `test_shipped_load_clean` | each loads with no error, no warning and no glossary (SC-001, FR-017) |
| `test_shipped_pins` | each shipped file's hash equals its `(name, version)` pin, else fails saying to bump the version (FR-016, US2-7) |
| `test_shipped_have_questions` | each shipped file has at least one competency question (US3-4) |
| `test_no_draft_copies` | `docs/product/packs/` holds no `core.yaml` or `enterprise-docs.yaml` (FR-015) |
| `test_finance_draft_stacks` | the draft loads and compiles alone on `core` and as `[enterprise-docs, finance]` (FR-019) |
| `test_hash_ignores_layout` | reordered keys, changed comments and NFD text keep all four hashes (US2-5, SC-004) |
| `test_hash_description_change` | one changed description changes the content and index hashes |
| `test_hash_set_order` | reordering `vetoes` or `to` keeps the hashes; reordering `identity` keys changes them |
| `test_hash_retrieval_only` | a retrieval change moves the content hash, not the index hash (US2-6) |
| `test_hash_glossary_only` | a glossary change moves the glossary hash, not the index hash (US2-6) |
| `test_hash_golden` | `core` and `enterprise-docs` give pinned content, index and glossary hashes on every CI Python |

Compile and coverage (`test_compile.py`, `test_coverage.py`):

| Test | Asserts |
|---|---|
| `test_compiled_fits_providers` | every shipped stack, the `finance` stacks and the example pack pass `check_schema` under the Databricks profile, with 52 properties (US2-1, SC-002) |
| `test_compile_limit` | `max_properties=40` fails with the count 52 and the parts listed by size (US2-2) |
| `test_compile_subset` | `types=["Person", "MEMBER_OF"]` gives enums with those names only (US2-3) |
| `test_compile_rejects_bad_subset` | an unknown name, or `Statement` under `core`, raises `ConfigError` |
| `test_extract_false_left_out` | `Statement` is absent under `core` and present under a child that sets `extract: true` (US2-4) |
| `test_compile_empty_parts_left_out` | a subset of one entity type with no attribute has no `relations` enum and no `attributes` item |
| `test_compile_golden` | `compile_schema(core).to_json()` equals `tests/fixtures/packs/compiled/core.json` byte for byte (FR-022) |
| `test_many_types_fit` | a generated user pack with 60 entity types still compiles to 52 properties (edge case) |
| `test_coverage_shipped` | `enterprise-docs` passes all 14 questions (US3-1, SC-001) |
| `test_coverage_missing_relation` | a question needing an undefined relation reports it as missing (US3-2) |
| `test_coverage_not_extracted` | a question needing `Statement` on `core` reports it as not extracted (US3-3) |
| `test_load_warns_unmet_question` | the same pack loads with one `coverage.unmet` warning |
