"""Text normalization for matching (contracts/text.md, research R18, ADR 0025).

Standard library only. The shared steps hold for every language. A language
whose text needs more has its own module here, and `norm` runs its rule only
when the caller names that language, from the profile's `text_languages`.
The stores never call `norm`: they receive the normalized fields already
computed (FR-004).
"""

from __future__ import annotations

import unicodedata
from collections.abc import Callable, Collection, Mapping

from tenetrag.engine.text import vi

# One rule per language that needs more than the shared steps. Each takes NFC,
# casefolded text and returns NFC text. A language with no rule adds nothing.
LANGUAGE_RULES: Mapping[str, Callable[[str], str]] = {"vi": vi.move_tone_marks}


def norm(text: str, *, languages: Collection[str] = ()) -> str:
    """Return the form of `text` that name, alias and full-text matching compare.

    NFC, casefolded, then the rule of each named language that has one, then
    single spaces. Diacritics and đ are kept, so lãi, lại and lai stay apart
    (engine brief §7). Index and query text must name the same languages, or
    the two sides stop matching. The second NFC recomposes the few letters
    that casefolding decomposes.
    """
    folded = unicodedata.normalize("NFC", unicodedata.normalize("NFC", text).casefold())
    for language in sorted(languages):
        rule = LANGUAGE_RULES.get(language)
        if rule is not None:
            folded = rule(folded)
    return " ".join(folded.split())
