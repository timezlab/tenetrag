"""Pack hashes and the stamp (data-model §5, research R7, FR-016, FR-024, US2-5, US2-6, SC-004).

Behaviours:
1. Each hash is sha256 over the canonical JSON of data-model §5, under its
   kind, with text kept as written (ensure_ascii=False).
2. Key order, comments, flow or block style and NFD text change no hash.
3. A changed description moves the content and index hashes.
4. Reordering a set keeps the hashes; reordering identity keys changes them.
5. Retrieval moves the content hash only; the glossary moves the content and
   glossary hashes, never the index hash.
6. A default written out equals the default left out, except in the file hash.
7. The stamp names the top pack and its version; the content hash does not.
8. Each PackInfo carries its file's hash.
9. core and enterprise-docs give pinned hashes.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
import unicodedata
from collections.abc import Mapping
from enum import Enum
from pathlib import Path
from typing import Any

import pytest

from tenetrag.packs import PackStack, Stamp, load_pack
from tests.support.packs import write_pack

TINY = """\
    # A small pack on core, with Vietnamese text.
    pack: tiny
    version: 1
    extends: core
    entities:
      Vendor:
        description: Một công ty cung cấp hàng hóa hoặc dịch vụ cho tổ chức theo hợp đồng.
        examples: [Công ty TNHH Gamma]
        attributes:
          tax_code: {range: str, compare: digits, unique: global}
          vendor_code: {range: str, compare: code, unique: global}
        identity: [[tax_code], [vendor_code]]
        vetoes: [tax_code, vendor_code]
    relations:
      SUPPLIES:
        description: The vendor supplies goods or services to the organization or person.
        from: [Vendor]
        to: [Organization, Person]
        time: interval
    retrieval:
      max_hops: 2
    glossary:
      - {name: Công ty TNHH Gamma, type: Vendor, aliases: [Gamma]}
    """

# TINY with its keys in another order, other comments and the other YAML style.
TINY_RELAID = """\
    glossary:
      - aliases:
          - Gamma
        type: Vendor
        name: Công ty TNHH Gamma   # the vendor's registered name
    relations:
      SUPPLIES:
        time: interval
        to: [Organization, Person]
        from: [Vendor]
        description: The vendor supplies goods or services to the organization or person.
    retrieval: {max_hops: 2}
    entities:
      Vendor:
        vetoes:
          - tax_code
          - vendor_code
        identity:
          - [tax_code]
          - [vendor_code]
        attributes:
          vendor_code: {unique: global, compare: code, range: str}
          tax_code:
            unique: global
            range: str
            compare: digits
        examples:
          - Công ty TNHH Gamma
        description: Một công ty cung cấp hàng hóa hoặc dịch vụ cho tổ chức theo hợp đồng.
    extends: [core]
    version: 1
    pack: tiny
    """

# The file of TINY as data-model §5 hashes it: the validated model, by alias,
# without unset fields. Written out by hand, so a change to what the file hash
# covers fails here.
TINY_FILE_CONTENT = {
    "pack": "tiny",
    "version": 1,
    "extends": ["core"],
    "entities": {
        "Vendor": {
            "description": "Một công ty cung cấp hàng hóa hoặc dịch vụ cho tổ chức theo hợp đồng.",
            "examples": ["Công ty TNHH Gamma"],
            "attributes": {
                "tax_code": {"range": "str", "compare": "digits", "unique": "global"},
                "vendor_code": {"range": "str", "compare": "code", "unique": "global"},
            },
            "identity": [{"key": ["tax_code"]}, {"key": ["vendor_code"]}],
            "vetoes": ["tax_code", "vendor_code"],
        }
    },
    "relations": {
        "SUPPLIES": {
            "description": "The vendor supplies goods or services to the organization or person.",
            "from": ["Vendor"],
            "to": ["Organization", "Person"],
            "time": "interval",
        }
    },
    "retrieval": {"max_hops": 2},
    "glossary": [{"name": "Công ty TNHH Gamma", "type": "Vendor", "aliases": ["Gamma"]}],
}

# The stack fields the content hash covers (data-model §5). Every other field
# of PackStack is named in EXCLUDED, so a new field fails test_every_field_placed.
CONTENT_FIELDS = (
    "mode",
    "entities",
    "relations",
    "events",
    "facts",
    "enums",
    "not_entities",
    "retrieval",
    "glossary",
    "competency_questions",
)
EXCLUDED = (
    "name",
    "version",
    "stamp",
    "index_hash",
    "glossary_hash",
    "packs",
    "origins",
    "warnings",
)
NOT_INDEXED = ("retrieval", "glossary")

# Pinned after the first green run. A change here changes every stamp and the
# extract and resolve stage hashes of every index, so it needs a reason in the
# commit: a change to a shipped pack also bumps its version (test_shipped_pins).
GOLDEN = {
    "core": {
        "content": "sha256:pending",
        "index": "sha256:pending",
        "glossary": "sha256:pending",
    },
    "enterprise-docs": {
        "content": "sha256:pending",
        "index": "sha256:pending",
        "glossary": "sha256:pending",
    },
}


def load(tmp_path: Path, text: str, name: str = "pack.yaml") -> PackStack:
    return load_pack(write_pack(tmp_path, name, text))


def changed(text: str, old: str, new: str) -> str:
    assert text.count(old) == 1, f"{old!r} must occur once"
    return text.replace(old, new)


def four_hashes(stack: PackStack) -> tuple[str, str, str, str]:
    return (
        stack.stamp.content_hash,
        stack.index_hash,
        stack.glossary_hash,
        stack.packs[-1].file_hash,
    )


def plain(value: Any) -> Any:
    """The stack as JSON data, walked independently of the implementation."""
    if isinstance(value, Enum):
        return plain(value.value)
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {item.name: plain(getattr(value, item.name)) for item in dataclasses.fields(value)}
    if isinstance(value, Mapping):
        return {key: plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(item) for item in value]
    assert value is None or isinstance(value, (bool, int)), f"no JSON form for {value!r}"
    return value


def recipe(kind: str, content: Any, *, ensure_ascii: bool = False) -> str:
    document = {"format": 1, "kind": kind, "content": content}
    text = json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=ensure_ascii,
        allow_nan=False,
    )
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def content_of(stack: PackStack) -> dict[str, Any]:
    return {name: plain(getattr(stack, name)) for name in CONTENT_FIELDS}


# The recipe


def test_every_field_placed():
    fields = {item.name for item in dataclasses.fields(PackStack)}
    assert fields == {*CONTENT_FIELDS, *EXCLUDED}


def test_hash_follows_the_recipe(tmp_path):
    stack = load(tmp_path, TINY)
    content = content_of(stack)
    index = {name: value for name, value in content.items() if name not in NOT_INDEXED}
    assert stack.stamp.content_hash == recipe("pack-content", content)
    assert stack.index_hash == recipe("pack-index", index)
    assert stack.glossary_hash == recipe("pack-glossary", plain(stack.glossary))


def test_file_hash_follows_the_recipe(tmp_path):
    stack = load(tmp_path, TINY)
    assert stack.packs[-1].file_hash == recipe("pack-file", TINY_FILE_CONTENT)


def test_no_glossary_hashes_an_empty_list():
    document = b'{"content":[],"format":1,"kind":"pack-glossary"}'
    expected = "sha256:" + hashlib.sha256(document).hexdigest()
    assert load_pack("core").glossary_hash == expected


def test_hash_keeps_non_ascii_text_as_is(tmp_path):
    stack = load(tmp_path, TINY)
    content = content_of(stack)
    assert stack.stamp.content_hash != recipe("pack-content", content, ensure_ascii=True)
    assert stack.packs[-1].file_hash != recipe("pack-file", TINY_FILE_CONTENT, ensure_ascii=True)


def test_hashes_are_well_formed(tmp_path):
    stack = load(tmp_path, TINY)
    for value in (*four_hashes(stack), *(info.file_hash for info in stack.packs)):
        assert re.fullmatch(r"sha256:[0-9a-f]{64}", value)


# What changes which hash


def test_hash_ignores_layout(tmp_path):
    base = four_hashes(load(tmp_path, TINY, "a.yaml"))
    assert four_hashes(load(tmp_path, TINY_RELAID, "b.yaml")) == base
    decomposed = unicodedata.normalize("NFD", TINY)
    assert decomposed != TINY
    assert four_hashes(load(tmp_path, decomposed, "c.yaml")) == base


def test_hash_description_change(tmp_path):
    base = load(tmp_path, TINY, "a.yaml")
    other = load(tmp_path, changed(TINY, "goods or services", "services"), "b.yaml")
    assert other.stamp.content_hash != base.stamp.content_hash
    assert other.index_hash != base.index_hash
    assert other.glossary_hash == base.glossary_hash


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("vetoes: [tax_code, vendor_code]", "vetoes: [vendor_code, tax_code]"),
        ("to: [Organization, Person]", "to: [Person, Organization]"),
    ],
)
def test_hash_set_order(tmp_path, old, new):
    base = load(tmp_path, TINY, "a.yaml")
    other = load(tmp_path, changed(TINY, old, new), "b.yaml")
    assert other.stamp.content_hash == base.stamp.content_hash
    assert other.index_hash == base.index_hash


def test_hash_identity_order(tmp_path):
    # Identity keys are tried in order, so their order is content.
    base = load(tmp_path, TINY, "a.yaml")
    swapped = changed(TINY, "[[tax_code], [vendor_code]]", "[[vendor_code], [tax_code]]")
    other = load(tmp_path, swapped, "b.yaml")
    assert other.stamp.content_hash != base.stamp.content_hash
    assert other.index_hash != base.index_hash


def test_hash_retrieval_only(tmp_path):
    base = load(tmp_path, TINY, "a.yaml")
    other = load(tmp_path, changed(TINY, "max_hops: 2", "max_hops: 3"), "b.yaml")
    assert other.stamp.content_hash != base.stamp.content_hash
    assert other.index_hash == base.index_hash
    assert other.glossary_hash == base.glossary_hash


def test_hash_glossary_only(tmp_path):
    base = load(tmp_path, TINY, "a.yaml")
    other = load(tmp_path, changed(TINY, "aliases: [Gamma]", "aliases: [Gamma, GMA]"), "b.yaml")
    assert other.glossary_hash != base.glossary_hash
    assert other.stamp.content_hash != base.stamp.content_hash
    assert other.index_hash == base.index_hash


def test_default_written_equals_omitted(tmp_path):
    base = load(tmp_path, TINY, "a.yaml")
    written = changed(
        TINY,
        "tax_code: {range: str, compare: digits, unique: global}",
        "tax_code: {range: str, compare: digits, unique: global, multivalued: false}",
    )
    written = changed(written, "    vetoes:", "    extract: true\n        vetoes:")
    other = load(tmp_path, written, "b.yaml")
    assert other.entities["Vendor"] == base.entities["Vendor"]
    assert other.stamp == base.stamp
    assert other.index_hash == base.index_hash
    # The file hash covers the file as written, so a written default moves it.
    assert other.packs[-1].file_hash != base.packs[-1].file_hash


# The stamp and the pack infos


def test_stamp_names_the_top_pack(tmp_path):
    base = load(tmp_path, TINY, "a.yaml")
    assert base.stamp == Stamp("tiny", 1, base.stamp.content_hash)
    renamed = changed(changed(TINY, "pack: tiny", "pack: other"), "version: 1", "version: 4")
    other = load(tmp_path, renamed, "b.yaml")
    assert other.stamp == Stamp("other", 4, base.stamp.content_hash)
    assert other.index_hash == base.index_hash
    assert other.packs[-1].file_hash != base.packs[-1].file_hash


def test_pack_info_carries_file_hash(tmp_path):
    stack = load(tmp_path, TINY)
    core = load_pack("core").packs[0]
    assert stack.packs[0] == core
    assert load_pack("enterprise-docs").packs[0] == core
    assert stack.packs[-1].file_hash != core.file_hash


# Pinned values


@pytest.mark.parametrize("name", ["core", "enterprise-docs"])
def test_hash_golden(name):
    stack = load_pack(name)
    actual = {
        "content": stack.stamp.content_hash,
        "index": stack.index_hash,
        "glossary": stack.glossary_hash,
    }
    assert actual == GOLDEN[name]
