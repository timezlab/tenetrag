"""Coverage of the competency questions (data-model §6, research R9).

A question passes when the stack defines every name it needs, of any
kind, and extracts each one: a type with `extract: false` never reaches
the graph, so a question that needs it cannot be answered from it. An
unmet question is a load warning (checks.py), never an error.
"""

from __future__ import annotations

from dataclasses import dataclass

from tenetrag.packs.stack import PackStack
from tenetrag.packs.stacking import KINDS, question_path


@dataclass(frozen=True, slots=True)
class QuestionCoverage:
    """One question and what it lacks. `missing` and `not_extracted` are sorted, each name once."""

    id: str
    text: str
    pack: str
    missing: tuple[str, ...]
    not_extracted: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.missing and not self.not_extracted


@dataclass(frozen=True, slots=True)
class CoverageReport:
    """Each competency question of the stack, in stack order."""

    questions: tuple[QuestionCoverage, ...]

    @property
    def passed(self) -> bool:
        return all(question.passed for question in self.questions)


def check_coverage(stack: PackStack) -> CoverageReport:
    """What each of the stack's competency questions lacks. Pure: no I/O, no model call."""
    # A name is defined in one kind only (ref.kind-clash), so one map holds them all.
    is_extracted = {
        name: item.extract for kind in KINDS for name, item in getattr(stack, kind).items()
    }
    questions = []
    for question in stack.competency_questions:
        needs = set(question.needs)
        questions.append(
            QuestionCoverage(
                id=question.id,
                text=question.text,
                pack=stack.origins[question_path(question.id)],
                missing=tuple(sorted(needs - is_extracted.keys())),
                not_extracted=tuple(
                    sorted(name for name in needs if is_extracted.get(name) is False)
                ),
            )
        )
    return CoverageReport(tuple(questions))
