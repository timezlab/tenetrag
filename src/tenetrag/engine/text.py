"""Text normalization for matching (contracts/text.md, research R18).

Standard library only. The stores never call `norm`: they receive the
normalized fields already computed (FR-004).
"""

from __future__ import annotations

import re
import unicodedata

# The old tone-mark placement in the endings oa, oe and uy, mapped to the new
# one (data-model §11). Engine brief §7 names the rule by example only.
_TONE_MARKS = {
    "oà": "òa",
    "oá": "óa",
    "oả": "ỏa",
    "oã": "õa",
    "oạ": "ọa",
    "oè": "òe",
    "oé": "óe",
    "oẻ": "ỏe",
    "oẽ": "õe",
    "oẹ": "ọe",
    "uỳ": "ùy",
    "uý": "úy",
    "uỷ": "ủy",
    "uỹ": "ũy",
    "uỵ": "ụy",
}

# An ending of the table that no letter follows, so hoàng and khuỷu keep their
# marks; uy after q is a different syllable shape, so quý keeps its mark too.
_ENDING = re.compile(r"(?:o[àáảãạèéẻẽẹ]|(?<!q)u[ỳýỷỹỵ])(?![^\W\d_])")


def norm(text: str) -> str:
    """Return the form of `text` that name, alias and full-text matching compare.

    NFC, casefolded, the tone mark of an oa, oe or uy ending on its first
    vowel (hoà → hòa), and single spaces. Diacritics and đ are kept, so lãi,
    lại and lai stay apart (engine brief §7). Casefolding before the table
    lets the table hold lower case only; the result is the contract's, since
    casefolding keeps each mark on its letter. The second NFC recomposes the
    few letters that casefolding decomposes.
    """
    folded = unicodedata.normalize("NFC", unicodedata.normalize("NFC", text).casefold())
    moved = _ENDING.sub(lambda match: _TONE_MARKS[match.group()], folded)
    return " ".join(moved.split())
