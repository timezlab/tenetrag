"""The corpus generator (contracts/corpus.md, research R12).

Test support, not SDK code: it reads the fact table under
`tests/fixtures/corpus/facts/` and writes the documents, their expected
items, the graph results and the golden set under `generated/`. No clock,
no randomness and no set iteration: the output depends only on the fact
table and the shipped `enterprise-docs` stack.
"""

from __future__ import annotations

import json
from pathlib import Path

from tenetrag.packs import load_pack
from tests.support.corpus.checks import STACK_NAME, check
from tests.support.corpus.derive import derive
from tests.support.corpus.facts import read_facts
from tests.support.corpus.golden import golden
from tests.support.corpus.problems import CorpusError, Problem
from tests.support.corpus.render import render

__all__ = ["CorpusError", "Problem", "generate"]


def _json(value: object, *, indent: int | None = None) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=indent)


def generate(facts_dir: Path, out_dir: Path) -> None:
    """Write the corpus from `facts_dir` into `out_dir`.

    Raises CorpusError listing every problem of the fact table, and then
    writes nothing.
    """
    table, problems = read_facts(facts_dir)
    if table is None:
        raise CorpusError(problems)
    stack = load_pack(STACK_NAME)
    rendered = {document.id: render(document) for document in table.documents}
    problems = check(table, rendered, stack)
    if problems:
        raise CorpusError(problems)
    graph, problems = derive(table, stack)
    if problems:
        raise CorpusError(problems)
    questions = golden(table, graph, stack)

    files = {f"docs/{document_id}.md": text for document_id, text in rendered.items()}
    files["documents.jsonl"] = "".join(
        _json(
            {
                **document.model_dump(
                    by_alias=True, exclude_defaults=True, exclude={"blocks", "items"}
                ),
                "dates": dict(document.dates),
                "items": [
                    item.model_dump(by_alias=True, exclude_defaults=True) for item in document.items
                ],
                "path": f"docs/{document.id}.md",
            }
        )
        + "\n"
        for document in table.documents
    )
    files["graph.json"] = _json(graph, indent=1) + "\n"
    files["golden.jsonl"] = "".join(_json(question) + "\n" for question in questions)

    for name, text in files.items():
        path = out_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))
