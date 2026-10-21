# Quickstart: validate domain packs and the synthetic corpus (M1, part 1)

A run guide that proves each user story works. Shapes are in
[data-model.md](data-model.md), and signatures in [contracts/](contracts/).

## Prerequisites

- A checkout of `main` with M0 in place, and uv 0.12 or later.
- `uv sync --locked --all-extras`. This feature adds no package, so the
  lock file does not change.
- No Docker, no model, no network beyond package downloads. Every check
  below runs offline.

## 1. Load and check a stack (Story 1, SC-001, SC-003, SC-005)

```python
from tenetrag.packs import load_pack, shipped_packs

shipped_packs()                       # (ShippedPack('core', 1), ShippedPack('enterprise-docs', 1))
stack = load_pack("enterprise-docs")
stack.warnings                        # ()
[k.attributes for k in stack.entities["Person"].identity]
                                      # [('scope', 'employee_id'), ('email',)]
stack.entities["Organization"].scope.when["category"]
                                      # ('branch', 'business_unit', 'committee', 'department', 'team', 'unit')
```

Save the user pack of
[contracts/packs.md](contracts/packs.md#example-a-user-pack-on-enterprise-docs)
as `/tmp/alpha-ops.yaml` (any scratch path) and load it:

```python
user = load_pack("/tmp/alpha-ops.yaml")
"Vendor" in user.entities, "SUPPLIES" in user.relations   # (True, True)
"vendor_desk" in user.enums["OrgCategory"]                # True
```

**Expected:**
- both shipped packs load with no warning;
- the user pack's three additions are in the stack, with no code
  change;
- `uv run pytest tests/unit/packs -q -k "broken_pack or every_rule"`
  passes: each rule id of data model §1 has a broken pack that fails
  with that id.

**Negative check:** add to the user pack

```yaml
entities:
  Person:
    attributes:
      email: {range: int}
```

and loading fails with `stack.changed-range`, naming `core`, `alpha-ops`
and `entities.Person.attributes.email.range`. Remove it.

## 2. Compile, stamp and hash (Story 2, SC-002, SC-004, SC-006)

```python
import time
from pathlib import Path
from tenetrag.packs import load_pack, compile_schema
from tenetrag.llm.capabilities import capability_profile
from tenetrag.llm.structured import check_schema

# A user pack on [enterprise-docs, finance], the largest planned stack.
# Run from the repository root; the finance path is made absolute.
finance = Path("docs/product/packs/finance.yaml").resolve()
Path("/tmp/largest.yaml").write_text(
    f"pack: largest\nversion: 1\nextends: [enterprise-docs, '{finance}']\n"
)
start = time.perf_counter()
stack = load_pack("/tmp/largest.yaml")
compiled = compile_schema(stack)
elapsed = time.perf_counter() - start

databricks = capability_profile("databricks", "databricks-claude-sonnet-5")
check_schema(compiled.schema, databricks, "databricks-claude-sonnet-5")   # no error
compiled.property_count, round(elapsed, 3)                                # (52, under 1.0)
```

**Expected:**
- `check_schema` raises nothing, and the schema has 52 properties;
- `elapsed` is under one second (SC-006); record the figure in the
  results below;
- `uv run pytest tests/unit/packs -q -k "hash or compile"` passes:
  reordering, comments and NFD keep every hash; one description changes
  it; retrieval and glossary changes leave the index hash alone.

**Negative check:** `compile_schema(stack, max_properties=40)` raises
`ConfigError` with the count 52 and the parts listed by size.

## 3. Coverage (Story 3, SC-001, SC-005)

```python
from tenetrag.packs import check_coverage, load_pack

report = check_coverage(load_pack("enterprise-docs"))
report.passed, len(report.questions)          # (True, 14)
check_coverage(load_pack("/tmp/alpha-ops.yaml")).passed   # True, 15 questions
```

**Negative check:** add to the user pack the question
`{id: alpha-ops-2, text: "Who audited system S?", needs: [AUDITED]}`.
Loading warns `coverage.unmet`, and the report lists `AUDITED` as
missing for `alpha-ops-2`. Remove it.

## 4. Identity cases (Story 4, SC-007)

```sh
uv run pytest tests/unit/packs/test_cases.py -q
```

**Expected:**
- 77 cases, 60 of them the design cases with their original ids;
- `check_cases` reports no problem for the shipped files and the
  `finance` file;
- `test_design_cases_match_snapshot` passes: every design case keeps
  its class and its R2 outcome.

**Negative check:** `test_missing_veto_case` removes PER-5 from a copy of
`enterprise-docs.cases.yaml`, and the check fails with
`case.coverage-element` naming `veto:employee_id`.

## 5. Corpus (Story 5, SC-008, SC-009, SC-010)

```sh
time make corpus                                  # rewrites tests/fixtures/corpus/generated/
git status --short tests/fixtures/corpus          # nothing: the committed corpus is current
uv run python -m tests.support.corpus --check     # exit 0
uv run pytest tests/unit/packs/test_corpus.py -q
```

**Expected:**
- one run takes under 30 seconds (SC-010);
- `git status` shows no change, and `--check` exits 0;
- the corpus tests pass: document mix, verbatim quotes, items that fit
  `enterprise-docs`, golden coverage, and the running example's
  statuses, including r1 `current` again after D2 is deleted.

**Negative check:** change one character of D2's sentence
"Mức phụ cấp lưu trú là 2.500.000 VND/ngày." in
`facts/documents/D2.yaml`. `make corpus` exits 2 and names D2 and the
items whose quotes no longer occur. Revert it.

## 6. Fresh install with no extras (SC-011)

```sh
uv build --wheel
uv run python -m zipfile -l dist/tenetrag-*.whl | grep shipped/
                                                  # core.yaml, core.cases.yaml, enterprise-docs.yaml, enterprise-docs.cases.yaml
uv venv /tmp/bare && uv pip install --python /tmp/bare dist/tenetrag-*.whl
/tmp/bare/bin/python -c "
from tenetrag.packs import shipped_packs, load_pack, compile_schema
from tenetrag.packs.cases import shipped_cases, check_cases
print(shipped_packs())
print(compile_schema(load_pack('enterprise-docs')).property_count)
print(check_cases(*shipped_cases()))
"
```

**Expected:** the wheel lists the four shipped files; the bare venv
prints both packs, `52` and `()`, with no optional package installed.

## 7. Gates

```sh
make check
```

**Expected:** every gate passes on the local Python, and in CI on 3.11
and 3.14. `lint-imports` shows `tenetrag.packs` in the `config | packs`
layer, with no import of an optional SDK.

**Negative check:** add `from tenetrag.config import Profile` to
`src/tenetrag/packs/stack.py`, and `lint-imports` fails, naming the two
sibling modules. Revert it.

## Done when

- `make check` passes locally and in CI on Python 3.11 and 3.14, with the
  corpus check among the unit tests.
- SC-006 and SC-010 are measured and recorded below.
- ARCHITECTURE.md, domain-packs.md, v1-packs.md, test-corpora.md, the
  engine brief's testing section and the `AGENTS.md` status reflect what
  landed (FR-043), and `docs/product/packs/` holds only `finance.yaml`.

## Results (2026-10-21, T053)

Run on Linux x86_64 with 88 CPUs and uv 0.12.23, in the working checkout
of `main` at `d430b78` plus the uncommitted Phase 8 doc edits. Scratch
files went to a scratch directory instead of `/tmp`. GitHub Actions CI
has been off since 2026-10-15, so a second local environment on Python
3.14, synced from the lock, stands in for the CI matrix.

| Check | Result |
|---|---|
| Load and check (§1, SC-001, SC-003, SC-005) | Both shipped packs load with `warnings == ()`, and the Person keys and Organization unit categories are as listed. The user pack adds `Vendor`, `SUPPLIES` and `vendor_desk` with no code change. `-k "broken_pack or every_rule"`: 41 passed. Negative check: one `stack.changed-range` problem naming `core`, the user pack's file and `entities.Person.attributes.email.range`. |
| Compile, stamp and hash (§2, SC-002, SC-004, SC-006) | The largest stack compiles to 52 properties, and `check_schema` for `databricks-claude-sonnet-5` raises nothing. Load and compile take 0.063–0.070 s over five runs (SC-006: under 1 s). `-k "hash or compile"`: 50 passed. Negative check: `max_properties=40` raises `ConfigError` with 52 and the parts by size, `entity (10)` first. |
| Coverage (§3) | `enterprise-docs`: `(True, 14)`. User pack: passed, 15 questions. Negative check: a `coverage.unmet` warning, and the report lists `AUDITED` missing for `alpha-ops-2`. |
| Identity cases (§4, SC-007) | `test_cases.py`: 88 passed. 77 cases: 60 design cases with their ids (30 apart, 30 merge) and 17 added; 27 in `core`, 43 in `enterprise-docs`, 7 for `finance`. `check_cases` returns `()` for the shipped files and the `finance` file. `test_design_cases_match_snapshot` and `test_missing_veto_case` pass. |
| Corpus (§5, SC-008, SC-009, SC-010) | `make corpus` takes 0.64 s on 3.11 (SC-010: under 30 s), and `--check` 0.98 s on 3.14. `git status` shows no change, and `--check` exits 0 on 3.11.14 and on 3.14.8, so both versions write the committed bytes. `test_corpus.py`: 22 passed. Negative check: one changed digit in D2's paragraph makes `make corpus` exit 2, naming `items[D2.6].quote` and `items[D2.6].attributes.threshold.quote`. |
| Fresh install (§6, SC-011) | The wheel lists the four shipped files. A venv with no extras prints both packs, `52` and `()`, and no `openai`, `databricks`, `neo4j` or `psycopg` module is loaded. Run twice: with the locked versions as constraints (pydantic 2.13.5), and unconstrained, which resolved pydantic 2.14.1 and pydantic-core 2.50.1 (published 2026-10-11, no OSV advisory). |
| Gates (§7) | `make check` on 3.11.14: every gate passes, 1168 passed and 22 deselected; the unit suite takes 24.7 s and the whole run 27.2 s. On 3.14.8: 1168 passed in 25.1 s. `lint-imports`: 3 contracts kept. Negative check: `Module layers BROKEN`, `tenetrag.packs is not allowed to import tenetrag.config`, at `tenetrag.packs.stack` line 19. |
| Docs (FR-043) | ARCHITECTURE.md, domain-packs.md, v1-packs.md, test-corpora.md, engine brief §10 and the `AGENTS.md` status are updated (T049–T052). `docs/product/packs/` holds only `finance.yaml`. |
