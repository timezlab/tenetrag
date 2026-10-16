"""The packs shipped inside tenetrag.packs (FR-015 to FR-018, research R10).

Behaviours:
1. shipped_packs() lists core 1 and enterprise-docs 1, sorted by name.
2. Each shipped pack loads with no error, no warning and no glossary.
3. The drafts of the shipped packs are gone from docs/product/packs/.
4. core keeps only the identity and time rules that hold in every domain,
   since a child pack cannot undo them (ADR 0023); enterprise-docs scopes
   people by employer and meetings by chair and title.
5. Each shipped file's hash equals the pin of its (name, version), so a
   changed file needs a new version (FR-016, US2-7).
6. The finance draft stacks and compiles alone on core and on
   enterprise-docs (FR-019).
"""

import pytest

from tenetrag.packs import Key, Scope, ShippedPack, compile_schema, load_pack, shipped_packs
from tests.support.packs import FINANCE_DRAFT, PACK_FIXTURES, REPO_ROOT

# The file hash of each shipped (name, version), data-model §5. Pins are only
# ever added: a changed file gets a new version and a new pin, so a stamp
# names one pack content for good.
PINS = {
    ("core", 1): "sha256:pending",
    ("enterprise-docs", 1): "sha256:pending",
}


def test_shipped_listed():
    assert shipped_packs() == (ShippedPack("core", 1), ShippedPack("enterprise-docs", 1))


@pytest.mark.parametrize("name", ["core", "enterprise-docs"])
def test_shipped_load_clean(name):
    stack = load_pack(name)
    assert (stack.name, stack.version) == (name, 1)
    top = stack.packs[-1]
    assert (top.name, top.version, top.source) == (name, 1, "shipped")
    assert stack.warnings == ()
    assert stack.glossary == ()


def test_core_rules_hold_in_every_domain():
    core = load_pack("core")
    person = core.entities["Person"]
    # An employer changes over a life, so it cannot be a scope that blocks a merge.
    assert person.scope is None
    assert person.vetoes == ("born_on",)
    assert core.entities["Product"].scope.to == ("Organization", "Person")
    assert core.relations["OFFERS"].from_types == ("Organization", "Person")
    # Many events share a date and a title, such as two companies' AGMs.
    assert core.events["Event"].identity == ()
    assert core.facts["Statement"].time == "point"
    # A child pack cannot add a description or examples to an inherited type.
    assert [name for name, relation in core.relations.items() if not relation.description] == []
    assert [name for name, entity in core.entities.items() if not entity.examples] == []


def test_enterprise_docs_scopes_people_and_meetings():
    stack = load_pack("enterprise-docs")
    assert stack.entities["Person"].scope == Scope(
        role="employer", to=("Organization",), inherit="document", when={}
    )
    assert stack.events["Meeting"].identity == (Key(("chair", "time", "title")),)


def test_no_draft_copies():
    drafts = REPO_ROOT / "docs" / "product" / "packs"
    assert sorted(path.name for path in drafts.glob("*.yaml")) == ["finance.yaml"]


@pytest.mark.parametrize("name", ["core", "enterprise-docs"])
def test_shipped_pins(name):
    top = load_pack(name).packs[-1]
    pin = PINS.get((name, top.version))
    assert top.file_hash == pin, (
        f"src/tenetrag/packs/shipped/{name}.yaml changed without a new version: bump "
        f"`version` in it and add a pin for ({name!r}, {top.version + 1}) to PINS, "
        "keeping the old pins"
    )


@pytest.mark.parametrize(
    ("reference", "names"),
    [
        (FINANCE_DRAFT, ["core", "finance"]),
        (
            PACK_FIXTURES / "valid" / "shared-ancestor.yaml",
            ["core", "enterprise-docs", "finance", "shared-ancestor"],
        ),
    ],
    ids=["on-core", "on-enterprise-docs"],
)
def test_finance_draft_stacks(reference, names):
    stack = load_pack(reference)
    assert [info.name for info in stack.packs] == names
    assert stack.warnings == ()
    assert compile_schema(stack).property_count == 52
