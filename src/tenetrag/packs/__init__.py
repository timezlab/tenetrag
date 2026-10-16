"""Domain packs: load, merge, check, compile and hash.

Contract: specs/002-packs-and-corpus/contracts/packs.md. Pure: the standard
library, pydantic, PyYAML, `tenetrag.protocols` and `tenetrag._yaml`, with no
optional SDK. A sibling of `tenetrag.config`, so neither imports the other
(research R1).
"""

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
)

__all__ = [
    "Attribute",
    "CompetencyQuestion",
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
    "RelationType",
    "Retrieval",
    "Scope",
    "ShippedPack",
    "load_pack",
    "shipped_packs",
]
