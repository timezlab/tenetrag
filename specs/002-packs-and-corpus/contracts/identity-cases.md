# Contract: identity case files and `tenetrag.packs.cases`

The case file format, the API that loads and checks it, and the files
that ship. Shapes are in
[data-model.md §8](../data-model.md#8-identity-cases), and the
conversion of the design cases is in
[research.md R11](../research.md#r11-identity-cases).

```python
from os import PathLike
from tenetrag.packs import PackProblem

def load_cases(path: str | PathLike[str]) -> CaseSet: ...
    # Reads one case file and loads the stack its `pack` names, a shipped
    # name or a path relative to the case file. Raises ConfigError for a
    # shape problem (file.* rule ids, as for packs) or a stack that fails.

def shipped_cases() -> tuple[CaseSet, ...]: ...
    # core.cases.yaml and enterprise-docs.cases.yaml, from package data.

def check_cases(*case_sets: CaseSet) -> tuple[PackProblem, ...]: ...
    # Consistency of every case against its own stack, ids unique across
    # all the sets given, and FR-031 coverage for each set whose top pack
    # is shipped. Empty when everything holds. Pure: no resolver runs.

class CaseSet:      # frozen
    source: str                          # "core.cases.yaml" for a shipped file, else the absolute path
    stack: PackStack
    entities: Mapping[str, CaseEntity]
    cases: tuple[Case, ...]
```

Feature 004 runs the cases through the resolver. This feature only
loads and checks them.

## Files

| File | `pack` | Cases |
|---|---|---|
| `src/tenetrag/packs/shipped/core.cases.yaml` | `core` | 23 design, 2 added |
| `src/tenetrag/packs/shipped/enterprise-docs.cases.yaml` | `enterprise-docs` | 30 design, 11 added |
| `tests/fixtures/identity/finance.cases.yaml` | `../../../docs/product/packs/finance.yaml` | 7 design |

The fixtures were converted once from the
[snapshot](../research/identity-design-cases.json) by a throwaway
script, which is not committed. From then on they are edited by hand,
and `test_design_cases_match_snapshot` keeps the 60 design cases true to
the snapshot.

## Example: PER-5 under `enterprise-docs`

```yaml
pack: enterprise-docs
entities:
  alpha:
    type: Organization
    name: Công ty CP Alpha
    attributes:
      category: {value: company, quote: "Công ty CP Alpha"}
      registration_id: {value: "0101234567", quote: "mã số doanh nghiệp 0101234567"}
  alpha.cntt:                       # the script held this unit as text in `unit_at`
    type: Organization
    name: Phòng Công nghệ thông tin
    scope: alpha
    attributes:
      category: {value: department, quote: "Phòng Công nghệ thông tin"}
  hung:
    type: Person
    name: Phạm Hùng
    scope: alpha
    attributes:
      employee_id: {value: A0123, quote: "ông Phạm Hùng (mã nhân viên A0123)"}
    relations:
      - {type: MEMBER_OF, to: alpha.cntt}
cases:
  - id: PER-5
    origin: design
    expect: apart
    title: Trùng họ tên và phòng, khác mã nhân viên
    existing: [hung]
    mention:
      type: Person
      name: Phạm Hùng
      scope: alpha
      scope_source: text
      attributes:
        employee_id: {value: A0456, quote: "ông Phạm Hùng, mã nhân viên A0456"}
      relations:
        - {type: MEMBER_OF, to: alpha.cntt}
      document: {issuer: alpha, date: "2025-06-10", language: vi}
    outcome: {kind: new}
    depends_on: ["veto:employee_id"]
    blocked_by: employee_id
```

The four outcome forms:

```yaml
outcome: {kind: merge, into: binh}                               # PER-2
outcome: {kind: new}                                             # PER-5
outcome: {kind: same_as, links: [alpha.hn.khdn, alpha.dn.khdn]}  # UNIT-3
outcome: {kind: confirm, candidates: [an.alpha], right: an.alpha}  # PER-7
```

## Example: a failed check

```text
  - enterprise-docs.cases.yaml: cases[PER-5].depends_on[0]: `Person` has no veto `employee_ids` under `enterprise-docs` [case.unknown-element]
  - core.cases.yaml: cases[PER-10].mention.attributes.employee_id: `Person` has no attribute `employee_id` under `core` [case.unknown-attribute]
  - enterprise-docs.cases.yaml: entities.Procedure.vetoes[code]: no case depends on `veto:code`; add one that this veto keeps apart [case.coverage-element]
```

## Behaviour pinned by tests

All in `tests/unit/packs/test_cases.py`:

| Test | Asserts |
|---|---|
| `test_cases_consistent` | `check_cases(*shipped_cases(), finance_cases)` returns no problem (FR-032, SC-007) |
| `test_case_counts` | 73 cases: 60 `design` and 13 `added`, split per file as in the table above |
| `test_design_cases_match_snapshot` | the 60 design ids, each `expect` and each outcome kind equal the snapshot's class and R2 outcome; 30 apart and 30 merge (US4-4, FR-030). Reads the snapshot, so it needs a checkout, like the `finance` tests |
| `test_coverage_shipped` | no `case.coverage-*` problem for `core` or `enterprise-docs` (US4-1, US4-2, FR-031) |
| `test_missing_veto_case` | the `enterprise-docs` cases without PER-5 give `case.coverage-element` naming `veto:employee_id` (US4 independent test) |
| `test_unknown_attribute` | a case giving `Person` an `employee_id` under `core` fails, naming the case and the attribute (US4-3) |
| `test_element_resolves_in_stack` | `veto:employee_id` passes under `enterprise-docs` and fails under `core` with `case.unknown-element` |
| `test_outcome_fits_expect` | `merge` with `expect: apart`, and an `into` outside `existing`, give `case.outcome` |
| `test_blocked_by_needs_veto` | `blocked_by: code` without `veto:code` in `depends_on` gives `case.blocked-by` |
| `test_duplicate_id_across_files` | one id in two files gives `case.duplicate-id`, naming both files |
| `test_d5_situation` | POL-1 and UNIT-1 keep Beta's mention apart from Alpha's entity, and MET-1 merges the metric (US4-5) |
| `test_case_shape` | an unknown field, an empty quote or an unknown outcome kind fails `load_cases` with a `file.*` rule id |
| `test_fictional_only` | every email in a case file uses the `.example` domain (FR-041) |
