"""Text normalization for matching (contracts/text.md, research R18).

Behaviours:
1. The tone-mark table moves the mark from the second vowel to the first in
   the endings oa, oe and uy, in lower, upper and mixed case.
2. An ending followed by a letter, and uy after q, are left alone.
3. Diacritics and đ are kept, so lãi, lại and lai stay apart (SC-009).
4. Decomposed input gives the same result as precomposed input.
5. Whitespace collapses to one space and the ends are trimmed.
6. Case is folded with casefold, not lower.
7. The result is NFC, even where casefolding decomposes a letter.
8. norm is idempotent, on the examples and on the corpus's entity names.
9. tenetrag.engine imports no store, no llm, no auth and no driver.
"""

import subprocess
import sys
import unicodedata
from pathlib import Path

import pytest
import yaml

from tenetrag.engine.text import norm

WORLD = Path(__file__).parents[2] / "fixtures" / "corpus" / "facts" / "world.yaml"

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

EXAMPLES = [*MOVED, *KEPT, "lãi", "lại", "lai", "Đà Nẵng", "  Ngân\thàng\n\u00a0Phương   Đông  "]


def corpus_names() -> list[str]:
    entities = yaml.safe_load(WORLD.read_text(encoding="utf-8"))["entities"]
    return [
        name
        for entity in entities.values()
        for name in [entity["name"], *entity.get("aliases", [])]
    ]


@pytest.mark.parametrize(("old", "new"), TONE_MARK_PAIRS)
def test_tone_mark_pairs_moved(old, new):
    assert norm(old) == new
    assert norm("h" + old) == "h" + new
    assert norm(("h" + old).upper()) == "h" + new


@pytest.mark.parametrize(("text", "expected"), MOVED.items())
def test_tone_marks_moved(text, expected):
    assert norm(text) == expected


@pytest.mark.parametrize(("text", "expected"), KEPT.items())
def test_tone_marks_kept(text, expected):
    assert norm(text) == expected


def test_diacritics_kept_apart():
    assert len({norm("lãi"), norm("lại"), norm("lai")}) == 3
    assert norm("Đà Nẵng") == "đà nẵng"
    assert norm("ĐỒNG") == "đồng"


@pytest.mark.parametrize("text", EXAMPLES)
def test_nfd_equals_nfc(text):
    decomposed = unicodedata.normalize("NFD", text)
    assert decomposed != unicodedata.normalize("NFC", text) or text.isascii()
    assert norm(decomposed) == norm(text)


def test_whitespace_collapsed():
    assert norm("  Ngân\thàng\n\u00a0Phương   Đông  ") == "ngân hàng phương đông"
    assert norm("   ") == ""
    assert norm("") == ""


def test_casefolded():
    # casefold, not lower: ß folds to ss, so the two spellings of a name match.
    assert norm("Straße") == norm("STRASSE") == "strasse"


def test_result_is_nfc():
    # Casefolding decomposes ǰ into j and a combining caron; stores compare text exactly.
    assert unicodedata.normalize("NFC", "ǰ").casefold() != "ǰ"
    assert norm("ǰ") == "ǰ"
    assert all(norm(text) == unicodedata.normalize("NFC", norm(text)) for text in EXAMPLES)


def test_idempotent():
    names = corpus_names()
    assert len(names) > 50
    for text in [*EXAMPLES, *names]:
        once = norm(text)
        assert norm(once) == once, text


def test_engine_imports():
    # A fresh interpreter, so modules the test session already imported do not count.
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys, tenetrag.engine, tenetrag.engine.text; print('\\n'.join(sys.modules))",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    loaded = set(result.stdout.splitlines())
    forbidden_tenetrag = {"tenetrag.storage", "tenetrag.llm", "tenetrag.auth"}
    drivers = {"openai", "httpx", "databricks", "neo4j", "psycopg", "psycopg_pool", "pyspark"}
    assert "tenetrag.engine.text" in loaded
    assert sorted(loaded & forbidden_tenetrag) == []
    assert sorted({name.partition(".")[0] for name in loaded} & drivers) == []
