"""Competency question coverage (data-model §6, research R9, FR-026, FR-027, US3-1 to US3-3).

Behaviours:
1. The shipped stacks pass every question: core its 6, enterprise-docs 14
   (6 + 8), and a user pack's question is checked with them (SC-001).
2. The report lists the stack's questions in stack order, each with its id,
   text and the pack that added it; `passed` holds when every question passes.
3. A need the stack lacks is `missing`; a need it defines with
   `extract: false` is `not_extracted`. Each is sorted, with each name once,
   and a need of any kind counts as defined.
4. Loading warns once for each unmet question, at
   `competency_questions[<id>]` of the file that holds it, shipped or not.
   The warning names what is lacking and never repeats the question's text.
5. The report is read-only.
"""

import dataclasses
import logging
from collections import Counter

import pytest

from tenetrag.packs import CoverageReport, check_coverage, load_pack
from tests.support.packs import PACK_FIXTURES, write_pack

HEADER = "pack: user\nversion: 1\nextends: core\n"
AUDIT_QUESTION = "Which units were audited in year Y?"
STATEMENT_QUESTION = "What did person P say about product X?"


def load(directory, text):
    write_pack(directory, "pack.yaml", text)
    return load_pack("pack.yaml", base_dir=directory)


def questions(*lines):
    return "competency_questions:\n" + "".join(f"  - {line}\n" for line in lines)


def unmet(report):
    return [
        (question.id, question.pack, question.missing, question.not_extracted)
        for question in report.questions
        if not question.passed
    ]


# The shipped packs (US3-1, SC-001)


@pytest.mark.parametrize(
    ("name", "per_pack"),
    [("core", {"core": 6}), ("enterprise-docs", {"core": 6, "enterprise-docs": 8})],
)
def test_coverage_shipped(name, per_pack):
    report = check_coverage(load_pack(name))
    assert isinstance(report, CoverageReport)
    assert report.passed
    assert Counter(question.pack for question in report.questions) == per_pack
    assert unmet(report) == []


def test_coverage_checks_user_questions():
    # FR-027: alpha-ops adds one question to the 14 it inherits.
    report = check_coverage(load_pack(PACK_FIXTURES / "valid" / "alpha-ops.yaml"))
    assert report.passed
    assert len(report.questions) == 15
    last = report.questions[-1]
    assert (last.id, last.pack, last.passed) == ("alpha-ops-1", "alpha-ops", True)


def test_report_follows_stack_order():
    stack = load_pack("enterprise-docs")
    report = check_coverage(stack)
    assert [(q.id, q.text) for q in report.questions] == [
        (q.id, q.text) for q in stack.competency_questions
    ]
    packs = [question.pack for question in report.questions]
    assert packs == ["core"] * 6 + ["enterprise-docs"] * 8
    first = report.questions[0]
    assert (first.id, first.missing, first.not_extracted) == ("core-1", (), ())


# What a question lacks (US3-2, US3-3)


def test_coverage_missing_relation(tmp_path):
    stack = load(
        tmp_path,
        HEADER
        + questions(
            f'{{id: user-1, text: "{AUDIT_QUESTION}", needs: [Organization, AUDITED]}}',
        ),
    )
    report = check_coverage(stack)
    assert not report.passed
    assert unmet(report) == [("user-1", "user", ("AUDITED",), ())]


def test_coverage_not_extracted(tmp_path):
    stack = load(
        tmp_path,
        HEADER + questions(f'{{id: user-1, text: "{STATEMENT_QUESTION}", needs: [Statement]}}'),
    )
    assert unmet(check_coverage(stack)) == [("user-1", "user", (), ("Statement",))]


def test_coverage_names_sorted_once(tmp_path):
    stack = load(
        tmp_path,
        HEADER
        + """\
entities:
  Memo:
    description: A short internal note.
    examples: [the March memo]
    extract: false
"""
        + questions(
            '{id: user-1, text: "Which notes name unit U?", '
            "needs: [ZONED_IN, Statement, AUDITED, Memo, Person, Audit, AUDITED]}",
        ),
    )
    assert unmet(check_coverage(stack)) == [
        ("user-1", "user", ("AUDITED", "Audit", "ZONED_IN"), ("Memo", "Statement"))
    ]


def test_coverage_every_kind_counts(tmp_path):
    stack = load(
        tmp_path,
        HEADER
        + questions(
            '{id: user-1, text: "Who met whom?", needs: [Person, MEMBER_OF, Event, Definition]}'
        ),
    )
    report = check_coverage(stack)
    assert report.passed
    assert report.questions[-1].passed


# Load warnings (FR-026)


def test_load_warns_unmet_question(tmp_path, caplog):
    caplog.set_level(logging.WARNING, logger="tenetrag.packs")
    stack = load(
        tmp_path,
        HEADER + questions(f'{{id: user-1, text: "{STATEMENT_QUESTION}", needs: [Statement]}}'),
    )
    assert [(w.rule, w.file, w.path, w.severity) for w in stack.warnings] == [
        ("coverage.unmet", "pack.yaml", "competency_questions[user-1]", "warning")
    ]
    message = stack.warnings[0].message
    assert "Statement" in message
    assert "extract: false" in message
    assert STATEMENT_QUESTION not in message
    assert [record.getMessage() for record in caplog.records].count(
        f"Pack pack.yaml: competency_questions[user-1]: {message} [coverage.unmet]"
    ) == 1


def test_load_warns_once_per_unmet_question(tmp_path):
    stack = load(
        tmp_path,
        HEADER
        + questions(
            f'{{id: user-1, text: "{AUDIT_QUESTION}", needs: [Organization, AUDITED]}}',
            '{id: user-2, text: "Who works where?", needs: [Person, MEMBER_OF]}',
            f'{{id: user-3, text: "{STATEMENT_QUESTION}", needs: [Statement, ZONED_IN]}}',
        ),
    )
    warnings = [(w.rule, w.path) for w in stack.warnings]
    assert warnings == [
        ("coverage.unmet", "competency_questions[user-1]"),
        ("coverage.unmet", "competency_questions[user-3]"),
    ]
    first, third = (w.message for w in stack.warnings)
    assert "AUDITED" in first
    assert "Statement" not in first
    assert "Statement" in third
    assert "ZONED_IN" in third
    assert AUDIT_QUESTION not in first
    assert STATEMENT_QUESTION not in third


def test_question_warns_at_its_own_file(tmp_path):
    # The warning names the file that holds the question, not the top of the
    # stack: here a parent's question, and core's, which the top file breaks
    # by turning off extraction of the relation it needs.
    write_pack(
        tmp_path,
        "base.yaml",
        HEADER.replace("user", "base")
        + questions(f'{{id: base-1, text: "{AUDIT_QUESTION}", needs: [AUDITED]}}'),
    )
    stack = load(
        tmp_path,
        "pack: top\nversion: 1\nextends: base.yaml\n"
        "relations:\n  HOLDS_POSITION: {extract: false}\n"
        + questions('{id: top-1, text: "Who works where?", needs: [Person, MEMBER_OF]}'),
    )
    assert [(w.file, w.path) for w in stack.warnings] == [
        ("core", "competency_questions[core-1]"),
        ("base.yaml", "competency_questions[base-1]"),
    ]
    assert "HOLDS_POSITION" in stack.warnings[0].message
    assert unmet(check_coverage(stack)) == [
        ("core-1", "core", (), ("HOLDS_POSITION",)),
        ("base-1", "base", ("AUDITED",), ()),
    ]


# Read-only


def test_report_read_only():
    report = check_coverage(load_pack("core"))
    with pytest.raises(dataclasses.FrozenInstanceError):
        report.questions = ()
    with pytest.raises(dataclasses.FrozenInstanceError):
        report.questions[0].missing = ("X",)
    assert isinstance(report.questions, tuple)
