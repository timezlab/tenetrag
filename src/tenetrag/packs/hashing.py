"""The four pack hashes and the stamp (data-model §5, research R7).

Each hash is `"sha256:" + hex` over canonical JSON of
`{"format", "kind", "content"}`: sorted keys, compact separators, text kept as
written and in NFC. That is `_digest` and `_canonical` of
tenetrag/config/hashing.py with the hash kind in place of the stage, repeated
here because packs and config cannot import each other (research R1); a
change to the recipe changes both copies.

- content hash: the merged stack, without what only names or places it;
- index hash: the content without the query-time hints, so changing them
  never asks for a re-index;
- glossary hash: the merged glossary, `[]` when there is none;
- file hash: one file's validated content, without the fields it leaves
  unset, so a default written out changes it. The pin test of the shipped
  versions uses it.
"""

from __future__ import annotations

import dataclasses
import enum
import hashlib
import json
import unicodedata
from collections.abc import Mapping
from typing import TypeAlias

from pydantic import BaseModel

from tenetrag.packs.format import ParsedPack
from tenetrag.packs.stack import PackStack, Stamp

_Json: TypeAlias = bool | int | float | str | list["_Json"] | dict[str, "_Json"] | None

# Bump with any change to the canonical form below, so old and new hashes never collide.
_FORMAT = 1

# Stack fields that name the stack, place its parts or are the hashes themselves.
# Every other field is content, so a field added later is hashed unless named here.
_NOT_CONTENT = frozenset(
    {"name", "version", "stamp", "index_hash", "glossary_hash", "packs", "origins", "warnings"}
)
# Query-time hints (research R7).
_NOT_INDEXED = frozenset({"retrieval", "glossary"})


def stamped(stack: PackStack) -> PackStack:
    """`stack` with its stamp, index hash and glossary hash filled in."""
    content = {
        field.name: _canonical(getattr(stack, field.name))
        for field in dataclasses.fields(stack)
        if field.name not in _NOT_CONTENT
    }
    index = {name: value for name, value in content.items() if name not in _NOT_INDEXED}
    return dataclasses.replace(
        stack,
        stamp=Stamp(stack.name, stack.version, _digest("pack-content", content)),
        index_hash=_digest("pack-index", index),
        glossary_hash=_digest("pack-glossary", content["glossary"]),
    )


def file_hash(parsed: ParsedPack) -> str:
    """The hash of one file's validated content, field names as written in the file."""
    content: dict[str, _Json] = {"pack": parsed.name, "version": parsed.version}
    if parsed.extends:
        content["extends"] = [reference for reference, _ in parsed.extends]
    if parsed.mode is not None:
        content["mode"] = parsed.mode.value
    for kind in ("entities", "relations", "events", "facts"):
        definitions: dict[str, BaseModel | None] = getattr(parsed, kind)
        if definitions:
            content[kind] = {name: _written(model) for name, model in definitions.items()}
    if parsed.enums:
        content["enums"] = _canonical(parsed.enums)
    if parsed.not_entities:
        content["not_entities"] = _canonical(parsed.not_entities)
    if parsed.retrieval is not None:
        content["retrieval"] = _written(parsed.retrieval)
    if parsed.glossary:
        content["glossary"] = [_written(entry) for _, entry in parsed.glossary]
    if parsed.questions:
        content["competency_questions"] = [_written(question) for _, question in parsed.questions]
    return _digest("pack-file", content)


def _written(model: BaseModel | None) -> _Json:
    """A model as the file wrote it: aliases such as `from`, and no unset field."""
    if model is None:
        return None
    return _canonical(model.model_dump(mode="json", by_alias=True, exclude_unset=True))


def _canonical(value: object) -> _Json:
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, enum.Enum):
        return _canonical(value.value)
    if value is None or isinstance(value, bool | int | float):
        return value
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _canonical(getattr(value, field.name))
            for field in dataclasses.fields(value)
        }
    if isinstance(value, list | tuple):
        return [_canonical(item) for item in value]
    if isinstance(value, Mapping):
        return {
            unicodedata.normalize("NFC", str(key)): _canonical(item) for key, item in value.items()
        }
    raise TypeError(f"no canonical form for a {type(value).__name__} value")


def _digest(kind: str, content: _Json) -> str:
    document = {"format": _FORMAT, "kind": kind, "content": content}
    text = json.dumps(
        document, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()
