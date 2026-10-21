"""Vietnamese rules for `norm`: tone-mark placement (research R18, ADR 0025).

The rule receives NFC, casefolded text, so its table holds lower case only.
"""

from __future__ import annotations

import re

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


def move_tone_marks(text: str) -> str:
    """Put the tone mark of an oa, oe or uy ending on its first vowel: hoà → hòa.

    Casefolding keeps each mark on its letter, so running this after
    casefolding gives what the table gives on the original case.
    """
    return _ENDING.sub(lambda match: _TONE_MARKS[match.group()], text)
