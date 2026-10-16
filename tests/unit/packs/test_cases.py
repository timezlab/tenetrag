"""Identity cases: loading and checking them (data-model §8, research R11, FR-028 to FR-032, US4).

Behaviours:
1. The shipped case files and the finance file load, and check_cases finds
   no problem in them: 77 cases, 60 from the design and 17 added, split per
   file as in contracts/identity-cases.md (SC-007).
2. The 60 design cases keep their ids, class, R2 outcome, existing
   entities and mention, converted by the rules of research R11 (US4-4).
3. Coverage runs for each set whose top pack is shipped: every entity type
   the top pack gives a scope, a key or a veto, or whose identity fields it
   changes, has a case that must merge and one that must stay apart, and
   every key and veto it declares is named by a case (FR-031). A gap is
   reported at the element's path in the stack.
4. Every name a case uses exists in its stack: entity ids, types,
   attributes (and enum values), relations and their ends, and the
   elements of `depends_on`, resolved against the mention's type (FR-032).
5. The outcome fits `expect` and names ids among the case's own; a
   `blocked_by` matches a veto in `depends_on`, and a `new` outcome that
   depends on a veto names one. Ids are unique across the files checked.
6. A badly shaped file fails load_cases with the file.* rule ids of a
   pack file, never quoting its text; a stack that fails to load fails it
   too. A relative `pack` path resolves against the case file.
7. The D5 situation holds, and every email is on the `.example` domain.
"""

import dataclasses
import json
import re
import unicodedata
from collections import Counter

import pydantic
import pytest
import yaml

from tenetrag.packs import CaseSet, check_cases, load_cases, shipped_cases
from tenetrag.packs.cases import CASE_RULES
from tenetrag.protocols.errors import ConfigError
from tests.support.packs import (
    DESIGN_SNAPSHOT,
    FINANCE_CASES,
    SHIPPED_DIR,
    problem_lines,
    problem_messages,
    write_pack,
)

CORE_CASES = SHIPPED_DIR / "core.cases.yaml"
ENTERPRISE_CASES = SHIPPED_DIR / "enterprise-docs.cases.yaml"

# Research R11's stack table, and its 17 added cases.
DESIGN_IDS = {
    "core": {
        *("ORG-1", "ORG-2", "ORG-3", "ORG-4", "ORG-7", "UNIT-7", "UNIT-11", "UNIT-12"),
        *("PER-1", "PER-2", "PER-3", "PER-4", "PER-7"),
        *("WRK-1", "WRK-2", "WRK-4", "WRK-5", "WRK-6", "PRD-1", "PLC-1", "MET-1", "CON-1"),
    },
    "enterprise-docs": {
        *(f"UNIT-{n}" for n in (1, 2, 3, 4, 5, 6, 8, 9, 10, 13)),
        *("PER-5", "PER-6", "PER-8", "PER-9"),
        *(f"POL-{n}" for n in range(1, 13)),
        *("WRK-3", "PRJ-1", "PRJ-2", "PRJ-3", "SYS-1"),
    },
    "finance": {"ORG-5", "ORG-6", *(f"INS-{n}" for n in range(1, 6))},
}
ADDED_IDS = {
    "core": {"PLC-2", "PRD-2", "PER-10", "PER-11", "PER-12"},
    "enterprise-docs": {
        *("PRD-3", "PRD-4", "WRK-7", "SYS-2", "PER-13"),
        *(f"PROC-{n}" for n in range(1, 8)),
    },
    "finance": set(),
}

# How research R11 converts the snapshot's script vocabulary.
SNAPSHOT_KINDS = {"MERGE": "merge", "NEW": "new", "LINK": "same_as", "ASK": "confirm"}
SNAPSHOT_TYPES = {"Company": "Organization", "OrgUnit": "Organization"}
# The script's scope strings that name an entity the snapshot also lists.
SNAPSHOT_SCOPES = {"cn-hanoi": "alpha.cnhn", "cn-danang": "alpha.cndn"}
# core's PlaceKind has no commune.
SNAPSHOT_VALUES = {("kind", "commune"): "other"}
# Their titles say the scope came from the document, which the script's flag missed.
DOCUMENT_SCOPED = {"WRK-3", "PER-9"}
# The mentions the snapshot writes in English.
ENGLISH = {"ORG-5", "ORG-6", "UNIT-9", "UNIT-10"}

EMAIL = re.compile(r"[\w.+-]+@([\w-]+(?:\.[\w-]+)+)")


def all_sets():
    return (*shipped_cases(), load_cases(FINANCE_CASES))


def by_id(*case_sets):
    return {case.id: (case_set, case) for case_set in case_sets for case in case_set.cases}


def found(problems):
    return [(problem.rule, problem.path) for problem in problems]


def consistency(problems):
    """The problems other than coverage, which a set on a shipped pack always has when cut down."""
    return [pair for pair in found(problems) if not pair[0].startswith("case.coverage-")]


def coverage(problems):
    return [pair for pair in found(problems) if pair[0].startswith("case.coverage-")]


def copy_cases(source, directory, *, keep=lambda case_id: True):
    """A copy of a case file with the cases `keep` accepts, and a relative `pack` made absolute."""
    data = yaml.safe_load(source.read_text(encoding="utf-8"))
    if data["pack"].endswith(".yaml"):
        # The finance file names the draft relative to itself (FINANCE_DRAFT).
        data["pack"] = str((source.parent / data["pack"]).resolve())
    data["cases"] = [case for case in data["cases"] if keep(case["id"])]
    path = directory / source.name
    path.write_text(dump(data), encoding="utf-8")
    return path


class _PlainDumper(yaml.SafeDumper):
    """Writes a dict the tests share between cases in full, without YAML anchors."""

    def ignore_aliases(self, data):
        return True


def dump(data):
    return yaml.dump(data, Dumper=_PlainDumper, allow_unicode=True, sort_keys=False)


# Small inline case files: a user pack on core or enterprise-docs, so that
# no coverage runs unless a test names a shipped pack.

ALPHA = {
    "type": "Organization",
    "name": "Công ty CP Alpha",
    "attributes": {"category": {"value": "company", "quote": "Công ty CP Alpha"}},
}
AN = {
    "type": "Person",
    "name": "Nguyễn Văn An",
    "attributes": {"email": {"value": "an.nv@alpha.example", "quote": "an.nv@alpha.example"}},
    "relations": [{"type": "MEMBER_OF", "to": "alpha"}],
}
DOCUMENT = {"issuer": "alpha", "date": "2025-06-10", "language": "vi"}


def mention(**changes):
    base = {
        "type": "Person",
        "name": "Nguyễn Văn An",
        "attributes": {
            "email": {"value": "an.nv@alpha.example", "quote": "email an.nv@alpha.example"}
        },
        "document": DOCUMENT,
    }
    return base | changes


def case(case_id="X-1", **changes):
    base = {
        "id": case_id,
        "origin": "added",
        "expect": "merge",
        "title": "Cùng email",
        "existing": ["an"],
        "mention": mention(),
        "outcome": {"kind": "merge", "into": "an"},
        "depends_on": ["key:email"],
    }
    return base | changes


def write_cases(directory, *cases, pack="user.yaml", parent="core", entities=None, name="c.yaml"):
    if pack == "user.yaml":
        write_pack(directory, "user.yaml", f"pack: user\nversion: 1\nextends: {parent}\n")
    data = {
        "pack": pack,
        "entities": {"alpha": ALPHA, "an": AN} if entities is None else entities,
        "cases": list(cases),
    }
    path = directory / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump(data), encoding="utf-8")
    return path


def check(directory, *cases, **options):
    return check_cases(load_cases(write_cases(directory, *cases, **options)))


# The shipped files (FR-032, SC-007)


def test_cases_consistent():
    assert check_cases(*all_sets()) == ()


def test_case_counts():
    core, enterprise, finance = all_sets()
    assert (core.source, enterprise.source) == ("core.cases.yaml", "enterprise-docs.cases.yaml")
    assert finance.source == str(FINANCE_CASES.resolve())
    for case_set, name in ((core, "core"), (enterprise, "enterprise-docs"), (finance, "finance")):
        assert case_set.stack.name == name
        origins = Counter(case.origin for case in case_set.cases)
        assert origins == Counter(design=len(DESIGN_IDS[name]), added=len(ADDED_IDS[name]))
        assert {case.id for case in case_set.cases if case.origin == "design"} == DESIGN_IDS[name]
        assert {case.id for case in case_set.cases if case.origin == "added"} == ADDED_IDS[name]
    assert sum(len(case_set.cases) for case_set in (core, enterprise, finance)) == 77
    assert [len(case_set.cases) for case_set in (core, enterprise, finance)] == [27, 43, 7]


def test_shipped_cases_on_shipped_packs():
    assert [case_set.stack.packs[-1].source for case_set in shipped_cases()] == ["shipped"] * 2


def test_design_cases_match_snapshot():
    snapshot = json.loads(DESIGN_SNAPSHOT.read_text(encoding="utf-8"))
    sets = all_sets()
    cases = by_id(*sets)
    design = {case_id for case_id, (_, case) in cases.items() if case.origin == "design"}
    assert design == {snapped["id"] for snapped in snapshot["cases"]}
    assert Counter(snapped["class"] for snapped in snapshot["cases"]) == {"apart": 30, "merge": 30}
    for snapped in snapshot["cases"]:
        case_set, case = cases[snapped["id"]]
        r2 = snapped["r2"]
        assert case.title == snapped["title_vi"], case.id
        assert case.expect == snapped["class"], case.id
        assert case.outcome.kind == SNAPSHOT_KINDS[r2["outcome"]], case.id
        assert case.existing == snapped["existing"], case.id
        if case.outcome.kind == "merge":
            assert case.outcome.into == snapped["expected_referent"], case.id
        elif case.outcome.kind == "same_as":
            assert case.outcome.links == r2["candidates"], case.id
        elif case.outcome.kind == "confirm":
            assert case.outcome.candidates == r2["candidates"], case.id
            assert case.outcome.right == snapped["expected_referent"], case.id
        snapped_mention = snapped["mention"]
        assert case.mention.name == snapped_mention["name"], case.id
        assert_converted(case_set, case.mention, snapped_mention, case.id)
        assert case.mention.document.date == snapped_mention["date"], case.id
        language = "en" if case.id in ENGLISH else "vi"
        assert case.mention.document.language == language, case.id
        assert case.mention.translation == snapped_mention["proposed"], case.id
        renamed_from = snapped_mention["renamed_from"]
        former = [former.name for former in case.mention.former_names]
        assert former == ([renamed_from] if renamed_from else []), case.id
        from_document = not snapped_mention["scope_exact"] or case.id in DOCUMENT_SCOPED
        assert case.mention.scope_source == ("document" if from_document else "text"), case.id
    for case_set in sets:
        for entity_id, entity in case_set.entities.items():
            snapped_entity = snapshot["entities"].get(entity_id)
            if snapped_entity is not None:
                assert entity.name == snapped_entity["names"][0], entity_id
                assert_converted(case_set, entity, snapped_entity, entity_id)


def assert_converted(case_set, converted, snapped, label):
    """Type, scope and attributes as R11 converts them, `unit_at` and `title_at` as relations."""
    snapped_type = snapped["type"]
    assert converted.type == SNAPSHOT_TYPES.get(snapped_type, snapped_type), label
    path = snapped["scope"]
    if path and case_set.stack.entities[converted.type].scope is not None:
        assert converted.scope == SNAPSHOT_SCOPES.get(path[-1], path[-1]), label
    else:
        assert converted.scope is None, label
    entities = case_set.entities
    for attribute, value in snapped["attrs"].items():
        if attribute == "unit_at":
            units = [r.to for r in converted.relations if r.type == "MEMBER_OF"]
            assert [entities[unit].name for unit in units] == [value], label
        elif attribute == "title_at":
            positions = [r for r in converted.relations if r.type == "HOLDS_POSITION"]
            assert [position.attributes["title"].value for position in positions] == [value], label
        else:
            expected = SNAPSHOT_VALUES.get((attribute, value), value)
            assert converted.attributes[attribute].value == expected, (label, attribute)


def test_fictional_only():
    domains = []
    for path in (CORE_CASES, ENTERPRISE_CASES, FINANCE_CASES):
        domains += EMAIL.findall(path.read_text(encoding="utf-8"))
    assert domains
    assert [domain for domain in domains if not domain.endswith(".example")] == []


def test_d5_situation():
    core, enterprise = shipped_cases()
    cases = by_id(enterprise)
    for case_id, alphas in (("POL-1", "pol.a1"), ("UNIT-1", "alpha.tc")):
        case = cases[case_id][1]
        existing = enterprise.entities[alphas]
        assert (case.expect, case.outcome.kind, case.existing) == ("apart", "new", [alphas])
        assert (existing.scope, case.mention.scope) == ("alpha", "beta")
        assert case.mention.name == existing.name
        assert "scope" in case.depends_on
    metric = by_id(core)["MET-1"][1]
    assert (metric.expect, metric.outcome.kind, metric.outcome.into) == (
        "merge",
        "merge",
        "met.npl",
    )
    assert metric.mention.document.issuer == "beta"
    assert (core.entities["met.npl"].scope, metric.mention.scope) == (None, None)


# Coverage (FR-031)


def test_coverage_shipped():
    problems = check_cases(*shipped_cases())
    assert coverage(problems) == []


def test_missing_veto_case(tmp_path):
    copy = copy_cases(ENTERPRISE_CASES, tmp_path, keep=lambda case_id: case_id != "PER-5")
    problems = check_cases(load_cases(copy))
    assert [(p.rule, p.file, p.path) for p in problems] == [
        ("case.coverage-element", str(copy.resolve()), "entities.Person.vetoes[employee_id]")
    ]
    assert problems[0].message == (
        "no case depends on `veto:employee_id`; add one that this veto keeps apart"
    )


@pytest.mark.parametrize(
    ("source", "dropped", "gaps"),
    [
        (
            ENTERPRISE_CASES,
            {"PROC-1", "PROC-2", "PROC-5", "PROC-6", "PROC-7"},
            [
                ("case.coverage-type", "entities.Procedure"),
                ("case.coverage-element", "entities.Procedure.identity[scope+code]"),
                ("case.coverage-element", "entities.Procedure.vetoes[code]"),
                ("case.coverage-element", "entities.Procedure.vetoes[issued_on]"),
                ("case.coverage-element", "entities.Procedure.vetoes[version_label]"),
            ],
        ),
        # A type with a scope and no key or veto.
        (CORE_CASES, {"PLC-2"}, [("case.coverage-type", "entities.Place")]),
        # A type whose scope enterprise-docs only changed, by inheriting from the document.
        (ENTERPRISE_CASES, {"WRK-7"}, [("case.coverage-type", "entities.Work")]),
        # Types with no identity field ask for no case.
        (CORE_CASES, {"MET-1", "CON-1"}, []),
    ],
)
def test_coverage_names_each_gap(tmp_path, source, dropped, gaps):
    copy = copy_cases(source, tmp_path, keep=lambda case_id: case_id not in dropped)
    assert found(check_cases(load_cases(copy))) == gaps


def test_coverage_messages(tmp_path):
    dropped = {"PROC-1", "PROC-2", "PROC-5", "PROC-6", "PROC-7"}
    copy = copy_cases(ENTERPRISE_CASES, tmp_path, keep=lambda case_id: case_id not in dropped)
    messages = {problem.path: problem.message for problem in check_cases(load_cases(copy))}
    assert messages["entities.Procedure"] == (
        "no case of `Procedure` must stay apart under `enterprise-docs`; add one"
    )
    assert messages["entities.Procedure.identity[scope+code]"] == (
        "no case depends on `key:scope+code`; add one that this key merges"
    )
    assert messages["entities.Procedure.vetoes[code]"] == (
        "no case depends on `veto:code`; add one that this veto keeps apart"
    )


def test_coverage_only_for_shipped_tops(tmp_path):
    finance = copy_cases(FINANCE_CASES, tmp_path, keep=lambda case_id: case_id == "INS-1")
    assert check_cases(load_cases(finance)) == ()
    enterprise = copy_cases(ENTERPRISE_CASES, tmp_path, keep=lambda case_id: case_id == "PER-5")
    gaps = coverage(check_cases(load_cases(enterprise)))
    assert ("case.coverage-type", "entities.Policy") in gaps
    # Types and elements core gives are covered by core's own file.
    assert [gap for gap in gaps if "Place" in gap[1] or "born_on" in gap[1]] == []


# Names a case uses (FR-032, US4-3)


def test_valid_inline_case_passes(tmp_path):
    assert check(tmp_path, case()) == ()


def test_unknown_attribute(tmp_path):
    hung = {
        "type": "Person",
        "name": "Phạm Hùng",
        "attributes": {"employee_id": {"value": "A0123", "quote": "mã nhân viên A0123"}},
    }
    per_20 = case(
        "PER-20",
        expect="apart",
        existing=["hung"],
        mention=mention(
            name="Phạm Hùng",
            attributes={"employee_id": {"value": "A0456", "quote": "mã nhân viên A0456"}},
        ),
        outcome={"kind": "new"},
        depends_on=["names:evidence"],
    )
    path = write_cases(tmp_path, per_20, pack="core", entities={"alpha": ALPHA, "hung": hung})
    problems = check_cases(load_cases(path))
    assert consistency(problems) == [
        ("case.unknown-attribute", "entities.hung.attributes.employee_id"),
        ("case.unknown-attribute", "cases[PER-20].mention.attributes.employee_id"),
    ]
    message = next(p.message for p in problems if p.path.startswith("cases[PER-20]"))
    assert message == "`Person` has no attribute `employee_id` under `core`"
    assert {p.file for p in problems} == {str(path.resolve())}


def test_element_resolves_in_stack(tmp_path):
    hung = {"type": "Person", "name": "Phạm Hùng"}
    per_21 = case(
        "PER-21",
        expect="apart",
        existing=["hung"],
        mention=mention(name="Phạm Hùng", attributes={}),
        outcome={"kind": "new"},
        depends_on=["veto:employee_id"],
        blocked_by="employee_id",
    )
    entities = {"alpha": ALPHA, "hung": hung}
    enterprise = check(tmp_path, per_21, pack="enterprise-docs", entities=entities)
    assert consistency(enterprise) == []
    core = check(tmp_path, per_21, pack="core", entities=entities)
    assert consistency(core) == [("case.unknown-element", "cases[PER-21].depends_on[0]")]
    message = next(p.message for p in core if p.rule == "case.unknown-element")
    assert message == "`Person` has no veto `employee_id` under `core`"


@pytest.mark.parametrize(
    "element",
    [
        "scope",
        "key:scope+employee_id",
        "key:email",
        "veto:employee_id",
        "veto:born_on",
        "names:evidence",
        "unique:email",
        "corroborate:MEMBER_OF",
    ],
)
def test_element_grammar_accepts(tmp_path, element):
    assert check(tmp_path, case(depends_on=[element]), parent="enterprise-docs") == ()


@pytest.mark.parametrize(
    "element",
    [
        "key:employee_id+scope",  # a key is written in its declared order
        "key:employee_id",
        "veto:email",
        "names:key",
        "unique:employee_id",  # the default `unique` is no element
        "corroborate:PART_OF",
        "scope:alpha",
        "veto:",
        "key:",
        "employee_id",
    ],
)
def test_element_grammar_refuses(tmp_path, element):
    problems = check(tmp_path, case(depends_on=["key:email", element]), parent="enterprise-docs")
    assert found(problems) == [("case.unknown-element", "cases[X-1].depends_on[1]")]


@pytest.mark.parametrize("element", ["veto:", "key:", "veto:Born_On", "employee_id"])
def test_bad_element_names_the_grammar(tmp_path, element):
    problems = check(tmp_path, case(depends_on=["key:email", element]), parent="enterprise-docs")
    assert len(problems) == 1
    assert "`key:<a>+<b>`" in problems[0].message
    assert "has no" not in problems[0].message


def test_scope_element_needs_a_scope(tmp_path):
    # core gives Person no scope; enterprise-docs gives it an employer.
    problems = check(tmp_path, case(depends_on=["key:email", "scope"]))
    assert found(problems) == [("case.unknown-element", "cases[X-1].depends_on[1]")]
    assert problems[0].message == "`Person` has no scope under `user`"


def test_enum_value_in_stack(tmp_path):
    unit = {
        "type": "Organization",
        "name": "Phòng Tài chính",
        "scope": "alpha",
        "attributes": {"category": {"value": "department", "quote": "Phòng Tài chính"}},
    }
    entities = {"alpha": ALPHA, "an": AN, "alpha.tc": unit}
    assert check(tmp_path, case(), parent="enterprise-docs", entities=entities) == ()
    problems = check(tmp_path, case(), entities=entities)
    assert found(problems) == [("case.unknown-attribute", "entities.alpha.tc.attributes.category")]
    assert "`OrgCategory`" in problems[0].message
    assert "department" not in problems[0].message


def test_scope_fits_the_type(tmp_path):
    scoped = AN | {"scope": "alpha"}
    entities = {"alpha": ALPHA, "an": scoped, "binh": AN | {"scope": "an"}}
    assert found(check(tmp_path, case(), entities=entities)) == [
        ("case.unknown-element", "entities.an.scope"),
        ("case.unknown-element", "entities.binh.scope"),
    ]
    # enterprise-docs scopes a person by an organization, never by a person.
    assert found(check(tmp_path, case(), parent="enterprise-docs", entities=entities)) == [
        ("case.unknown-element", "entities.binh.scope"),
    ]
    metric = {"type": "Metric", "name": "Tỷ lệ nợ xấu"}
    met = case(
        existing=["met"],
        mention=mention(type="Metric", name="Tỷ lệ nợ xấu", attributes={}, scope="alpha"),
        outcome={"kind": "merge", "into": "met"},
        depends_on=["names:key"],
    )
    problems = check(tmp_path, met, entities={"alpha": ALPHA, "met": metric})
    assert found(problems) == [("case.unknown-element", "cases[X-1].mention.scope")]


def test_scope_is_an_entity(tmp_path):
    entities = {"alpha": ALPHA, "an": AN | {"scope": "nobody"}}
    problems = check(tmp_path, case(), parent="enterprise-docs", entities=entities)
    assert found(problems) == [("case.unknown-entity", "entities.an.scope")]


def test_issuer_is_an_entity(tmp_path):
    cited = mention(document=DOCUMENT | {"issuer": "gamma"})
    problems = check(tmp_path, case(mention=cited))
    assert found(problems) == [("case.unknown-entity", "cases[X-1].mention.document.issuer")]


def test_relations_fit_the_stack(tmp_path):
    relations = [
        {"type": "MEMBER_OF", "to": "an"},
        {
            "type": "HOLDS_POSITION",
            "to": "alpha",
            "attributes": {"grade": {"value": "A", "quote": "bậc A"}},
        },
        {"type": "SUPPLIES", "to": "alpha"},
        {"type": "MEMBER_OF", "to": "gamma"},
    ]
    problems = check(tmp_path, case(mention=mention(relations=relations)))
    assert found(problems) == [
        ("case.unknown-relation", "cases[X-1].mention.relations[0]"),
        ("case.unknown-attribute", "cases[X-1].mention.relations[1].attributes.grade"),
        ("case.unknown-relation", "cases[X-1].mention.relations[2].type"),
        ("case.unknown-entity", "cases[X-1].mention.relations[3].to"),
    ]


# Outcomes, vetoes and ids


def test_outcome_fits_expect(tmp_path):
    binh = AN | {"name": "Trần Thị Bình"}
    problems = check(
        tmp_path,
        case("A-1", expect="apart"),
        case("A-2", outcome={"kind": "merge", "into": "binh"}),
        case("A-3", outcome={"kind": "same_as", "links": ["an"]}),
        entities={"alpha": ALPHA, "an": AN, "binh": binh},
    )
    assert found(problems) == [
        ("case.outcome", "cases[A-1].outcome.kind"),
        ("case.outcome", "cases[A-2].outcome.into"),
    ]


@pytest.mark.parametrize(
    ("expect", "outcome", "problem"),
    [
        ("merge", {"kind": "merge"}, ("case.outcome", "cases[X-1].outcome")),
        ("apart", {"kind": "new", "into": "an"}, ("case.outcome", "cases[X-1].outcome")),
        ("merge", {"kind": "same_as", "into": "an"}, ("case.outcome", "cases[X-1].outcome")),
        (
            "merge",
            {"kind": "confirm", "candidates": ["an"], "right": "alpha"},
            ("case.outcome", "cases[X-1].outcome.right"),
        ),
        (
            "merge",
            {"kind": "confirm", "candidates": ["alpha"], "right": "alpha"},
            ("case.outcome", "cases[X-1].outcome.candidates[0]"),
        ),
        (
            "apart",
            {"kind": "confirm", "candidates": ["an"], "right": "an"},
            ("case.outcome", "cases[X-1].outcome.kind"),
        ),
        (
            "apart",
            {"kind": "same_as", "links": ["gamma"]},
            ("case.unknown-entity", "cases[X-1].outcome.links[0]"),
        ),
    ],
)
def test_outcome_problems(tmp_path, expect, outcome, problem):
    assert found(check(tmp_path, case(expect=expect, outcome=outcome))) == [problem]


def test_blocked_by_needs_veto(tmp_path):
    issued = {"value": "2025-01-10", "quote": "ban hành ngày 10/01/2025"}
    work = {
        "type": "Work",
        "name": "Hợp đồng cung cấp dịch vụ",
        "scope": "alpha",
        "attributes": {
            "code": {"value": "01/2025/HĐDV", "quote": "Hợp đồng số 01/2025/HĐDV"},
            "issued_on": issued,
        },
    }
    work_mention = mention(
        type="Work",
        name="Hợp đồng cung cấp dịch vụ",
        scope="alpha",
        attributes={
            "code": {"value": "02/2025/HĐDV", "quote": "Hợp đồng số 02/2025/HĐDV"},
            "issued_on": issued,
        },
    )
    apart = {"expect": "apart", "existing": ["w"], "mention": work_mention}
    problems = check(
        tmp_path,
        case("B-1", **apart, outcome={"kind": "new"}, depends_on=["veto:code"], blocked_by="code"),
        case(
            "B-2",
            **apart,
            outcome={"kind": "new"},
            depends_on=["veto:issued_on"],
            blocked_by="code",
        ),
        case("B-3", **apart, outcome={"kind": "new"}, depends_on=["veto:code"]),
        case("B-4", **apart, outcome={"kind": "same_as", "links": ["w"]}, depends_on=["veto:code"]),
        entities={"alpha": ALPHA, "w": work},
    )
    assert found(problems) == [
        ("case.blocked-by", "cases[B-2].blocked_by"),
        ("case.blocked-by", "cases[B-3]"),
    ]


def test_duplicate_id_across_files(tmp_path):
    core = shipped_cases()[0]
    inline = load_cases(write_cases(tmp_path, case("PER-2")))
    problems = check_cases(core, inline)
    assert [(p.rule, p.file, p.path) for p in problems] == [
        ("case.duplicate-id", inline.source, "cases[PER-2]")
    ]
    assert "core.cases.yaml" in problems[0].message
    problems = check_cases(inline, core)
    assert [(p.rule, p.file, p.path) for p in problems] == [
        ("case.duplicate-id", "core.cases.yaml", "cases[PER-2]")
    ]
    assert inline.source in problems[0].message


def test_duplicate_id_in_one_file(tmp_path):
    problems = check(tmp_path, case("X-1"), case("X-1"))
    assert found(problems) == [("case.duplicate-id", "cases[X-1]")]
    assert "in this file" in problems[0].message


# One small file for each case.* rule of data-model §8

RULE_FILES = {
    "case.duplicate-id": ({"cases": [case("X-1"), case("X-1")]}, "cases[X-1]"),
    "case.unknown-entity": ({"cases": [case(existing=["an", "nobody"])]}, "cases[X-1].existing[1]"),
    "case.unknown-type": (
        {
            "cases": [case()],
            "entities": {"alpha": ALPHA, "an": AN, "gamma": {"type": "Vendor", "name": "Gamma"}},
        },
        "entities.gamma.type",
    ),
    "case.unknown-attribute": (
        {
            "cases": [
                case(
                    mention=mention(
                        attributes={"tax_code": {"value": "0109998887", "quote": "MST 0109998887"}}
                    )
                )
            ]
        },
        "cases[X-1].mention.attributes.tax_code",
    ),
    "case.unknown-relation": (
        {"cases": [case(mention=mention(relations=[{"type": "SUPPLIES", "to": "alpha"}]))]},
        "cases[X-1].mention.relations[0].type",
    ),
    "case.unknown-element": (
        {"cases": [case(depends_on=["key:email", "veto:email"])]},
        "cases[X-1].depends_on[1]",
    ),
    "case.outcome": ({"cases": [case(expect="apart")]}, "cases[X-1].outcome.kind"),
    "case.blocked-by": ({"cases": [case(blocked_by="born_on")]}, "cases[X-1].blocked_by"),
    "case.coverage-type": ({"cases": [case()], "pack": "core"}, "entities.Person"),
    "case.coverage-element": (
        {"cases": [case()], "pack": "core"},
        "entities.Person.vetoes[born_on]",
    ),
}


def test_every_case_rule_has_a_case_file():
    assert set(RULE_FILES) == CASE_RULES


@pytest.mark.parametrize("rule", sorted(RULE_FILES))
def test_case_rule(tmp_path, rule):
    options, path = RULE_FILES[rule]
    cases = options["cases"]
    problems = check(tmp_path, *cases, **{k: v for k, v in options.items() if k != "cases"})
    if rule.startswith("case.coverage-"):
        assert (rule, path) in found(problems)
        assert consistency(problems) == []
    else:
        assert found(problems) == [(rule, path)]


# Loading (data-model §8)


@pytest.mark.parametrize(
    ("changes", "path", "rule"),
    [
        ({"mention": mention(colour="red")}, "cases[0].mention.colour", "file.unknown-field"),
        (
            {
                "mention": mention(
                    attributes={"email": {"value": "an.nv@alpha.example", "quote": ""}}
                )
            },
            "cases[0].mention.attributes.email.quote",
            "file.invalid-value",
        ),
        ({"outcome": {"kind": "maybe"}}, "cases[0].outcome.kind", "file.invalid-value"),
        ({"id": "per-1"}, "cases[0].id", "file.bad-name"),
        ({"depends_on": []}, "cases[0].depends_on", "file.invalid-value"),
        (
            {"mention": mention(document=DOCUMENT | {"date": "10/06/2025"})},
            "cases[0].mention.document.date",
            "file.invalid-value",
        ),
        # Python reads 20250610 as a date; a case file writes the ISO form with dashes.
        (
            {"mention": mention(document=DOCUMENT | {"date": "20250610"})},
            "cases[0].mention.document.date",
            "file.invalid-value",
        ),
        (
            {"mention": mention(document=DOCUMENT | {"language": "fr"})},
            "cases[0].mention.document.language",
            "file.invalid-value",
        ),
        (
            {"mention": mention(attributes={"email": {"value": "", "quote": "email"}})},
            "cases[0].mention.attributes.email.value",
            "file.invalid-value",
        ),
        # A `!!binary` value reads as bytes, which strict mode refuses as text.
        (
            {
                "mention": mention(
                    attributes={"email": {"value": b"an.nv@alpha.example", "quote": "email"}}
                )
            },
            "cases[0].mention.attributes.email.value",
            "file.invalid-value",
        ),
        ({"existing": []}, "cases[0].existing", "file.invalid-value"),
        ({"existing": ["An"]}, "cases[0].existing[0]", "file.bad-name"),
    ],
)
def test_case_shape(tmp_path, changes, path, rule):
    written = write_cases(tmp_path, case(**changes))
    with pytest.raises(ConfigError) as caught:
        load_cases(written)
    assert problem_lines(caught.value) == [(str(written.resolve()), path, rule)]
    assert str(caught.value).startswith("The case file has 1 problem:")


def test_case_file_shape(tmp_path):
    written = tmp_path / "c.yaml"
    written.write_text(
        "pack: core\nentities: {}\ncases: []\nnotes: x\nnotes: y\n", encoding="utf-8"
    )
    with pytest.raises(ConfigError) as caught:
        load_cases(written)
    label = str(written.resolve())
    assert problem_lines(caught.value) == [
        (label, "", "file.duplicate-key"),
        (label, "cases", "file.invalid-value"),
        (label, "notes", "file.unknown-field"),
    ]


def test_case_dates_read_either_way(tmp_path):
    written = write_cases(tmp_path, case())
    text = written.read_text(encoding="utf-8").replace("'2025-06-10'", "2025-06-10")
    assert "date: 2025-06-10" in text
    written.write_text(text, encoding="utf-8")
    assert load_cases(written).cases[0].mention.document.date == "2025-06-10"


def test_attribute_dates_read_either_way(tmp_path):
    born = {"born_on": {"value": "1990-01-02", "quote": "sinh ngày 02/01/1990"}}
    written = write_cases(tmp_path, case(mention=mention(attributes=born)))
    text = written.read_text(encoding="utf-8").replace("'1990-01-02'", "1990-01-02")
    assert "value: 1990-01-02" in text
    written.write_text(text, encoding="utf-8")
    loaded = load_cases(written).cases[0].mention.attributes["born_on"]
    assert loaded.value == "1990-01-02"


def test_case_text_read_as_nfc(tmp_path):
    written = write_cases(tmp_path, case())
    decomposed = unicodedata.normalize("NFD", written.read_text(encoding="utf-8"))
    assert decomposed != written.read_text(encoding="utf-8")
    written.write_text(decomposed, encoding="utf-8")
    loaded = load_cases(written)
    assert loaded.entities["alpha"].name == unicodedata.normalize("NFC", "Công ty CP Alpha")
    assert loaded.cases[0].title == unicodedata.normalize("NFC", "Cùng email")


def test_case_text_never_echoed(tmp_path):
    secret = "sk-live-0123456789abcdef"
    written = write_cases(tmp_path, case(mention=mention(colour=secret), title=""))
    with pytest.raises(ConfigError) as caught:
        load_cases(written)
    assert secret not in str(caught.value)
    assert all(secret not in message for message in problem_messages(caught.value))


def test_pack_relative_to_case_file(tmp_path, monkeypatch):
    write_pack(tmp_path / "packs", "user.yaml", "pack: user\nversion: 1\nextends: core\n")
    written = write_cases(tmp_path / "cases" / "x", case(), pack="../../packs/user.yaml")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    assert load_cases(written).stack.name == "user"
    monkeypatch.chdir(tmp_path)
    loaded = load_cases("cases/x/c.yaml")
    assert loaded.source == str(written.resolve())


def test_failing_stack_raises(tmp_path):
    written = write_cases(tmp_path, case(), pack="missing.yaml")
    with pytest.raises(ConfigError) as caught:
        load_cases(written)
    assert problem_lines(caught.value) == [("missing.yaml", "", "file.unreadable")]


def test_case_set_read_only():
    core = shipped_cases()[0]
    assert isinstance(core, CaseSet)
    with pytest.raises(dataclasses.FrozenInstanceError):
        core.source = "other"
    with pytest.raises(TypeError):
        core.entities["alpha"] = core.entities["alpha"]
    assert isinstance(core.cases, tuple)


def test_cases_frozen():
    core = shipped_cases()[0]
    with pytest.raises(pydantic.ValidationError):
        core.cases[0].title = "other"
    with pytest.raises(pydantic.ValidationError):
        core.entities["alpha"].name = "other"
