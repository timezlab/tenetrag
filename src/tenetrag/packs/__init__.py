"""Domain packs: load, merge, check, compile and hash.

Contract: specs/002-packs-and-corpus/contracts/packs.md. Pure: the standard
library, pydantic, PyYAML, `tenetrag.protocols` and `tenetrag._yaml`, with no
optional SDK. A sibling of `tenetrag.config`, so neither imports the other
(research R1).
"""

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

__all__ = [
    "Attribute",
    "CompetencyQuestion",
    "CompiledSchema",
    "CoverageReport",
    "EntityType",
    "EventType",
    "FactType",
    "GlossaryEntry",
    "Key",
    "Mode",
    "NameRule",
    "PackInfo",
    "PackProblem",
    "PackStack",
    "QuestionCoverage",
    "RelationType",
    "Retrieval",
    "Scope",
    "ShippedPack",
    "Stamp",
    "check_coverage",
    "compile_schema",
    "load_pack",
    "shipped_packs",
]
