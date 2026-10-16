"""Pack problems and the one ConfigError that lists them (data-model §1).

Standard library and `tenetrag.protocols` only. Each phase of a pack load
collects problems instead of stopping at the first, so one error lists them
all (research R4).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

from tenetrag.protocols.errors import ConfigError

Severity = Literal["error", "warning"]

# The rule ids a pack load gives (data-model §1). Each has a broken test pack
# under tests/fixtures/packs/broken/<rule>/, and a test checks both ways.
# The case.* ids live in cases.py, since no pack load gives them.
RULES: frozenset[str] = frozenset(
    {
        # Resolving references
        "pack.bad-reference",
        "pack.unknown",
        "pack.cycle",
        "pack.no-extends",
        "pack.shadows-shipped",
        # Reading one file
        "file.unreadable",
        "file.not-utf8",
        "file.yaml",
        "file.duplicate-key",
        "file.empty",
        "file.not-mapping",
        "file.unknown-field",
        "file.invalid-value",
        "file.bad-name",
        "file.reserved-name",
        # Stacking a file on its ancestors
        "stack.missing-description",
        "stack.changed-range",
        "stack.changed-time",
        "stack.changed-description",
        "stack.changed-identity",
        "stack.added-identity",
        "stack.required-on-inherited",
        "stack.removed",
        "stack.changed",
        "stack.parents-conflict",
        "stack.duplicate-question",
        # Checking the merged stack
        "ref.unknown",
        "ref.is-a",
        "ref.where-not-enum",
        "ref.kind-clash",
        "identity.key-needs-scope",
        "identity.key-not-minimal",
        "identity.veto-multivalued",
        "identity.veto-range",
        "identity.veto-is-name",
        "identity.versioned-needs-start",
        "glossary.alias-clash",
        # Warnings; text.instruction is an error in strict mode
        "identity.evidence-without-corroborate",
        "text.instruction",
        "coverage.unmet",
    }
)


@dataclass(frozen=True, slots=True)
class PackProblem:
    """One problem found while loading a pack stack.

    `file` is a shipped pack's name or a user file's path as the reference
    gave it, and `path` the dotted place inside the pack, or "" for the whole
    file. A message says what to change and never repeats the file's text,
    which may hold anything.
    """

    rule: str
    file: str
    path: str
    message: str
    severity: Severity


def config_error(
    problems: Iterable[PackProblem], *, subject: str = "The pack stack"
) -> ConfigError:
    """One `ConfigError` listing every error in the order found, without the warnings.

    `subject` names what was read: a pack stack, or an identity case file.
    """
    errors = [problem for problem in problems if problem.severity == "error"]
    if not errors:
        raise ValueError("config_error needs at least one error problem; this is a caller bug")
    noun = "problem" if len(errors) == 1 else "problems"
    lines = [f"{subject} has {len(errors)} {noun}:"]
    lines.extend(
        f"  - {error.file}: {error.path}: {error.message} [{error.rule}]" for error in errors
    )
    return ConfigError("\n".join(lines))
