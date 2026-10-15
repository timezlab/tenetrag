"""The packs shipped inside tenetrag.packs (FR-015 to FR-018, research R10).

Behaviours:
1. shipped_packs() lists core 1 and enterprise-docs 1, sorted by name.
2. Each shipped pack loads with no error, no warning and no glossary.
3. The drafts of the shipped packs are gone from docs/product/packs/.
"""

import pytest

from tenetrag.packs import PackInfo, ShippedPack, load_pack, shipped_packs
from tests.support.packs import REPO_ROOT


def test_shipped_listed():
    assert shipped_packs() == (ShippedPack("core", 1), ShippedPack("enterprise-docs", 1))


@pytest.mark.parametrize("name", ["core", "enterprise-docs"])
def test_shipped_load_clean(name):
    stack = load_pack(name)
    assert (stack.name, stack.version) == (name, 1)
    assert stack.packs[-1] == PackInfo(name=name, version=1, source="shipped")
    assert stack.warnings == ()
    assert stack.glossary == ()


def test_no_draft_copies():
    drafts = REPO_ROOT / "docs" / "product" / "packs"
    assert sorted(path.name for path in drafts.glob("*.yaml")) == ["finance.yaml"]
