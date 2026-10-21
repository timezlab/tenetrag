"""The shared steps of norm, and how it picks language rules (contracts/text.md, ADR 0025).

Behaviours:
1. With no language named, norm runs the shared steps only, so a Vietnamese
   tone mark stays where it is.
2. A named language with no rules adds nothing, and the order of the
   languages does not matter: rules run in the order of their codes.
3. Diacritics and đ are kept, so lãi, lại and lai stay apart (SC-009).
4. Decomposed input gives the same result as precomposed input.
5. Whitespace collapses to one space and the ends are trimmed.
6. Case is folded with casefold, not lower.
7. The result is NFC, even where casefolding decomposes a letter.
8. norm is idempotent, with and without the vi rule, on the examples and on
   the corpus's entity names.
9. tenetrag.engine imports no store, no llm, no auth and no driver.
"""

import subprocess
import sys
import unicodedata
from pathlib import Path

import pytest
import yaml

from tenetrag.engine.text import norm

WORLD = Path(__file__).parents[3] / "fixtures" / "corpus" / "facts" / "world.yaml"

EXAMPLES = [
    "hoà",
    "Hoàng",
    "quý",
    "lãi",
    "lại",
    "lai",
    "Đà Nẵng",
    "  Ngân\thàng\n\u00a0Phương   Đông  ",
]


def corpus_names() -> list[str]:
    entities = yaml.safe_load(WORLD.read_text(encoding="utf-8"))["entities"]
    return [
        name
        for entity in entities.values()
        for name in [entity["name"], *entity.get("aliases", [])]
    ]


def test_no_language_rules_by_default():
    assert norm("hoà") == "hoà"
    assert norm("HOÀ  Bình") == "hoà bình"
    assert norm("Uỷ ban") == "uỷ ban"


def test_language_without_rules_adds_nothing():
    assert norm("Hoà", languages=["en"]) == norm("Hoà") == "hoà"
    assert norm("Hoà", languages=["en", "vi"]) == norm("Hoà", languages=["vi", "en"])
    assert norm("Hoà", languages=["en", "vi"]) == norm("Hoà", languages=["vi"]) == "hòa"


def test_rules_run_in_language_order(monkeypatch):
    # Two rules that do not commute; a set of languages has no stable order.
    rules = {"aa": lambda s: s + "a", "bb": lambda s: s + "b"}
    monkeypatch.setattr("tenetrag.engine.text.LANGUAGE_RULES", rules)
    assert norm("x", languages={"bb", "aa"}) == norm("x", languages=["bb", "aa"]) == "xab"


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


@pytest.mark.parametrize("languages", [(), ("vi",)])
def test_idempotent(languages):
    names = corpus_names()
    assert len(names) > 50
    for text in [*EXAMPLES, *names]:
        once = norm(text, languages=languages)
        assert norm(once, languages=languages) == once, text


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
    assert "tenetrag.engine.text.vi" in loaded
    assert sorted(loaded & forbidden_tenetrag) == []
    assert sorted({name.partition(".")[0] for name in loaded} & drivers) == []
