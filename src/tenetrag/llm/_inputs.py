"""The embedding input rule of the real and fake models (contracts/llm.md, request rule 1)."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from tenetrag.protocols.errors import UnsupportedRequestError

_LISTED_POSITIONS = 10


def refuse_unusable_texts(
    texts: Sequence[str],
    *,
    prefix: str,
    max_input_tokens: int,
    count_tokens: Callable[[str], int | None],
) -> None:
    """Refuse empty texts, and texts over the limit when the count is known, by position."""
    empty = [index for index, text in enumerate(texts) if not text.strip()]
    if empty:
        raise UnsupportedRequestError(
            f"The texts at positions {_positions(empty)} are empty. Remove them before embedding."
        )
    too_long = []
    for index, text in enumerate(texts):
        tokens = count_tokens(prefix + text)
        if tokens is not None and tokens > max_input_tokens:
            too_long.append(index)
    if too_long:
        raise UnsupportedRequestError(
            f"The texts at positions {_positions(too_long)} are longer than the "
            f"{max_input_tokens}-token input limit. Split them before embedding."
        )


def _positions(indexes: list[int]) -> str:
    listed = ", ".join(str(index) for index in indexes[:_LISTED_POSITIONS])
    hidden = len(indexes) - _LISTED_POSITIONS
    return f"{listed} and {hidden} more" if hidden > 0 else listed
