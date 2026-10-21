# Contract: `tenetrag.engine.text`

Imports allowed: the standard library only. The first module of
`tenetrag.engine`; the rest of the engine arrives in 004. The table is in
[data-model.md §11](../data-model.md#11-tone-mark-table-norm), the
reasons in [research.md R18](../research.md#r18-norm-and-the-tone-mark-table).

```python
def norm(text: str) -> str: ...
    # 1. unicodedata.normalize("NFC", text)
    # 2. the tone-mark table: in a syllable ending oa, oe or uy (no letter after it),
    #    move the mark from the second vowel to the first; uy after q is left alone
    # 3. casefold(), then NFC again
    # 4. " ".join(text.split())
    # Pure and total: any str gives a str; "" gives "".
```

- Diacritics and `đ` are kept: `lãi`, `lại` and `lai` stay three
  strings (engine brief §7).
- The function is the engine's (ADR 0008 §4). No store calls it: stores
  receive `name_norm`, `alias_norm`, `value_norm`, `text_norm`,
  `title_norm` and `code_norm` already computed (FR-004, FR-047).
- `norm(norm(x)) == norm(x)` for every `x`.
- The contract suite's fixture builder calls it now; the 004 pipeline
  calls it for every normalized field.

```python
from tenetrag.engine.text import norm

norm("Uỷ ban  Nhân dân")    # 'ủy ban nhân dân'
norm("HOÀ BÌNH")            # 'hòa bình'
norm("Hoàng")               # 'hoàng': the mark is followed by ng
norm("quý")                 # 'quý': uy after q
```

## Behaviour pinned by tests

`tests/unit/engine/test_text.py`:

| Test | Asserts |
|---|---|
| `test_tone_marks_moved` | `hoà`→`hòa`, `Hoà`→`hòa`, `thuỷ`→`thủy`, `khoẻ`→`khỏe`, `uỷ ban`→`ủy ban`, and all fifteen pairs of the table in lower and upper case |
| `test_tone_marks_kept` | `hoàng`, `quý`, `khuỷu`, `toàn`, `hòa` (already new) are unchanged apart from case |
| `test_diacritics_kept_apart` | `lãi`, `lại`, `lai` give three different results; `đ` stays `đ` (SC-009) |
| `test_nfd_equals_nfc` | the decomposed form of each example gives the same result as the composed one |
| `test_whitespace_collapsed` | tabs, newlines, NBSP and runs of spaces become one space; ends are trimmed |
| `test_idempotent` | `norm(norm(x)) == norm(x)` over every example and the corpus's entity names |
| `test_engine_imports` | `tenetrag.engine` imports no store, no `llm`, no `auth` and no driver (also enforced by `lint-imports`, FR-048) |
