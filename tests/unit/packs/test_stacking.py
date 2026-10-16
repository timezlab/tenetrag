"""Stacking pack files into one read-only stack (data-model §3 and §4, research R3).

Behaviours:
1. enterprise-docs over core merges as data-model §4 shows for Person.
2. A user pack's new type, relation, enum value and question join the stack.
3. A change to an inherited range names the pack that set it and the file
   that changed it.
4. Two parents that add one identical attribute merge silently; two that
   differ fail with stack.parents-conflict, naming both.
5. An `extends` cycle fails with pack.cycle, listing the cycle.
6. A pack shared by two parents is applied once, in depth-first post-order.
7. The stack and every part of it are read-only.
8. `origins` maps each element path to the pack that added it.
9. Lists whose order means nothing are sorted; identity keys keep their
   order, a child's keys first.
10. Defaults are filled in after stacking.
11. `is_a` copies roles, attributes and time, not identity or required. A
    subtype may state its own time; an inherited type keeps its own.
12. `mode` is the top pack's, else the nearest ancestor's.
13. Restating an inherited value word for word merges, as does an enum value
    that two packs add.
14. A relative reference resolves against base_dir, else the working
    directory; an `extends` path against the file that holds it. A problem
    names a file by those relative paths.
15. A pack may add a whole scope to an inherited entity type that has none
    (ADR 0023).
"""

import dataclasses
import shutil

import pytest

from tenetrag.packs import Key, Mode, NameRule, Scope, load_pack
from tenetrag.protocols.errors import ConfigError
from tests.support.packs import PACK_FIXTURES, problem_lines, problem_messages, write_pack

VALID = PACK_FIXTURES / "valid"
BROKEN = PACK_FIXTURES / "broken"
HEADER = "pack: user\nversion: 1\nextends: core\n"


def load(directory, text):
    write_pack(directory, "pack.yaml", text)
    return load_pack("pack.yaml", base_dir=directory)


def failing(directory, text):
    with pytest.raises(ConfigError) as caught:
        load(directory, text)
    return caught.value


def test_enterprise_docs_merged():
    stack = load_pack("enterprise-docs")
    assert stack.entities["Organization"].scope.when["category"] == (
        "branch",
        "business_unit",
        "committee",
        "department",
        "team",
        "unit",
    )
    assert [key.attributes for key in stack.entities["Person"].identity] == [
        ("scope", "employee_id"),
        ("email",),
    ]


def test_person_merged_field_by_field():
    person = load_pack("enterprise-docs").entities["Person"]
    assert person.scope == Scope(role="employer", to=("Organization",), inherit="document", when={})
    assert person.identity == (Key(("scope", "employee_id")), Key(("email",)))
    assert person.vetoes == ("born_on", "employee_id")
    assert list(person.attributes) == ["born_on", "email", "employee_id"]
    assert person.attributes["employee_id"].compare == "upper"
    assert person.names is NameRule.EVIDENCE
    assert person.corroborate == ("HOLDS_POSITION", "MEMBER_OF")
    assert person.description == "A specific, named human being."


def test_user_pack_additions():
    stack = load_pack(VALID / "alpha-ops.yaml")
    assert [info.name for info in stack.packs] == ["core", "enterprise-docs", "alpha-ops"]
    core = stack.packs[0]
    assert (core.name, core.version, core.source) == ("core", 1, "shipped")
    assert stack.packs[-1].source == str((VALID / "alpha-ops.yaml").resolve())
    vendor = stack.entities["Vendor"]
    assert vendor.identity == (Key(("tax_code",)),)
    assert vendor.vetoes == ("tax_code",)
    assert stack.relations["SUPPLIES"].from_types == ("Vendor",)
    assert "vendor_desk" in stack.enums["OrgCategory"]
    assert stack.competency_questions[-1].id == "alpha-ops-1"
    assert [question.id for question in stack.competency_questions][:7] == [
        "core-1",
        "core-2",
        "core-3",
        "core-4",
        "core-5",
        "core-6",
        "ed-1",
    ]
    assert stack.warnings == ()


def test_conflict_names_both_packs(tmp_path):
    text = (VALID / "alpha-ops.yaml").read_text(encoding="utf-8")
    text = text.replace(
        "entities:\n", "entities:\n  Person:\n    attributes:\n      email: {range: int}\n", 1
    )
    write_pack(tmp_path, "alpha-ops.yaml", text)
    with pytest.raises(ConfigError) as caught:
        load_pack("alpha-ops.yaml", base_dir=tmp_path)
    assert problem_lines(caught.value) == [
        ("alpha-ops.yaml", "entities.Person.attributes.email.range", "stack.changed-range")
    ]
    assert "core" in problem_messages(caught.value)[0]


def test_parents_identical_merge():
    stack = load_pack(VALID / "two-parents" / "child.yaml")
    assert [info.name for info in stack.packs] == ["core", "left", "right", "child"]
    assert stack.entities["Organization"].attributes["tax_code"].range == "str"
    assert stack.origins["entities.Organization.attributes.tax_code"] == "left"
    assert stack.warnings == ()


def test_parents_conflict():
    with pytest.raises(ConfigError) as caught:
        load_pack("pack.yaml", base_dir=BROKEN / "stack.parents-conflict")
    assert problem_lines(caught.value) == [
        (
            "right.yaml",
            "entities.Organization.attributes.tax_code.range",
            "stack.parents-conflict",
        )
    ]
    assert "left" in problem_messages(caught.value)[0]


def test_cycle_named(tmp_path):
    write_pack(tmp_path, "a.yaml", "pack: a\nversion: 1\nextends: b.yaml\n")
    write_pack(tmp_path, "b.yaml", "pack: b\nversion: 1\nextends: a.yaml\n")
    with pytest.raises(ConfigError) as caught:
        load_pack("a.yaml", base_dir=tmp_path)
    assert problem_lines(caught.value) == [("b.yaml", "extends", "pack.cycle")]
    assert "a.yaml → b.yaml → a.yaml" in problem_messages(caught.value)[0]


def test_shared_ancestor_once():
    stack = load_pack(VALID / "shared-ancestor.yaml")
    assert [info.name for info in stack.packs] == [
        "core",
        "enterprise-docs",
        "finance",
        "shared-ancestor",
    ]


def test_stack_read_only():
    stack = load_pack("enterprise-docs")
    person = stack.entities["Person"]
    with pytest.raises(dataclasses.FrozenInstanceError):
        stack.name = "other"
    with pytest.raises(dataclasses.FrozenInstanceError):
        person.description = "other"
    with pytest.raises(TypeError):
        stack.entities["Vendor"] = person
    with pytest.raises(TypeError):
        person.attributes["code"] = person.attributes["email"]
    with pytest.raises(TypeError):
        stack.entities["Organization"].scope.when["category"] = ()
    with pytest.raises(TypeError):
        stack.relations["OWNER_OF"].where["to"] = {}
    with pytest.raises(TypeError):
        stack.origins["entities.Vendor"] = "user"
    assert isinstance(stack.enums["OrgCategory"], tuple)
    assert isinstance(stack.packs, tuple)
    assert isinstance(person.vetoes, tuple)


def test_origins_name_the_adding_pack():
    origins = load_pack(VALID / "alpha-ops.yaml").origins
    assert origins["entities.Person"] == "core"
    assert origins["entities.Person.identity[scope+employee_id]"] == "enterprise-docs"
    assert origins["entities.Person.identity[email]"] == "core"
    assert origins["entities.Person.vetoes[employee_id]"] == "enterprise-docs"
    assert origins["entities.Person.attributes.employee_id"] == "enterprise-docs"
    assert origins["entities.Organization.scope.inherit"] == "enterprise-docs"
    assert origins["entities.Organization.scope.when.category[unit]"] == "core"
    assert origins["entities.Organization.scope.when.category[branch]"] == "enterprise-docs"
    assert origins["relations.OWNER_OF.to[System]"] == "enterprise-docs"
    assert origins["enums.OrgCategory"] == "core"
    assert origins["enums.OrgCategory[branch]"] == "enterprise-docs"
    assert origins["enums.OrgCategory[vendor_desk]"] == "alpha-ops"
    assert origins["entities.Vendor"] == "alpha-ops"
    assert origins["relations.SUPPLIES"] == "alpha-ops"


def test_child_enum_value_sorted_into_place():
    values = load_pack(VALID / "alpha-ops.yaml").enums["OrgCategory"]
    assert values == tuple(sorted(values))
    assert {"company", "branch", "vendor_desk"} <= set(values)


def test_set_like_lists_are_sorted():
    stack = load_pack("enterprise-docs")
    assert stack.relations["OWNER_OF"].to_types == (
        "Metric",
        "Policy",
        "Procedure",
        "Product",
        "Project",
        "System",
    )
    assert stack.relations["MEMBER_OF"].from_types == ("Organization", "Person")
    assert stack.entities["Organization"].vetoes == ("established_on", "registration_id")
    assert stack.facts["ReportedFigure"].required == ("metric", "subject", "value")
    assert stack.not_entities == tuple(sorted(stack.not_entities))
    # version_start is tried in order, so it keeps the order written.
    assert stack.entities["Policy"].version_start == ("effective_from", "issued_on")


def test_attributes_and_retrieval_hints_are_sorted(tmp_path):
    stack = load(
        tmp_path,
        HEADER
        + "entities:\n  Person:\n    attributes: {birth_date: {range: date}}\n"
        + "retrieval:\n  hub_penalty: [Person, Organization, Place]\n"
        + "  context_relations: [MEMBER_OF, HOLDS_POSITION]\n",
    )
    names = list(stack.entities["Person"].attributes)
    assert names == sorted(names)
    assert names[0] == "birth_date"
    assert stack.retrieval.hub_penalty == ("Organization", "Person", "Place")
    assert stack.retrieval.context_relations == ("HOLDS_POSITION", "MEMBER_OF")


def test_reordered_vetoes_give_an_equal_stack(tmp_path):
    body = (
        "entities:\n  Desk:\n    description: A named service desk.\n"
        "    attributes: {code: {range: str}, opened_on: {range: date}}\n"
        "    vetoes: {vetoes}\n"
    )
    one = load(tmp_path / "one", HEADER + body.replace("{vetoes}", "[code, opened_on]"))
    two = load(tmp_path / "two", HEADER + body.replace("{vetoes}", "[opened_on, code]"))
    assert two.entities == one.entities


def test_child_identity_keys_come_first(tmp_path):
    stack = load(
        tmp_path,
        "pack: user\nversion: 1\nextends: enterprise-docs\n"
        "entities:\n  Person:\n    attributes: {badge: {range: str}}\n"
        "    identity: [[scope, badge], [email]]\n",
    )
    assert [key.attributes for key in stack.entities["Person"].identity] == [
        ("scope", "badge"),
        ("scope", "employee_id"),
        ("email",),
    ]


def test_defaults_filled_in(tmp_path):
    stack = load(
        tmp_path,
        HEADER
        + "entities:\n  Desk:\n    description: A named service desk.\n"
        + "    attributes: {code: {range: str}}\n"
        + "    scope: {role: parent, to: [Organization]}\n"
        + "  Kiosk:\n    description: A self-service kiosk.\n"
        + "facts:\n  Supply:\n    description: A supply of goods.\n"
        + "    roles: {supplier: [Organization]}\n",
    )
    desk = stack.entities["Desk"]
    code = desk.attributes["code"]
    assert (code.compare, code.unique, code.multivalued) == ("text", "scope", False)
    assert (code.unit, code.description) == (None, None)
    assert desk.names is NameRule.KEY
    assert desk.scope.inherit == "none"
    assert dict(desk.scope.when) == {}
    assert (desk.extract, desk.agent_visible, desk.deprecated) == (True, False, False)
    assert (desk.identity, desk.vetoes, desk.required) == ((), (), ())
    assert (desk.exact_mappings, desk.renamed_from) == ((), None)
    assert stack.entities["Kiosk"].scope is None
    supply = stack.facts["Supply"]
    assert (supply.time, supply.extract, supply.version_key) == ("interval", True, ())


def test_is_a_copies_roles_attributes_and_time(tmp_path):
    stack = load(
        tmp_path,
        "pack: user\nversion: 1\nextends: enterprise-docs\n"
        "events:\n  Audit:\n    is_a: Decision\n"
        "    description: A decision recorded at the end of an audit.\n"
        "    roles: {auditor: [Person]}\n",
    )
    audit = stack.events["Audit"]
    assert set(audit.roles) == {
        "auditor",
        "decided_by",
        "about",
        "made_in",
        "participant",
        "location",
    }
    assert set(audit.attributes) == {"status", "rationale", "title"}
    assert audit.time == "point"
    assert (audit.identity, audit.required) == ((), ())
    assert stack.events["Decision"].required == ("about",)


def test_is_a_subtype_states_its_own_time(tmp_path):
    stack = load(
        tmp_path,
        HEADER
        + "events:\n  Conference:\n    is_a: Event\n"
        + "    description: A named conference that runs over several days.\n"
        + "    time: interval\n",
    )
    assert stack.events["Conference"].time == "interval"
    assert stack.events["Event"].time == "point"


def test_inherited_event_keeps_its_time(tmp_path):
    error = failing(tmp_path, HEADER + "events:\n  Event:\n    time: interval\n")
    assert problem_lines(error) == [("pack.yaml", "events.Event.time", "stack.changed-time")]


def test_mode_from_nearest_pack(tmp_path):
    assert load_pack("core").mode is Mode.STRICT
    assert load_pack("enterprise-docs").mode is Mode.STRICT
    write_pack(tmp_path, "loose.yaml", "pack: loose\nversion: 1\nextends: core\nmode: discovery\n")
    write_pack(tmp_path, "child.yaml", "pack: child\nversion: 1\nextends: loose.yaml\n")
    write_pack(
        tmp_path, "strict.yaml", "pack: tight\nversion: 1\nextends: loose.yaml\nmode: strict\n"
    )
    assert load_pack("loose.yaml", base_dir=tmp_path).mode is Mode.DISCOVERY
    assert load_pack("child.yaml", base_dir=tmp_path).mode is Mode.DISCOVERY
    assert load_pack("strict.yaml", base_dir=tmp_path).mode is Mode.STRICT


def test_restated_values_merge(tmp_path):
    stack = load(
        tmp_path,
        HEADER
        + "entities:\n  Person:\n    description: A specific, named human being.\n"
        + "    vetoes: [born_on]\n"
        + "    attributes: {email: {range: str, compare: lower, unique: global}}\n"
        + "relations:\n  MEMBER_OF: {from: [Person], time: interval}\n",
    )
    assert stack.entities["Person"] == load_pack("core").entities["Person"]
    assert stack.relations["MEMBER_OF"] == load_pack("core").relations["MEMBER_OF"]


def test_child_adds_a_scope_to_an_unscoped_type(tmp_path):
    stack = load(
        tmp_path,
        HEADER
        + "entities:\n  Metric:\n"
        + "    scope: {role: owner, to: [Organization], inherit: document}\n",
    )
    assert stack.entities["Metric"].scope == Scope(
        role="owner", to=("Organization",), inherit="document", when={}
    )
    assert stack.origins["entities.Metric.scope"] == "user"


def test_added_scope_is_stated_whole(tmp_path):
    error = failing(tmp_path, HEADER + "entities:\n  Metric:\n    scope: {inherit: document}\n")
    assert problem_lines(error) == [
        ("pack.yaml", "entities.Metric.scope.role", "file.invalid-value"),
        ("pack.yaml", "entities.Metric.scope.to", "file.invalid-value"),
    ]


def test_enum_value_added_twice_merges(tmp_path):
    for name in ("left", "right"):
        write_pack(
            tmp_path,
            f"{name}.yaml",
            f"pack: {name}\nversion: 1\nextends: core\nenums:\n  OrgCategory: [vendor_desk]\n",
        )
    write_pack(
        tmp_path, "child.yaml", "pack: child\nversion: 1\nextends: [left.yaml, right.yaml]\n"
    )
    values = load_pack("child.yaml", base_dir=tmp_path).enums["OrgCategory"]
    assert values.count("vendor_desk") == 1


def test_bad_reference_in_a_list_names_its_index(tmp_path):
    error = failing(tmp_path, "pack: user\nversion: 1\nextends: [core, base.json]\n")
    assert problem_lines(error) == [("pack.yaml", "extends[1]", "pack.bad-reference")]


def test_extends_resolves_against_its_file(tmp_path):
    write_pack(
        tmp_path / "packs", "user.yaml", "pack: user\nversion: 1\nextends: base/parent.yaml\n"
    )
    write_pack(
        tmp_path / "packs" / "base", "parent.yaml", "pack: parent\nversion: 1\nextends: core\n"
    )
    stack = load_pack("packs/user.yaml", base_dir=tmp_path)
    assert [info.name for info in stack.packs] == ["core", "parent", "user"]
    assert stack.packs[1].source == str((tmp_path / "packs" / "base" / "parent.yaml").resolve())


def test_problem_names_a_parent_by_its_relative_path(tmp_path):
    write_pack(
        tmp_path / "packs", "user.yaml", "pack: user\nversion: 1\nextends: base/parent.yaml\n"
    )
    write_pack(
        tmp_path / "packs" / "base", "parent.yaml", "pack: parent\nversion: 0\nextends: core\n"
    )
    with pytest.raises(ConfigError) as caught:
        load_pack("packs/user.yaml", base_dir=tmp_path)
    assert problem_lines(caught.value) == [
        ("packs/base/parent.yaml", "version", "file.invalid-value")
    ]


def test_relative_reference_uses_the_working_directory(tmp_path, monkeypatch):
    shutil.copy(VALID / "alpha-ops.yaml", tmp_path / "alpha-ops.yaml")
    monkeypatch.chdir(tmp_path)
    assert load_pack("alpha-ops.yaml").name == "alpha-ops"


def test_base_dir_wins_over_the_working_directory(tmp_path, monkeypatch):
    write_pack(tmp_path / "here", "pack.yaml", "pack: here\nversion: 1\nextends: core\n")
    write_pack(tmp_path / "there", "pack.yaml", "pack: there\nversion: 1\nextends: core\n")
    monkeypatch.chdir(tmp_path / "here")
    assert load_pack("pack.yaml", base_dir=tmp_path / "there").name == "there"
    assert load_pack("pack.yaml").name == "here"
