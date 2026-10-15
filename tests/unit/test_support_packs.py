"""The pack test helpers must read and write what they claim to, or the pack tests prove nothing."""

import pytest

from tests.support.packs import FINANCE_DRAFT, REPO_ROOT, problem_lines, write_pack


def test_paths_are_absolute_and_exist():
    assert REPO_ROOT.is_absolute()
    assert (REPO_ROOT / "pyproject.toml").is_file()
    assert FINANCE_DRAFT.is_file()


def test_write_pack_dedents_and_writes_utf8_with_lf(tmp_path):
    path = write_pack(
        tmp_path / "nested",
        "user.yaml",
        """
        pack: user
        entities:
          Vendor: {description: Nhà cung cấp}
        """,
    )
    assert path == tmp_path / "nested" / "user.yaml"
    data = path.read_bytes()
    assert b"\r" not in data
    assert data.decode("utf-8") == (
        "\npack: user\nentities:\n  Vendor: {description: Nhà cung cấp}\n"
    )


def test_problem_lines_reads_an_empty_path_and_a_colon_in_the_message():
    error = ValueError(
        "The pack stack has 2 problems:\n"
        "  - packs/empty.yaml: : the file is empty: write `pack` and `version` [file.empty]\n"
        "  - core: entities.Person.identity[scope+employee_id]: see [x] [stack.changed-identity]"
    )
    assert problem_lines(error) == [
        ("packs/empty.yaml", "", "file.empty"),
        ("core", "entities.Person.identity[scope+employee_id]", "stack.changed-identity"),
    ]


@pytest.mark.parametrize(
    "text",
    [
        "Invalid profile, 1 problem(s). Fix each field below:\n  - models: unknown field",
        "The pack stack has 2 problems:\n  - core: entities: message [file.empty]",
        "The pack stack has 1 problem:\n  - core: entities: message without a rule",
    ],
    ids=["other-error", "count-mismatch", "no-rule"],
)
def test_problem_lines_fails_on_another_format(text):
    with pytest.raises(AssertionError):
        problem_lines(ValueError(text))
