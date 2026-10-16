"""The golden set: generated questions, then the hand-written ones (contracts/corpus.md).

Each question type has a template per language, filled from the fact
table. Answers are the items' own quotes with their document ids, so
figures are copied, never reformatted. A question's `cq` lists the
competency questions whose needed types all occur among the items its
answer uses. Generated ids are `<qtype>:<item id>`, or `<qtype>:<world id>`
for a question about an entity or a term.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, timedelta
from typing import Any

from tenetrag.packs import PackStack
from tests.support.corpus.checks import company, refs
from tests.support.corpus.derive import Item, issuer_of, position, start_of, world_ids
from tests.support.corpus.facts import (
    Document,
    EntityItem,
    FactTable,
    RelationItem,
    StatementItem,
)

QTYPES = (
    "single_fact",
    "entity_all",
    "meeting_decision",
    "definition",
    "historical_figure",
    "as_of",
    "conflicting_versions",
    "cross_lingual",
)
MONTHS = (
    *("January", "February", "March", "April", "May", "June"),
    *("July", "August", "September", "October", "November", "December"),
)
BASIS = {
    "vi": {"actual": "thực tế", "target": "kế hoạch", "forecast": "dự báo", "budget": "ngân sách"},
    "en": {"actual": "actual", "target": "target", "forecast": "forecast", "budget": "budgeted"},
}
# An as-of question asks about a date this far into a version's interval.
AS_OF_OFFSET = timedelta(days=30)
# An entity mentioned in this many documents gets an `entity_all` question.
ENTITY_ALL_DOCUMENTS = 3


def format_date(iso: str, lang: str) -> str:
    """15/03/2025 in Vietnamese, 15 March 2025 in English."""
    day = date.fromisoformat(iso)
    if lang == "vi":
        return f"{day.day:02d}/{day.month:02d}/{day.year}"
    return f"{day.day} {MONTHS[day.month - 1]} {day.year}"


def _sentence(text: str) -> str:
    return text[:1].upper() + text[1:]


def _group_parts(group_id: str) -> tuple[str, dict[str, str]]:
    type_name, _, key = group_id.partition(":")
    return type_name, dict(part.split("=", 1) for part in key.split(";") if part)


class _Golden:
    def __init__(self, table: FactTable, graph: dict[str, Any], stack: PackStack) -> None:
        self.table = table
        self.graph = graph
        self.stack = stack
        self.world_of = world_ids(table)
        self.items: dict[str, Item] = {}
        self.document_of: dict[str, Document] = {}
        for document in table.documents:
            for item in document.items:
                self.items[item.id] = item
                self.document_of[item.id] = document
        self.group_of: dict[str, str] = {}
        self.member_of: dict[str, dict[str, str]] = {}
        for group, members in graph["versions"].items():
            for member in members:
                self.group_of[member["item"]] = group
                self.member_of[member["item"]] = member
        self.questions: list[tuple[tuple[int, int], int, dict[str, Any]]] = []
        self.named: dict[tuple[str, str], list[str]] = {}
        for world_id in table.world.entities:
            for lang in ("vi", "en"):
                self.named.setdefault((lang, self.plain_label(world_id, lang)), []).append(world_id)

    # Names

    def plain_label(self, world_id: str, lang: str) -> str:
        entity = self.table.world.entities[world_id]
        return entity.labels.get(lang, entity.name)

    def label(self, world_id: str, lang: str, *, qualify: bool = True) -> str:
        """How a question names a world entity, told apart from entities sharing its label.

        Versions of one company's document add their version label; entities
        of two companies add the company.
        """
        name = self.plain_label(world_id, lang)
        rivals = [other for other in self.named[lang, name] if other != world_id]
        if not qualify or not rivals:
            return name
        home = company(self.table, world_id)
        version = self.table.world.entities[world_id].attributes.get("version_label")
        if version is not None and any(company(self.table, r) == home for r in rivals):
            name += f" phiên bản {version}" if lang == "vi" else f" (version {version})"
        if any(company(self.table, rival) != home for rival in rivals):
            owner = self.plain_label(home, lang)
            name += f" của {owner}" if lang == "vi" else f" of {owner}"
        return name

    def ref_label(self, ref: str, lang: str, *, qualify: bool = True) -> str:
        item = self.items[ref]
        if isinstance(item, EntityItem):
            return self.label(item.world, lang, qualify=qualify)
        title = item.attributes.get("title")
        return title.value if title is not None else item.type

    def role_label(self, item: StatementItem, role: str, lang: str) -> str | None:
        if role not in item.roles:
            return None
        joiner = " và " if lang == "vi" else " and "
        return joiner.join(self.ref_label(ref, lang) for ref in refs(item.roles[role]))

    def value(self, item: Item, name: str) -> str | None:
        attribute = item.attributes.get(name)
        return attribute.value if attribute is not None else None

    def lang_of(self, item_id: str) -> str:
        """English for an English document; Vietnamese for a Vietnamese or mixed one."""
        return "en" if self.document_of[item_id].language == "en" else "vi"

    # Answers, sources and competency questions

    def answer(self, item_ids: list[str]) -> str:
        """Each quote with its document id, as `quote (D1); quote (D2).`

        Only a quote's final full stop is dropped, so figures stay verbatim.
        """
        parts = [
            f"{self.items[item_id].quote.removesuffix('.')} ({self.document_of[item_id].id})"
            for item_id in item_ids
        ]
        return "; ".join(parts) + "."

    def sources(self, item_ids: list[str]) -> list[str]:
        return sorted({self.document_of[item_id].id for item_id in item_ids})

    def cq(self, item_ids: list[str], extra: Iterable[str] = ()) -> str:
        types = set(extra)
        for item_id in item_ids:
            item = self.items[item_id]
            types.add(item.type)
            linked: list[str] = []
            if isinstance(item, RelationItem):
                linked = [item.from_, item.to]
            elif isinstance(item, StatementItem):
                linked = [ref for value in item.roles.values() for ref in refs(value)]
            types |= {self.items[ref].type for ref in linked}
        return ",".join(
            question.id
            for question in self.stack.competency_questions
            if set(question.needs) <= types
        )

    def add(
        self,
        qtype: str,
        anchor: str,
        key: str,
        lang: str,
        question: str,
        answer_items: list[str],
        *,
        as_of: str = "",
        source_items: list[str] | None = None,
        extra_types: Iterable[str] = (),
        answer: str | None = None,
    ) -> None:
        entry = {
            "expected_answer": answer if answer is not None else self.answer(answer_items),
            "expected_sources": self.sources(source_items or answer_items),
            "question": question,
            "tags": {
                "as_of": as_of,
                "cq": self.cq(answer_items, extra_types),
                "id": f"{qtype}:{key}",
                "lang": lang,
                "origin": "generated",
                "qtype": qtype,
            },
        }
        self.questions.append((position(anchor), QTYPES.index(qtype), entry))

    # Templates

    def requirement(self, item: StatementItem, lang: str) -> str:
        document = self.document_of[item.id]
        source_ref = refs(item.roles["source"])[0]
        # The template adds the version and the issuer itself.
        source = self.ref_label(source_ref, lang, qualify=False)
        source_item = self.items[source_ref]
        if isinstance(source_item, EntityItem):
            version = self.table.world.entities[source_item.world].attributes.get("version_label")
            if version is not None:
                source += f" (phiên bản {version})" if lang == "vi" else f" (version {version})"
        issuer = self.label(issuer_of(self.table, document, item, self.world_of), lang)
        topic = self._topic(item, lang, with_source=False)
        if lang == "vi":
            return f"{_sentence(source)} của {issuer} quy định gì{topic}?"
        return f"What does {issuer}'s {source} require{topic}?"

    def _topic(self, item: StatementItem, lang: str, *, with_source: bool) -> str:
        metric = self.role_label(item, "metric", lang)
        if metric is None and with_source:
            metric = self.role_label(item, "source", lang)
        applies = self.role_label(item, "applies_to", lang)
        condition = self.value(item, "condition")
        words = {"vi": (" về ", " cho ", " khi "), "en": (" on ", " for ", " when ")}[lang]
        return "".join(
            word + part
            for word, part in zip(words, (metric, applies, condition), strict=True)
            if part is not None
        )

    def figure(self, item: StatementItem, lang: str) -> tuple[str, str, str, str]:
        """Metric, subject, period phrase and basis phrase of a reported figure."""
        metric = self.role_label(item, "metric", lang) or ""
        subject = self.role_label(item, "subject", lang) or ""
        period, basis = self.value(item, "period"), self.value(item, "basis")
        if lang == "vi":
            return (
                metric,
                subject,
                f" trong {period}" if period else "",
                f" ({BASIS['vi'][basis]})" if basis else "",
            )
        return (
            metric,
            subject,
            f" for {period}" if period else "",
            f"{BASIS['en'][basis]} " if basis else "",
        )

    def definition(self, item: StatementItem, lang: str) -> str:
        title = self.document_of[item.id].title
        term = self.role_label(item, "term", lang)
        if lang == "vi":
            return f"Theo {title}, {term} được định nghĩa thế nào?"
        return f"How does {title} define {term}?"

    def describe_group(self, group: str, item: Item, lang: str) -> dict[str, str]:
        """The words a question about a version group uses."""
        type_name, parts = _group_parts(group)
        words = {"type": type_name}
        if "issuer" in parts:
            words["issuer"] = self.label(parts["issuer"], lang)
        if isinstance(item, RelationItem):
            words["object"] = self.label(self.world_of[item.to], lang)
        elif type_name == "Requirement":
            words["topic"] = self._topic(item, lang, with_source=True)
        elif type_name == "Definition":
            words["term"] = self.role_label(item, "term", lang) or ""
        elif type_name == "ReportedFigure":
            metric, subject, period, basis = self.figure(item, lang)
            words.update(metric=metric, subject=subject, period=period, basis=basis)
        return words

    def as_of_question(self, group: str, item: Item, lang: str, day: str) -> str:
        words = self.describe_group(group, item, lang)
        when = format_date(day, lang)
        type_name = words["type"]
        if lang == "vi":
            if type_name == "Requirement":
                return f"Vào ngày {when}, {words['issuer']} quy định gì{words['topic']}?"
            if type_name == "Definition":
                return f"Vào ngày {when}, {words['issuer']} định nghĩa {words['term']} thế nào?"
            if type_name == "ReportedFigure":
                return (
                    f"Vào ngày {when}, {words['metric']} của {words['subject']}"
                    f"{words['period']}{words['basis']} được báo cáo là bao nhiêu?"
                )
            if type_name == "OWNER_OF":
                return f"Vào ngày {when}, ai phụ trách {words['object']}?"
        else:
            if type_name == "Requirement":
                return f"On {when}, what did {words['issuer']} require{words['topic']}?"
            if type_name == "Definition":
                return f"On {when}, how did {words['issuer']} define {words['term']}?"
            if type_name == "ReportedFigure":
                return (
                    f"On {when}, what was the reported {words['basis']}{words['metric']} "
                    f"of {words['subject']}{words['period']}?"
                )
            if type_name == "OWNER_OF":
                return f"On {when}, who owned {words['object']}?"
        raise ValueError(f"no as_of template for `{type_name}`")

    def conflict_question(self, group: str, item: Item, lang: str) -> str:
        words = self.describe_group(group, item, lang)
        type_name = words["type"]
        issuer = words.get("issuer", "")
        if lang == "vi":
            if type_name == "Requirement":
                return f"Các tài liệu của {issuer} quy định khác nhau thế nào{words['topic']}?"
            if type_name == "Definition":
                return f"Các tài liệu của {issuer} định nghĩa {words['term']} khác nhau thế nào?"
            if type_name == "ReportedFigure":
                return (
                    f"Các nguồn báo cáo {words['metric']} của {words['subject']}"
                    f"{words['period']}{words['basis']} khác nhau thế nào?"
                )
            if type_name == "OWNER_OF":
                return f"Các tài liệu nói khác nhau thế nào về người phụ trách {words['object']}?"
        else:
            if type_name == "Requirement":
                return f"How do {issuer}'s documents differ on what they require{words['topic']}?"
            if type_name == "Definition":
                return f"How do {issuer}'s documents define {words['term']} differently?"
            if type_name == "ReportedFigure":
                return (
                    f"How do sources differ on the {words['basis']}{words['metric']} "
                    f"of {words['subject']}{words['period']}?"
                )
            if type_name == "OWNER_OF":
                return f"How do the documents differ on who owns {words['object']}?"
        raise ValueError(f"no conflicting_versions template for `{type_name}`")

    # Question types

    def by_item(self) -> None:
        for document in self.table.documents:
            for item in document.items:
                if isinstance(item, StatementItem):
                    self.statement(item)

    def statement(self, item: StatementItem) -> None:
        lang = self.lang_of(item.id)
        other = "en" if lang == "vi" else "vi"
        group = self.group_of.get(item.id)
        alone = group is not None and len(self.graph["versions"][group]) == 1
        status = self.member_of.get(item.id, {}).get("status")
        if item.type == "ReportedFigure":
            metric, subject, period, basis = self.figure(item, lang)
            title = self.document_of[item.id].title
            if alone:
                question = (
                    f"Theo {title}, {metric} của {subject}{period}{basis} là bao nhiêu?"
                    if lang == "vi"
                    else f"According to {title}, what is the {basis}{metric} of {subject}{period}?"
                )
                self.add("single_fact", item.id, item.id, lang, question, [item.id])
            if self.value(item, "period") is not None and status == "current":
                period_value = self.value(item, "period")
                question = (
                    _sentence(f"{metric} của {subject} trong {period_value}{basis} là bao nhiêu?")
                    if lang == "vi"
                    else f"What was the {basis}{metric} of {subject} in {period_value}?"
                )
                self.add("historical_figure", item.id, item.id, lang, question, [item.id])
        elif item.type == "Requirement":
            if alone:
                self.add(
                    "single_fact", item.id, item.id, lang, self.requirement(item, lang), [item.id]
                )
            self.add(
                "cross_lingual", item.id, item.id, other, self.requirement(item, other), [item.id]
            )
        elif item.type == "Definition":
            self.add("definition", item.id, item.id, lang, self.definition(item, lang), [item.id])
            self.add(
                "cross_lingual", item.id, item.id, other, self.definition(item, other), [item.id]
            )
        elif item.type == "Decision" and "made_in" in item.roles:
            self.meeting_decision(item, lang)

    def meeting_decision(self, item: StatementItem, lang: str) -> None:
        meeting = self.items[refs(item.roles["made_in"])[0]]
        document = self.document_of[item.id]
        held = getattr(meeting, "valid_from", None) or document.dates.get("held_on")
        when = format_date(held, lang) if held else None
        about = self.role_label(item, "about", lang)
        holder = self.role_label(item, "decided_by", lang)
        if lang == "vi":
            question = (
                "Cuộc họp"
                + (f" của {holder}" if holder else "")
                + (f" ngày {when}" if when else "")
                + f" đã quyết định gì về {about}?"
            )
        else:
            question = (
                "What did the meeting"
                + (f" of {holder}" if holder else "")
                + (f" on {when}" if when else "")
                + f" decide about {about}?"
            )
        self.add("meeting_decision", item.id, item.id, lang, question, [item.id])

    def entity_all(self) -> None:
        mentions: dict[str, list[str]] = {}
        for item_id, world_id in self.world_of.items():
            mentions.setdefault(world_id, []).append(item_id)
        for world_id, item_ids in mentions.items():
            documents = self.sources(item_ids)
            if len(documents) < ENTITY_ALL_DOCUMENTS:
                continue
            first = min(item_ids, key=position)
            lang = self.lang_of(first)
            name = self.label(world_id, lang)
            mentioned = set(item_ids)
            statements = [
                item_id for item_id, item in self.items.items() if self._links(item) & mentioned
            ]
            entity_type = self.table.world.entities[world_id].type
            question = (
                f"Các tài liệu cho biết gì về {name}?"
                if lang == "vi"
                else f"What do the documents say about {name}?"
            )
            fallback = (
                f"{name} được nhắc đến trong {', '.join(documents)}."
                if lang == "vi"
                else f"{name} is mentioned in {', '.join(documents)}."
            )
            self.add(
                "entity_all",
                first,
                world_id,
                lang,
                question,
                statements,
                source_items=item_ids,
                extra_types={entity_type},
                answer=None if statements else fallback,
            )

    def _links(self, item: Item) -> set[str]:
        if isinstance(item, RelationItem):
            return {item.from_, item.to}
        if isinstance(item, StatementItem):
            return {ref for value in item.roles.values() for ref in refs(value)}
        return set()

    def as_of(self) -> None:
        for group, members in self.graph["versions"].items():
            if len(members) < 2:
                continue
            item_ids = [member["item"] for member in members]
            for member in members:
                if member["status"] == "conflicting":
                    continue
                item = self.items[member["item"]]
                start = start_of(item, self.document_of[item.id])
                assert start is not None
                end = member["closed_at"] or getattr(item, "valid_to", None)
                day = date.fromisoformat(start) + AS_OF_OFFSET
                if end and day.isoformat() >= end:
                    day = date.fromisoformat(start)
                lang = self.lang_of(item.id)
                question = self.as_of_question(group, item, lang, day.isoformat())
                self.add(
                    "as_of",
                    item.id,
                    item.id,
                    lang,
                    question,
                    [item.id],
                    as_of=day.isoformat(),
                    source_items=item_ids,
                )

    def conflicting(self) -> None:
        for group, members in self.graph["versions"].items():
            conflicting = [m["item"] for m in members if m["status"] == "conflicting"]
            if not conflicting:
                continue
            first = conflicting[0]
            lang = self.lang_of(first)
            question = self.conflict_question(group, self.items[first], lang)
            self.add("conflicting_versions", first, first, lang, question, conflicting)

        definitions: dict[str, list[str]] = {}
        for group, members in self.graph["versions"].items():
            type_name, parts = _group_parts(group)
            if type_name != "Definition" or "term" not in parts:
                continue
            current = [m["item"] for m in members if m["status"] == "current"]
            definitions.setdefault(parts["term"], []).extend(current)
        for term, item_ids in definitions.items():
            item_ids = sorted(item_ids, key=position)
            texts = {self.value(self.items[item_id], "text") for item_id in item_ids}
            if len(item_ids) < 2 or len(texts) < 2:
                continue
            lang = self.lang_of(item_ids[0])
            name = self.label(term, lang)
            question = (
                _sentence(f"{name} được các nguồn định nghĩa khác nhau thế nào?")
                if lang == "vi"
                else f"How do sources define {name} differently?"
            )
            self.add("conflicting_versions", item_ids[0], term, lang, question, item_ids)

    def hand_written(self) -> list[dict[str, Any]]:
        return [
            {
                "expected_answer": question.expected_answer,
                "expected_sources": sorted(set(question.expected_sources)),
                "question": question.question,
                "tags": {
                    "as_of": question.as_of or "",
                    "cq": ",".join(question.cq),
                    "id": question.id,
                    "lang": question.lang,
                    "origin": "hand_written",
                    "qtype": question.qtype,
                },
            }
            for question in self.table.golden.questions
        ]


def golden(table: FactTable, graph: dict[str, Any], stack: PackStack) -> list[dict[str, Any]]:
    """Generated questions in fact-table order, then the hand-written ones in file order."""
    builder = _Golden(table, graph, stack)
    builder.by_item()
    builder.entity_all()
    builder.as_of()
    builder.conflicting()
    ordered = sorted(
        builder.questions,
        key=lambda entry: (entry[0], entry[1], entry[2]["tags"]["id"]),
    )
    return [entry for _, _, entry in ordered] + builder.hand_written()
