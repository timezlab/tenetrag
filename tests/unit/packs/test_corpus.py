"""The synthetic corpus: fact table, generator and generated files (data-model §9, research R12).

Behaviours (FR-033 to FR-041, US5, SC-008 to SC-010):
1. Generating from the fact table gives the committed files byte for byte.
2. The corpus has 30 to 60 documents: at least 10 vi, 10 en and 3 mixed.
3. Every quote occurs in its document's rendered text, and every item fits
   the shipped `enterprise-docs` stack.
4. A changed quote or an unfit item fails generation, naming the document
   and the item, and nothing is written.
5. D1 to D5 hold the engine brief's running example, and graph.json states
   its statuses, including r1 current again after D2 is deleted. The
   expected values here are written by hand, never read from the generator.
6. The golden set has the benchmark's fields, covers every question type
   and competency question, holds Q-a to Q-c, and cites only generated
   documents.
7. The fact table plants each situation of FR-034.
8. Every generated file is NFC with LF endings and one final newline, and
   every name is fictional or a listed public authority.
9. graph.json follows the version rules: a superseded member closes at the
   next later start unless it states its own end, a fact's issuer is the
   scope of its source, and a deletion lists each group it changes, with a
   group it empties as [].
10. Generated questions follow their rules: single_fact asks about each
    figure or requirement alone in its group, historical_figure about each
    current figure with a period, and as_of about each member of a group
    that does not conflict, 30 days into its interval.

Only test_regenerates_same_bytes and the failure tests run the generator;
the rest read the committed files. The expected values in 9 and 10 come from
the rules applied to the fact table, never from the generator's code.
"""

import json
import re
import shutil
import unicodedata
from collections import Counter
from datetime import date, timedelta
from functools import cache
from pathlib import Path

import pytest
import yaml

from tenetrag.packs import PackStack, load_pack
from tests.support.corpus import CorpusError, generate
from tests.support.packs import REPO_ROOT

CORPUS = REPO_ROOT / "tests" / "fixtures" / "corpus"
FACTS = CORPUS / "facts"
GENERATED = CORPUS / "generated"

QTYPES = {
    "single_fact",
    "entity_all",
    "meeting_decision",
    "definition",
    "historical_figure",
    "as_of",
    "conflicting_versions",
    "cross_lingual",
}
TAGS = {"id", "qtype", "lang", "cq", "as_of", "origin"}
ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
EMAIL = re.compile(r"[\w.+-]+@([\w-]+(?:\.[\w-]+)*)")

# The engine brief's running example (docs/product/engine-brief.md#running-example).
RUNNING_EXAMPLE = {
    "D1": {
        "language": "vi",
        "issuer": "alpha",
        "format": "docx",
        "title": "Quy chế công tác phí",
        "dates": {"issued_on": "2025-01-10", "effective_from": "2025-02-01"},
        "text": ["Mức phụ cấp lưu trú là 2.000.000 VND/ngày.", "Phòng Tài chính"],
    },
    "D2": {
        "language": "vi",
        "issuer": "alpha",
        "format": "pdf",
        "title": "Quy chế công tác phí",
        "dates": {"issued_on": "2026-01-05", "effective_from": "2026-01-15"},
        "text": ["Mức phụ cấp lưu trú là 2.500.000 VND/ngày.", "Quy chế này thay thế phiên bản 1."],
    },
    "D3": {
        "language": "vi",
        "issuer": "alpha",
        "format": "docx",
        "title": "Biên bản họp Ủy ban Rủi ro",
        "dates": {"held_on": "2025-12-20"},
        "text": ["20/12/2025", "Ủy ban Rủi ro", "Nguyễn Văn An", "10/01/2026"],
    },
    "D4": {
        "language": "en",
        "issuer": "alpha",
        "format": "pdf",
        "title": "KPI handbook 2025",
        "dates": {"issued_on": "2025-03-01"},
        "text": [
            "Churn rate = customers lost in the period ÷ customers at the start of the period."
        ],
    },
    "D5": {
        "language": "vi",
        "issuer": "beta",
        "format": "docx",
        "title": "Quy chế công tác phí",
        "dates": {"issued_on": "2026-03-01", "effective_from": "2026-03-15"},
        "text": ["Mức phụ cấp lưu trú là 800.000 VND/ngày.", "Phòng Tài chính"],
    },
}
R2_SENTENCE = "Mức phụ cấp lưu trú là 2.500.000 VND/ngày."
ALPHA_LIMIT = "Requirement:issuer=alpha;metric=met.luu-tru"
BETA_LIMIT = "Requirement:issuer=beta;metric=met.luu-tru"

# FR-041: the fictional companies the corpus may name, and the public
# authorities it may name as the issuer of a public legal document.
FICTIONAL_COMPANIES = {
    "alpha": "Công ty CP Alpha",
    "beta": "Công ty CP Beta",
    "gamma": "Công ty TNHH Gamma",
}
PUBLIC_AUTHORITIES = {"btc": "Bộ Tài chính"}


@cache
def _stack() -> PackStack:
    return load_pack("enterprise-docs")


@cache
def _documents() -> tuple[dict, ...]:
    lines = (GENERATED / "documents.jsonl").read_text(encoding="utf-8").splitlines()
    return tuple(json.loads(line) for line in lines)


@cache
def _graph() -> dict:
    return json.loads((GENERATED / "graph.json").read_text(encoding="utf-8"))


@cache
def _golden() -> tuple[dict, ...]:
    lines = (GENERATED / "golden.jsonl").read_text(encoding="utf-8").splitlines()
    return tuple(json.loads(line) for line in lines)


@cache
def _world() -> dict:
    return yaml.safe_load((FACTS / "world.yaml").read_text(encoding="utf-8"))["entities"]


def _document(document_id: str) -> dict:
    return next(document for document in _documents() if document["id"] == document_id)


def _text(document: dict) -> str:
    return (GENERATED / document["path"]).read_text(encoding="utf-8")


def _items(document: dict) -> dict[str, dict]:
    return {item["id"]: item for item in document["items"]}


def _refs(value: str | list[str]) -> list[str]:
    return [value] if isinstance(value, str) else value


def _group_parts(group_id: str) -> tuple[str, dict[str, str]]:
    """Split `Type:a=x;b=y` into the type and its key parts."""
    type_name, _, key = group_id.partition(":")
    parts = dict(part.split("=", 1) for part in key.split(";") if part)
    return type_name, parts


def _located_items() -> dict[str, tuple[dict, dict]]:
    """Each item id's document and item."""
    return {item["id"]: (document, item) for document in _documents() for item in document["items"]}


def _start(document: dict, item: dict) -> str:
    """`valid_from`, else the document's `effective_from`, else its date (contracts/corpus.md)."""
    dates = document["dates"]
    for start in (
        item.get("valid_from"),
        dates.get("effective_from"),
        dates.get("issued_on"),
        dates.get("held_on"),
    ):
        if start:
            return start
    raise AssertionError(f"{item['id']} has no start")


def _item_groups() -> dict[str, str]:
    """Each version member's group id."""
    return {
        member["item"]: group_id
        for group_id, members in _graph()["versions"].items()
        for member in members
    }


def _tree(directory: Path) -> dict[str, bytes]:
    return {
        path.relative_to(directory).as_posix(): path.read_bytes()
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


def _copy_facts(tmp_path: Path) -> Path:
    facts = tmp_path / "facts"
    shutil.copytree(FACTS, facts)
    return facts


def _edit_document(facts: Path, document_id: str, edit) -> None:
    path = facts / "documents" / f"{document_id}.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    edit(data)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


# 1. Regeneration


def test_regenerates_same_bytes(tmp_path):
    out = tmp_path / "generated"
    generate(FACTS, out)
    produced = _tree(out)
    committed = _tree(GENERATED)
    assert sorted(produced) == sorted(committed)
    changed = [name for name in committed if produced[name] != committed[name]]
    assert changed == []


# 2. Document mix


def test_document_mix():
    documents = _documents()
    assert 30 <= len(documents) <= 60
    languages = Counter(document["language"] for document in documents)
    assert languages["vi"] >= 10
    assert languages["en"] >= 10
    assert languages["mixed"] >= 3
    assert set(languages) == {"vi", "en", "mixed"}
    ids = [document["id"] for document in documents]
    assert ids == sorted(ids, key=lambda document_id: int(document_id[1:]))
    assert len(set(ids)) == len(ids)
    assert {path.name for path in (GENERATED / "docs").iterdir()} == {f"{i}.md" for i in ids}
    assert all(document["path"] == f"docs/{document['id']}.md" for document in documents)


# 3. Quotes and fit


def test_quotes_verbatim():
    checked = 0
    for document in _documents():
        text = _text(document)
        for item in document["items"]:
            where = f"{document['id']} {item['id']}"
            quotes = [attribute["quote"] for attribute in item.get("attributes", {}).values()]
            quotes += [former["quote"] for former in item.get("former_names", [])]
            if item["kind"] == "entity":
                quotes.append(item["surface"])
            else:
                quotes.append(item["quote"])
            for quote in quotes:
                assert quote, where
                assert quote in text, f"{where}: {quote!r}"
                checked += 1
    assert checked >= sum(len(document["items"]) for document in _documents())


def _lineage(stack: PackStack, type_name: str) -> set[str]:
    """The type and every event type it is a kind of."""
    names = {type_name}
    while type_name in stack.events and stack.events[type_name].is_a is not None:
        type_name = stack.events[type_name].is_a
        names.add(type_name)
    return names


def test_items_fit_stack():
    stack = _stack()
    world = _world()
    kinds = Counter()
    for document in _documents():
        items = _items(document)
        for item in document["items"]:
            where = f"{document['id']} {item['id']}"
            kind, type_name = item["kind"], item["type"]
            kinds[kind] += 1
            definition = {
                "entity": stack.entities,
                "relation": stack.relations,
                "event": stack.events,
                "fact": stack.facts,
            }[kind].get(type_name)
            assert definition is not None, where
            assert definition.extract, where
            attributes = item.get("attributes", {})
            assert set(attributes) <= set(definition.attributes), where
            for name, attribute in attributes.items():
                values = stack.enums.get(definition.attributes[name].range)
                if values is not None:
                    assert attribute["value"] in values, f"{where} {name}"
            if kind == "entity":
                assert world[item["world"]]["type"] == type_name, where
                continue
            if kind == "relation":
                assert items[item["from"]]["type"] in definition.from_types, where
                assert items[item["to"]]["type"] in definition.to_types, where
                assert set(definition.required) <= set(attributes), where
                continue
            roles = item.get("roles", {})
            assert set(roles) <= set(definition.roles), where
            assert set(definition.required) <= set(roles) | set(attributes), where
            for role, value in roles.items():
                for ref in _refs(value):
                    allowed = set(definition.roles[role])
                    assert _lineage(stack, items[ref]["type"]) & allowed, f"{where} {role}"
    assert set(kinds) == {"entity", "relation", "event", "fact"}


# 4. Failures


def test_missing_quote_fails(tmp_path):
    facts = _copy_facts(tmp_path)

    def change_sentence(data):
        index = next(
            i for i, block in enumerate(data["blocks"]) if block.get("paragraph") == R2_SENTENCE
        )
        data["blocks"][index] = {"paragraph": R2_SENTENCE.replace("2.500.000", "2.600.000")}

    _edit_document(facts, "D2", change_sentence)
    out = tmp_path / "out"
    with pytest.raises(CorpusError) as caught:
        generate(facts, out)
    lines = str(caught.value).splitlines()
    assert "documents/D2.yaml: items[D2.6].quote: not in the rendered text of D2" in lines
    assert (
        "documents/D2.yaml: items[D2.6].attributes.threshold.quote: not in the rendered text of D2"
        in lines
    )
    assert not out.exists()


def test_unfit_item_fails(tmp_path):
    facts = _copy_facts(tmp_path)

    def add_attribute(data):
        metric = next(item for item in data["items"] if item["id"] == "D2.3")
        metric["attributes"] = {"title": {"value": "phụ cấp lưu trú", "quote": "phụ cấp lưu trú"}}

    _edit_document(facts, "D2", add_attribute)
    out = tmp_path / "out"
    with pytest.raises(CorpusError) as caught:
        generate(facts, out)
    lines = str(caught.value).splitlines()
    unfit = [line for line in lines if line.startswith("documents/D2.yaml: items[D2.3].attributes")]
    assert len(unfit) == 1
    assert unfit[0].startswith("documents/D2.yaml: items[D2.3].attributes.title: ")
    assert "`Metric`" in unfit[0]
    assert "`title`" in unfit[0]
    assert not out.exists()


# 5. Running example


def test_running_example():
    for document_id, expected in RUNNING_EXAMPLE.items():
        document = _document(document_id)
        for field in ("language", "issuer", "format", "title", "dates"):
            assert document[field] == expected[field], f"{document_id} {field}"
        text = _text(document)
        for sentence in expected["text"]:
            assert sentence in text, f"{document_id}: {sentence!r}"

    world = _world()
    assert world["alpha"]["name"] == "Công ty CP Alpha"
    assert world["beta"]["name"] == "Công ty CP Beta"
    assert world["alpha.tc"]["scope"] == "alpha"
    assert world["beta.tc"]["scope"] == "beta"
    assert world["alpha.tc"]["name"] == world["beta.tc"]["name"] == "Phòng Tài chính"

    d1, d2, d5 = _items(_document("D1")), _items(_document("D2")), _items(_document("D5"))
    assert d1["D1.6"]["quote"] == "Mức phụ cấp lưu trú là 2.000.000 VND/ngày."
    assert d2["D2.6"]["quote"] == R2_SENTENCE
    assert d5["D5.6"]["quote"] == "Mức phụ cấp lưu trú là 800.000 VND/ngày."
    assert d2["D2.7"]["type"] == "SUPERSEDES"

    d3 = _items(_document("D3"))
    decision = next(item for item in d3.values() if item["type"] == "Decision")
    meeting = d3[decision["roles"]["made_in"]]
    assert meeting["type"] == "Meeting"
    assert meeting["valid_from"] == "2025-12-20"
    assert d3[decision["roles"]["decided_by"]]["world"] == "alpha.ubrr"
    assert d3[decision["roles"]["about"]]["world"] == "alpha.ctp.v2"
    action = next(item for item in d3.values() if item["type"] == "ActionItem")
    assert world[d3[action["roles"]["owner"]]["world"]]["name"] == "Nguyễn Văn An"
    assert action["attributes"]["due_date"]["value"] == "2026-01-10"

    d4 = _items(_document("D4"))
    definition = next(item for item in d4.values() if item["type"] == "Definition")
    assert d4[definition["roles"]["term"]]["world"] == "met.churn"


def test_running_example_statuses():
    graph = _graph()
    assert graph["versions"][ALPHA_LIMIT] == [
        {"closed_at": "2026-01-15", "item": "D1.6", "status": "superseded"},
        {"closed_at": "", "item": "D2.6", "status": "current"},
    ]
    assert graph["versions"][BETA_LIMIT] == [{"closed_at": "", "item": "D5.6", "status": "current"}]
    deleted = graph["deletions"]["D2"]["versions"]
    assert deleted[ALPHA_LIMIT] == [{"closed_at": "", "item": "D1.6", "status": "current"}]
    assert BETA_LIMIT not in deleted
    assert {"from": "alpha.ctp.v2", "item": "D2.7", "to": "alpha.ctp.v1"} in graph["supersedes"]
    entities = graph["entities"]
    assert {"D1.2", "D2.2"} <= set(entities["alpha.tc"])
    assert "D5.2" not in entities["alpha.tc"]
    assert "D5.2" in entities["beta.tc"]
    assert {"D1.3", "D2.3", "D5.3"} <= set(entities["met.luu-tru"])


# 6. Golden set


def test_golden_fields():
    competency_ids = {question.id for question in _stack().competency_questions}
    ids = []
    for entry in _golden():
        assert set(entry) == {"question", "expected_answer", "expected_sources", "tags"}
        tags = entry["tags"]
        assert set(tags) == TAGS
        assert all(isinstance(value, str) for value in tags.values())
        assert tags["qtype"] in QTYPES
        assert tags["lang"] in {"vi", "en"}
        assert tags["origin"] in {"generated", "hand_written"}
        assert (tags["as_of"] != "") == (tags["qtype"] == "as_of"), tags["id"]
        if tags["as_of"]:
            assert ISO_DATE.fullmatch(tags["as_of"])
        if tags["cq"]:
            assert set(tags["cq"].split(",")) <= competency_ids, tags["id"]
        assert isinstance(entry["question"], str)
        assert entry["question"].strip()
        assert isinstance(entry["expected_answer"], str)
        assert entry["expected_answer"].strip()
        sources = entry["expected_sources"]
        assert sources
        assert sources == sorted(sources)
        assert all(isinstance(source, str) for source in sources)
        ids.append(tags["id"])
    assert len(set(ids)) == len(ids)


def test_golden_coverage():
    golden = _golden()
    counts = Counter(entry["tags"]["qtype"] for entry in golden)
    assert {qtype: counts[qtype] for qtype in QTYPES if counts[qtype] < 3} == {}
    hand_written = {
        entry["tags"]["qtype"] for entry in golden if entry["tags"]["origin"] == "hand_written"
    }
    assert hand_written == QTYPES
    covered = {cq for entry in golden for cq in entry["tags"]["cq"].split(",") if cq}
    competency_ids = {question.id for question in _stack().competency_questions}
    assert len(competency_ids) == 14
    assert competency_ids <= covered


def test_golden_running_example():
    by_id = {entry["tags"]["id"]: entry for entry in _golden()}
    q_a, q_b, q_c = by_id["Q-a"], by_id["Q-b"], by_id["Q-c"]

    assert (
        q_a["question"]
        == "Phụ cấp lưu trú theo quy chế công tác phí vào tháng 3/2025 là bao nhiêu?"
    )
    assert q_a["expected_sources"] == ["D1", "D2"]
    assert q_a["tags"]["qtype"] == "as_of"
    assert q_a["tags"]["as_of"] == "2025-03-15"
    assert q_a["tags"]["lang"] == "vi"
    assert "2.000.000 VND/ngày" in q_a["expected_answer"]

    assert q_b["question"] == "Ai thông qua quy chế công tác phí phiên bản 2, khi nào?"
    assert q_b["expected_sources"] == ["D3"]
    assert q_b["tags"]["qtype"] == "meeting_decision"
    assert "Ủy ban Rủi ro" in q_b["expected_answer"]
    assert "20/12/2025" in q_b["expected_answer"]

    assert q_c["question"] == "How is churn rate calculated?"
    assert q_c["expected_sources"] == ["D4"]
    assert q_c["tags"]["qtype"] == "definition"
    assert q_c["tags"]["lang"] == "en"
    assert (
        "customers lost in the period ÷ customers at the start of the period"
        in q_c["expected_answer"]
    )
    for entry in (q_a, q_b, q_c):
        assert entry["tags"]["origin"] == "hand_written"


def test_golden_names_tell_apart():
    """A question about an entity names it so that a same-named entity does not answer.

    Versions of one company's document differ by their version label;
    same-named entities of two companies differ by the company.
    """
    world = _world()

    def label(entity_id, lang):
        entry = world[entity_id]
        return entry.get("labels", {}).get(lang, entry["name"])

    def company(entity_id):
        while "scope" in world[entity_id]:
            entity_id = world[entity_id]["scope"]
        return entity_id

    checked = 0
    for entry in _golden():
        qtype, _, entity_id = entry["tags"]["id"].partition(":")
        if qtype != "entity_all" or entity_id not in world:
            continue
        lang, question = entry["tags"]["lang"], entry["question"]
        name = label(entity_id, lang)
        for rival in (other for other in world if other != entity_id):
            if label(rival, lang) != name:
                continue
            if company(rival) != company(entity_id):
                assert label(company(entity_id), lang) in question, entry["tags"]["id"]
            else:
                version = world[entity_id]["attributes"]["version_label"]
                expected = f"phiên bản {version}" if lang == "vi" else f"version {version}"
                assert expected in question, entry["tags"]["id"]
            checked += 1
    assert checked


def test_golden_sources_exist():
    document_ids = {document["id"] for document in _documents()}
    cited = {source for entry in _golden() for source in entry["expected_sources"]}
    assert cited
    assert cited <= document_ids


# 7. Planted situations


def test_corpus_plants():
    world = _world()
    graph = _graph()
    groups = {group_id: _group_parts(group_id) for group_id in graph["versions"]}

    def statuses(group_id):
        return [member["status"] for member in graph["versions"][group_id]]

    owner_groups = [group_id for group_id, (kind, _) in groups.items() if kind == "OWNER_OF"]
    assert any("superseded" in statuses(group_id) for group_id in owner_groups)
    assert any("conflicting" in statuses(group_id) for group_id in owner_groups)

    issuers_by_term = {}
    for kind, parts in groups.values():
        if kind == "Definition":
            issuers_by_term.setdefault(parts["term"], set()).add(parts["issuer"])
    assert any(len(issuers) >= 2 for issuers in issuers_by_term.values())
    definitions = [group_id for group_id, (kind, _) in groups.items() if kind == "Definition"]
    assert any("superseded" in statuses(group_id) for group_id in definitions)

    limits = {}
    for kind, parts in groups.values():
        if kind == "Requirement" and "metric" in parts:
            limits.setdefault(parts["metric"], set()).add(parts["issuer"])
    assert any(len(issuers) >= 2 for issuers in limits.values())

    def same_name_two_scopes(type_name, unit_only=False):
        scopes = {}
        for entry in world.values():
            if entry["type"] != type_name or "scope" not in entry:
                continue
            if unit_only and entry.get("attributes", {}).get("category") == "company":
                continue
            scopes.setdefault(entry["name"], set()).add(entry["scope"])
        return any(len(found) >= 2 for found in scopes.values())

    assert same_name_two_scopes("Policy")
    assert same_name_two_scopes("Organization", unit_only=True)
    assert same_name_two_scopes("Person")

    figures = {}
    for kind, parts in groups.values():
        if kind == "ReportedFigure" and "basis" in parts:
            key = (parts["metric"], parts["subject"], parts.get("period"))
            figures.setdefault(key, set()).add(parts["basis"])
    assert any({"actual", "target"} <= bases for bases in figures.values())

    assert graph["text_in"]
    superseded_types = set()
    for document in _documents():
        items = _items(document)
        for link in (item for item in document["items"] if item["type"] == "SUPERSEDES"):
            superseded_types.add(items[link["to"]]["type"])
    assert {"Policy", "Procedure"} <= superseded_types

    surfaces = {}
    for document in _documents():
        for item in document["items"]:
            if item["kind"] == "entity":
                surfaces.setdefault(item["world"], set()).add(item["surface"])
    assert any(len(found) >= 3 for found in surfaces.values())

    all_items = [item for document in _documents() for item in document["items"]]
    meetings = [item for item in all_items if item["type"] == "Meeting"]
    assert any({"chair", "attendee"} <= set(item["roles"]) for item in meetings)
    assert any("made_in" in item["roles"] for item in all_items if item["type"] == "Decision")
    actions = [item for item in all_items if item["type"] == "ActionItem"]
    assert any({"due_date", "status"} <= set(item.get("attributes", {})) for item in actions)


# 8. Text form and fictional names


def test_text_form():
    files = _tree(GENERATED)
    assert len(files) >= 4
    for name, content in files.items():
        text = content.decode("utf-8")
        assert unicodedata.is_normalized("NFC", text), name
        assert "\r" not in text, name
        assert text.endswith("\n"), name
        assert not text.endswith("\n\n"), name


def test_fictional_only():
    world = _world()

    def company(entity_id):
        seen = set()
        while entity_id not in seen:
            seen.add(entity_id)
            if entity_id in FICTIONAL_COMPANIES:
                return entity_id
            entity_id = world[entity_id].get("scope", entity_id)
        return None

    for entity_id, company_name in FICTIONAL_COMPANIES.items():
        assert world[entity_id]["name"] == company_name
    issued_codes = {
        entry.get("scope")
        for entry in world.values()
        if entry["type"] == "Work" and "code" in entry.get("attributes", {})
    }
    for entity_id, entry in world.items():
        if entry["type"] not in {"Organization", "Person"}:
            continue
        if entity_id in PUBLIC_AUTHORITIES:
            assert entry["name"] == PUBLIC_AUTHORITIES[entity_id]
            assert entity_id in issued_codes
            continue
        assert company(entity_id) is not None, entity_id

    texts = [(path, path.read_text(encoding="utf-8")) for path in sorted(GENERATED.rglob("*.*"))]
    texts += [(path, path.read_text(encoding="utf-8")) for path in sorted(FACTS.rglob("*.yaml"))]
    domains = {match[1] for _, text in texts for match in EMAIL.finditer(text)}
    assert domains
    assert all(domain.endswith(".example") for domain in domains), domains


# 9. Version rules


def test_closed_at_next_start():
    """A superseded member closes at the next later start, unless it states its own end."""
    graph = _graph()
    items = _located_items()
    stated_ends = 0
    for members in graph["versions"].values():
        starts = {member["item"]: _start(*items[member["item"]]) for member in members}
        for member in members:
            if member["status"] != "superseded":
                continue
            _, item = items[member["item"]]
            if item.get("valid_to"):
                assert member["closed_at"] == "", member["item"]
                stated_ends += 1
            else:
                own = starts[member["item"]]
                later = min(start for start in starts.values() if start > own)
                assert member["closed_at"] == later, member["item"]
    assert stated_ends
    assert graph["versions"]["OWNER_OF:object=alpha.crm"] == [
        {"closed_at": "", "item": "D35.9", "status": "superseded"},
        {"closed_at": "2026-06-01", "item": "D36.6", "status": "superseded"},
        {"closed_at": "", "item": "D41.4", "status": "current"},
    ]


def test_fact_issuer_is_source_scope():
    """A fact's version issuer is the scope of its source, else the document's issuer.

    Engine brief §3.2. D14 is issued by Phòng Tài chính, but its guidance is
    scoped by Alpha, so its requirement joins Alpha's group.
    """
    stack = _stack()
    world = _world()
    groups = _item_groups()
    checked = differs = 0
    for document in _documents():
        items = _items(document)
        for item in document["items"]:
            if item["kind"] != "fact" or "issuer" not in stack.facts[item["type"]].version_key:
                continue
            source = item.get("roles", {}).get("source")
            scope = world[items[_refs(source)[0]]["world"]].get("scope") if source else None
            expected = scope or document["issuer"]
            _, parts = _group_parts(groups[item["id"]])
            assert parts["issuer"] == expected, item["id"]
            checked += 1
            differs += expected != document["issuer"]
    assert checked
    assert differs
    assert _document("D14")["issuer"] == "alpha.tc"
    members = _graph()["versions"]["Requirement:issuer=alpha;metric=met.han-nop"]
    assert "D14.9" in [member["item"] for member in members]


def test_deletions_replay():
    """A deletion lists each group it changes with the members left, and an emptied group as []."""
    graph = _graph()
    emptied = 0
    left = []
    for document_id, deletion in graph["deletions"].items():
        listed = deletion["versions"]
        for group_id, members in graph["versions"].items():
            kept = [m["item"] for m in members if not m["item"].startswith(f"{document_id}.")]
            where = f"{document_id} {group_id}"
            if len(kept) == len(members):
                assert group_id not in listed, where
            elif not kept:
                assert listed.get(group_id) == [], where
                emptied += 1
            elif group_id in listed:
                assert [member["item"] for member in listed[group_id]] == kept, where
                left.append(len(kept))
    assert emptied
    assert max(left) >= 2
    # Deleting the newest of three versions makes the middle one current again.
    assert graph["deletions"]["D41"]["versions"] == {
        "OWNER_OF:object=alpha.crm": [
            {"closed_at": "", "item": "D35.9", "status": "superseded"},
            {"closed_at": "", "item": "D36.6", "status": "current"},
        ]
    }


def _content(document: dict, item: dict) -> tuple:
    """What a relation or statement says: its ends or roles as world ids, and its values."""
    items = _items(document)
    values = tuple(sorted((name, a["value"]) for name, a in item.get("attributes", {}).items()))
    if item["kind"] == "relation":
        return items[item["from"]]["world"], items[item["to"]]["world"], values
    roles = tuple(
        sorted(
            (role, tuple(sorted(items[ref]["world"] for ref in _refs(value))))
            for role, value in item["roles"].items()
        )
    )
    return roles, values


def test_no_equal_content_in_a_group():
    """No two members of a group say the same thing.

    The engine makes equal content one version backed by several sources
    (engine brief §3.2). The generator gives each member its own status, so
    the fact table never plants equal content in one group.
    """
    located = _located_items()
    for group_id, members in _graph()["versions"].items():
        contents = Counter(_content(*located[member["item"]]) for member in members)
        repeated = [content for content, count in contents.items() if count > 1]
        assert repeated == [], group_id


# 10. Generated questions


def _generated(qtype: str) -> dict[str, dict]:
    """The generated questions of one type, by the item or entity in their id."""
    return {
        entry["tags"]["id"].partition(":")[2]: entry
        for entry in _golden()
        if entry["tags"]["origin"] == "generated" and entry["tags"]["qtype"] == qtype
    }


def test_golden_single_and_historical():
    """single_fact asks about each figure or requirement alone in its group;
    historical_figure about each current figure with a period."""
    versions = _graph()["versions"]
    groups = _item_groups()
    statuses = {m["item"]: m["status"] for members in versions.values() for m in members}
    single, historical = set(), set()
    for _, item in _located_items().values():
        if item["kind"] != "fact":
            continue
        group_id = groups.get(item["id"])
        alone = group_id is not None and len(versions[group_id]) == 1
        if item["type"] in {"ReportedFigure", "Requirement"} and alone:
            single.add(item["id"])
        if (
            item["type"] == "ReportedFigure"
            and "period" in item.get("attributes", {})
            and statuses.get(item["id"]) == "current"
        ):
            historical.add(item["id"])
    assert single
    assert historical
    assert set(_generated("single_fact")) == single
    assert set(_generated("historical_figure")) == historical


def test_golden_as_of_dates():
    """Each member of a group of two or more that does not conflict gets an as_of question.

    It is dated 30 days after the member's start, so it asks which version
    held, not what happens on a boundary day; when the member ends sooner,
    it is dated at the start.
    """
    items = _located_items()
    expected = {}
    superseded = 0
    for members in _graph()["versions"].values():
        if len(members) < 2:
            continue
        for member in members:
            if member["status"] == "conflicting":
                continue
            document, item = items[member["item"]]
            start = date.fromisoformat(_start(document, item))
            end = member["closed_at"] or item.get("valid_to")
            day = start + timedelta(days=30)
            if end and day.isoformat() >= end:
                day = start
            expected[member["item"]] = day.isoformat()
            superseded += member["status"] == "superseded"
    assert superseded
    as_of = {item_id: entry["tags"]["as_of"] for item_id, entry in _generated("as_of").items()}
    assert as_of == expected
