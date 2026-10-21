"""Domain packs: load, merge, check, compile and hash, and the identity cases.

Contracts: specs/002-packs-and-corpus/contracts/packs.md and identity-cases.md. Pure: the standard
library, pydantic, PyYAML, `tenetrag.protocols` and `tenetrag._yaml`, with no
optional SDK. A sibling of `tenetrag.config`, so neither imports the other
(research R1).
"""

from tenetrag.packs.cases import (
    Case,
    CaseEntity,
    CaseSet,
    Mention,
    Outcome,
    check_cases,
    load_cases,
    shipped_cases,
)
from tenetrag.packs.compile import CompiledSchema, compile_schema
from tenetrag.packs.coverage import CoverageReport, QuestionCoverage, check_coverage
from tenetrag.packs.loading import load_pack, shipped_packs
from tenetrag.packs.problems import PackProblem
from tenetrag.packs.stack import (
    Attribute,
    CompetencyQuestion,
    EntityType,
    EventType,
    FactType,
    GlossaryEntry,
    Key,
    Mode,
    NameRule,
    PackInfo,
    PackStack,
    RelationType,
    Retrieval,
    Scope,
    ShippedPack,
    Stamp,
)
from tenetrag.packs.store import store_schema

__all__ = [
    "Attribute",
    "Case",
    "CaseEntity",
    "CaseSet",
    "CompetencyQuestion",
    "CompiledSchema",
    "CoverageReport",
    "EntityType",
    "EventType",
    "FactType",
    "GlossaryEntry",
    "Key",
    "Mention",
    "Mode",
    "NameRule",
    "Outcome",
    "PackInfo",
    "PackProblem",
    "PackStack",
    "QuestionCoverage",
    "RelationType",
    "Retrieval",
    "Scope",
    "ShippedPack",
    "Stamp",
    "check_cases",
    "check_coverage",
    "compile_schema",
    "load_cases",
    "load_pack",
    "shipped_cases",
    "shipped_packs",
    "store_schema",
]
