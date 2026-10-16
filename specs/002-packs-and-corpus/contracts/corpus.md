# Contract: the corpus generator and its files

The generator is test support, not SDK code. It lives in
`tests/support/corpus/` and is neither packaged nor type-checked by the
SDK's mypy run. Imports allowed: the standard library, PyYAML, pydantic
and `tenetrag.packs` (to check items against the shipped stack). Shapes
are in [data-model.md §9](../data-model.md#9-corpus), and the reasons in
[research.md R12](../research.md#r12-the-corpus-generator).

## Command

```sh
uv run python -m tests.support.corpus           # rewrite tests/fixtures/corpus/generated/
uv run python -m tests.support.corpus --check   # generate into a temporary directory and compare
make corpus                                     # the first form
```

- Exit 0 on success. With `--check`, exit 1 and list each file that is
  missing, extra or different.
- A fact table problem exits 2 and lists every problem as
  `{file}: {path}: {message}`, such as
  `documents/D2.yaml: items[D2.3].quote: not in the rendered text of D2`.
- No clock, no randomness, no network. The output depends only on the
  fact table and the shipped `enterprise-docs` stack.

```python
# tests/support/corpus/__init__.py
def generate(facts_dir: Path, out_dir: Path) -> None: ...
    # Raises CorpusError listing every problem; writes nothing in that case.
class CorpusError(Exception): ...
```

## Fact table: one document

```yaml
# tests/fixtures/corpus/facts/documents/D2.yaml
id: D2
language: vi
issuer: alpha
title: Quy chế công tác phí
format: pdf
dates: {issued_on: "2026-01-05", effective_from: "2026-01-15"}
blocks:
  - {heading: "QUY CHẾ CÔNG TÁC PHÍ", level: 1}
  - paragraph: "Phiên bản 2. Ban hành ngày 05/01/2026, có hiệu lực từ ngày 15/01/2026. Đơn vị chủ trì: Phòng Tài chính."
  - paragraph: "Mức phụ cấp lưu trú là 2.500.000 VND/ngày."
  - paragraph: "Quy chế này thay thế phiên bản 1."
items:
  - id: D2.1
    kind: entity
    type: Policy
    world: alpha.ctp.v2
    surface: QUY CHẾ CÔNG TÁC PHÍ
    is_name: true
    attributes:
      title: {value: Quy chế công tác phí, quote: "QUY CHẾ CÔNG TÁC PHÍ"}
      version_label: {value: "2", quote: "Phiên bản 2"}
      issued_on: {value: "2026-01-05", quote: "Ban hành ngày 05/01/2026"}
      effective_from: {value: "2026-01-15", quote: "có hiệu lực từ ngày 15/01/2026"}
  - {id: D2.2, kind: entity, type: Organization, world: alpha.tc, surface: Phòng Tài chính, is_name: true}
  - {id: D2.3, kind: entity, type: Metric, world: met.luu-tru, surface: phụ cấp lưu trú, is_name: true}
  - {id: D2.4, kind: entity, type: Policy, world: alpha.ctp.v1, surface: phiên bản 1, is_name: false}
  - {id: D2.5, kind: relation, type: OWNER_OF, from: D2.2, to: D2.1, quote: "Đơn vị chủ trì: Phòng Tài chính"}
  - id: D2.6
    kind: fact
    type: Requirement
    roles: {source: D2.1, metric: D2.3}
    attributes:
      threshold: {value: 2.500.000 VND/ngày, quote: "2.500.000 VND/ngày"}
    quote: "Mức phụ cấp lưu trú là 2.500.000 VND/ngày."
    valid_from: "2026-01-15"
  - {id: D2.7, kind: relation, type: SUPERSEDES, from: D2.1, to: D2.4, quote: "Quy chế này thay thế phiên bản 1."}
```

- Item ids are `<document>.<n>`, numbered from 1 in file order. An
  item's position compares the numbers, so `D2.10` comes after `D2.9`
  and `D10.1` after `D9.1`.
- Refs in `from`, `to` and `roles` are item ids of the same document. A
  role takes one ref or a list. An entity item links across documents
  through its `world` id.
- `valid_from` and `valid_to` are stated only when the text gives them;
  here the requirement starts when the policy takes effect.
- Every attribute is `{value, quote}`, as in the compiled schema. A
  heading's `level` is 1 to 3, default 1.
- No version group holds two members with equal content: the same ends
  for a relation, or the same role entities and values for a fact. The
  engine makes equal content one version backed by several sources
  (engine brief §3.2), but the generator gives each member its own
  status, so the statuses it derives would be wrong.

## Fact table: the world

```yaml
# tests/fixtures/corpus/facts/world.yaml, one entry
entities:
  alpha.tc:
    type: Organization
    name: Phòng Tài chính
    scope: alpha
    aliases: [P.TC, Finance Department]
    labels: {en: the Finance Department}
    attributes: {category: department}
```

- A world id names one real-world entity. `scope` is the world id of
  the entity it sits in, such as a unit's company. Metrics and places
  have none.
- `labels` says how a generated question names the entity in each
  language. Without one, the question uses `name`.

## Generated files

`docs/D2.md`, rendered from the blocks only. Metadata stays in
`documents.jsonl`:

```markdown
# QUY CHẾ CÔNG TÁC PHÍ

Phiên bản 2. Ban hành ngày 05/01/2026, có hiệu lực từ ngày 15/01/2026. Đơn vị chủ trì: Phòng Tài chính.

Mức phụ cấp lưu trú là 2.500.000 VND/ngày.

Quy chế này thay thế phiên bản 1.
```

`documents.jsonl`, one line per document in id order (`D1`, `D2`, …,
`D10`, compared by number), shown wrapped:

```json
{"dates": {"effective_from": "2026-01-15", "issued_on": "2026-01-05"}, "format": "pdf",
 "id": "D2", "issuer": "alpha", "items": [{"id": "D2.1", "kind": "entity", …}, …],
 "language": "vi", "path": "docs/D2.md", "title": "Quy chế công tác phí"}
```

`graph.json`, excerpt for the running example:

```json
{"deletions": {"D2": {"versions": {
    "OWNER_OF:object=alpha.ctp.v2": [],
    "Requirement:issuer=alpha;metric=met.luu-tru": [
      {"closed_at": "", "item": "D1.6", "status": "current"}]}}, …},
 "entities": {"alpha.tc": ["D1.2", "D2.2", …], "beta.tc": ["D5.2", …], "met.luu-tru": ["D1.3", "D2.3", "D5.3", …]},
 "supersedes": [{"from": "alpha.ctp.v2", "item": "D2.7", "to": "alpha.ctp.v1"}, …],
 "text_in": [{"document": "D1", "entity": "alpha.ctp.v1"}, …],
 "versions": {
  "Requirement:issuer=alpha;metric=met.luu-tru": [
    {"closed_at": "2026-01-15", "item": "D1.6", "status": "superseded"},
    {"closed_at": "", "item": "D2.6", "status": "current"}],
  "Requirement:issuer=beta;metric=met.luu-tru": [
    {"closed_at": "", "item": "D5.6", "status": "current"}], …}}
```

- A relation type with `one_at_a_time` groups by the ends it lists, and
  a fact type with `version_key` by the parts of that key. A group's id
  is the type, then each part as `name=value` in key order, joined by
  `;`. A role's value is the world id of the entity it refers to
  (several are sorted and joined by `,`), an attribute's value is its
  value, and an absent part is left out. A relation type without
  `one_at_a_time`, or a fact with none of its key parts, has no group.
- `issuer` is the scope of the entity in the fact's `source` role, else
  the document's issuer (engine brief §3.2). Phòng Tài chính issues D14,
  but Alpha scopes the guidance in its `source` role, so D14's
  requirement joins Alpha's group.
- A member starts at its `valid_from`, else the document's
  `effective_from`, else `issued_on`, else `held_on`. These document
  dates stand in for the brief's `observed_at`. A member with no start
  is a fact table problem.
- Members are ordered by start, then by position. The newest start is
  `current`. Each older member is `superseded`, with `closed_at` set to
  the next later start, or `""` when the item states its own `valid_to`
  (D35.9). Members that share the newest start are all `conflicting`
  (engine brief §3.2).
- `deletions` replays each document named in `graph.yaml` as if it were
  removed. It lists each group whose statuses change, with the statuses
  of the members left, and maps a group the document empties to `[]`. A
  group the document does not touch, or whose other members keep their
  statuses, is not listed. Deleting D41, the newest of three CRM owners,
  makes D36.6 `current` again.
- `entities` maps each world id to its entity items, and `supersedes`
  lists each `SUPERSEDES` relation by world ids.
- `text_in` comes from `graph.yaml` unchanged, after checking that both
  ends exist, that the entity's type has a document link, that its title
  is the document's title, and that its scope is in the company of the
  document's issuer.

`golden.jsonl`, one question per line. Generated questions come first,
ordered by the position of the item each one starts from, then by
`qtype` in the order of the table below, then by `id`. Hand-written ones
follow in `golden.yaml` order. A generated line, then Q-a:

```json
{"expected_answer": "Thời hạn nộp hồ sơ thanh toán công tác phí là 10 ngày làm việc sau chuyến công tác (D14).",
 "expected_sources": ["D14"],
 "question": "Hướng dẫn thực hiện Quy chế công tác phí của Công ty CP Alpha quy định gì về thời hạn nộp hồ sơ thanh toán?",
 "tags": {"as_of": "", "cq": "ed-7", "id": "single_fact:D14.9", "lang": "vi", "origin": "generated", "qtype": "single_fact"}}
{"expected_answer": "2.000.000 VND/ngày, theo Quy chế công tác phí phiên bản 1 (D1). Phiên bản 2 (D2) nâng mức này lên 2.500.000 VND/ngày từ ngày 15/01/2026.",
 "expected_sources": ["D1", "D2"],
 "question": "Phụ cấp lưu trú theo quy chế công tác phí vào tháng 3/2025 là bao nhiêu?",
 "tags": {"as_of": "2025-03-15", "cq": "ed-7", "id": "Q-a", "lang": "vi", "origin": "hand_written", "qtype": "as_of"}}
```

## Generated golden questions

Each question type has a template in each language. The generator
fills it from the fact table, and answers quote the figures verbatim.

| `qtype` | Generated from | `id` |
|---|---|---|
| `single_fact` | each `ReportedFigure` and `Requirement` alone in its version group | `single_fact:<item>` |
| `entity_all` | each world entity mentioned in three or more documents; the answer quotes every relation, event and fact that links a mention, and the sources are the documents that mention it | `entity_all:<world id>` |
| `meeting_decision` | each `Decision` with a `made_in` meeting | `meeting_decision:<item>` |
| `definition` | each `Definition` | `definition:<item>` |
| `historical_figure` | each `current` `ReportedFigure` with a `period` | `historical_figure:<item>` |
| `as_of` | each member of a group of two or more that is not `conflicting`, dated 30 days after its start, or at its start when it ends sooner; the sources are the documents of every member | `as_of:<item>` |
| `conflicting_versions` | each group with `conflicting` members, and each term whose `current` definitions differ in text across groups | `conflicting_versions:<first item>` or `conflicting_versions:<term world id>` |
| `cross_lingual` | each `Definition` and `Requirement`, asked in the other language | `cross_lingual:<item>` |

- A question's language is its document's: English for `en`,
  Vietnamese for `vi` and `mixed`. A `cross_lingual` question uses the
  other one.
- The answer quotes each answer item with its document, as
  `quote (D1); quote (D2).` Only a quote's final full stop is dropped,
  so figures stay verbatim. An `entity_all` entity that no statement
  links says which documents mention it instead.
- `expected_sources` are document ids sorted as strings, so `D10` comes
  before `D2`.
- `cq` lists every competency question whose `needs` are all among the
  types of the answer items and of the items they link to, plus the
  entity's own type for `entity_all`.
- A question names a world entity by its label (`labels`, else `name`).
  When another world entity shares that label, a version of the same
  company's document adds its version label (`Information Security
  Policy (version 1)`), and an entity of another company adds the
  company's label (`the CRM system of Alpha JSC`). Both can apply:
  `Quy chế công tác phí phiên bản 2 của Công ty CP Alpha`. A requirement
  question names its source's version and issuer itself.
- Vietnamese questions write dates as `15/03/2025`, English ones as
  `15 March 2025`. Figures inside answers are copied from quotes, never
  reformatted.

## Behaviour pinned by tests

All in `tests/unit/packs/test_corpus.py`. Only `test_regenerates_same_bytes`
and the two failure tests run the generator; the rest read the committed
files. Expected values come from the rules applied to the fact table,
never from the generator's code.

| Test | Asserts |
|---|---|
| `test_regenerates_same_bytes` | `generate` into a temporary directory gives files byte-identical to `generated/` (US5-1, FR-040, SC-010) |
| `test_document_mix` | 30 to 60 documents; at least 10 `vi`, 10 `en` and 3 `mixed` (FR-033, SC-008) |
| `test_quotes_verbatim` | every item quote and attribute quote occurs in its document's rendered text (US5-3, SC-008) |
| `test_items_fit_stack` | every item's type, roles, attributes, required parts and endpoint types fit `enterprise-docs`, and every type is extracted (US5-4, SC-008) |
| `test_missing_quote_fails` | a fact table copy with one changed quote raises `CorpusError` naming the document and the item (US5-5, FR-039) |
| `test_unfit_item_fails` | an item with an attribute its type lacks raises `CorpusError` naming the document and the item (FR-039) |
| `test_running_example` | D1 to D5 hold the brief's sentences, issuers and dates; written by hand, not read from the generator (US5-2, FR-035) |
| `test_running_example_statuses` | r1 `superseded` with `closed_at` 2026-01-15, r2 `current`, D5's limit `current` in its own group, and r1 `current` after deleting D2 (US5-2, FR-037) |
| `test_golden_fields` | every line has exactly the four fields, and `tags` has the six string tags (FR-038) |
| `test_golden_coverage` | three or more questions per `qtype`, at least one `hand_written` per `qtype`, and every competency question of `core` and `enterprise-docs` in some `cq` (US5-6, SC-009) |
| `test_golden_running_example` | Q-a, Q-b and Q-c are present with their sources (FR-035) |
| `test_golden_names_tell_apart` | an `entity_all` question about an entity that shares its label names its version or its company |
| `test_golden_sources_exist` | every `expected_sources` id is a generated document (edge case) |
| `test_corpus_plants` | the fact table holds each situation of FR-034: a superseded and a conflicting `OWNER_OF`, one term defined by two issuers and a superseded definition, one limit from two issuers, the same-named policy, unit and person in two companies, an actual and a target figure for one metric, subject and period, `TEXT_IN` links, superseded policies and procedures, an entity under three surfaces, and meetings, decisions and action items with their parts |
| `test_text_form` | every generated file is NFC with LF line endings and ends with one newline |
| `test_fictional_only` | every email uses `.example`, and every organization in `world.yaml` is a fictional company the test lists, a unit of one, or a public authority the test lists as the issuer of a public legal document (FR-041) |
| `test_closed_at_next_start` | a superseded member's `closed_at` is the next later start, or `""` when it states `valid_to`; the CRM owners D35.9, D36.6 and D41.4 are pinned |
| `test_fact_issuer_is_source_scope` | each fact's `issuer` is its source's scope, else the document's issuer, and D14 shows the two differ (engine brief §3.2) |
| `test_deletions_replay` | a deletion lists each changed group with the members left, an emptied group as `[]`, and no untouched group; deleting D41 leaves two members and makes D36.6 `current` (FR-037) |
| `test_no_equal_content_in_a_group` | no two members of a group have the same ends, role entities and values |
| `test_golden_single_and_historical` | `single_fact` covers exactly the figures and requirements alone in their group, and `historical_figure` exactly the current figures with a period |
| `test_golden_as_of_dates` | `as_of` covers exactly the members of groups of two or more that do not conflict, each dated 30 days after its start or at its start when it ends sooner |
