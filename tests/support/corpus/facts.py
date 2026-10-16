"""The fact table's shapes, and reading it (data-model §9, contracts/corpus.md).

Every file is read with a safe YAML loader that refuses duplicate keys, and
every string is normalized to NFC before validation, so the generated files
are NFC whatever the editor wrote. Models refuse unknown fields and are
strict: an unquoted date is a YAML date, not a string, and is refused.
"""

from __future__ import annotations

import unicodedata
from datetime import date
from pathlib import Path
from typing import Annotated, Any, Literal

import yaml
from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Discriminator,
    Field,
    StringConstraints,
    Tag,
    ValidationError,
    model_validator,
)

from tests.support.corpus.problems import Problem


def _iso_date(value: str) -> str:
    date.fromisoformat(value)
    return value


Text = Annotated[str, StringConstraints(min_length=1)]
Name = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")]
DocumentId = Annotated[str, StringConstraints(pattern=r"^D[1-9][0-9]*$")]
ItemId = Annotated[str, StringConstraints(pattern=r"^D[1-9][0-9]*\.[1-9][0-9]*$")]
WorldId = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9]*(?:[.-][a-z0-9]+)*$")]
IsoDate = Annotated[
    str, StringConstraints(pattern=r"^\d{4}-\d{2}-\d{2}$"), AfterValidator(_iso_date)
]
Language = Literal["vi", "en"]
QType = Literal[
    "single_fact",
    "entity_all",
    "meeting_decision",
    "definition",
    "historical_figure",
    "as_of",
    "conflicting_versions",
    "cross_lingual",
]
# The dates a document's text may state. `issued_on` and `held_on` are the
# document date (engine brief §3.1, observed_at); `effective_from` is
# inherited by items that state no start.
DateName = Literal["issued_on", "effective_from", "effective_to", "held_on"]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class Quoted(_Model):
    value: Text
    quote: Text


class Heading(_Model):
    heading: Text
    level: Literal[1, 2, 3] = 1


class Paragraph(_Model):
    paragraph: Text


class ListBlock(_Model):
    entries: list[Text] = Field(alias="list", min_length=1)


class Table(_Model):
    header: list[Text] = Field(min_length=1)
    rows: list[list[Text]] = Field(min_length=1)

    @model_validator(mode="after")
    def _same_width(self) -> Table:
        if any(len(row) != len(self.header) for row in self.rows):
            raise ValueError("every row needs as many cells as the header")
        return self


class TableBlock(_Model):
    table: Table


def _block_kind(value: Any) -> str | None:
    if isinstance(value, BaseModel):
        return f"block={type(value).__name__}"
    if isinstance(value, dict):
        for key in ("heading", "paragraph", "list", "table"):
            if key in value:
                return f"block={key}"
    return None


Block = Annotated[
    Annotated[Heading, Tag("block=heading")]
    | Annotated[Paragraph, Tag("block=paragraph")]
    | Annotated[ListBlock, Tag("block=list")]
    | Annotated[TableBlock, Tag("block=table")],
    Discriminator(
        _block_kind,
        custom_error_type="block_kind",
        custom_error_message="a block is one of `heading`, `paragraph`, `list` or `table`",
    ),
]


class EntityItem(_Model):
    id: ItemId
    kind: Literal["entity"]
    type: Text
    world: WorldId
    surface: Text
    is_name: bool
    attributes: dict[Name, Quoted] = {}
    former_names: list[Quoted] = []


class RelationItem(_Model):
    id: ItemId
    kind: Literal["relation"]
    type: Text
    from_: ItemId = Field(alias="from")
    to: ItemId
    attributes: dict[Name, Quoted] = {}
    quote: Text
    valid_from: IsoDate | None = None
    valid_to: IsoDate | None = None


class StatementItem(_Model):
    """An event or a fact: roles hold refs to items of the same document."""

    id: ItemId
    kind: Literal["event", "fact"]
    type: Text
    roles: dict[Name, ItemId | list[ItemId]] = Field(min_length=1)
    attributes: dict[Name, Quoted] = {}
    quote: Text
    valid_from: IsoDate | None = None
    valid_to: IsoDate | None = None


def _item_kind(value: Any) -> str | None:
    kind = value.kind if isinstance(value, BaseModel) else value.get("kind")
    if kind in ("event", "fact"):
        return "kind=statement"
    if kind in ("entity", "relation"):
        return f"kind={kind}"
    return None


Item = Annotated[
    Annotated[EntityItem, Tag("kind=entity")]
    | Annotated[RelationItem, Tag("kind=relation")]
    | Annotated[StatementItem, Tag("kind=statement")],
    Discriminator(
        _item_kind,
        custom_error_type="item_kind",
        custom_error_message="`kind` is one of `entity`, `relation`, `event` or `fact`",
    ),
]
TAGS = frozenset(
    {
        "block=heading",
        "block=paragraph",
        "block=list",
        "block=table",
        "kind=entity",
        "kind=relation",
        "kind=statement",
    }
)


class Document(_Model):
    id: DocumentId
    language: Literal["vi", "en", "mixed"]
    issuer: WorldId
    title: Text
    format: Literal["docx", "pdf", "pptx", "xlsx", "md"]
    dates: dict[DateName, IsoDate] = {}
    blocks: list[Block] = Field(min_length=1)
    items: list[Item] = Field(min_length=1)

    @property
    def number(self) -> int:
        return int(self.id[1:])


class WorldEntity(_Model):
    type: Text
    name: Text
    aliases: list[Text] = []
    # How a question in each language names the entity; `name` when absent.
    labels: dict[Language, Text] = {}
    scope: WorldId | None = None
    attributes: dict[Name, Text] = {}


class World(_Model):
    entities: dict[WorldId, WorldEntity] = Field(min_length=1)


class TextIn(_Model):
    entity: WorldId
    document: DocumentId


class Graph(_Model):
    deletions: list[DocumentId] = []
    text_in: list[TextIn] = []


class Question(_Model):
    id: Annotated[str, StringConstraints(pattern=r"^Q-[a-z0-9]+(?:-[a-z0-9]+)*$")]
    qtype: QType
    lang: Language
    cq: list[Text] = Field(min_length=1)
    as_of: IsoDate | None = None
    question: Text
    expected_answer: Text
    expected_sources: list[DocumentId] = Field(min_length=1)


class Golden(_Model):
    questions: list[Question] = []


class FactTable(_Model):
    world: World
    documents: tuple[Document, ...]
    graph: Graph
    golden: Golden


class _UniqueKeyLoader(yaml.SafeLoader):
    """A safe loader that refuses a key written twice in one mapping."""


def _construct_mapping(loader: _UniqueKeyLoader, node: yaml.MappingNode) -> dict[Any, Any]:
    seen: dict[Any, int] = {}
    for key_node, _ in node.value:
        key = loader.construct_object(key_node)
        if key in seen:
            raise yaml.constructor.ConstructorError(
                None,
                None,
                f"`{key}` appears twice (first at line {seen[key] + 1})",
                key_node.start_mark,
            )
        seen[key] = key_node.start_mark.line
    return loader.construct_mapping(node)


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_mapping,
)


def _nfc(data: Any) -> Any:
    if isinstance(data, str):
        return unicodedata.normalize("NFC", data)
    if isinstance(data, dict):
        return {_nfc(key): _nfc(value) for key, value in data.items()}
    if isinstance(data, list):
        return [_nfc(value) for value in data]
    return data


def _path(data: Any, loc: tuple[int | str, ...]) -> str:
    """A pydantic location as `items[D2.6].attributes.threshold.quote`.

    A list element is named by its `id` when it has one, a mapping key in
    brackets when it holds a dot, and union tags are left out.
    """
    path = ""
    for part in loc:
        if part in TAGS:
            continue
        if isinstance(part, int):
            element = data[part] if isinstance(data, list) and part < len(data) else None
            name = element.get("id") if isinstance(element, dict) else None
            path += f"[{name if isinstance(name, str) else part}]"
            data = element
            continue
        data = data.get(part) if isinstance(data, dict) else None
        path += f"[{part}]" if "." in part else f"{'.' if path else ''}{part}"
    return path or "(top)"


def _read(
    facts_dir: Path, name: str, model: type[_Model], problems: list[Problem]
) -> _Model | None:
    path = facts_dir / name
    try:
        text = path.read_bytes().decode("utf-8")
    except FileNotFoundError:
        problems.append(Problem(name, "(file)", "missing"))
        return None
    except UnicodeDecodeError:
        problems.append(Problem(name, "(file)", "not UTF-8"))
        return None
    try:
        data = _nfc(yaml.load(text, Loader=_UniqueKeyLoader))  # noqa: S506 - a safe loader subclass
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        where = f"line {mark.line + 1}" if mark is not None else "(file)"
        problems.append(Problem(name, where, getattr(exc, "problem", None) or "not valid YAML"))
        return None
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        for error in exc.errors(include_url=False, include_input=False):
            problems.append(Problem(name, _path(data, error["loc"]), error["msg"]))
        return None


def read_facts(facts_dir: Path) -> tuple[FactTable | None, list[Problem]]:
    """Read every file of the fact table, collecting each file's problems."""
    problems: list[Problem] = []
    world = _read(facts_dir, "world.yaml", World, problems)
    documents = []
    for path in sorted((facts_dir / "documents").glob("*.yaml"), key=_document_order):
        name = f"documents/{path.name}"
        document = _read(facts_dir, name, Document, problems)
        if isinstance(document, Document) and document.id != path.stem:
            problems.append(Problem(name, "id", f"the file of {document.id} is {document.id}.yaml"))
        elif isinstance(document, Document):
            documents.append(document)
    if not documents:
        problems.append(Problem("documents", "(directory)", "holds no document file"))
    graph = _read(facts_dir, "graph.yaml", Graph, problems)
    golden = _read(facts_dir, "golden.yaml", Golden, problems)
    if problems:
        return None, problems
    assert isinstance(world, World)
    assert isinstance(graph, Graph)
    assert isinstance(golden, Golden)
    table = FactTable(world=world, documents=tuple(documents), graph=graph, golden=golden)
    return table, problems


def _document_order(path: Path) -> tuple[int, str]:
    """`D2.yaml` before `D10.yaml`; a name that is not `D<n>.yaml` sorts last, by name."""
    stem = path.stem
    number = int(stem[1:]) if stem[:1] == "D" and stem[1:].isdigit() else 10**9
    return number, path.name
