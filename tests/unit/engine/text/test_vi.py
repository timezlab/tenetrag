"""Vietnamese tone-mark placement, the `vi` rule of norm (contracts/text.md, data-model §11).

Behaviours:
1. The rule moves the mark from the second vowel to the first in the endings
   oa, oe and uy, in lower, upper and mixed case.
2. An ending followed by a letter, and uy after q, are left alone.
3. With the rule, decomposed input still gives the same result as
   precomposed input, and norm stays idempotent.
"""

import unicodedata

import pytest

from tenetrag.engine.text import norm

VI = ("vi",)

# data-model §11, written out here so the test does not share the module's table.
TONE_MARK_PAIRS = [
    ("oà", "òa"),
    ("oá", "óa"),
    ("oả", "ỏa"),
    ("oã", "õa"),
    ("oạ", "ọa"),
    ("oè", "òe"),
    ("oé", "óe"),
    ("oẻ", "ỏe"),
    ("oẽ", "õe"),
    ("oẹ", "ọe"),
    ("uỳ", "ùy"),
    ("uý", "úy"),
    ("uỷ", "ủy"),
    ("uỹ", "ũy"),
    ("uỵ", "ụy"),
]

MOVED = {
    "hoà": "hòa",
    "Hoà": "hòa",
    "HOÀ BÌNH": "hòa bình",
    "thuỷ": "thủy",
    "Thuỷ": "thủy",
    "khoẻ": "khỏe",
    "KHOẺ": "khỏe",
    "uỷ ban": "ủy ban",
    "Uỷ ban  Nhân dân": "ủy ban nhân dân",
    "hoà,": "hòa,",
}

KEPT = {
    "hoàng": "hoàng",
    "Hoàng": "hoàng",
    "quý": "quý",
    "QUÝ": "quý",
    "quỳ": "quỳ",
    "khuỷu": "khuỷu",
    "toàn": "toàn",
    "khoảng": "khoảng",
    "hòa": "hòa",
}


@pytest.mark.parametrize(("old", "new"), TONE_MARK_PAIRS)
def test_tone_mark_pairs_moved(old, new):
    assert norm(old, languages=VI) == new
    assert norm("h" + old, languages=VI) == "h" + new
    assert norm(("h" + old).upper(), languages=VI) == "h" + new


@pytest.mark.parametrize(("text", "expected"), MOVED.items())
def test_tone_marks_moved(text, expected):
    assert norm(text, languages=VI) == expected


@pytest.mark.parametrize(("text", "expected"), KEPT.items())
def test_tone_marks_kept(text, expected):
    assert norm(text, languages=VI) == expected


@pytest.mark.parametrize("text", [*MOVED, *KEPT])
def test_nfd_equals_nfc(text):
    decomposed = unicodedata.normalize("NFD", text)
    assert decomposed != unicodedata.normalize("NFC", text)
    assert norm(decomposed, languages=VI) == norm(text, languages=VI)


@pytest.mark.parametrize("text", [*MOVED, *KEPT])
def test_idempotent(text):
    once = norm(text, languages=VI)
    assert norm(once, languages=VI) == once
