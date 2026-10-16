"""Rewrite or check the committed corpus (contracts/corpus.md).

    uv run python -m tests.support.corpus           # rewrite tests/fixtures/corpus/generated/
    uv run python -m tests.support.corpus --check   # compare; exit 1 on a difference

A fact table problem exits 2 and prints one `{file}: {path}: {message}` line each.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

from tests.support.corpus import CorpusError, generate

CORPUS = Path(__file__).resolve().parents[2] / "fixtures" / "corpus"
FACTS = CORPUS / "facts"
GENERATED = CORPUS / "generated"


def _files(directory: Path) -> dict[str, bytes]:
    if not directory.is_dir():
        return {}
    return {
        path.relative_to(directory).as_posix(): path.read_bytes()
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


def differences(produced: Path, committed: Path) -> list[str]:
    """One line per file that is missing from, extra in or different in `committed`."""
    new, old = _files(produced), _files(committed)
    lines = [f"missing: {name}" for name in sorted(new.keys() - old.keys())]
    lines += [f"extra: {name}" for name in sorted(old.keys() - new.keys())]
    lines += [
        f"different: {name}" for name in sorted(new.keys() & old.keys()) if new[name] != old[name]
    ]
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tests.support.corpus",
        description="Generate the synthetic corpus from its fact table.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="generate into a temporary directory and compare with the committed files",
    )
    args = parser.parse_args(argv)
    with tempfile.TemporaryDirectory() as temporary:
        produced = Path(temporary) / "generated"
        try:
            generate(FACTS, produced)
        except CorpusError as exc:
            print(exc, file=sys.stderr)
            return 2
        if args.check:
            lines = differences(produced, GENERATED)
            for line in lines:
                print(line)
            return 1 if lines else 0
        # Replace the whole directory, so a file the fact table no longer makes goes too.
        shutil.rmtree(GENERATED, ignore_errors=True)
        shutil.copytree(produced, GENERATED)
    return 0


if __name__ == "__main__":
    sys.exit(main())
