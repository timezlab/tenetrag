"""Pack problems and the one ConfigError that lists them (data-model §1).

Behaviours:
1. PackProblem is a frozen value of rule, file, path, message and severity.
2. config_error's first line counts the errors, in the singular for one.
3. Each error is one line, `  - {file}: {path}: {message} [{rule}]`, in the order found.
4. Warnings are left out of the error.
5. config_error with no error is a caller bug and raises ValueError.
6. Every rule id is a phase, a dot and a kebab-case name.
7. problem_lines reads back each error's file, path and rule.
"""

import dataclasses
import re

import pytest

from tenetrag.packs.problems import RULES, PackProblem, config_error
from tenetrag.protocols.errors import ConfigError
from tests.support.packs import problem_lines

# The three errors of the failed-load example in contracts/packs.md.
UNKNOWN_FIELD = PackProblem(
    rule="file.unknown-field",
    file="packs/alpha-ops.yaml",
    path="entities.Vendor.vetos",
    message="unknown field; remove it or use a field of the pack format",
    severity="error",
)
DUPLICATE = PackProblem(
    rule="file.duplicate-key",
    file="packs/alpha-ops.yaml",
    path="entities",
    message="`Vendor` appears twice, at line 12 (first at line 5)",
    severity="error",
)
UNKNOWN_TYPE = PackProblem(
    rule="ref.unknown",
    file="packs/alpha-ops.yaml",
    path="relations.SUPPLIES.to[0]",
    message="no entity type `Organisation`; define it or use one of the stack's types",
    severity="error",
)
INSTRUCTION = PackProblem(
    rule="text.instruction",
    file="packs/alpha-ops.yaml",
    path="entities.Vendor.description",
    message="reads like an instruction to the model; describe the type instead",
    severity="warning",
)


def test_problem_fields():
    assert [field.name for field in dataclasses.fields(PackProblem)] == [
        "rule",
        "file",
        "path",
        "message",
        "severity",
    ]


def test_problem_is_frozen():
    with pytest.raises(dataclasses.FrozenInstanceError):
        UNKNOWN_FIELD.message = "changed"


def test_error_lists_every_error_in_order():
    error = config_error([UNKNOWN_FIELD, DUPLICATE, UNKNOWN_TYPE])
    assert isinstance(error, ConfigError)
    assert str(error) == (
        "The pack stack has 3 problems:\n"
        "  - packs/alpha-ops.yaml: entities.Vendor.vetos: unknown field; "
        "remove it or use a field of the pack format [file.unknown-field]\n"
        "  - packs/alpha-ops.yaml: entities: `Vendor` appears twice, "
        "at line 12 (first at line 5) [file.duplicate-key]\n"
        "  - packs/alpha-ops.yaml: relations.SUPPLIES.to[0]: no entity type `Organisation`; "
        "define it or use one of the stack's types [ref.unknown]"
    )


def test_one_error_is_singular():
    assert str(config_error([DUPLICATE])).startswith("The pack stack has 1 problem:\n")


def test_warnings_are_left_out():
    error = config_error([INSTRUCTION, DUPLICATE, INSTRUCTION])
    assert str(error).startswith("The pack stack has 1 problem:\n")
    assert "text.instruction" not in str(error)


@pytest.mark.parametrize("problems", [[], [INSTRUCTION]])
def test_no_error_is_a_caller_bug(problems):
    with pytest.raises(ValueError, match="at least one error"):
        config_error(problems)


def test_rule_ids_are_well_formed():
    pattern = re.compile(r"[a-z]+\.[a-z]+(-[a-z0-9]+)*")
    assert RULES, "no rule id defined"
    assert sorted(rule for rule in RULES if not pattern.fullmatch(rule)) == []


def test_problem_lines_reads_back_each_error():
    error = config_error([UNKNOWN_FIELD, INSTRUCTION, DUPLICATE, UNKNOWN_TYPE])
    assert problem_lines(error) == [
        ("packs/alpha-ops.yaml", "entities.Vendor.vetos", "file.unknown-field"),
        ("packs/alpha-ops.yaml", "entities", "file.duplicate-key"),
        ("packs/alpha-ops.yaml", "relations.SUPPLIES.to[0]", "ref.unknown"),
    ]
