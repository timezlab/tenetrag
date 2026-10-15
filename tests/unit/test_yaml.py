"""The shared safe YAML loader (contracts/config.md §3, research R1).

Behaviours:
1. A clean document parses to its data and no duplicates.
2. A repeated key is reported with both lines, at the top level and nested.
3. Every repeated key in the document is listed, in order.
4. A merge key (`<<`) that a later key overrides is not a duplicate.
5. Tags that would build Python objects raise yaml.YAMLError and build nothing.
6. yaml_problem gives the problem with its line and column, never the text
   around it, which may hold a secret.
7. An error with no position, such as a character YAML refuses, gets a fixed text.
8. DuplicateKeyLoader is PyYAML's safe loader.
9. Each duplicate carries the key, both lines and the dotted path of its
   mapping: "" at the top level, `entities.Vendor` nested, `qs[0]` in a list.
"""

import re

import pytest
import yaml

from tenetrag._yaml import DuplicateKey, DuplicateKeyLoader, parse_yaml, yaml_problem
from tests.support.secrets import PLANTED, assert_no_secret

BUILT: list[object] = []


class Tripwire:
    """Records every instance built, so a test can show that none was."""

    def __new__(cls) -> "Tripwire":
        instance = super().__new__(cls)
        BUILT.append(instance)
        return instance


@pytest.fixture(autouse=True)
def _clear_built():
    BUILT.clear()
    yield
    BUILT.clear()


def test_clean_document_parses():
    assert parse_yaml("a: 1\nb: [x, y]\n") == ({"a": 1, "b": ["x", "y"]}, [])


def test_repeated_top_level_key_names_both_lines():
    _, duplicates = parse_yaml("a: 1\nb: 2\na: 3\n")
    assert [str(duplicate) for duplicate in duplicates] == ["'a' at line 3 (first at line 1)"]


def test_repeated_nested_key_names_both_lines():
    _, duplicates = parse_yaml("outer:\n  x: 1\n  x: 2\n")
    assert [str(duplicate) for duplicate in duplicates] == ["'x' at line 3 (first at line 2)"]


def test_every_repeated_key_is_listed():
    _, duplicates = parse_yaml("a: 1\na: 2\nb: 1\nb: 2\n")
    assert [str(duplicate) for duplicate in duplicates] == [
        "'a' at line 2 (first at line 1)",
        "'b' at line 4 (first at line 3)",
    ]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("a: 1\na: 2\n", DuplicateKey(path="", key="a", line=2, first_line=1)),
        (
            "entities:\n  Vendor:\n    code: 1\n    code: 2\n",
            DuplicateKey(path="entities.Vendor", key="code", line=4, first_line=3),
        ),
        (
            "qs:\n  - {id: a}\n  - {id: b, id: c}\n",
            DuplicateKey(path="qs[1]", key="id", line=3, first_line=3),
        ),
        (
            "a:\n  - [x, {k: 1, k: 2}]\n",
            DuplicateKey(path="a[0][1]", key="k", line=2, first_line=2),
        ),
    ],
    ids=["top-level", "nested", "in-a-list", "in-a-nested-list"],
)
def test_duplicate_names_its_mapping_path(text, expected):
    assert parse_yaml(text)[1] == [expected]


def test_merge_key_override_is_not_a_duplicate():
    data, duplicates = parse_yaml("base: &base {x: 1, y: 2}\nchild: {<<: *base, x: 3}\n")
    assert duplicates == []
    assert data == {"base": {"x": 1, "y": 2}, "child": {"x": 3, "y": 2}}


OBJECT_TAGS = [
    "a: !!python/object:tests.unit.test_yaml.Tripwire {}\n",
    "a: !!python/object/new:tests.unit.test_yaml.Tripwire []\n",
    "a: !!python/name:tests.unit.test_yaml.Tripwire\n",
]


def test_tripwire_detects_an_unsafe_load():
    # Control for the test below: without it, "nothing built" could pass vacuously.
    yaml.load(OBJECT_TAGS[0], Loader=yaml.UnsafeLoader)  # noqa: S506 -- a constant from this file
    assert len(BUILT) == 1


@pytest.mark.parametrize("text", OBJECT_TAGS)
def test_object_building_tags_raise_and_build_nothing(text):
    with pytest.raises(yaml.YAMLError):
        parse_yaml(text)
    assert BUILT == []


# PyYAML quotes about 35 characters on each side of the error mark, so the
# secret sits right next to it.
@pytest.mark.parametrize(
    "text",
    [
        f"graph:\n  password: {PLANTED[1]}: extra\n",
        f"graph:\n  password: [{PLANTED[1]}\n",
    ],
)
def test_problem_gives_the_position_without_the_text(text):
    with pytest.raises(yaml.YAMLError) as caught:
        parse_yaml(text)
    problem = yaml_problem(caught.value)
    assert re.search(r" at line \d+, column \d+$", problem)
    assert_no_secret(problem)


def test_problem_without_a_position_has_a_fixed_text():
    with pytest.raises(yaml.YAMLError) as caught:
        parse_yaml(f"a: {PLANTED[0]}\x07\n")
    assert yaml_problem(caught.value) == "the text has characters YAML does not accept"


def test_loader_is_the_safe_loader():
    assert issubclass(DuplicateKeyLoader, yaml.SafeLoader)
