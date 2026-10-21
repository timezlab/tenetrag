"""Full text on chunks (protocols.md §3, research R6), case `tone-mark-matching` (full text).

Queries pass through `norm` as the engine's would. The suite compares hit
sets only, never search_text scores or order (contract-suite.md §3).
"""

from __future__ import annotations

from tenetrag.engine.text import norm
from tests.support.contract.backends import ContractStores
from tests.support.contract.generated import tone_mark_writes
from tests.support.contract.writes import LANGUAGES, write_all

K = 10


def _chunk_ids(stores: ContractStores) -> dict[str, str]:
    """Paragraph text -> chunk id, after writing D904."""
    [write] = tone_mark_writes()
    write_all(stores, [write])
    return {chunk.text: chunk.chunk_id for chunk in write.chunks}


def _found(stores: ContractStores, query: str) -> set[str]:
    hits = stores.vectors.search_text("chunks", norm(query, languages=LANGUAGES), K, None)
    return {hit.id for hit in hits}


def test_diacritics_not_folded(stores: ContractStores) -> None:
    chunk = _chunk_ids(stores)

    assert _found(stores, "lãi") == {chunk["Xóm Lãi: lãi suất cho vay."]}
    assert _found(stores, "lại") == {chunk["Xóm Lại: quay lại sau."]}
    assert _found(stores, "lai") == {chunk["Xóm Lai: lai lịch nhân viên."]}


def test_tone_mark_placement_matches(stores: ContractStores) -> None:
    chunk = _chunk_ids(stores)

    assert _found(stores, "Hoà") == {chunk["Người liên hệ: Lê Thị Hoà."]}
    assert _found(stores, "hòa") == {chunk["Người liên hệ: Lê Thị Hoà."]}
    assert _found(stores, "THUỶ") == {chunk["Người phụ trách: Phạm Văn Thuỷ."]}
    assert _found(stores, "thủy") == {chunk["Người phụ trách: Phạm Văn Thuỷ."]}


def test_figures_and_joined_words(stores: ContractStores) -> None:
    allowance = _chunk_ids(stores)["Phụ cấp 2.500.000 vnd/ngày cho phòng-ban và đơn vị."]

    assert _found(stores, "2.500.000") == {allowance}
    assert _found(stores, "vnd/ngày") == {allowance}
    assert _found(stores, "phòng-ban") == {allowance}
    # A figure is one token: part of it matches nothing.
    assert _found(stores, "500") == set()


def test_any_syllable_matches(stores: ContractStores) -> None:
    chunk = _chunk_ids(stores)

    assert _found(stores, "quay tàu điện") == {chunk["Xóm Lại: quay lại sau."]}
    assert _found(stores, "xóm") == {
        chunk["Xóm Lãi: lãi suất cho vay."],
        chunk["Xóm Lại: quay lại sau."],
        chunk["Xóm Lai: lai lịch nhân viên."],
    }


def test_query_syntax_is_plain_text(stores: ContractStores) -> None:
    chunk = _chunk_ids(stores)

    assert _found(stores, "a & b | c:* !d") == {chunk["Mục a, b, c và d của phụ lục."]}
    assert _found(stores, "o'neil") == set()
    assert _found(stores, "'") == set()
    assert _found(stores, "...") == set()
    assert _found(stores, "") == set()
