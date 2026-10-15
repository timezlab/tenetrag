"""One pack file's format (data-model §2, research R2).

Behaviours:
1. A tag that would build an object fails with file.yaml, and nothing is built.
2. Text written in NFD loads equal to its NFC form.
3. A secret-shaped value never appears in the error: beside a YAML syntax
   error, in an unknown field's value, or in an invalid value.
4. Each name follows its pattern; a bad one fails with file.bad-name at its path.
5. An entity attribute `scope`, an event role or attribute `time`, and a fact
   role or attribute `issuer` fail with file.reserved-name; a fact attribute
   `scope` loads.
6. A field the format lacks fails with file.unknown-field at its path.
7. Every field of the format loads, including the four it only stores.
8. Types are strict: a wrong type, or a value outside its choices or range,
   fails with file.invalid-value at its dotted path, `[n]` for a list item.
9. `pack` and `version` are required.
10. file.duplicate-key names the mapping and both lines.
"""

import dataclasses
import unicodedata

import pytest

from tenetrag.packs import (
    CompetencyQuestion,
    GlossaryEntry,
    Key,
    Mode,
    NameRule,
    Retrieval,
    load_pack,
)
from tenetrag.protocols.errors import ConfigError
from tests.support.packs import BUILT, problem_lines, write_pack
from tests.support.secrets import PLANTED, assert_exception_clean

HEADER = "pack: user\nversion: 1\nextends: core\n"


def load(directory, text):
    write_pack(directory, "pack.yaml", text)
    return load_pack("pack.yaml", base_dir=directory)


def failing(directory, text):
    with pytest.raises(ConfigError) as caught:
        load(directory, text)
    return caught.value


@pytest.fixture
def _clear_built():
    BUILT.clear()
    yield
    BUILT.clear()


@pytest.mark.usefixtures("_clear_built")
def test_yaml_tag_refused(tmp_path):
    error = failing(
        tmp_path,
        HEADER
        + "entities:\n"
        + "  Vendor:\n"
        + "    description: !!python/object:tests.support.packs.Tripwire {}\n",
    )
    assert problem_lines(error) == [("pack.yaml", "", "file.yaml")]
    assert BUILT == []


def test_nfc(tmp_path):
    composed = "Nhà cung cấp hàng hoá cho đơn vị"
    decomposed = unicodedata.normalize("NFD", composed)
    assert decomposed != composed
    template = (
        HEADER
        + "entities:\n"
        + "  Vendor:\n"
        + "    description: {text}\n"
        + "    examples: [{text}]\n"
        + "glossary:\n"
        + "  - {{name: {text}, type: Vendor, aliases: [{text} Co], note: {text}}}\n"
        + "competency_questions:\n"
        + "  - {{id: user-1, text: {text}?, needs: [Vendor]}}\n"
    )
    from_nfc = load(tmp_path / "nfc", template.format(text=composed))
    from_nfd = load(tmp_path / "nfd", template.format(text=decomposed))
    # The two files differ only in their paths, which `packs` records.
    assert dataclasses.replace(from_nfd, packs=from_nfc.packs) == from_nfc
    assert from_nfd.entities["Vendor"].description == composed


@pytest.mark.parametrize(
    ("body", "rule"),
    [
        (
            f"entities:\n  Vendor:\n    description: {PLANTED[1]}: extra\n",
            "file.yaml",
        ),
        (
            f"entities:\n  Vendor:\n    description: A supplier.\n    api_key: {PLANTED[0]}\n",
            "file.unknown-field",
        ),
        (
            f"entities:\n  Vendor:\n    description: A supplier.\n"
            f"    attributes:\n      code: {{range: {PLANTED[3]}}}\n",
            "file.invalid-value",
        ),
        (
            f"entities:\n  Vendor:\n    description: A supplier.\n"
            f"    attributes:\n      code: {{range: str, compare: {PLANTED[4]}}}\n",
            "file.invalid-value",
        ),
    ],
    ids=["yaml-syntax", "unknown-field", "invalid-range", "invalid-choice"],
)
def test_text_never_echoed(tmp_path, body, rule):
    error = failing(tmp_path, HEADER + body)
    assert [line[2] for line in problem_lines(error)] == [rule]
    assert_exception_clean(error)


def test_invalid_version_never_echoed(tmp_path):
    error = failing(tmp_path, f"pack: user\nversion: {PLANTED[2]}\nextends: core\n")
    assert problem_lines(error) == [("pack.yaml", "version", "file.invalid-value")]
    assert_exception_clean(error)


DESCRIBED = "    description: A thing the text names.\n"

# (template with NAME, the path a bad name is reported at, good names, bad names)
NAME_CASES = {
    "pack": (
        "pack: NAME\nversion: 1\nextends: core\n",
        "pack",
        ["vendors", "alpha-ops", "a1-b2"],
        ["Vendors", "alpha_ops", "alpha--ops", "-alpha", "alpha-", "1alpha", "đơn-vị"],
    ),
    "entity": (
        HEADER + "entities:\n  NAME:\n" + DESCRIBED,
        "entities.NAME",
        ["Vendor", "VendorDesk", "V2"],
        ["vendor", "Vendor_Desk", "Vendor-Desk", "2Vendor", "Đơn"],
    ),
    "event": (
        HEADER + "events:\n  NAME:\n" + DESCRIBED + "    time: point\n",
        "events.NAME",
        ["Audit", "SiteVisit"],
        ["audit", "Site_Visit"],
    ),
    "fact": (
        HEADER + "facts:\n  NAME:\n" + DESCRIBED,
        "facts.NAME",
        ["Supply", "SlaTarget"],
        ["supply", "Sla-Target"],
    ),
    "enum": (
        HEADER + "enums:\n  NAME: [gold]\n",
        "enums.NAME",
        ["Tier", "DeskTier"],
        ["tier", "DESK_TIER"],
    ),
    "relation": (
        HEADER + "relations:\n  NAME: {from: [Person], to: [Organization], time: interval}\n",
        "relations.NAME",
        ["SUPPLIES", "REPORTS_TO", "HAS_2FA"],
        ["supplies", "Reports_To", "REPORTS__TO", "_REPORTS", "REPORTS_", "2FA"],
    ),
    "attribute": (
        HEADER
        + "entities:\n  Vendor:\n"
        + DESCRIBED
        + "    attributes:\n      NAME: {range: str}\n",
        "entities.Vendor.attributes.NAME",
        ["tax_code", "code2", "a"],
        ["taxCode", "Tax_code", "tax__code", "_tax", "tax_", "2tax", "mã_số"],
    ),
    "role": (
        HEADER + "facts:\n  Supply:\n" + DESCRIBED + "    roles: {NAME: [Organization]}\n",
        "facts.Supply.roles.NAME",
        ["supplier", "made_in"],
        ["Supplier", "made-in"],
    ),
    "enum-value": (
        HEADER + "enums:\n  Tier: [NAME]\n",
        "enums.Tier[0]",
        ["gold", "very_high"],
        ["Gold", "very-high"],
    ),
    "question-id": (
        HEADER
        + "competency_questions:\n"
        + "  - {id: NAME, text: Which organizations exist?, needs: [Organization]}\n",
        "competency_questions[0].id",
        ["user-1", "q2"],
        ["User-1", "user_1"],
    ),
}


@pytest.mark.parametrize(
    ("kind", "name"),
    [(kind, name) for kind, case in NAME_CASES.items() for name in case[2]],
)
def test_good_name_loads(tmp_path, kind, name):
    template = NAME_CASES[kind][0]
    load(tmp_path, template.replace("NAME", name))


@pytest.mark.parametrize(
    ("kind", "name"),
    [(kind, name) for kind, case in NAME_CASES.items() for name in case[3]],
)
def test_bad_name_fails(tmp_path, kind, name):
    template, path = NAME_CASES[kind][:2]
    error = failing(tmp_path, template.replace("NAME", name))
    assert problem_lines(error) == [("pack.yaml", path.replace("NAME", name), "file.bad-name")]


@pytest.mark.parametrize(
    ("body", "path"),
    [
        (
            "entities:\n  Vendor:\n" + DESCRIBED + "    attributes:\n      scope: {range: str}\n",
            "entities.Vendor.attributes.scope",
        ),
        (
            "events:\n  Audit:\n" + DESCRIBED + "    time: point\n    roles: {time: [Person]}\n",
            "events.Audit.roles.time",
        ),
        (
            "events:\n  Audit:\n"
            + DESCRIBED
            + "    time: point\n    attributes: {time: {range: date}}\n",
            "events.Audit.attributes.time",
        ),
        (
            "facts:\n  Supply:\n" + DESCRIBED + "    roles: {issuer: [Organization]}\n",
            "facts.Supply.roles.issuer",
        ),
        (
            "facts:\n  Supply:\n" + DESCRIBED + "    attributes: {issuer: {range: str}}\n",
            "facts.Supply.attributes.issuer",
        ),
    ],
    ids=[
        "entity-scope",
        "event-role-time",
        "event-attribute-time",
        "fact-role-issuer",
        "fact-attribute-issuer",
    ],
)
def test_reserved_word_fails(tmp_path, body, path):
    error = failing(tmp_path, HEADER + body)
    assert problem_lines(error) == [("pack.yaml", path, "file.reserved-name")]


def test_fact_attribute_scope_loads(tmp_path):
    stack = load(
        tmp_path,
        HEADER + "facts:\n  Supply:\n" + DESCRIBED + "    attributes: {scope: {range: str}}\n",
    )
    assert "scope" in stack.facts["Supply"].attributes
    assert "scope" in stack.facts["Definition"].attributes


@pytest.mark.parametrize(
    ("body", "path"),
    [
        (
            "entities:\n  Vendor:\n"
            + DESCRIBED
            + "    attributes: {tax_code: {range: str}}\n    vetos: [tax_code]\n",
            "entities.Vendor.vetos",
        ),
        ("entitys:\n  Vendor:\n" + DESCRIBED, "entitys"),
        (
            "entities:\n  Vendor:\n" + DESCRIBED + "    attributes: {code: {ranges: str}}\n",
            "entities.Vendor.attributes.code.ranges",
        ),
        (
            "relations:\n  SUPPLIES: {from: [Person], to: [Organization], time: interval, "
            "where: {object: {category: [unit]}}}\n",
            "relations.SUPPLIES.where.object",
        ),
        (
            "competency_questions:\n"
            "  - {id: user-1, text: Which organizations exist?, needs: [Organization], "
            "answer: none}\n",
            "competency_questions[0].answer",
        ),
    ],
    ids=["vetos", "top-level", "attribute", "where", "question"],
)
def test_unknown_field_fails(tmp_path, body, path):
    error = failing(tmp_path, HEADER + body)
    assert problem_lines(error) == [("pack.yaml", path, "file.unknown-field")]


EVERY_FIELD = """\
pack: every-field
version: 3
extends: [core]
mode: discovery
entities:
  Desk:
    description: A named service desk inside an organization.
    examples: [IT Help Desk]
    aliases: [service desk]
    attributes:
      code: {range: str, compare: code, unique: self_scoped, description: The desk's code.}
      opened_on: {range: date, required: true}
      closed_on: {range: date}
      phones: {range: str, multivalued: true}
      budget: {range: money, unit: VND}
      tier: {range: DeskTier}
    scope: {role: parent, to: [Organization], inherit: document, when: {tier: [gold]}}
    identity: [[scope, code], {key: [scope, tier], during: [opened_on, closed_on]}]
    vetoes: [code]
    names: evidence
    corroborate: [PART_OF]
    version_start: [opened_on]
    document_link: [code]
    required: [code]
    extract: true
    agent_visible: true
    exact_mappings: ["schema:Organization"]
    deprecated: false
    renamed_from: HelpDesk
relations:
  STAFFS:
    description: A person who works at a desk.
    from: [Person]
    to: [Desk]
    where: {to: {tier: [gold]}}
    time: interval
    attributes: {shift: {range: str}}
    value: percentage
    cardinality: {one_at_a_time: [subject]}
    required: [shift]
    extract: true
    exact_mappings: ["org:memberOf"]
    deprecated: true
    renamed_from: WORKS_AT
events:
  Outage:
    description: A period when a desk could not take requests.
    examples: [the March outage]
    aliases: [downtime]
    is_a: Event
    roles: {desk: [Desk], reported_by: [Person]}
    attributes: {cause: {range: str}}
    time: point
    identity: [[time, desk]]
    required: [desk]
    extract: true
    agent_visible: true
    exact_mappings: ["schema:Event"]
    deprecated: false
    renamed_from: Downtime
facts:
  SlaTarget:
    description: A response time that a desk commits to.
    examples: [four hours]
    aliases: [service level]
    roles: {desk: [Desk]}
    attributes: {hours: {range: int}}
    time: point
    required: [desk, hours]
    version_key: [issuer, desk]
    extract: false
    agent_visible: true
    exact_mappings: ["schema:Thing"]
    deprecated: false
    renamed_from: Sla
enums:
  DeskTier: [silver, gold]
  OrgCategory: [desk]
not_entities: [ticket_number]
retrieval: {hub_penalty: [Desk], max_hops: 3, context_relations: [STAFFS]}
glossary:
  - {name: Bàn hỗ trợ CNTT, type: Desk, aliases: [IT desk], note: The main help desk.}
competency_questions:
  - {id: every-field-1, text: "Which desks did person P staff in year Y?", needs: [Desk, STAFFS]}
"""


def test_every_field_loads(tmp_path):
    stack = load(tmp_path, EVERY_FIELD)
    assert (stack.name, stack.version, stack.mode) == ("every-field", 3, Mode.DISCOVERY)
    assert stack.warnings == ()

    desk = stack.entities["Desk"]
    assert (desk.examples, desk.aliases) == (("IT Help Desk",), ("service desk",))
    code = desk.attributes["code"]
    assert (code.range, code.compare, code.unique) == ("str", "code", "self_scoped")
    assert code.description == "The desk's code."
    assert desk.attributes["phones"].multivalued is True
    assert desk.attributes["budget"].unit == "VND"
    assert desk.attributes["tier"].range == "DeskTier"
    assert (desk.scope.role, desk.scope.to, desk.scope.inherit) == (
        "parent",
        ("Organization",),
        "document",
    )
    assert dict(desk.scope.when) == {"tier": ("gold",)}
    assert desk.identity == (
        Key(("scope", "code")),
        Key(("scope", "tier"), during=("opened_on", "closed_on")),
    )
    assert desk.vetoes == ("code",)
    assert desk.names is NameRule.EVIDENCE
    assert desk.corroborate == ("PART_OF",)
    assert desk.version_start == ("opened_on",)
    assert desk.document_link == ("code",)
    assert desk.required == ("code", "opened_on")
    assert (desk.extract, desk.agent_visible, desk.deprecated) == (True, True, False)
    assert desk.exact_mappings == ("schema:Organization",)
    assert desk.renamed_from == "HelpDesk"

    staffs = stack.relations["STAFFS"]
    assert staffs.description == "A person who works at a desk."
    assert (staffs.from_types, staffs.to_types) == (("Person",), ("Desk",))
    assert {end: dict(values) for end, values in staffs.where.items()} == {
        "to": {"tier": ("gold",)}
    }
    assert (staffs.time, staffs.value, staffs.cardinality) == (
        "interval",
        "percentage",
        ("subject",),
    )
    assert staffs.attributes["shift"].range == "str"
    assert staffs.required == ("shift",)
    assert (staffs.extract, staffs.deprecated, staffs.renamed_from) == (True, True, "WORKS_AT")
    assert staffs.exact_mappings == ("org:memberOf",)

    outage = stack.events["Outage"]
    assert (outage.is_a, outage.time) == ("Event", "point")
    assert (outage.examples, outage.aliases) == (("the March outage",), ("downtime",))
    assert set(outage.roles) == {"desk", "reported_by", "participant", "location"}
    assert set(outage.attributes) == {"cause", "title"}
    assert outage.identity == (Key(("desk", "time")),)
    assert outage.required == ("desk",)
    assert (outage.agent_visible, outage.renamed_from) == (True, "Downtime")
    assert outage.exact_mappings == ("schema:Event",)

    sla = stack.facts["SlaTarget"]
    assert (sla.time, sla.extract, sla.agent_visible) == ("point", False, True)
    assert sla.roles["desk"] == ("Desk",)
    assert sla.attributes["hours"].range == "int"
    assert sla.required == ("desk", "hours")
    assert sla.version_key == ("desk", "issuer")
    assert (sla.examples, sla.aliases, sla.renamed_from) == (
        ("four hours",),
        ("service level",),
        "Sla",
    )

    assert stack.enums["DeskTier"] == ("gold", "silver")
    assert "desk" in stack.enums["OrgCategory"]
    assert "ticket_number" in stack.not_entities
    assert stack.retrieval == Retrieval(
        hub_penalty=("Desk",), max_hops=3, context_relations=("STAFFS",)
    )
    assert stack.glossary == (
        GlossaryEntry(
            name="Bàn hỗ trợ CNTT", type="Desk", aliases=("IT desk",), note="The main help desk."
        ),
    )
    assert stack.competency_questions[-1] == CompetencyQuestion(
        id="every-field-1",
        text="Which desks did person P staff in year Y?",
        needs=("Desk", "STAFFS"),
    )


@pytest.mark.parametrize("version", ['"1"', "0", "-1", "1.0", "true"])
def test_version_is_a_positive_int(tmp_path, version):
    error = failing(tmp_path, f"pack: user\nversion: {version}\nextends: core\n")
    assert problem_lines(error) == [("pack.yaml", "version", "file.invalid-value")]


@pytest.mark.parametrize(
    ("body", "path"),
    [
        ("mode: lenient\n", "mode"),
        ("retrieval: {max_hops: 0}\n", "retrieval.max_hops"),
        ("not_entities: ticket_number\n", "not_entities"),
        ("entities:\n  Vendor:\n    description: 5\n", "entities.Vendor.description"),
        ("entities:\n  Vendor:\n    description: ''\n", "entities.Vendor.description"),
        (
            "entities:\n  Vendor:\n" + DESCRIBED + "    examples: [Gamma, 5]\n",
            "entities.Vendor.examples[1]",
        ),
        (
            "entities:\n  Vendor:\n" + DESCRIBED + "    names: fuzzy\n",
            "entities.Vendor.names",
        ),
        (
            "entities:\n  Vendor:\n"
            + DESCRIBED
            + "    attributes: {code: {range: str, compare: fuzzy}}\n",
            "entities.Vendor.attributes.code.compare",
        ),
        (
            "entities:\n  Vendor:\n"
            + DESCRIBED
            + "    attributes: {code: {range: str, required: 'yes'}}\n",
            "entities.Vendor.attributes.code.required",
        ),
        (
            "entities:\n  Vendor:\n" + DESCRIBED + "    attributes: {code: {range: string}}\n",
            "entities.Vendor.attributes.code.range",
        ),
        (
            "entities:\n  Vendor:\n" + DESCRIBED + "    attributes: {code: {unique: global}}\n",
            "entities.Vendor.attributes.code.range",
        ),
        (
            "entities:\n  Vendor:\n"
            + DESCRIBED
            + "    attributes: {code: {range: str}}\n    identity: [[code], 5]\n",
            "entities.Vendor.identity[1]",
        ),
        (
            "entities:\n  Vendor:\n"
            + DESCRIBED
            + "    attributes: {code: {range: str}, opened_on: {range: date}}\n"
            + "    identity: [{key: [code], during: [opened_on]}]\n",
            "entities.Vendor.identity[0].during",
        ),
        (
            "entities:\n  Vendor:\n" + DESCRIBED + "    scope: {to: [Organization]}\n",
            "entities.Vendor.scope.role",
        ),
        (
            "relations:\n  SUPPLIES: {from: [Person], to: [Organization], time: always}\n",
            "relations.SUPPLIES.time",
        ),
        (
            "relations:\n  SUPPLIES: {from: [Person], to: [Organization]}\n",
            "relations.SUPPLIES.time",
        ),
        ("events:\n  Audit:\n" + DESCRIBED, "events.Audit.time"),
        (
            "competency_questions:\n  - {id: user-1, text: Which ones?, needs: []}\n",
            "competency_questions[0].needs",
        ),
        (
            "competency_questions:\n  - {id: user-1, needs: [Person]}\n",
            "competency_questions[0].text",
        ),
        ("glossary:\n  - {name: Alpha}\n", "glossary[0].type"),
    ],
    ids=[
        "mode",
        "max-hops",
        "not-entities-scalar",
        "description-int",
        "description-empty",
        "example-int",
        "names",
        "compare",
        "required-str",
        "range-unknown-builtin",
        "new-attribute-no-range",
        "identity-key-int",
        "during-one-date",
        "new-scope-no-role",
        "time-choice",
        "new-relation-no-time",
        "root-event-no-time",
        "needs-empty",
        "question-no-text",
        "glossary-no-type",
    ],
)
def test_invalid_value_fails_at_its_path(tmp_path, body, path):
    error = failing(tmp_path, HEADER + body)
    assert problem_lines(error) == [("pack.yaml", path, "file.invalid-value")]


@pytest.mark.parametrize(
    ("text", "path"),
    [("version: 1\nextends: core\n", "pack"), ("pack: user\nextends: core\n", "version")],
)
def test_pack_and_version_required(tmp_path, text, path):
    error = failing(tmp_path, text)
    assert problem_lines(error) == [("pack.yaml", path, "file.invalid-value")]


def test_duplicate_key_names_both_lines(tmp_path):
    error = failing(
        tmp_path,
        HEADER
        + "entities:\n"
        + "  Vendor:\n"
        + "    description: A company that supplies goods or services.\n"
        + "  Vendor:\n"
        + "    description: A company that supplies goods or services.\n",
    )
    assert str(error) == (
        "The pack stack has 1 problem:\n"
        "  - pack.yaml: entities: `Vendor` appears twice, at line 7 (first at line 5)"
        " [file.duplicate-key]"
    )
