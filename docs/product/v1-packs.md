# v1 default packs — schemas (2026-10-04)

Status: `core` and `enterprise-docs` ship with the SDK as version 1, in
[core.yaml](../../src/tenetrag/packs/shipped/core.yaml) and
[enterprise-docs.yaml](../../src/tenetrag/packs/shipped/enterprise-docs.yaml),
with their identity cases beside them
([specs/002-packs-and-corpus](../../specs/002-packs-and-corpus/spec.md));
those files are the source of truth and this page keeps the reasoning.
[finance.yaml](packs/finance.yaml) stays a draft until M4, and its cases
are in [tests/fixtures/identity/](../../tests/fixtures/identity/finance.cases.yaml). The format
and the design workflow are in [domain-packs.md](domain-packs.md), and the
evidence is in [domain-schemas.md](../reference/domain-schemas.md).

## At a glance

| Pack or stack | For | Types the LLM sees | CQs |
|---|---|---|---|
| `core` | every corpus | 7 entities, 1 event, 2 facts (+1 off), 6 relations = 16 | 6 |
| `enterprise-docs` | internal documents: policies, procedures, minutes, decisions, tasks, projects, systems | 29 | 8 + core |
| `finance` | company and market disclosures: filings, ownership, ratings, securities | 26 | 9 + core |
| `[enterprise-docs, finance]` | both | 39 | 23 |

The counts come from `load_pack`, `check_coverage` and `compile_schema`
(measured on 2026-10-21). Every competency question (CQ) of each stack
passes the coverage check. Every stack compiles to 52 properties, under
the limit of 64, with no `$ref`, `anyOf`, `oneOf`, `allOf` or `pattern`.
More types grow the enums and the prompt, not the property count. A user pack adds its own
types on top of these, so extraction for a full stack will likely run in
passes (open question 2 in
[domain-packs.md](domain-packs.md#open-questions)).

## What changed from the first draft

1. **`Metric`, `Definition` and `ReportedFigure` move into `core`.**
   Definitions that change over time and figures with their period and
   source appear in every domain. Internal documents carry KPI formulas
   and past figures, not only filings. A `Metric` node joins the two: "how
   is M calculated" and "what was M last year" start from the same node.
   None of the glossary or semantic-layer products read keeps dated
   versions of a definition
   ([evidence](../reference/domain-schemas.md#products-glossaries-and-semantic-layers)).
2. **The `Definition` fact replaces the `DEFINES` relation.** A relation
   cannot hold the definition text, the formula or several versions. Each
   source's definition is its own fact with its own time, so conflicting
   definitions are all returned, newest marked.
3. **`Statement` is off by default** (`extract: false`). MS GraphRAG ships
   claim extraction off because the prompts need tuning per corpus
   ([evidence](../reference/domain-schemas.md#cross-domain-types)).
4. **`Concept` is limited to terms the text defines.** There is no `Topic`
   type. Microsoft retired Viva Topics, a topic-centred graph, in 2025.
   Pruning about 40 % of LLM-extracted entities and relations improved four
   graph-RAG methods in one preprint
   ([evidence](../reference/domain-schemas.md#cross-domain-types)).
5. **Sub-kinds are enums:** `Place.kind`, `Work.kind`, `Product.kind`.
   Few-NERD merged country, province and city into one class because
   context rarely separates them.
6. **Positions stay a relation** (`HOLDS_POSITION` with a verbatim
   `title`), not a `Post` node. W3C ORG and Wikidata both support either
   shape, and no study compares them for LLM extraction.
7. **`enterprise-docs` stays generic.** It versions `Policy` and
   `Procedure`, and lets a `Requirement` set a limit on a metric. Campaigns,
   customer segments and product terms are common in companies that sell to
   customers, but not in every organization, so they move to user packs
   ([industry packs](#industry-packs-such-as-banking)).
8. **`finance` narrows to company and market disclosures.** `loan` leaves
   `Instrument.kind`. `ReportedFigure` gains normalization fields, and
   events gain status and scope fields.
9. **Format additions** (now in [domain-packs.md](domain-packs.md#pack-format)):
   - composite identity keys;
   - roles that point to events;
   - the `extract` flag;
   - the `bool` range;
   - the rule that only the pack defining a type sets its `required` fields.
10. **Claims are now called facts.** The pack section is `facts:` and the
    node kind is Fact. A fact still records what one source states, so two
    sources that disagree give two facts. An edge between two entities is a
    relation. The author chose the plainer word.
11. **Identity by scope, keys and vetoes** (2026-10-06,
    [ADR 0016](../decisions/0016-identify-entities-by-scope-keys-and-vetoes.md)).
    A name no longer identifies an entity. Each type declares whose thing
    it is, which attributes prove two mentions the same, and which prove
    them different ([identity fields](domain-packs.md#identity-fields)).
    Without this, a second company's "Quy chế công tác phí" and
    "Phòng Tài chính" merged into the first company's, and its limit
    superseded the first company's. The per-type choices are in the notes
    below, and the table in
    [engine brief §2.6](engine-brief.md#26-resolve-entities-e8) lists them
    all.

## `core`

[core.yaml](../../src/tenetrag/packs/shipped/core.yaml)

- **Entities:** `Person`, `Organization`, `Place`, `Work`, `Product`,
  `Metric`, `Concept`.
- **Event:** the `Event` parent, with roles `participant` and `location`
  and a point time. A subtype may state its own time.
- **Facts:** `Definition` (`term`, `defined_by`; `text`, `formula`,
  `scope`) and `ReportedFigure` (`metric`, `subject`; `value`, `unit`,
  `period`, `basis`: actual, target, forecast or budget). `Statement`, a
  point in time, is off by default.
- **Relations:** `MEMBER_OF`, `HOLDS_POSITION`, `PART_OF`, `LOCATED_IN`,
  `ISSUED_BY`, `OFFERS`.

Notes:
- `Work` is a document the text names, such as a regulation or a standard.
  The indexed file is the engine's `Document`. Decided on 2026-10-04: when
  a `Work`'s code or title matches an indexed document exactly, the engine
  adds a `TEXT_IN` edge to it (`document_link`, also set on `Policy` and
  `Procedure`).
- `ReportedFigure.basis` separates targets and budgets from actuals. Plans
  in internal documents are full of targets, and mixing the two gives wrong
  answers.
- `OFFERS` (organization → product) recurs in FinDKG, FinRED and
  FinReflectKG as "produces" or "product of".
- Literals stay attributes. The not-an-entity list adds quantity, URL,
  email and phone.
- **Identity.** `core` holds only the rules that hold in every domain,
  since a child pack can tighten identity but never loosen it
  ([ADR 0023](../decisions/0023-keep-only-identity-rules-true-in-every-domain-in-core.md)).
  - `Person`: no scope, since an employer changes over a life. The key is
    email, but a hit whose names clash is linked by `same_as`, not
    merged, since a mailbox can be shared. `born_on` is a veto. A name is
    only evidence: a shared name merges only when the unit (`MEMBER_OF`)
    or the title (`HOLDS_POSITION`) at the same organization matches,
    at overlapping times, else the LLM confirms. A person who changed
    jobs is linked by `same_as`.
  - `Organization`: a company has no scope. Its registration number is a
    key and a veto, and so is its founding date. A unit (category `unit`)
    is scoped by its parent, and its name is a key only within it.
  - `Work`: scoped by its issuer, who issued or wrote it, not a
    publisher. A code that names its issuer, such as "39/2016/TT-NHNN",
    matches without the scope.
  - `Product` and `Place`: scoped by provider and parent place. A
    provider is an organization or a person, never a reseller. A place
    or product that moves under another parent splits; dated scopes are
    an [open question](domain-packs.md#open-questions).
  - `Event`: no identity, so a plain event never merges across
    documents: two companies' AGMs can share a date and a title.
  - `Metric` and `Concept`: lexical. The term is the node, and each
    source's meaning is a `Definition` fact.
  - No type inherits a scope from the document in `core`: a news
    publisher is not the parent or provider of everything it names.

## `enterprise-docs`

[enterprise-docs.yaml](../../src/tenetrag/packs/shipped/enterprise-docs.yaml)

| Kind | Types |
|---|---|
| Entities | `Policy`, `Procedure` (versioned), `Project`, `System` |
| Events | `Meeting` (attendee, chair), `Decision` (decided_by, about, made_in; status, rationale) |
| Facts | `ActionItem` (owner, about, assigned_in; due_date, status), `Requirement` (source, applies_to, metric; modality, condition, threshold, deadline) |
| Relations | `OWNER_OF` (one owner at a time), `IMPLEMENTS`, `APPLIES_TO`, `SUPERSEDES`, `USES` |
| Enum values | `OrgCategory` += department, team, committee, business_unit, branch |
| Identity | units, works and products inherit the document's issuer as their scope; `Person` gets an employer scope inherited from the document, and `employee_id` (key and veto, tried before email); `Meeting` merges on time, title and chair; the new types are scoped by issuer or owner |

Notes:
- **Scope.** The pack holds what most organizations' internal documents
  share: governed documents and their versions, meetings, decisions,
  tasks, obligations, projects and systems. Decision logs and RAID logs
  share the same small core of fields
  ([evidence](../reference/domain-schemas.md#enterprise-documents)).
  Anything tied to one line of business, such as sales campaigns or
  product terms, goes in a user pack.
- **Versions.** Each issued version of a policy or procedure is its own
  entity, scoped by its issuer. Keys are tried in this order:
  1. issuer plus `code`, where every version gets a new number;
  2. issuer, title and `version_label`;
  3. issuer, title and `issued_on`.

  `code`, `version_label` and `issued_on` are vetoes: two versions that
  state different values never merge. A mention with no version, such as
  "theo quy chế công tác phí", means the version in force on the citing
  document's date. `SUPERSEDES` links the versions. "In force on date D" means effective by
  D and not superseded by D. Mixing versions is the failure mode
  VersionRAG names. Its version-aware retrieval scored 90 % against 58 %
  for naive RAG, on 100 questions (preprint).
- **`Decision` is an event**, with its date, its decision-maker and its
  meeting, and a verbatim rationale. Decision logs and QMSum's
  "reasons for proposals" queries carry the same fields.
- **`Requirement`** covers obligations and limits. Its modality maps
  must/should/may/must_not onto the obligation, recommendation, permission
  and prohibition classes used in compliance NLP. A limit on a metric,
  such as "ratio X at most 85 %", is a `Requirement` with a `metric` role
  and a verbatim `threshold`. A separate threshold type is not needed.
  Its version key starts with the engine's `issuer`, so one company's
  limit never supersedes another's.

## `finance`

[finance.yaml](packs/finance.yaml)

| Kind | Types |
|---|---|
| Entities | `Organization` += `lei` (key and veto, tried first), `ticker`; `Instrument` (isin, ticker, exchange, listed_on, delisted_on, kind, currency): keys `isin` and exchange plus ticker while listed, veto `isin`, the name is not identity |
| Events | `Acquisition` (+ status), `RatingAction` (+ scope issuer or issue), `CorporateAction` (kind adds issuance, listing, delisting, bankruptcy) |
| Facts | `ReportedFigure` += currency, scale, period_kind, consolidation, segment, restated |
| Relations | `OWNS_STAKE`, `SUBSIDIARY_OF`, `ISSUED`, `LISTED_ON`, `REGULATED_BY`, `MANAGED_BY` |

Notes:
- **Literature.** Finance schemas in the literature are small: 10 to 29
  relation types. What recurs across sources is ownership and control,
  acquisitions, people in roles, products and places. The draft covers all
  of them.
- **Left out.** Single-source types (segment, risk factor, ESG topic,
  sector) and vague "impacts" relations stay out.
  - A business segment is a `ReportedFigure.segment` value.
  - A risk factor is a `Statement`.
- **GLEIF mappings.** `SUBSIDIARY_OF` maps to `IS_DIRECTLY_CONSOLIDATED_BY`
  and `MANAGED_BY` to `IS_FUND-MANAGED_BY` (hyphen as in RR-CDF 2.1). The
  ultimate parent comes from traversal, not from a separate relation.
- **Control** (who ultimately controls B) is computed from `OWNS_STAKE` by
  rules, as the Bank of Italy company-control work does. Rules are a later
  format feature, so v1 extracts stakes only.
- **Executive changes** are `HOLDS_POSITION` relations. Share pledges and
  freezes, which are document-level events in Chinese-market datasets,
  wait for a user who needs them.

## Industry packs, such as banking

**Decision (2026-10-04).** Banking is not a default pack. An industry pack
is a user pack: it extends `enterprise-docs`, adds the types its
documents need, and adds `finance` when the corpus has annual reports,
ratings or securities. An adopting organization keeps its own pack, with
its terms, examples and questions, outside this repository.

**Why no default banking pack.** A bank's internal documents are mostly
covered by `core` plus `enterprise-docs`: policies, procedures, committee
minutes, decisions and KPI definitions. A draft banking layer added only
the commercial side and vocabulary. The evidence points the same way:
- **Standards.** FIBO has no banking module: banking concepts sit in its
  shared FBC and LOAN domains.
- **Industry models.** Industry data models cover banking and markets in
  one model. No standard or vendor found ships a document schema for
  banking apart from finance.
- **Out of scope.** The concepts that are truly bank-specific are
  contract-level structured data that a document graph does not need:
  accounts, facilities, collateral, transactions.

Details are in [domain-schemas.md](../reference/domain-schemas.md#banking).

**What a commercial user pack typically adds.** These are the types that
left `enterprise-docs`:
- entities `Campaign` (objective, channel, budget, period, status) and
  `Segment` (a named customer group);
- a `ProductTerm` fact that holds a price, fee, rate, limit or eligibility
  condition as written, with the engine's valid time recording when it
  applied;
- relations `PROMOTES` (campaign → product), `TARGETS` (campaign or
  product → segment) and `PARTNER_OF`;
- the new types added to inherited endpoints and roles, such as
  `OWNER_OF → Campaign` and `Decision.about → Campaign`;
- vocabulary as enum values: product lines, organization categories, term
  kinds.

An industry pack becomes a default pack when several adopters need the
same types and questions, and public synthetic test documents exist for
it.

## Not in v1

| Candidate | Why not now | Revisit when |
|---|---|---|
| `Campaign`, `Segment`, `ProductTerm`, `PROMOTES`, `TARGETS`, `PARTNER_OF` | common where a company sells to customers, not in every organization; they live in user packs | several adopters need the same shape |
| `Risk` fact (risk, issue, assumption, dependency) | RAID logs are common, but no v1 CQ needs it | a pilot asks risk questions |
| `CONTROLS`, ultimate controller | derived by rules, not extracted | the format gains rules |
| Shareholding pledge and freeze events | market-specific datasets only | a user's corpus has them |
| `Facility`, `Collateral`, `Guarantee` | contract-level data; mostly structured | credit memos are in scope |
| `Account`, `Customer`, `Transaction` | structured, personal data; belongs in SQL | not planned |
| `Post` node, `Step`, `Goal` | no CQ needs them; `HOLDS_POSITION`, chunks and `Project` cover the cases | a CQ fails without them |
| `Topic` | becomes a noisy hub | not planned |

## Test material

Each default pack ships synthetic test documents with expected items, and
its CQs double as the golden set. It also ships identity cases: pairs
that must merge and pairs that must stay apart, for every type with a
scope, a key or a veto
([identity fields](domain-packs.md#identity-fields)). There are 77 cases:
27 for `core`, 43 for `enterprise-docs` and 7 for the `finance` draft; 60
come from the ADR 0016 design suite and 17 were added later. The
synthetic corpus is tier 1 of [test-corpora.md](../reference/test-corpora.md).
Public datasets serve only as evidence of
extractable types or as benchmark candidates, because several forbid
redistribution or commercial use
([datasets](../reference/domain-schemas.md#datasets-for-tests-and-benchmarks)).

## Open items
- Resolved on 2026-10-04: `Work`, `Policy` and `Procedure` link to their
  document through `document_link`, and `LISTED_ON` requires an exchange
  through a `where` constraint
  ([pack format](domain-packs.md#pack-format)).
