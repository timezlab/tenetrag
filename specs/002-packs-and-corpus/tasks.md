---

description: "Task list for domain packs and the synthetic corpus (M1, part 1)"
---

# Tasks: Domain packs and the synthetic corpus (M1, part 1)

**Input**: Design documents from `specs/002-packs-and-corpus/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: Required. The constitution (Development Workflow, Tests)
overrides the template's "tests are optional" note. In every story phase,
write the tests first and watch them fail before implementing.

**Organization**: Tasks are grouped by user story. The stories are layered.
US1's `load_pack` and the shipped packs feed every other story: US2
compiles and hashes a loaded stack, US3 checks its questions, US4 checks
cases against it, and US5 checks corpus items against it. Once US1 is
done, US2 to US5 touch different files, except for small, sequential
edits to `packs/__init__.py`, `packs/problems.py` and `test_shipped.py`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: the user story the task belongs to (US1–US5)
- Paths are from the repository root. Layout: `src/tenetrag/`, `tests/`
- Each task is one reviewable unit. A test task leaves the suite failing
  only on its new tests; the implementation task after it turns them green.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: the shared YAML loader, the import rules and the empty
`packs` package

- [X] T001 Write `tests/unit/test_yaml.py` (contracts/config.md
  `test_yaml_moved`). It tests `tenetrag._yaml` directly:
  - `parse_yaml` returns the data and an empty list for a clean document;
  - a repeated key, at the top level and nested, is reported with both
    line numbers, and every duplicate in the file is listed;
  - a YAML merge key (`<<`) that overrides a key is not a duplicate;
  - `!!python/object` and `!!python/name` tags raise `yaml.YAMLError` and
    build nothing;
  - `yaml_problem` gives the problem with its line and column and never
    the offending text. Plant a `tests/support/secrets.py` value right
    next to the error mark, since PyYAML quotes only about 35 characters
    around it (M0 T028);
  - `DuplicateKeyLoader` is a `yaml.SafeLoader` subclass.

  Red: `ModuleNotFoundError` for `tenetrag._yaml`.
- [X] T002 Create `src/tenetrag/_yaml.py` by moving code unchanged out of
  `src/tenetrag/config/loading.py` (contracts/config.md §3, research R1):
  - `_ProfileLoader` becomes `DuplicateKeyLoader`, `_parse` becomes
    `parse_yaml`, and `_yaml_problem` becomes `yaml_problem`;
  - `config/loading.py` imports them and keeps no copy;
  - in `[tool.importlinter]` of `pyproject.toml`, the bottom layer becomes
    `"protocols | _retry | _yaml"`.

  T001 passes, and `tests/unit/config/test_loading.py` passes unchanged,
  which shows the move changed no behaviour. Depends on T001.
- [X] T003 Create the `packs` package:
  - `src/tenetrag/packs/__init__.py` with a module docstring that links
    `specs/002-packs-and-corpus/contracts/packs.md`;
  - `tests/unit/packs/__init__.py`;
  - in `[tool.importlinter]`, the layer `"config | packs"` replaces
    `"config"` (siblings, research R1), and `tenetrag.packs` joins the
    source modules of the forbidden contract that keeps `protocols` and
    `config` off the optional SDKs. Rename that contract to name all three.

  `shipped/` is created with its files in T020, not empty now. Run
  `uv run lint-imports` and `make check`. Depends on T002.

  Result (2026-10-15): `make check` passes with 683 unit tests, 13 of
  them in `tests/unit/test_yaml.py`. Before T002 they failed with
  `ModuleNotFoundError: No module named 'tenetrag._yaml'`.
  `tests/unit/config/test_loading.py` passed unchanged after the move.
  Faults tried:
  - both no-echo texts put the planted secret in PyYAML's own
    `str(exc)`, so a `yaml_problem` that returned it would fail;
  - `test_tripwire_detects_an_unsafe_load` shows that the tripwire
    records an object that `yaml.UnsafeLoader` builds;
  - a probe `import tenetrag.config` in `tenetrag.packs` broke the
    layers contract ("tenetrag.packs is not allowed to import
    tenetrag.config").

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the problem type and error text every pack, case and story
uses, and the test helpers for packs

**⚠️ CRITICAL**: no story work begins until this phase is complete

- [X] T004 [P] Write `tests/unit/packs/test_problems.py`. It asserts:
  - `PackProblem` is frozen, with `rule`, `file`, `path`, `message` and
    `severity` (`"error"` or `"warning"`);
  - `config_error(problems)` builds one `ConfigError` whose first line
    reads "The pack stack has 3 problems:" ("has 1 problem:" for one),
    then one line per error, `  - {file}: {path}: {message} [{rule}]`,
    in the order found, with warnings left out (data-model §1);
  - every id in `RULES` matches `^[a-z]+\.[a-z]+(-[a-z0-9]+)*$`;
  - `problem_lines` of T006, applied to `config_error(problems)`, gives
    back each error's file, path and rule.
- [X] T005 Implement `src/tenetrag/packs/problems.py`, standard library
  and `tenetrag.protocols` only:
  - `PackProblem` as a frozen dataclass with `slots=True`;
  - `RULES`, a frozenset of the rule ids of data-model §1 that US1 raises:
    every row of the main table, `identity.evidence-without-corroborate`
    and `text.instruction`. US3 adds `coverage.unmet` (T031). The `case.*`
    ids live in `cases.py` (T034), since no pack load raises them;
  - `config_error(problems) -> ConfigError`.

  T004 passes. Depends on T004 and T006.
- [X] T006 [P] Create `tests/support/packs.py`:
  - `REPO_ROOT`, `PACK_FIXTURES` (`tests/fixtures/packs`) and
    `FINANCE_DRAFT` (`docs/product/packs/finance.yaml`), as absolute
    paths;
  - `write_pack(directory, name, text) -> Path`, which writes UTF-8 text
    with LF line endings;
  - `problem_lines(exc) -> list[tuple[str, str, str]]`, which parses the
    `(file, path, rule)` of each line of a pack `ConfigError` in the
    format of data-model §1.

  Result (2026-10-15): `make check` passes with 698 unit tests.
  - `tests/unit/packs/test_problems.py` (9 tests) failed with
    `ModuleNotFoundError` before T005.
  - `RULES` holds 39 ids, the same set as data-model §1 without
    `coverage.unmet`, compared by script.
  - `config_error` with no error raises `ValueError`, a caller bug.
  - `problem_lines` fails on a line that does not parse, or when the
    count on the first line differs from the number of lines, so that a
    changed format cannot pass on an empty list.
    `tests/unit/test_support_packs.py` (6 tests) pins this, `write_pack`
    and the paths.
  - Five deliberate faults in `config_error` were each caught: warnings
    kept, always plural, no guard, reversed order, path dropped.

**Checkpoint**: problems, the error text and the pack test helpers are
ready

---

## Phase 3: User Story 1 - Load and check a pack stack (Priority: P1) 🎯 MVP

**Goal**: `load_pack` reads a shipped pack or a user file and its
ancestors, merges them, checks the result, and gives one read-only stack
or one `ConfigError` listing every problem

**Independent Test**: follow
[quickstart.md §1](quickstart.md#1-load-and-check-a-stack-story-1-sc-001-sc-003-sc-005),
including its negative check. `uv run pytest tests/unit/packs -q -k
"broken_pack or every_rule"` passes: each rule id of data-model §1 has a
broken pack that fails with that id.

### Tests for User Story 1

- [X] T007 [P] [US1] Add the valid test packs under
  `tests/fixtures/packs/valid/`:
  - `alpha-ops.yaml`: the user pack of
    [contracts/packs.md](contracts/packs.md#example-a-user-pack-on-enterprise-docs),
    word for word;
  - `two-parents/left.yaml` and `two-parents/right.yaml`, each extending
    `core` and adding the same attribute `tax_code: {range: str}` to
    `Organization`, and `two-parents/child.yaml`, which extends
    `[left.yaml, right.yaml]`;
  - `shared-ancestor.yaml`, which extends
    `[enterprise-docs, ../../../../docs/product/packs/finance.yaml]`.
- [X] T008 [P] [US1] Add the broken test packs for the reference and file
  phases, one directory per rule id under `tests/fixtures/packs/broken/`.
  Each holds `pack.yaml`, the file `load_pack` is given, and
  `expected.yaml`, naming the `file` (relative to the directory) and the
  `path` that the problem must carry. Any other file the case needs sits
  beside them.

  | Directory | `pack.yaml` |
  |---|---|
  | `pack.bad-reference` | `extends: core.json` |
  | `pack.unknown` | `extends: corp` |
  | `pack.cycle` | extends `b.yaml`, which extends `pack.yaml` |
  | `pack.no-extends` | a user pack with no `extends` |
  | `pack.shadows-shipped` | `pack: enterprise-docs`, extending `core` |
  | `file.unreadable` | extends `missing.yaml`, which does not exist |
  | `file.not-utf8` | a description holding a Latin-1 byte |
  | `file.yaml` | a value tagged `!!python/object:builtins.object` |
  | `file.duplicate-key` | `Vendor` twice under `entities` |
  | `file.empty`, `file.not-mapping` | an empty file; a top-level list |
  | `file.unknown-field` | `vetos` on an entity |
  | `file.invalid-value` | `version: 0` |
  | `file.bad-name` | an entity type named `vendor` |
  | `file.reserved-name` | an entity attribute named `scope` |
- [X] T009 [P] [US1] Add the broken test packs for the stack phase, in the
  form of T008, each a user pack on `core` or `enterprise-docs`:
  - `stack.missing-description`: a new entity type with no description;
  - `stack.changed-range`: `Person.attributes.email` with `range: int`
    (the quickstart §1 negative check);
  - `stack.changed-time`: `MEMBER_OF` with another `time`;
  - `stack.changed-description`: a changed `Person` description;
  - `stack.changed-identity`: `Person` with `names: key`;
  - `stack.added-identity`: `corroborate` added to a `core` type that
    has none;
  - `stack.required-on-inherited`: `required: [email]` on `Person`;
  - `stack.removed`: `vetoes: []` on `Organization`;
  - `stack.changed`: `multivalued: true` on an inherited attribute;
  - `stack.parents-conflict`: two parents adding `tax_code` to
    `Organization`, one as `str` and one as `int`;
  - `stack.duplicate-question`: a question with a `core` question's id and
    another text.
- [X] T010 [P] [US1] Add the broken test packs for the check phase and
  the two load warnings, in the form of T008:
  - `ref.unknown`: `SUPPLIES.to: [Organisation]`;
  - `ref.is-a`: an event type with `is_a: Organization`;
  - `ref.where-not-enum`: a `where` on a `str` attribute;
  - `ref.kind-clash`: a fact type named `Policy` on `enterprise-docs`;
  - `identity.key-needs-scope`: a scoped type with key `[code]`, where
    `code` has `unique: scope`;
  - `identity.key-not-minimal`: keys `[scope, code]` and
    `[scope, code, title]`;
  - `identity.veto-multivalued`, `identity.veto-range` (a `money` veto),
    `identity.veto-is-name` (a `title` veto) and
    `identity.versioned-needs-start`;
  - `glossary.alias-clash`: one alias on two `Organization` entries;
  - `identity.evidence-without-corroborate` and `text.instruction`, whose
    `expected.yaml` adds `severity: warning`. The `text.instruction` pack
    sets `mode: discovery`, so it loads with the warning.
- [X] T011 [P] [US1] Write `tests/unit/packs/test_format.py`, calling
  `load_pack` on files written with `write_pack`:
  - the contract tests `test_yaml_tag_refused` (the tag names a class in
    `tests/support/packs.py` that records any instance built, and none
    is), `test_nfc` (NFD text loads equal to its NFC form) and
    `test_text_never_echoed` (a planted secret beside a YAML syntax
    error, in an unknown field's value and in an invalid value never
    appears in the error);
  - each name pattern of data-model §2, parametrized with good and bad
    names, failing with `file.bad-name` and the path;
  - the reserved words: an entity's `scope`, an event's `time` and a
    fact's `issuer` fail, and `Definition.attributes.scope` loads;
  - `vetos` fails with `file.unknown-field` at `entities.Vendor.vetos`;
  - every field of the format loads, including `deprecated`,
    `renamed_from`, `exact_mappings` and `agent_visible`;
  - strict types: `version: "1"` and `version: 0` fail with
    `file.invalid-value`;
  - `file.duplicate-key` names both lines.
- [X] T012 [P] [US1] Write `tests/unit/packs/test_stacking.py`:
  - the contract tests `test_enterprise_docs_merged`,
    `test_user_pack_additions`, `test_conflict_names_both_packs`,
    `test_parents_identical_merge`, `test_parents_conflict`,
    `test_cycle_named`, `test_shared_ancestor_once` and
    `test_stack_read_only`;
  - the `Person` example of data-model §4, field by field;
  - `origins` maps `entities.Person.identity[scope+employee_id]` to
    `enterprise-docs` and `entities.Person` to `core`;
  - the order table of data-model §3: an enum value added by a child is
    sorted into place, reordered `vetoes` give an equal stack, and a
    child's identity keys come before inherited ones;
  - defaults are filled in: `compare: text`, `unique: scope`,
    `extract: true`, `names: key`, a fact's `time: interval`;
  - `is_a` copies roles, attributes and `time`, but not `identity`,
    `required` or `version_key`;
  - `mode` is `strict` from `core`, and a user pack's `mode: discovery`
    wins;
  - restating an inherited description word for word merges, and an enum
    value that two packs add merges into one;
  - a path in `extends` resolves against the file that holds it, and a
    relative `load_pack` path against `base_dir`.
- [X] T013 [P] [US1] Write `tests/unit/packs/test_checks.py`:
  - `test_broken_pack`, parametrized over the directories of
    `tests/fixtures/packs/broken/`, which reads each `expected.yaml`
    through `problem_lines`. A warning rule's pack loads, and the
    warning is on `stack.warnings`;
  - `test_every_rule_has_a_broken_pack`: `problems.RULES` equals the set
    of directory names, both ways;
  - the contract tests `test_problems_reported_together`,
    `test_evidence_without_corroborate_warns` and
    `test_instruction_text_by_mode`;
  - each reference of research R5: a `version_key`, `document_link`,
    `corroborate`, `version_start`, `cardinality` or `during` entry that
    names what the type lacks fails with `ref.unknown` and its path;
  - a definition with a file problem is set aside but still counts as
    defined, so `vetos` on `Vendor` does not also report
    `SUPPLIES.from: [Vendor]` (research R4);
  - the glossary: two user packs' glossaries are united, and an entry
    whose type the stack lacks fails with `ref.unknown`;
  - each pattern family of research R5 (English, Vietnamese, URL, tool
    name) warns in `discovery` mode, while "customer(s)" and "you" alone
    do not;
  - each warning is logged once at WARNING by the `tenetrag.packs`
    logger.
- [X] T014 [P] [US1] Write `tests/unit/packs/test_shipped.py`, part 1,
  with the contract tests `test_shipped_listed`, `test_shipped_load_clean`
  and `test_no_draft_copies`.

### Implementation for User Story 1

- [X] T015 [P] [US1] Implement `src/tenetrag/packs/stack.py`, standard
  library only, following data-model §3:
  - frozen dataclasses with `slots=True`, mappings wrapped in
    `MappingProxyType`, sequences as tuples;
  - `Mode`, `NameRule`, `PackInfo(name, version, source)`, `Scope`,
    `Key`, `Attribute`, `EntityType`, `RelationType`, `EventType`,
    `FactType`, `Retrieval`, `GlossaryEntry` and `CompetencyQuestion`,
    plus the `ShippedPack` named tuple of contracts/packs.md;
  - `PackStack` with every field of data-model §3 except `stamp`,
    `index_hash` and `glossary_hash`. US2 adds those three and
    `PackInfo.file_hash` together with the hashes (T026).
- [X] T016 [P] [US1] Implement `src/tenetrag/packs/format.py`, the
  private pydantic models of one pack file (data-model §2, research R2):
  - `extra="forbid"`, `frozen=True` and strict types;
  - every string, key or value, normalized to NFC before validation;
  - the name patterns and reserved words;
  - every field optional at file level except `pack` and `version`;
  - each definition validated on its own, so one bad definition is set
    aside while the rest of the file still stacks (research R4);
  - pydantic errors mapped to `file.unknown-field`, `file.bad-name`,
    `file.reserved-name` or `file.invalid-value`, with dotted paths such
    as `entities.Vendor.vetos` and `[n]` for list items. Messages never
    use pydantic's `input`, since a mistaken file may hold anything.
- [X] T017 [US1] Implement `src/tenetrag/packs/stacking.py`, which applies
  the parsed files in linear order (data-model §4, research R3):
  - a definition new to the stack is taken whole, and a new entity, event
    or fact type needs a `description`;
  - a definition already in the stack is a delta: each field it states
    either adds, as in R3's "Allowed change" table, or equals the stack's
    value. Anything else gets the matching `stack.*` rule;
  - a delta from a pack that does not descend from the pack that defined
    the element is a parents conflict: `stack.parents-conflict`, naming
    both packs. Identical definitions merge silently;
  - `origins` records which pack added each element, by the element
    paths of data-model §3;
  - then defaults are filled in, `is_a` is resolved, set-like lists are
    sorted, questions are united (`stack.duplicate-question`),
    `retrieval` is replaced per key, and `mode` is resolved.

  Depends on T015 and T016.
- [X] T018 [US1] Implement `src/tenetrag/packs/checks.py` over the merged
  stack (research R5):
  - the `ref.*` checks;
  - the identity lint, with `identity.evidence-without-corroborate` as a
    warning;
  - the text lint over every model-visible text, with R5's patterns
    matched as whole words after NFC and case folding. It is a warning in
    `discovery` mode and an error in `strict` mode;
  - the glossary checks.

  Depends on T017.
- [X] T019 [US1] Implement `src/tenetrag/packs/loading.py` and export
  `load_pack`:
  - **References:** a shipped name reads
    `importlib.resources.files("tenetrag.packs") / "shipped" / f"{name}.yaml"`.
    A path ends in `.yaml` or `.yml`, and resolves against `base_dir`,
    else the working directory. An `extends` path resolves against the
    file that holds it.
  - **Files:** `file.unreadable`, `file.not-utf8`, then
    `_yaml.parse_yaml`, with `_yaml.yaml_problem` for `file.yaml`, the
    duplicates as `file.duplicate-key`, and `file.empty` and
    `file.not-mapping`. `parse_yaml` gives only the key and both lines,
    while `file.duplicate-key` needs the path of the mapping
    (`entities`, contracts/packs.md). So `DuplicateKeyLoader` also
    records that path, test first in `tests/unit/test_yaml.py`, and
    `config`'s message stays as it is (found in T002).
  - **Order:** depth-first over `extends`, post-order, each pack once. A
    pack met again on the current path is `pack.cycle`, listing the path.
    Also `pack.no-extends` and `pack.shadows-shipped`.
  - **Phases:** files, then stacking (T017), then checks (T018). A later
    phase runs even when an earlier one found problems (R4). Errors raise
    `config_error`. Warnings are logged once at WARNING by
    `logging.getLogger("tenetrag.packs")` and kept on `stack.warnings`.

  Export `load_pack`, `Mode`, `PackStack`, `PackProblem` and the parts of
  T015 from `src/tenetrag/packs/__init__.py`. Depends on T005, T016, T017
  and T018.
- [X] T020 [US1] Ship the two packs:
  1. Copy `docs/product/packs/core.yaml` and `enterprise-docs.yaml` to
     `src/tenetrag/packs/shipped/`, and remove the "Draft, no code loads
     it" comment lines. Give a `description` to any new entity, event or
     fact type that lacks one. A check on 2026-10-12 found none; list any
     change in the commit message (research R10).
  2. Implement `shipped_packs()` in `src/tenetrag/packs/__init__.py`:
     sorted by name, each version read from its file, `*.cases.yaml`
     left out.
  3. Delete the two drafts. In `docs/product/domain-packs.md` and
     `docs/product/v1-packs.md`, point their links at the shipped files
     (find them with
     `grep -rn "packs/core.yaml\|packs/enterprise-docs.yaml" docs README.md ARCHITECTURE.md`).
     The `finance` draft keeps `extends: core`.

  T014 passes. Depends on T019.
- [X] T021 [US1] Run `uv run pytest tests/unit/packs -q`, quickstart §1
  with its negative check, and `make check`. Try deliberate faults in
  `stacking.py` and `checks.py`, such as dropping a sort, accepting a
  changed range, or skipping the parents-conflict test. A fault that
  survives gets a test. Record the results here, as M0 did.

  Result (2026-10-16): `make check` passes with 948 unit tests.
  - Red, before T015: `uv run pytest tests/unit/packs tests/unit/test_yaml.py -q`
    stopped with 5 collection errors, an `ImportError` for `DuplicateKey`
    from `tenetrag._yaml` and for `PackProblem`, `CompetencyQuestion`,
    `PackInfo` and `Key` from `tenetrag.packs`. The rest of the suite
    passed (686 passed, 22 deselected). Green: 271 passed.
  - Four test packs were not valid YAML, found at green. In a flow
    mapping (`{...}`) PyYAML ends a plain scalar at `?`, so
    `text: Which ones?, needs: [...]` does not parse. The question texts
    in `test_nfc` and three `test_format.py` cases are now quoted; no
    assertion changed.
  - Quickstart §1 gives its expected values. Its negative check fails
    with one `stack.changed-range` line naming the file,
    `entities.Person.attributes.email.range` and `core`.
  - Deliberate faults, each run under `PYTHONHASHSEED` 0, 1 and 2: of 17,
    13 were caught at once (dropping the enum, `not_entities`,
    `corroborate`, `from`, event identity or `required` sort; accepting
    a changed range; skipping the parents-conflict test; no
    `identity.veto-range`; no `ref.kind-clash`; set-aside names not
    defined; `<=` in `identity.key-not-minimal`; no case folding in the
    text lint). Four survived and now each has a test that catches it:
    the `hub_penalty` and attribute-map sorts
    (`test_attributes_and_retrieval_hints_are_sorted`), the leading word
    boundary of the text lint ("The bayou must be dredged each year."),
    and case folding in glossary clashes
    (`test_glossary_alias_clash_ignores_case`).
  - The wheel holds `tenetrag/packs/shipped/core.yaml` and
    `enterprise-docs.yaml`. Installed alone in an isolated environment,
    `shipped_packs()` and `load_pack("enterprise-docs")` work from it.
  - No shipped type lacked a `description` (R10), so the shipped packs
    are the drafts without the draft comment line.
  - Two departures from the task text. `shipped_packs()` lives in
    `loading.py` and is exported from `__init__.py`. A file with no
    content to stack, or a `pack.*` problem, stops the load after the
    file phase; R4 now says so.
  - `exact_mappings` is unioned and sorted, and `cardinality` sorted:
    R3 and data-model §3 now say so.

**Checkpoint**: packs load, stack and fail loudly with every problem.
MVP reached.

---

## Phase 4: User Story 2 - Compile schemas and stamp the pack (Priority: P1)

**Goal**: a flat compiled schema within provider limits, a stamp and four
hashes, a `pack` field in the profile, and stage hashes that include the
pack's index hash

**Independent Test**: follow
[quickstart.md §2](quickstart.md#2-compile-stamp-and-hash-story-2-sc-002-sc-004-sc-006),
including its negative check. `uv run pytest tests/unit/packs
tests/unit/config -q -k "hash or compile or pack"` passes.

### Tests for User Story 2

- [X] T022 [P] [US2] Write `tests/unit/packs/test_hashing.py`:
  - the contract tests `test_hash_ignores_layout`,
    `test_hash_description_change`, `test_hash_set_order`,
    `test_hash_retrieval_only`, `test_hash_glossary_only` and
    `test_hash_golden`. Pin the golden values after the first green run;
  - each hash recomputed by hand from the recipe of data-model §5 for a
    tiny stack, as in M0's `test_hash_follows_the_spec_recipe`;
  - a default written out equals the default left out, except in the
    file hash;
  - Vietnamese text is hashed as is (`ensure_ascii=False`), so a recipe
    with `ensure_ascii=True` would fail (M0 T028);
  - `stack.stamp` is `Stamp(top name, version, content_hash)`, and two
    stacks with the same content under different top names have equal
    content hashes;
  - each `PackInfo` carries its file hash.
- [X] T023 [P] [US2] Write `tests/unit/packs/test_compile.py`:
  - the contract tests `test_compiled_fits_providers` (with
    `check_schema` from `tenetrag.llm.structured` and
    `capability_profile("databricks", "databricks-claude-sonnet-5")`),
    `test_compile_limit`, `test_compile_subset`,
    `test_compile_rejects_bad_subset`, `test_extract_false_left_out`,
    `test_compile_empty_parts_left_out`, `test_compile_golden` and
    `test_many_types_fit`;
  - `test_compile_golden` compares `to_json() + "\n"` with the bytes of
    `tests/fixtures/packs/compiled/core.json`, which T029 writes;
  - `property_count` equals the count `check_schema` makes, `types` is
    sorted, every enum is sorted, and two calls give equal bytes.
- [X] T024 [P] [US2] Extend `tests/unit/packs/test_shipped.py` with part 2:
  `test_shipped_pins` (the pins dict of data-model §5, filled after the
  first green run; a mismatch says to bump `version` and add a pin) and
  `test_finance_draft_stacks` (FR-019).
- [X] T025 [P] [US2] Extend the config tests with the contract tests of
  [contracts/config.md](contracts/config.md#behaviour-pinned-by-tests):
  - `tests/unit/config/test_profile.py`: `test_pack_default`,
    `test_pack_name_or_path`, and a test that the pack name pattern in
    `config/profile.py` equals the one in `packs/format.py`. `config`
    cannot import `packs`, so the pattern is written twice, as with
    M0's `StrategyName`;
  - `tests/unit/config/test_phases.py`: `test_pack_is_operational`;
  - `tests/unit/config/test_loading.py`:
    `test_pack_path_relative_to_profile`;
  - `tests/unit/config/test_hashing.py`: `test_hash_needs_pack_hash`,
    `test_hash_pack_extract_and_resolve_only`,
    `test_hash_pack_path_ignored` and
    `test_hash_retrieval_and_glossary_ignored`.

  Every existing `stage_hashes(profile)` call gains
  `pack_hash=PACK_HASH`, a well-formed constant. The spec-recipe test
  adds `"pack"` to the `extract` and `resolve` fields, and
  `test_hash_golden` passes `load_pack("core").index_hash`. Its new
  `extract` and `resolve` values are pinned after the first green run.
  This is an interface change made visible in the diff: no assertion is
  dropped.

### Implementation for User Story 2

- [X] T026 [P] [US2] Implement `src/tenetrag/packs/hashing.py`, following
  data-model §5 and research R7:
  - the content, index, glossary and file hashes;
  - the canonical JSON recipe of `config/hashing.py`'s `_digest`, with
    the hash kind in place of the stage. `packs` cannot import `config`
    (R1), so the few lines are repeated, with a comment naming the other
    copy;
  - `PackStack` gains `stamp`, `index_hash` and `glossary_hash`, and
    `PackInfo` gains `file_hash`. `loading.py` fills them in.

  Export `Stamp`. Depends on T019.
- [X] T027 [P] [US2] Implement `src/tenetrag/packs/compile.py`, following
  research R6 and data-model §6:
  - the fixed 52-property shape, with sorted enums, every property
    required, `additionalProperties: false`, and `""` for an absent
    value;
  - a part whose name set is empty is left out;
  - `types`: an unknown name, an `extract: false` type or an empty
    selection raises `ConfigError`;
  - past `max_properties`, a `ConfigError` gives the count and the parts
    by size;
  - `CompiledSchema` with `schema`, `types`, `property_count` and
    `to_json()`.

  `schema` returns a fresh deep copy in plain dicts and lists on each
  read, since `check_schema` refuses a `MappingProxyType` (data-model §6).
  Export `compile_schema` and `CompiledSchema`. Depends on T019.
- [X] T028 [US2] Change `tenetrag.config` (contracts/config.md §1 and §2,
  research R8):
  - `src/tenetrag/config/profile.py`:
    `pack: Annotated[PackReference, Operational()] = "core"`. A value
    ending in `.yaml` or `.yml` is a path, and anything else must match
    the pack name pattern. The error names both forms;
  - `src/tenetrag/config/loading.py`: `load_profile` makes a relative
    pack path absolute against the profile file's directory;
  - `src/tenetrag/config/hashing.py`:
    `stage_hashes(profile, *, pack_hash: str)`. A hash that does not
    match `^sha256:[0-9a-f]{64}$` raises `ValueError` ("a caller bug").
    The value enters the `extract` and `resolve` fields as `pack`, and
    `_FORMAT` stays 1.

  The T025 tests that load a pack need T026.
- [X] T029 [US2] Pin and run:
  1. Write `tests/fixtures/packs/compiled/core.json` from
     `compile_schema(load_pack("core")).to_json()` plus one final
     newline. Review it by hand against data-model §6 and the R6 table:
     52 properties, `Statement` absent.
  2. Pin the shipped file hashes (`test_shipped_pins`), the pack golden
     hashes (`test_hash_golden`) and the new config golden values.
  3. Run `uv run pytest tests/unit/packs tests/unit/config -q`,
     quickstart §2 with its negative check (record the SC-006 time), and
     `make check`.
  4. Try deliberate faults in `hashing.py` and `compile.py`. A fault that
     survives gets a test.

  Record the results here.

  Result (2026-10-16): `make check` passes with 1041 unit tests.
  - Red, the tests of 54e55e7 on the code before T026:
    `uv run pytest tests/unit/packs tests/unit/config -q` stopped with 3
    collection errors, an `ImportError` for `CompiledSchema`,
    `compile_schema` and `Stamp` from `tenetrag.packs`. With
    `--continue-on-collection-errors`: 73 failed, 419 passed, 3 errors.
    Green: 552 passed, also under `PYTHONHASHSEED` 0, 1 and 2.
  - `core.json` reviewed by hand: 52 properties, `Statement` absent,
    every enum sorted, no `null`. Its entity attribute enum holds
    `born_on`, which data-model §6 lacked; the excerpt now has it.
  - Pinned: the file hashes of `core` 1 and `enterprise-docs` 1, their
    content, index and glossary hashes (both glossaries are empty, so
    both glossary hashes are the hash of `[]`), and the config golden
    values. Only `extract` and `resolve` moved, in both golden profiles;
    the other four stages kept their M0 values.
  - Quickstart §2: the stack `[core, enterprise-docs, finance, largest]`
    loads and compiles in 0.065 s (SC-006: under 1 s; first of five
    runs, median 0.063 s), with 52 properties, 39 types, no warning, and
    `check_schema` raising nothing for `databricks-claude-sonnet-5`. The
    negative check, `max_properties=40`, raises `ConfigError` with 52,
    40 and the 12 parts by size, from `entity (10)` to `fact role (2)`.
  - Deliberate faults, one at a time: of 37, 33 were caught at once
    (index or content field sets, sorted keys, ASCII escapes, `_FORMAT`,
    the glossary hash kind, the stamp version, `exclude_unset`, aliases,
    each part of the file hash; in `compile.py` the `required` sort,
    `additionalProperties`, enum sort, relation `value`, empty attribute
    parts kept, `>=` at the limit, parts in ascending order, `extract:
    false` kept or allowed, unknown names or an empty selection allowed,
    events without `id`, unsorted `types`, the root left out of the
    count). Four survived:
    - an empty roles part kept: event and fact roles are optional, and
      no test compiled a type without them.
      `test_compile_roleless_types_have_no_roles_part` now catches it;
    - no NFC for values, or for keys, in `hashing._canonical`: the loader
      already gives NFC strings, so each layer covers the other.
      `test_hash_ignores_layout` fails when both are dropped. The step
      stays so the recipe matches `config/hashing.py`;
    - ASCII escapes in `to_json`: every string in a compiled schema is a
      name matching an ASCII pattern, so the output cannot change.
  - Design notes. `load_pack` computes the stack hashes once the checks
    pass (`hashing.stamped`); `freeze` leaves empty placeholders that
    never leave `load_pack`. `PackInfo` gained `file_hash`, so two
    stacking and shipped tests compare `(name, version, source)` instead
    of whole `PackInfo` values. `load_profile` uses `abspath` and
    `normpath`, not `resolve`, so a pack path keeps its links and only
    `..` is folded.

**Checkpoint**: stacks compile within the limits, and a pack change moves
the right stage hashes. Both P1 stories are done.

---

## Phase 5: User Story 3 - Check that a pack can answer its questions (Priority: P2)

**Goal**: a coverage report per competency question, with no model call,
and a load warning for each question that fails it

**Independent Test**: follow
[quickstart.md §3](quickstart.md#3-coverage-story-3-sc-001-sc-005),
including its negative check. `uv run pytest tests/unit/packs/test_coverage.py -q`
passes.

### Tests for User Story 3

- [X] T030 [P] [US3] Write the coverage tests:
  - `tests/unit/packs/test_coverage.py`: the contract tests
    `test_coverage_shipped`, `test_coverage_missing_relation`,
    `test_coverage_not_extracted` and `test_load_warns_unmet_question`.
    Also assert the report's shape (data-model §6): questions in stack
    order, each with its pack, `missing` and `not_extracted` sorted, and
    `passed`;
  - `tests/unit/packs/test_shipped.py`: `test_shipped_have_questions`;
  - `tests/fixtures/packs/broken/coverage.unmet/`, a pack whose question
    needs `AUDITED`, with `severity: warning`. Until T031 registers the
    rule, `test_every_rule_has_a_broken_pack` fails on it.

### Implementation for User Story 3

- [X] T031 [US3] Implement `src/tenetrag/packs/coverage.py` with
  `check_coverage`, `CoverageReport` and `QuestionCoverage` (data-model
  §6, research R9). Add `coverage.unmet` to `RULES`. `load_pack` adds one
  warning per unmet question, at `competency_questions[<id>]`. Export
  `check_coverage` and `CoverageReport`. Depends on T030.
- [X] T032 [US3] Run `uv run pytest tests/unit/packs -q`, quickstart §3
  with its negative check, and `make check`. Record the results here.

  Result (2026-10-16): `make check` passes with 1058 unit tests.
  - Red, the tests of dc46c2b on the code before T031:
    `uv run pytest tests/unit/packs -q` stopped with 2 collection errors,
    an `ImportError` for `check_coverage` from `tenetrag.packs`. The
    other files: 2 failed (`test_broken_pack[coverage.unmet]` with no
    warning, `test_every_rule_has_a_broken_pack`), 303 passed. Green:
    331 passed, also under `PYTHONHASHSEED` 0, 1 and 2.
  - A wrong test, fixed in its own commit (fbe5000): four test packs left
    a question text ending in `?` unquoted inside a YAML flow mapping,
    which fails as `file.yaml`. The collection error hid it in the red
    run. Only the quoting changed.
  - Quickstart §3: `enterprise-docs` gives `(True, 14)`; the alpha-ops
    copy passes with 15 questions, loaded and checked in 0.098 s with
    `enterprise-docs`. The negative check, `alpha-ops-2` needing
    `AUDITED`, loads with one `coverage.unmet` warning at
    `competency_questions[alpha-ops-2]`, and the report lists
    `("AUDITED",)` missing for it.
  - Deliberate faults, one at a time: of 27, 23 were caught at once (in
    `coverage.py` duplicate names, `is True` for `is False`, `passed`
    ignoring `not_extracted`, `any` for `all`, the top pack for the
    question's pack, events and facts not counted, the id for the text,
    either type not frozen, a list for the tuple, questions sorted by id
    or reversed; in stacking no question origin or the last file's; in
    checks no coverage step, warning on passed questions, the top file's
    label, `error` severity, the text in the message, either cause left
    out, a path by position; the rule left out of `RULES`). Four
    survived:
    - `missing` unsorted: with three names, the set sometimes iterates
      them in order. `test_coverage_names_sorted_whatever_the_set_order`
      sorts 10 and 7 names; it caught this fault, and a new one leaving
      `not_extracted` unsorted, on three runs out of three;
    - advice that omits `extract: true`, or gives it for a missing name:
      no test read the advice. `test_warning_advice_fits_the_cause` now
      catches both;
    - `() or tuple(...)` for no `not_extracted`: a no-op, since `()` is
      falsy. Rewritten as `() and tuple(...)`, `test_coverage_not_extracted`
      catches it.
  - Design notes. Stacking records each question's origin at
    `competency_questions[<id>]` (`stacking.question_path`), as the first
    file that adds the id; data-model §3 lists the path. `origins` is not
    hashed, so every hash pin held. The warnings come from a coverage
    step that `check_stack` runs last, through `check_coverage`, and sit
    in the file that holds the question, which for a shipped question is
    the shipped pack: a child that sets `extract: false` on
    `HOLDS_POSITION` gets a warning at `core`'s `core-1` that names
    `HOLDS_POSITION`. `QuestionCoverage` is exported with
    `CoverageReport`, as a part the engine can type.

**Checkpoint**: a pack author learns what a question lacks before any
index run

---

## Phase 6: User Story 4 - Identity cases ship with each pack (Priority: P2)

**Goal**: 77 identity cases in the packs' vocabulary, the 60 design cases
among them, loaded and checked for consistency and coverage

**Independent Test**: follow
[quickstart.md §4](quickstart.md#4-identity-cases-story-4-sc-007),
including its negative check. `uv run pytest tests/unit/packs/test_cases.py -q`
passes.

### Tests for User Story 4

- [X] T033 [P] [US4] Write `tests/unit/packs/test_cases.py`:
  - the 13 contract tests of
    [contracts/identity-cases.md](contracts/identity-cases.md#behaviour-pinned-by-tests).
    `test_design_cases_match_snapshot` reads
    `specs/002-packs-and-corpus/research/identity-design-cases.json`;
  - negative tests work on copies in `tmp_path`. A copied `finance` case
    file gets its `pack` path rewritten to `FINANCE_DRAFT`;
  - for each `case.*` rule of data-model §8, one small inline case file
    that gives that rule.

### Implementation for User Story 4

- [X] T034 [US4] Implement `src/tenetrag/packs/cases.py`, following
  data-model §8:
  - pydantic models `CaseFile`, `CaseEntity`, `Case`, `Mention` and
    `Outcome`, with the rules of a pack file, read through the file
    phase of `loading.py`, so the `file.*` rule ids are shared;
  - `load_cases(path)`, which loads the stack its `pack` names, relative
    to the case file;
  - `shipped_cases()` from `importlib.resources`, and the frozen
    `CaseSet`;
  - `check_cases(*case_sets)`, covering:
    - every entity id, type, attribute and relation exists;
    - the element grammar is resolved against the mention type;
    - the outcome fits `expect`, and `blocked_by` matches a veto;
    - ids are unique across the sets;
    - FR-031 coverage per set whose top pack is shipped, from the
      elements that `stack.origins` gives to the top pack;
  - `CASE_RULES`, the `case.*` ids.

  Depends on T033.
- [X] T035 [US4] Convert the 60 design cases:
  - A throwaway script in the session scratchpad, never committed, reads
    `research/identity-design-cases.json` and applies the conversion
    rules of research R11.
  - It writes `src/tenetrag/packs/shipped/core.cases.yaml` (22 cases),
    `src/tenetrag/packs/shipped/enterprise-docs.cases.yaml` (31, with
    PER-6 moved there by ADR 0023) and
    `tests/fixtures/identity/finance.cases.yaml` (7, with
    `pack: ../../../docs/product/packs/finance.yaml`), per R11's stack
    table.
  - From then on, the files are edited by hand. `load_cases` reads all
    three, and `check_cases` reports only the `case.coverage-*` gaps
    that T036 fills.

  Depends on T034.
- [X] T036 [US4] Write the 17 added cases of research R11's table by
  hand (PLC-2, PRD-2 to PRD-4, WRK-7, SYS-2, PROC-1 to PROC-7, and
  PER-10 to PER-13 of ADR 0023), with fictional names and `.example`
  emails. `check_cases(*shipped_cases(),
  finance_cases)` then returns no problem. Depends on T035.
- [X] T037 [US4] Run `uv run pytest tests/unit/packs/test_cases.py -q`,
  quickstart §4 with its negative check, and `make check`. Record the
  case counts per file here.

  Result (2026-10-16): `make check` passes with 1146 unit tests.
  - Red, the tests of 53c8e80 on the code before T034:
    `uv run pytest tests/unit/packs -q` stopped with 1 collection error,
    an `ImportError` for `CaseSet` from `tenetrag.packs`. With
    `--continue-on-collection-errors`: 331 passed, 1 error. That commit
    also carried one ruff `I001` in `test_cases.py`, since the import of
    `tenetrag.packs.cases` sorts as third-party until the module exists;
    it cleared with T034. Green: 419 passed, also under `PYTHONHASHSEED`
    0, 1 and 2.
  - Case counts: `core.cases.yaml` 27 (22 design, 5 added, 23
    entities), `enterprise-docs.cases.yaml` 43 (31 design, 12 added, 25
    entities), `tests/fixtures/identity/finance.cases.yaml` 7 (7 design,
    3 entities): 77 cases, 60 of them the design cases. With the design
    cases only, `check_cases` gives 13 problems, all `case.coverage-*`:
    `Place`, `Product` and the `born_on` veto in `core`; `Procedure` (the
    type, its 3 keys and 3 vetoes), `Product`, `System` and `Work` in
    `enterprise-docs`. The added cases close each of them; PER-11 to
    PER-13 are the ADR 0023 cases, not gaps.
  - Quickstart §4: `test_case_counts`, `check_cases` on all three files
    with no problem, and `test_design_cases_match_snapshot` pass. The
    negative check, `test_missing_veto_case`, gives one
    `case.coverage-element` at `entities.Person.vetoes[employee_id]`
    naming `veto:employee_id`.
  - FR-041: the case files name one real organization, `nhnn`, the
    State Bank of Vietnam, as the scope of the public code
    39/2016/TT-NHNN that the design case WRK-1 needs. FR-041 now admits
    the authority that issues a public legal code, beside the code.
    Every email is on `alpha.example`.
  - Deliberate faults, one at a time: of 56, 42 were caught at once (in
    `cases.py` coverage on user tops, coverage ignoring the owner, a veto
    counted as a key, changed parts, identity-free types, `expect`
    ignored, element coverage across types; `blocked_by` both ways;
    duplicate ids skipped or per file; `right`, `existing` membership,
    outcome fields, the `same_as`, `confirm` and `expect` fits; enum
    values, relation ends and attributes, `existing` ids, key order,
    default `unique`, `names`, `corroborate`, vetoes, the scope target
    type, a scopeless type's scope, unknown types and attributes; a
    mutable `entities`, the pack path, the case file header, unquoted
    document dates, empty `depends_on` or `cases`, the `scope_source`
    default, lower-case case ids, the shipped suffix and order; in
    `loading.py` a `.cases.yaml` file taken for a pack). Fourteen
    survived, and each now has a test:
    - the duplicate-id message for one file, an unknown issuer, `scope`
      for a type without one, the grammar advice for `veto:` or
      `veto:Born_On`, and an unknown scope entity:
      `test_duplicate_id_in_one_file`, `test_issuer_is_an_entity`,
      `test_scope_element_needs_a_scope`,
      `test_bad_element_names_the_grammar`, `test_scope_is_an_entity`;
    - no NFC, and unquoted attribute dates:
      `test_case_text_read_as_nfc`, `test_attribute_dates_read_either_way`;
    - an empty value, the basic date form `20250610` (which
      `date.fromisoformat` accepts), an empty `existing`, a language
      other than `vi` or `en`, lax types (a `!!binary` value reads as
      bytes, which lax mode turns into text), and an upper-case entity
      id: six new rows of `test_case_shape`;
    - mutable case models: `test_cases_frozen`.
  - Design notes. The file phase of `loading.py` is now `read_mapping`,
    shared by packs and case files with a `FileKind` for the two
    file-specific messages; `format.py` exposes `name_checker`,
    `normalized` and `validation_problems` for the same reason.
    `config_error` takes a `subject`, so a case file error opens with
    "The case file has". `shipped_pack_names` skips `.cases.yaml`, and
    the wheel carries both case files beside the packs. The case files
    were written by a throwaway script, not committed, that checked its
    YAML round-trip; digit-only values such as registration ids are
    quoted, so a YAML 1.2 reader keeps them as text.

**Checkpoint**: every shipped pack carries identity cases, checked
against its stack

---

## Phase 7: User Story 5 - A synthetic bilingual corpus with planted answers (Priority: P2)

**Goal**: about 40 synthetic documents in Vietnamese, English and both,
with expected items, graph results and golden questions, all rebuilt
byte for byte from a fact table

**Independent Test**: follow
[quickstart.md §5](quickstart.md#5-corpus-story-5-sc-008-sc-009-sc-010),
including its negative check. `uv run pytest tests/unit/packs/test_corpus.py -q`
passes.

### Tests for User Story 5

- [X] T038 [P] [US5] Write `tests/unit/packs/test_corpus.py` with the 15
  contract tests of
  [contracts/corpus.md](contracts/corpus.md#behaviour-pinned-by-tests):
  - `test_running_example` and `test_running_example_statuses` hold
    their expected values by hand, from the engine brief and data-model
    §9, never from the generator;
  - `test_missing_quote_fails` and `test_unfit_item_fails` copy the fact
    table to `tmp_path` and change one entry;
  - `test_fictional_only` lists the fictional companies and the public
    authorities it accepts.

### Implementation for User Story 5

- [X] T039 [P] [US5] Write the running example into the fact table under
  `tests/fixtures/corpus/facts/`:
  - `world.yaml`: Công ty CP Alpha and Công ty CP Beta, their Phòng Tài
    chính, Ủy ban Rủi ro, Nguyễn Văn An, the policies, the metric
    "phụ cấp lưu trú" and the expense system;
  - `documents/D1.yaml` to `D5.yaml`, with the sentences, owners, issuers
    and dates of the
    [engine brief's running example](../../docs/product/engine-brief.md#running-example)
    word for word. D2 is as in contracts/corpus.md;
  - `graph.yaml`, with the deletion of D2;
  - `golden.yaml`, with Q-a, Q-b and Q-c and their expected answers.
- [X] T040 [US5] Write the first part of the generator in
  `tests/support/corpus/`:
  - `__init__.py`: `generate(facts_dir, out_dir)` and `CorpusError`;
  - `facts.py`: pydantic models of the fact table (data-model §9), with
    `extra="forbid"` and `frozen=True`, read with `yaml.safe_load`;
  - `render.py`: blocks to Markdown (`#` per heading level, paragraphs,
    `- ` lists, pipe tables), NFC, LF, one final newline;
  - `checks.py`:
    - every item and attribute quote occurs in the rendered text;
    - every ref resolves within its document, and every world id exists;
    - every item fits `load_pack("enterprise-docs")`: the type exists
      and is extracted, its roles and attributes exist, required roles
      are present, and endpoint types are allowed.

  `generate` writes `docs/<id>.md` and `documents.jsonl` (in id order by
  number, sorted keys). It collects every problem first and writes
  nothing when there is one (FR-039). Depends on T039.
- [X] T041 [US5] Write `tests/support/corpus/derive.py`, which writes
  `graph.json` as contracts/corpus.md shows:
  - `entities` by world id;
  - version groups, with ids built from the type and its `version_key`
    parts;
  - statuses by `valid_from`, then item id, per engine brief §3.2:
    newest `current`, older `superseded` with `closed_at`, and a shared
    newest start `conflicting`;
  - `supersedes`, from the `SUPERSEDES` items;
  - `text_in`, from `graph.yaml`, after checking each end exists;
  - `deletions`: for each document `graph.yaml` names, the groups whose
    statuses change when it is removed.

  Depends on T040.
- [X] T042 [US5] Write `tests/support/corpus/golden.py`, which writes
  `golden.jsonl`:
  - one template per question type and language, per contracts/corpus.md;
  - Vietnamese dates and numbers as `15/03/2025` and `2.000.000`, English
    as `15 March 2025` and `2,000,000`, with figures copied from quotes;
  - each template names the competency questions it answers, for the
    `cq` tag;
  - generated ids are stable: `<qtype>:<item id>`. Generated questions
    come first, in fact-table order, then the hand-written ones from
    `golden.yaml`, after checking that every source they cite is a
    generated document.

  Depends on T041.
- [X] T043 [US5] Write `tests/support/corpus/__main__.py` and the
  `corpus` target:
  - with no flag, generate into a temporary directory, then replace the
    contents of `tests/fixtures/corpus/generated/`, so stale files go;
  - with `--check`, compare and list each missing, extra or different
    file (exit 1);
  - a `CorpusError` prints every problem as `{file}: {path}: {message}`
    (exit 2);
  - `Makefile`: `corpus: uv run python -m tests.support.corpus`, added to
    `.PHONY`, not to `check`, since `test_regenerates_same_bytes` covers
    it.

  Generate the first output from D1 to D5. Depends on T042.
- [X] T044 [US5] Batch A, policies and procedures: D6 to D15, 4 `vi`,
  4 `en`, 2 `mixed`. Plant from FR-034:
  - policy and procedure versions with issued and effective dates,
    supersession statements, and later mentions with no version;
  - a work or policy whose code or title matches another indexed
    document, as a `TEXT_IN` link in `graph.yaml`;
  - two `OWNER_OF` statements on one object with different starts, and
    two with the same start.

  Add a hand-written `conflicting_versions` question to `golden.yaml`.
  Run `make corpus`. Depends on T043.
- [X] T045 [US5] Batch B, meetings: D16 to D23, 3 `vi`, 4 `en`,
  1 `mixed`, with chairs, attendees, decisions, and action items with
  due dates and statuses. Add a hand-written `entity_all` question. Run
  `make corpus`. Depends on T044.
- [X] T046 [US5] Batch C, metrics and figures: D24 to D32, 3 `vi`,
  4 `en`, 2 `mixed`. Plant two sources that define one metric
  differently, a definition that changes over time, and figures with
  periods, units and basis, actual beside target. Add hand-written
  `single_fact` and `historical_figure` questions. Run `make corpus`.
  Depends on T045.
- [X] T047 [US5] Batch D, names and people: D33 to D40, 3 `vi`, 3 `en`,
  2 `mixed`. Plant:
  - names written several ways: acronyms, both languages, short forms;
  - a person of the same name in two companies;
  - projects and systems with their owners.

  Add a hand-written `cross_lingual` question. Every competency question
  of `core` and `enterprise-docs` must now appear in some `cq`; add
  hand-written questions for any that do not. Run `make corpus`. Totals:
  40 documents, 17 `vi`, 16 `en`, 7 `mixed`. Depends on T046.
- [X] T048 [US5] Run `time make corpus` (record the SC-010 time), check
  `git status --short tests/fixtures/corpus`, run
  `uv run python -m tests.support.corpus --check` (exit 0) and
  `uv run pytest tests/unit/packs/test_corpus.py -q`. Run quickstart §5's
  negative check (exit 2, naming D2) and `make check`. Try deliberate
  faults in `derive.py`, such as ordering ties by item id only or
  dropping `closed_at`. A fault that survives gets a test. Record the
  results here.

  Result (2026-10-16): `make check` passes with 1168 unit tests.
  - Red, the tests of 51ee721 at their commit: 1 collection error, a
    `ModuleNotFoundError` for `tests.support.corpus`. The test of ad7375d
    (`test_golden_names_tell_apart`) failed on questions such as "Các tài
    liệu cho biết gì về Nguyễn Văn An?", which two companies' people
    answer; the label rule below fixed it. Green:
    `uv run pytest tests/unit/packs/test_corpus.py -q` gives 22 passed.
  - SC-010: `time make corpus` takes 0.655 s. `git status --short
    tests/fixtures/corpus` shows no change after it, and `--check` exits
    0. Quickstart §5's negative check (2.500.000 changed to 2.600.000 in
    D2) exits 2 with `documents/D2.yaml: items[D2.6].quote: not in the
    rendered text of D2` and the same for its `threshold` quote; after the
    revert, `--check` exits 0.
  - Corpus: 41 documents, 18 `vi`, 16 `en`, 7 `mixed` (25 docx, 10 pdf,
    5 xlsx, 1 pptx); 335 items (201 entities, 80 relations, 35 facts, 19
    events); 36 version groups with 35 `current`, 8 `superseded` and 2
    `conflicting` members. The golden set has 104 questions, 96
    generated and 8 hand-written, 54 `vi` and 50 `en`: entity_all 29,
    cross_lingual 17, as_of 16, single_fact 13, meeting_decision 11,
    historical_figure 9, definition 6, conflicting_versions 3. All 14
    competency questions appear in some `cq`.
  - Deliberate faults, one at a time, each regenerating the corpus
    before the tests ran, so only a behaviour test can catch one
    (`test_regenerates_same_bytes` then checks determinism only). Of 16,
    9 were caught at first: ties by item id only (the generator fails),
    dropping `closed_at`, no `effective_from` fallback, no `conflicting`,
    `entity_all` needing four documents, no label qualification, no
    cross-issuer definition conflict, `cq` ignoring linked items, and
    sources from the first answer item only. Seven survived, because the
    data never exercised them or no test stated the rule:
    - a stated end ignored, and the issuer taken from the document: D35.9
      now states "until 31 December 2025" (`valid_to`), and Phòng Tài
      chính issues D14 while Alpha scopes its guidance;
      `test_closed_at_next_start`, `test_fact_issuer_is_source_scope`;
    - an emptied group left out of a deletion, and deletions that skip
      groups with two or more members left: D41 makes a third CRM owner
      and `graph.yaml` deletes it; `test_deletions_replay`;
    - `as_of` on the start day, and `as_of` for current members only:
      `test_golden_as_of_dates`;
    - `single_fact` for requirements that are not alone in their group:
      `test_golden_single_and_historical`.

    Rerun on the final data, all 16 are caught.
  - Equal content. D41 first handed the CRM back to the IT Department,
    which would make it equal to D35.9. The engine treats equal content
    as one version with several sources (engine brief §3.2); the
    generator gives each member its own status. `test_no_equal_content_in_a_group`
    failed on that `OWNER_OF:object=alpha.crm` group, and D41 now names
    a new unit, Trung tâm Chăm sóc khách hàng.
  - Departures from the task text, now in contracts/corpus.md:
    - T038's 15 tests are 22: `test_golden_names_tell_apart` and the six
      fault tests above;
    - T047's totals grew by D41: 41 documents, 18 `vi`;
    - T041: a member starts at `valid_from`, else the document's
      `effective_from`, `issued_on` or `held_on`, and ties order by
      position, not item id as text. A member that states `valid_to`
      keeps `closed_at` empty. A fact's `issuer` is its source's scope,
      else the document's issuer (engine brief §3.2), and a deletion
      maps a group it empties to `[]`;
    - T042: `cq` is derived, not named per template: every competency
      question whose `needs` are among the types of the answer items and
      the items they link to. Questions format dates only; figures
      come from quotes. Ids are `<qtype>:<item>`, or a world id for
      `entity_all` and for a term's definition conflict. A question
      qualifies a label another entity shares, with the version or the
      company.

**Checkpoint**: the engine has a corpus with known answers, and every
story works

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: docs that change with the code (FR-043), and the final
validation

- [X] T049 [P] Update `ARCHITECTURE.md`:
  - the `packs` row is built: its modules, what it imports, and the
    shipped packs and cases as package data;
  - a row for `_yaml`, the private bottom-layer helper of `config` and
    `packs`;
  - the layers contract now reads `config | packs`.
- [X] T050 [P] Update `docs/product/domain-packs.md` and
  `docs/product/v1-packs.md` (research R13):
  - new entity, event and fact types need a description, and examples
    are optional;
  - the name patterns and reserved words of data-model §2;
  - `load_pack`, `compile_schema` and `check_coverage` as the way to check
    a pack;
  - links to the shipped case files;
  - in v1-packs.md, `core` and `enterprise-docs` ship as version 1, and
    `finance` stays a draft until M4.
- [X] T051 [P] Update `docs/reference/test-corpora.md` and
  `docs/product/engine-brief.md` §10:
  - test-corpora.md: tier 1 lives in `tests/fixtures/corpus/`, built
    from the fact table by `make corpus`, with one golden JSONL file
    filtered by `qtype`, rendered as Markdown until feature 004
    (research R13);
  - engine brief §10: where the identity cases (77: 60 design, 17 added)
    and the running example live.
- [X] T052 [P] Update `AGENTS.md`: the status line (002 implemented, 003
  next) and a `make corpus` line in Commands. Keep it under 150 lines.

  Result (2026-10-21) for T049–T052:
  - `ARCHITECTURE.md`: the `packs` row is built, with its public
    functions, the shipped packs and cases as package data and the
    `finance` draft left in `docs/product/packs/`; a new `_yaml` row;
    `config` may import `_yaml`; the layers contract is spelled out.
  - domain-packs.md: the status names what is built; `description` is
    required on a new type and `examples` optional; new "Names" and
    "Checking a pack" sections. The example in "Checking a pack" was run
    on the `finance` draft: 52 properties, 15 of 15 questions, no case
    problem. The links to the shipped case files are in "Identity cases".
  - v1-packs.md: `core` and `enterprise-docs` ship as version 1, and
    `finance` stays a draft until M4. **Departure:** the old line "every
    stack compiled to 39 keys" came from the throwaway script of
    2026-10-04. `compile_schema` gives 52 properties for every stack, so
    the line now gives 52, measured on 2026-10-21. The type and question
    counts were re-measured and still hold. "Test material" gives the
    case counts.
  - test-corpora.md: tier 1 is built, with its input, output, checks and
    figures (41 documents, 104 questions, 8 of them hand-written).
  - engine brief §10: the running example is D1–D5 of the corpus, and
    the 77 cases (39 apart, 38 merge) are in the three case files.
  - `AGENTS.md`: the status line, and a corpus line under Commands.
    **Departure:** the status line also moves "settled through ADR 0019"
    to ADR 0023, since ADRs 0020–0023 exist. 102 lines.
- [X] T053 Run [quickstart.md](quickstart.md) end to end, §1 to §7,
  including the wheel check of §6 in a scratch virtual environment and
  §7's negative check. Record SC-006, SC-010, SC-011 and the unit suite
  duration under "Results" in `quickstart.md`, in the form of M0's.

  Result (2026-10-21): every section passes as written, and every
  negative check fails in the way the guide states. The figures are under
  [Results](quickstart.md#results-2026-10-21-t053):
  - SC-006: 0.063–0.070 s;
  - SC-010: 0.64 s per run, the same bytes on 3.11.14 and 3.14.8;
  - SC-011: passed in a venv with no extras;
  - the unit suite: 1168 passed in 24.7 s.

  **Departures:**
  - Scratch files went to the session scratch directory, not `/tmp`.
  - CI has been off since 2026-10-15, so a second local environment on
    Python 3.14.8, synced from the lock, stood in for the CI matrix.
  - §6 resolves the wheel's dependencies from PyPI, which picked
    pydantic 2.14.1 and pydantic-core 2.50.1 over the locked 2.13.5 and
    2.46.5. Both were published on 2026-10-11 and have no OSV advisory.
    The check was repeated with the lock as constraints, with the same
    result.
- [X] T054 Set the status in `specs/002-packs-and-corpus/spec.md` to
  "Implemented". Confirm that every FR and SC maps to a passing test or a
  recorded check, and add the map here in the form of M0's T066. List any
  gap in the spec's Assumptions or in `docs/tech-debt.md`.

  Result (2026-10-21): every FR and SC maps to a passing test or a
  recorded check. One gap: CI is off, so the CI parts of FR-033, SC-010
  and SC-011 ran locally. It is in `docs/tech-debt.md`. Test names drop
  the `test_` prefix; the file is under `tests/unit/packs/` unless named.

  | Req | Passing test or recorded check |
  |---|---|
  | FR-001 | `config/test_profile.py`: `pack_default`, `pack_name_or_path`, `pack_name_or_path_rejected`, `pack_name_pattern_matches_packs`; `config/test_loading.py`: `pack_path_relative_to_profile` |
  | FR-002 | `test_format.py`: `yaml_tag_refused`, `unknown_field_fails`, `invalid_value_fails_at_its_path`, `duplicate_key_names_both_lines`, `every_field_loads` |
  | FR-003 | `cycle_named`, `shared_ancestor_once`, `extends_resolves_against_its_file` |
  | FR-004 | `user_pack_additions`, `child_identity_keys_come_first`, `child_adds_a_scope_to_an_unscoped_type`, `child_enum_value_sorted_into_place`, `restated_values_merge` |
  | FR-005 | `broken_pack` over the `stack.*` rules; `conflict_names_both_packs`; quickstart §1 negative check |
  | FR-006 | `parents_identical_merge`, `parents_conflict`, `glossaries_are_united` |
  | FR-007 | `broken_pack` over the `ref.*` rules; `unknown_reference_fails`, `bad_reference_in_a_list_names_its_index` |
  | FR-008 | `broken_pack` over the `identity.*` rules; `evidence_without_corroborate_warns` |
  | FR-009 | `instruction_text_by_mode`, `instruction_pattern_warns`, `every_model_visible_text_is_linted` |
  | FR-010 | `problems_reported_together`, `error_lists_every_error_in_order`, `problem_fields` |
  | FR-011 | `nfc`, `hash_ignores_layout`, `case_text_read_as_nfc` |
  | FR-012 | `glossary_type_must_exist`, `glossary_alias_clash_ignores_case`, `one_alias_on_two_types_is_fine`. Shipped packs carry no glossary (`shipped_load_clean`, pinned by `shipped_pins`), and a user pack cannot take a shipped name (`pack.shadows-shipped`) |
  | FR-013 | `stack_read_only`, `enterprise_docs_merged`, `defaults_filled_in`, `is_a_copies_roles_attributes_and_time`, `every_field_placed` |
  | FR-014 | `shipped_listed`, `shipped_load_clean`; quickstart §6 |
  | FR-015 | `no_draft_copies`; T050's links; `docs/product/packs/` holds only `finance.yaml` |
  | FR-016 | `shipped_pins` |
  | FR-017 | `shipped_load_clean`, `shipped_have_questions`, `coverage_shipped` |
  | FR-018 | `shipped_listed` |
  | FR-019 | `finance_draft_stacks` (on `core` and on `enterprise-docs`) |
  | FR-020 | `compiled_fits_providers`, `many_types_fit`, `compile_limit`, `compile_at_the_limit`, `every_property_required_and_no_other` |
  | FR-021 | `compile_subset`, `extract_false_left_out`, `compile_rejects_bad_subset` |
  | FR-022 | `compile_deterministic`, `compile_golden` |
  | FR-023 | `hash_ignores_layout`, `hash_description_change`, `hash_set_order`, `hash_identity_order`, `hash_golden` |
  | FR-024 | `stamp_names_the_top_pack` |
  | FR-025 | `hash_retrieval_only`, `hash_glossary_only`; `config/test_hashing.py`: `hash_pack_extract_and_resolve_only`, `hash_needs_pack_hash` |
  | FR-026 | `coverage_missing_relation`, `coverage_not_extracted`, `load_warns_unmet_question`, `load_warns_once_per_unmet_question` |
  | FR-027 | `coverage_checks_user_questions`; quickstart §3 |
  | FR-028 | `case_shape`, `case_file_shape`, `valid_inline_case_passes` |
  | FR-029 | `outcome_fits_expect`, `outcome_problems` |
  | FR-030 | `design_cases_match_snapshot`, `case_counts` |
  | FR-031 | `coverage_shipped`, `missing_veto_case`, `coverage_names_each_gap` |
  | FR-032 | `cases_consistent`, `unknown_attribute`, `element_resolves_in_stack`, `every_case_rule_has_a_case_file` |
  | FR-033 | `document_mix`, `regenerates_same_bytes`; `--check` exits 0 on 3.11.14 and 3.14.8 (T053). **Gap:** Linux only, with CI off |
  | FR-034 | `corpus_plants` |
  | FR-035 | `running_example`, `running_example_statuses`, `golden_running_example` |
  | FR-036 | `items_fit_stack`, `quotes_verbatim` |
  | FR-037 | `running_example_statuses`, `closed_at_next_start`, `fact_issuer_is_source_scope`, `deletions_replay`, `no_equal_content_in_a_group` |
  | FR-038 | `golden_fields`, `golden_coverage`, `golden_as_of_dates`, `golden_single_and_historical`, `golden_names_tell_apart` |
  | FR-039 | `missing_quote_fails`, `unfit_item_fails`; quickstart §5 negative check |
  | FR-040 | `regenerates_same_bytes`; `--check` exits 1 on a difference |
  | FR-041 | `fictional_only` in `test_corpus.py` and `test_cases.py` |
  | FR-042 | `make imports` (three contracts); `test_base_import.py`; quickstart §7 negative check; `error_lists_every_error_in_order` |
  | FR-043 | T049–T052 |
  | SC-001 | `shipped_load_clean`, `coverage_shipped`; quickstart §1 and §3 |
  | SC-002 | `compiled_fits_providers`, `finance_draft_stacks`, `many_types_fit` |
  | SC-003 | `every_rule_has_a_broken_pack` |
  | SC-004 | `hash_ignores_layout`, `hash_description_change`, `hash_retrieval_only`, `hash_glossary_only` |
  | SC-005 | `user_pack_additions`, `coverage_checks_user_questions`; quickstart §1 and §3 |
  | SC-006 | quickstart §2: 0.063–0.070 s, under 1 s |
  | SC-007 | `case_counts` (77), `coverage_shipped`, `cases_consistent` |
  | SC-008 | `document_mix` (41 documents), `quotes_verbatim`, `items_fit_stack` |
  | SC-009 | `golden_coverage` |
  | SC-010 | `regenerates_same_bytes`; quickstart §5: 0.64 s, the same bytes on 3.11.14 and 3.14.8. **Gap:** run locally, not in CI |
  | SC-011 | quickstart §6, with locked and with latest dependencies; `make check` on 3.11.14 and 3.14.8. **Gap:** run locally, not in CI |

---

## Dependencies & Execution Order

### Phase dependencies

- Setup (T001–T003) runs first and in order: T001, then T002, then T003,
  since T002 and T003 both edit the import rules.
- Foundational (T004–T006) needs Setup and blocks every story.
- US1 (T007–T021) needs Foundational. It is the MVP.
- US2 (T022–T029) needs US1's `load_pack` and shipped packs.
- US3 (T030–T032) needs US1. It is independent of US2.
- US4 (T033–T037) needs US1's `load_pack`, `origins` and file phase. It
  is independent of US2 and US3.
- US5 (T038–T048) needs US1's `load_pack` and competency questions. It is
  independent of US2, US3 and US4.
- Polish (T049–T054) needs every story it documents.

### Within each story

- Tests are written first and must fail. Then come implementation and
  the story's run task (T021, T029, T032, T037, T048).
- Shapes come before logic, and logic before the files that ship:
  `stack.py` and `format.py`, then stacking, checks and loading, then the
  shipped packs. In US4, `cases.py` comes before the case files; in US5,
  the generator before the batches.
- A change to a shipped pack after T029 needs a new version and a new pin
  (FR-016). When a corpus item does not fit, change the corpus.

### Parallel opportunities

- Setup: none.
- Foundational: T004 and T006 together, then T005.
- US1: T007–T014 together, then T015 and T016 together.
- US2: T022–T025 together, then T026 and T027 together. T028 can run
  alongside them.
- After US1, US3, US4 and US5 can each run alongside US2.
- US4: T035's conversion script can be written alongside T034, but it
  is checked only once T034 is done.
- US5: T038 and T039 together.
- Polish: T049–T052 together.

---

## Parallel Example: User Story 1

```bash
# Fixtures and tests first, all at once (different files):
Task: "Add the valid test packs under tests/fixtures/packs/valid/"
Task: "Add the broken test packs for the reference and file phases"
Task: "Add the broken test packs for the stack phase"
Task: "Add the broken test packs for the check phase and the two load warnings"
Task: "Write tests/unit/packs/test_format.py"
Task: "Write tests/unit/packs/test_stacking.py"
Task: "Write tests/unit/packs/test_checks.py"
Task: "Write tests/unit/packs/test_shipped.py, part 1"

# Then the two shapes together:
Task: "Implement src/tenetrag/packs/stack.py"
Task: "Implement src/tenetrag/packs/format.py"
```

---

## Implementation Strategy

### MVP first

1. Setup, then Foundational.
2. US1: shipped and user packs load, stack, and fail with every problem
   named.
3. Stop and validate quickstart §1. Every later story reads a stack
   that US1 loads.

### Incremental delivery

1. US2 (compile, stamp, stage hashes). Validate quickstart §2. Both P1
   stories are then done.
2. US3 (coverage), US4 (identity cases) and US5 (corpus), in any order
   or together. Validate quickstart §3, §4 and §5 after each.
3. Polish: docs, the end-to-end quickstart, and the spec marked
   Implemented.

## Notes

- One commit per phase, on `main`, made and pushed at the phase's
  checkpoint with `make check` green, after the `git status` check for
  adopter material. Phases 1 and 2 were committed task by task, before
  this was settled. The red run of each test task is recorded in the
  phase's Result, since no test commit shows it.
- No dependency is added (plan.md). Any that turns out to be needed goes
  through M0's dependency gate (M0 T005) first.
- A task that changes a module boundary updates `ARCHITECTURE.md` in the
  same change; T049 collects this feature's changes.
- The conversion script of T035 stays out of git. The snapshot and
  `test_design_cases_match_snapshot` keep the 60 design cases true.
- The fact table is the corpus's only input. Files under
  `tests/fixtures/corpus/generated/` are never edited by hand.
- Estimate: about 6 working days (plan.md). The packs module takes about
  2 days (US1, US2, US3), identity cases 1 day, and the corpus 2.5 days.
