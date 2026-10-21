"""pg_trgm's trigrams and similarity, for name search off Postgres (research R10).

Standard library only. The reference store and the Neo4j store rank name
candidates with these, so their candidates equal what Postgres's
`similarity()` gives (FR-021).
"""

from __future__ import annotations

import re

# pg_trgm splits words on anything that is not a letter or a digit.
_WORD = re.compile(r"[^\W_]+")


def trigrams(text: str) -> frozenset[str]:
    """Return pg_trgm's trigrams: each word lower-cased and padded as "  " + word + " "."""
    found: set[str] = set()
    for word in _WORD.findall(text.lower()):
        padded = f"  {word} "
        found.update(padded[start : start + 3] for start in range(len(padded) - 2))
    return frozenset(found)


def similarity(a: str, b: str) -> float:
    """Return pg_trgm's similarity: the trigrams both texts share over all of theirs."""
    first, second = trigrams(a), trigrams(b)
    union = first | second
    if not union:
        return 0.0
    return len(first & second) / len(union)


def trigram_tokens(text: str) -> str:
    """Return the trigrams sorted and space-separated, with their inner spaces written "_".

    The Neo4j `trigrams` property, indexed with the whitespace analyzer. Words
    hold no "_", so the token maps back to one trigram.
    """
    return " ".join(sorted(trigram.replace(" ", "_") for trigram in trigrams(text)))
