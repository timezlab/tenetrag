"""pg_trgm's trigrams and similarity in Python (contracts/stores.md §4.3, research R10).

The reference store and the Neo4j store rank name candidates with these, so
their candidate sets equal Postgres's (FR-021, SC-009).

Behaviours:
1. similarity equals pg_trgm on the eight pairs measured in research R10, to
   four places, in either order.
2. trigrams pads each word as pg_trgm does, and lowercases as pg_trgm does.
3. trigram_tokens writes each trigram as a token, inner spaces as "_".
4. A text with no word has no trigrams, and two such texts have similarity 0.0.
"""

import pytest

from tenetrag.storage._trigram import similarity, trigram_tokens, trigrams

# Measured with pg_trgm on the pinned pgvector pg17 image (research R10).
PG_TRGM = [
    ("ngân hàng phương đông", "ngân hàng phương nam", 0.6957),
    ("nguyễn văn hòa", "nguyễn văn hoà", 0.6667),
    ("lãi", "lai", 0.1429),
    ("lãi", "lại", 0.1429),
    ("a_b", "a b", 1.0),
    ("công ty số 12", "công ty số 21", 0.6471),
    ("đ/c hà", "đc hà", 0.4444),
    ("phòng-ban", "phòng ban", 1.0),
]


@pytest.mark.parametrize(("a", "b", "expected"), PG_TRGM)
def test_trigrams_match_pg_trgm(a, b, expected):
    assert round(similarity(a, b), 4) == expected
    assert similarity(b, a) == similarity(a, b)


def test_trigrams_padded_per_word():
    assert trigrams("lãi") == frozenset({"  l", " lã", "lãi", "ãi "})
    assert trigrams("a_b") == trigrams("a b") == frozenset({"  a", " a ", "  b", " b "})
    assert trigrams("LÃI") == trigrams("lãi")


def test_trigram_tokens():
    assert trigram_tokens("lãi") == "__l _lã lãi ãi_"


def test_no_word_no_trigrams():
    assert trigrams("") == frozenset()
    assert trigrams(" -/_ ") == frozenset()
    assert trigram_tokens("") == ""
    assert similarity("", "") == 0.0
    assert similarity("", "lãi") == 0.0
