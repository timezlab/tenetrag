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

- Refs in `from`, `to` and `roles` are item ids of the same document. A
  role takes one ref or a list. An entity item links across documents
  through its `world` id.
- `valid_from` and `valid_to` are stated only when the text gives them;
  here the requirement starts when the policy takes effect.
- Every attribute is `{value, quote}`, as in the compiled schema. A
  heading's `level` is 1 to 3, default 1.

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
{"deletions": {"D2": {"versions": {"Requirement:issuer=alpha;metric=met.luu-tru": [
    {"closed_at": "", "item": "D1.6", "status": "current"}]}}},
 "entities": {"alpha.tc": ["D1.2", "D2.2"], "beta.tc": ["D5.2"], "met.luu-tru": ["D1.3", "D2.3", "D5.3"]},
 "supersedes": [{"from": "alpha.ctp.v2", "item": "D2.7", "to": "alpha.ctp.v1"}],
 "text_in": [],
 "versions": {
  "Requirement:issuer=alpha;metric=met.luu-tru": [
    {"closed_at": "2026-01-15", "item": "D1.6", "status": "superseded"},
    {"closed_at": "", "item": "D2.6", "status": "current"}],
  "Requirement:issuer=beta;metric=met.luu-tru": [
    {"closed_at": "", "item": "D5.6", "status": "current"}]}}
```

- A version group's id is the type, then each `version_key` part as
  `name=value` in key order, joined by `;`. A role's value is the world
  id of the entity it refers to, `issuer` is the document's issuer, and
  an absent part is left out.
- Members are ordered by `valid_from`, then item id. The newest start is
  `current`, each older one `superseded` with `closed_at` set to the next
  start, and members that share the newest start are all `conflicting`
  (engine brief §3.2).
- `deletions` lists, for each document named in `graph.yaml`, only the
  groups whose statuses change when that document is removed.
- `text_in` comes from `graph.yaml` unchanged, after checking that each
  end exists.

`golden.jsonl`, one question per line, generated questions first in fact
table order, then hand-written ones in `golden.yaml` order:

```json
{"expected_answer": "2.000.000 VND/ngày, theo Quy chế công tác phí phiên bản 1 (D1). Phiên bản 2 (D2) nâng mức này lên 2.500.000 VND/ngày từ ngày 15/01/2026.",
 "expected_sources": ["D1", "D2"],
 "question": "Phụ cấp lưu trú theo quy chế công tác phí vào tháng 3/2025 là bao nhiêu?",
 "tags": {"as_of": "2025-03-15", "cq": "ed-7", "id": "Q-a", "lang": "vi", "origin": "hand_written", "qtype": "as_of"}}
```

## Generated golden questions

Each question type has a template in each language. The generator
fills it from the fact table, and answers quote the figures verbatim.

| `qtype` | Generated from |
|---|---|
| `single_fact` | each `ReportedFigure` and `Requirement` with one source |
| `entity_all` | each world entity mentioned in three or more documents |
| `meeting_decision` | each `Decision` made in a `Meeting` |
| `definition` | each `Definition` |
| `historical_figure` | each `ReportedFigure` with a `period` |
| `as_of` | each version group with two or more members, at one date inside each member's interval |
| `conflicting_versions` | each group with `conflicting` members, and each metric that two sources define differently |
| `cross_lingual` | each `Definition` and `Requirement`, asked in the other language than its document's |

Vietnamese questions write dates as `15/03/2025` and numbers as
`2.000.000`; English ones write `15 March 2025` and `2,000,000`. Figures
inside answers are copied from quotes, never reformatted.

## Behaviour pinned by tests

All in `tests/unit/packs/test_corpus.py`. Only `test_regenerates_same_bytes`
runs the generator; the rest read the committed files.

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
| `test_golden_sources_exist` | every `expected_sources` id is a generated document (edge case) |
| `test_corpus_plants` | the fact table holds each situation of FR-034: two `OWNER_OF` starts, two equal starts, two definitions of one metric, the two companies' same-titled policy, unit, limit and same-named person |
| `test_text_form` | every generated file is NFC with LF line endings and ends with one newline |
| `test_fictional_only` | every email uses `.example`, and every organization in `world.yaml` is a fictional company the test lists, a unit of one, or a public authority the test lists as the issuer of a public legal document (FR-041) |
