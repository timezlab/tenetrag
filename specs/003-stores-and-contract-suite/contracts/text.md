# Contract: `tenetrag.engine.text`

Imports allowed: the standard library only. The first package of
`tenetrag.engine`; the rest of the engine arrives in 004. The shared
steps hold for every language. Each language with extra rules has its
own module, and `norm` runs a rule only when the caller names its
language
([ADR 0025](../../../docs/decisions/0025-normalize-text-by-the-languages-the-profile-names.md)).
The `vi` table is in
[data-model.md §11](../data-model.md#11-tone-mark-table-norm-the-vi-rule),
the reasons in [research.md R18](../research.md#r18-norm-and-the-tone-mark-table).

```python
# tenetrag/engine/text/__init__.py
LANGUAGE_RULES: Mapping[str, Callable[[str], str]]    # {"vi": vi.move_tone_marks}

def norm(text: str, *, languages: Collection[str] = ()) -> str: ...
    # 1. unicodedata.normalize("NFC", text), casefold(), then NFC again
    # 2. the rule of each language in sorted(languages) that has one;
    #    a language with no rule adds nothing
    # 3. " ".join(text.split())
    # Pure and total: any str gives a str; "" gives "".

# tenetrag/engine/text/vi.py
def move_tone_marks(text: str) -> str: ...
    # On NFC, casefolded text: in a syllable ending oa, oe or uy (no letter
    # after it), move the mark from the second vowel to the first; uy after
    # q is left alone.
```

- The engine passes the profile's `text_languages` as `languages`, at
  index and query time alike, for every text whatever its own language
  tag ([config.md §1b](config.md#1b-text_languages)). Index and query
  text that name different languages stop matching.
- Diacritics and `đ` are kept: `lãi`, `lại` and `lai` stay three
  strings (engine brief §7).
- A rule takes NFC, casefolded text and returns NFC text. Casefolding
  keeps each mark on its letter, so the `vi` rule's lower-case table
  gives what the table gives on the original case.
- The function is the engine's (ADR 0008 §4). No store calls it: stores
  receive `name_norm`, `alias_norm`, `value_norm`, `text_norm`,
  `title_norm` and `code_norm` already computed (FR-004, FR-047).
- `norm(norm(x, languages=l), languages=l) == norm(x, languages=l)` for
  every `x` and `l`.
- The contract suite's fixture builder calls it now with
  `languages=("vi",)`; the 004 pipeline calls it for every normalized
  field.

```python
from tenetrag.engine.text import norm

norm("Uỷ ban  Nhân dân")                    # 'uỷ ban nhân dân': no language named
norm("Uỷ ban  Nhân dân", languages=["vi"])  # 'ủy ban nhân dân'
norm("HOÀ BÌNH", languages=["vi"])          # 'hòa bình'
norm("Hoàng", languages=["vi"])             # 'hoàng': the mark is followed by ng
norm("quý", languages=["vi"])               # 'quý': uy after q
norm("Hoà", languages=["en"])               # 'hoà': en has no extra rule
```

## Behaviour pinned by tests

`tests/unit/engine/text/test_norm.py`:

| Test | Asserts |
|---|---|
| `test_no_language_rules_by_default` | with no language, `hoà` stays `hoà` and `Uỷ ban` gives `uỷ ban` |
| `test_language_without_rules_adds_nothing` | `en` adds nothing; `["en", "vi"]` equals `["vi", "en"]` and `["vi"]` |
| `test_rules_run_in_language_order` | two non-commuting rules run in the order of their codes, for a set and for a list |
| `test_diacritics_kept_apart` | `lãi`, `lại`, `lai` give three different results; `đ` stays `đ` (SC-009) |
| `test_nfd_equals_nfc` | the decomposed form of each example gives the same result as the composed one |
| `test_whitespace_collapsed` | tabs, newlines, NBSP and runs of spaces become one space; ends are trimmed |
| `test_casefolded` | `Straße` and `STRASSE` both give `strasse` |
| `test_result_is_nfc` | `ǰ`, which casefolding decomposes, comes back composed |
| `test_idempotent` | `norm(norm(x)) == norm(x)` over every example and the corpus's entity names, with no language and with `vi` |
| `test_engine_imports` | `tenetrag.engine` loads `tenetrag.engine.text.vi` and no store, no `llm`, no `auth` and no driver (also enforced by `lint-imports`, FR-048) |

`tests/unit/engine/text/test_vi.py`, all with `languages=("vi",)`:

| Test | Asserts |
|---|---|
| `test_tone_mark_pairs_moved` | all fifteen pairs of the table, alone and after a consonant, in lower and upper case |
| `test_tone_marks_moved` | `hoà`→`hòa`, `Hoà`→`hòa`, `thuỷ`→`thủy`, `khoẻ`→`khỏe`, `uỷ ban`→`ủy ban` |
| `test_tone_marks_kept` | `hoàng`, `quý`, `quỳ`, `khuỷu`, `toàn`, `khoảng`, `hòa` (already new) are unchanged apart from case |
| `test_nfd_equals_nfc` | the decomposed form of each example gives the same result |
| `test_idempotent` | `norm` is idempotent on each example |
