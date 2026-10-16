"""Blocks to Markdown (contracts/corpus.md): the text a document's quotes are checked against."""

from __future__ import annotations

import unicodedata

from tests.support.corpus.facts import Document, Heading, ListBlock, Paragraph, TableBlock


def _row(cells: list[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def render(document: Document) -> str:
    """The document as Markdown: NFC, LF line endings, one blank line between blocks."""
    parts = []
    for block in document.blocks:
        if isinstance(block, Heading):
            parts.append(f"{'#' * block.level} {block.heading}")
        elif isinstance(block, Paragraph):
            parts.append(block.paragraph)
        elif isinstance(block, ListBlock):
            parts.append("\n".join(f"- {entry}" for entry in block.entries))
        elif isinstance(block, TableBlock):
            table = block.table
            lines = [_row(table.header), _row(["---"] * len(table.header))]
            lines += [_row(row) for row in table.rows]
            parts.append("\n".join(lines))
    return unicodedata.normalize("NFC", "\n\n".join(parts) + "\n")
