# Domain packs — design brief (2026-10-04)

Status: draft. The decisions are recorded in
[ADR 0007](../decisions/0007-define-the-graph-schema-as-layered-domain-packs.md);
the research behind them is in
[graph-schema-design.md](../reference/graph-schema-design.md) and, for the
v1 packs, [domain-schemas.md](../reference/domain-schemas.md). The
identity fields were added on 2026-10-06
([ADR 0016](../decisions/0016-identify-entities-by-scope-keys-and-vetoes.md)).
Scope: how a
TenetRAG user defines what the graph contains, the default packs v1 ships,
and the workflow that helps users reach a good schema. The engine brief
settles how extraction, resolution and retrieval use the pack internally.

**Goal** — A developer picks a default pack for their field, adapts it with
a domain expert, and can check before a full index run that the graph will
answer their questions. Every extracted item is typed by the pack, validated
in code and traceable to its source chunk.

**Users**
- The developer who indexes a corpus and attaches the graph to an agent.
- The domain expert who knows which questions matter and which distinctions
  are real. They edit YAML or review drafts; they do not write code.

## What the graph contains

**Nodes**

| Kind | Defined by | Examples | Notes |
|---|---|---|---|
| Document, Chunk | engine | an annual report; its chunk c12 | Every relation, event and fact points to a chunk. Deleting a document cascades through these links. |
| Entity | pack | `Person`, `Organization`, `Instrument` | Lasts over time, has a proper name, recurs across documents. Merged by its scope, keys and vetoes, never by name alone ([identity fields](#identity-fields)). |
| Event | pack | `Acquisition`, `Meeting`, `Decision` | Something that happened. N-ary: typed roles point to entities. A graph node that retrieval can traverse. |
| Fact | pack | `Definition`, `ReportedFigure`, `ActionItem`, `Requirement` | Something a source states or requires, kept per source: two sources that disagree give two facts. N-ary like events, attached to the entities in its roles and reached through them; not an entry point for retrieval ([pitfall](../reference/graphrag-engines.md#pitfalls-to-avoid)). |

**Edges**

| Kind | From → to | Carries |
|---|---|---|
| Relation | entity → entity, typed by a pack relation (`OWNS_STAKE`) | value, time, evidence |
| Role | event or fact → entity or event (`buyer`, `made_in`) | role name |
| `MENTIONED_IN` | entity → chunk | surface form as written |
| `SUPPORTED_BY` | relation, event or fact → chunk | verbatim quote |
| `PART_OF` | chunk → document | position |
| `TEXT_IN` | entity with `document_link` → document | the attribute that matched |

**Not nodes:** amounts, dates, percentages and other literals are
attributes; alternative names are `aliases`; fine distinctions are enum
values such as `category: bank`. Communities are not pack kinds. They are
derived after each index run
([ADR 0011](../decisions/0011-cluster-by-default-and-make-community-reports-opt-in.md)).

**Choosing the shape of a new piece of knowledge:**

| If it… | Model it as |
|---|---|
| has a proper name, recurs across documents and must be merged | entity type |
| happened at a time, or is stated by a source, and has three or more parts (who, with whom, how much, when) | event or fact type |
| links exactly two entities with few details | relation, details as attributes |
| is a number, date, amount, percentage or alternative name | attribute |
| is a finer kind of an existing type | enum value on that type |

## Pack format

```yaml
pack: core                 # kebab-case name
version: 1                 # bump on any change; recorded on every extracted item
mode: strict               # strict | discovery (unknown types go to a review queue)
entities:
  Organization:
    description: A named company, agency or institution, or a named unit or group inside one.
    examples: [Công ty CP Alpha, Acme Corp, Risk Committee]
    scope: {role: parent, to: [Organization], inherit: none, when: {category: [unit]}}   # units only
    identity: [[registration_id]]        # keys, tried in order during resolution
    vetoes: [registration_id, established_on]
    attributes:
      category: {range: OrgCategory}
      registration_id: {range: str, compare: digits, unique: global}   # national business registration number
      established_on: {range: date}
    exact_mappings: ["schema:Organization"]
  Person:
    description: A specific, named human being.
    scope: {role: employer, to: [Organization], inherit: none}
    identity: [[email]]
    names: evidence                      # a shared name never merges alone
    corroborate: [MEMBER_OF, HOLDS_POSITION]
    attributes:
      email: {range: str, compare: lower, unique: global}
  Metric:
    description: A named measure that documents define, calculate or report.
enums:
  OrgCategory: [company, government_agency, nonprofit, unit, other]
relations:
  HOLDS_POSITION: {from: [Person], to: [Organization], time: interval, attributes: {title: {range: str, required: true}}}
facts:
  Definition:
    description: A source's statement of what a term or metric means or how it is calculated.
    roles: {term: [Concept, Metric], defined_by: [Organization, Person, Work]}
    attributes: {text: {range: str}, formula: {range: str}}
    required: [term, text]
  Statement:
    roles: {speaker: [Person, Organization], about: [Person, Organization, Product, Concept, Work, Metric]}
    extract: false           # defined, but not extracted unless a child pack switches it on
not_entities: [money, date, percentage, number, duration]
retrieval:                 # query-time: changing it never triggers a re-index
  hub_penalty: [Organization]
competency_questions:
  - {id: core-1, text: "Who held position T at organization O on date D?", needs: [HOLDS_POSITION]}
```

This is an excerpt of [core.yaml](packs/core.yaml). The v1 packs are in
[packs/](packs/), with their reasoning in [v1-packs.md](v1-packs.md).

| Field | Meaning | v1 |
|---|---|---|
| `extends` | Parent pack, or a list of parents. Absent only in `core`. | required |
| `description`, `examples`, `aliases` | What the LLM reads. Every type needs a definition and examples. | required |
| `is_a` | Single parent type, such as `Acquisition: {is_a: Event}`. | required |
| `identity` | On an entity type: keys tried in order, with `scope`, `vetoes`, `names` and the other [identity fields](#identity-fields). On an event type: entries such as `[time, about, decided_by]`; two events from different documents merge only when every role and attribute of one entry matches ([ADR 0013](../decisions/0013-resolve-events-by-identity-and-version-facts-in-the-engine.md)). An event type without it never merges across documents. | optional |
| `version_key` | On a fact type: the roles and attributes that make two facts statements of the same thing, such as `Requirement: [issuer, metric, applies_to, condition]`. Facts with equal values form a version group, and the engine marks them `current`, `superseded` or `conflicting`. Without it, every fact of the type is current ([ADR 0013](../decisions/0013-resolve-events-by-identity-and-version-facts-in-the-engine.md)). | optional |
| `glossary` | User packs only: canonical names with their type, aliases and an optional note, such as `{name: Công ty CP Alpha, type: Organization, aliases: [Alpha]}`. An entry that occurs in a chunk goes into that chunk's extraction prompt, and resolution maps its names and aliases to one entity of that type ([engine brief §2.4](engine-brief.md#24-extract-e6), [§2.6](engine-brief.md#26-resolve-entities-e8)). | optional |
| `attributes` | `range` (`str`, `date`, `money`, `percentage`, `int`, `float`, `bool`, an enum), `required`, `multivalued`, `unit`, and an optional `description` for the prompt. Key and veto attributes also take `compare` and `unique` ([identity fields](#identity-fields)). | required |
| `from`, `to` | Allowed endpoint types of a relation. | required |
| `where` | Allowed enum values on an endpoint, such as `LISTED_ON: {from: [Instrument], to: [Organization], where: {to: {category: [exchange]}}}`. The attribute must be an enum on every allowed type of that endpoint. Checked in code, never in the compiled schema. | optional |
| `time` | `none`, `point` or `interval`. | required |
| `roles` | Role name → allowed types, for events and facts. A role may point to an event, such as a decision's `made_in` meeting. | required |
| `required` | Roles or attributes an item must have. Each one costs recall, since items without it are dropped. Only the pack that defines a type sets it. | required |
| `not_entities` | Literal kinds the LLM must not emit as entities. | required |
| `competency_questions` | Questions the pack must answer, with the types and relations each needs. | required for shipped packs |
| `cardinality` | `one_at_a_time: [subject]` or `[subject, object]`: a newer relation closes the older one's interval instead of adding a parallel one. | optional |
| `value` | Range of a relation's main value, such as the stake in `OWNS_STAKE`. | optional |
| `exact_mappings` | IRIs in external standards. Never their text. | optional |
| `retrieval` | Hub penalties, hop limits, context relations. Query-time. | optional |
| `deprecated`, `renamed_from` | Retire or rename a type without breaking older items. | optional |
| `extract` | `false` keeps a type defined but skips it during extraction, as `core` does for `Statement`. | optional |
| `document_link` | Entity attributes, such as `[code, title]`, that the engine compares with each indexed document's code and title. On an exact match after normalization, the engine adds a `TEXT_IN` edge from the entity to that document. `core` sets it on `Work`, `enterprise-docs` on `Policy` and `Procedure`. | optional |
| `agent_visible` | `true` on a type also shows its examples and competency questions to agents ([step 7](#how-the-pack-is-used)). | optional |

Later: inverse, symmetric and transitive relations, disjointness, rules,
multiple parents.

**Engine-owned fields.** Packs never declare these; every relation, event and
fact has them: `valid_from`, `valid_to`, `valid_precision` (day, month,
year), `observed_at` (date of the source document or of ingestion),
`recorded_at`, `doc_id`, `chunk_id`, `quote`, `confidence`, `status`
(`current`, `superseded`, `conflicting`), `pack`, `pack_version`. The LLM proposes the
valid time and the quote; the pipeline sets the rest. The engine brief
adds `quote_start`, `quote_end`, `quote_match` (`exact` or `fuzzy`),
`valid_source` (`text`, or `document` when the time comes from the
document card), `version_key`, `closed_at` and `run_id`
([engine brief §1](engine-brief.md#engine-owned-fields)). Events keep
their quotes in evidence rows, one per chunk. Entities get
`scope_path`, `scope_source` and `label`, and every fact gets an `issuer`
that its `version_key` may name: the scope of its `source` entity, else
the document's issuer
([engine brief §3.2](engine-brief.md#32-version-groups-e3)).

**Stacking.** A child pack may:
- add types;
- add attributes and roles to inherited types;
- add allowed types to inherited roles and relation endpoints;
- add allowed values to an inherited `where` constraint;
- add enum values;
- put identity keys in front of the inherited ones (finance puts `[lei]`
  before core's keys);
- add vetoes, and add values to an inherited scope's `when` list;
- switch an inherited scope's `inherit` to `document` (enterprise-docs
  does this for internal documents);
- add attributes to an inherited `version_key` (finance adds `segment`,
  `consolidation` and `period_kind` to `ReportedFigure`);
- switch `extract` on or off.

It may not change a range, a time kind or a description, and it may not
add `required` fields to a type it did not define. A required field added
by a child would tighten the type for every other pack in the stack. For
the same reason it may not remove a scope, a key or a veto, or change
`names`: that would loosen identity for every pack in the stack. A
pack that extends several parents (`extends: [enterprise-docs, finance]`)
gets their union, and a shared ancestor such as `core` is loaded once.
Identical definitions from two parents merge. Conflicting ones, such as
one attribute with two ranges, fail with a `ConfigError` naming both
sources.

### Identity fields

Added on 2026-10-06
([ADR 0016](../decisions/0016-identify-entities-by-scope-keys-and-vetoes.md)).
They decide when two mentions are one entity, and a name alone never
does. The engine applies them in
[engine brief §2.6](engine-brief.md#26-resolve-entities-e8). The research
is in [the identity criteria snapshot](../research/2026-10-05-entity-identity-criteria.md).

Four questions sort each attribute of an entity type into a role:

| Question | Key | Veto |
|---|---|---|
| Is the value unique within a known scope? | yes | no need |
| Does it stay fixed for the entity's life? | yes | yes |
| Does an entity have one value at a time? | no need | yes |
| Do documents state it, in a form code can check? | yes | yes |

An attribute that is neither a key nor a veto only describes the
entity. A value many entities share, such as a person's name, is
evidence: it can support a merge but never decide one. A name, a unit, a
title, an end date or a status is never a veto, because each changes
over an entity's life.

| Field | On | Meaning |
|---|---|---|
| `scope` | entity type | Whose thing it is, as `{role, to, inherit, when}`. `role` is the word the prompt uses: issuer, employer, owner, provider, parent. `to` lists the allowed scope types. `inherit: document` takes the document's issuer when the text names none (caller metadata, the card, the profile's `default_issuer`). `inherit: none` leaves the scope unknown. `when` limits the scope to some enum values, as `Organization` does for unit categories. No `scope` means the type is unscoped. |
| `identity` | entity type | Keys, tried in order. Each key is a list of attributes, with `scope` first for a scoped type: `[[scope, code], [scope, title, version_label]]`. A key that holds only for a time is written `{key: [exchange, ticker], during: [listed_on, delisted_on]}`. |
| `vetoes` | entity type | Attributes that block a merge when both sides know them and the values differ. A missing value never blocks. |
| `names` | entity type | `key` (default): the name or an alias is a key within the scope. `evidence`: a shared name merges only with the corroboration below, else it goes to the LLM confirmation. `versioned`: one entity per version, and a mention with no version resolves to the version in force on the citing date. `none`: the name is never matched. |
| `corroborate` | entity type with `names: evidence` | Relations that confirm a name match when the mention and the candidate share an endpoint, such as `[MEMBER_OF, HOLDS_POSITION]` for `Person`. |
| `version_start` | entity type with `names: versioned` | Date attributes, in order, that start a version's force, such as `[effective_from, issued_on]`. |
| `compare` | key or veto attribute | `text` (default, the engine's normalization), `code` (case, spaces, "số", Đ → D), `digits`, `lower`, `upper` or `date`. |
| `unique` | key attribute | `scope` (default): unique within a scope. `global`: unique everywhere, such as a tax ID, an LEI, an ISIN or an email. A key made only of global attributes needs no `scope` and is checked against candidates of every scope; vetoes still apply. `self_scoped`: unique everywhere when the value names its issuer, by the engine's `resolution.self_scoped_codes`, as Vietnamese law codes do. Such a value is checked the same way, and its mention inherits no scope from the document. |

**Lint at load.** A pack fails to load when:
- a key of a scoped type has no `scope` and holds an attribute whose
  `unique` is `scope`;
- one key of a type contains another key of that type, since keys must be
  minimal;
- a veto is `multivalued`, has a range other than `str`, `date` or `int`,
  or is a name or a title;
- `names: versioned` has no `version_start`.

`names: evidence` without `corroborate` loads with a warning: every
shared name then goes to the LLM.

**Identity cases.** Each shipped pack ships identity cases with its
synthetic test documents:
- for each type with a scope, a key or a veto, at least one pair that must
  merge and one that must stay apart;
- for every key and veto, a case that goes wrong when it is removed, so
  nothing in the identity is unjustified.

CI requires zero wrong merges. A user pack can add its own cases.

## How the pack is used

1. **Compile.** The SDK merges the stack and compiles flat JSON Schemas for
   structured output: type and relation names become enums, attributes and
   roles become key/value lists. No `$ref`, `anyOf`, `oneOf`, `allOf` or
   `pattern`, at most 64 keys. Adding a type grows an enum and the prompt,
   not the key count. When the prompt gets too long, extraction is split
   into passes by type group, or only the types relevant to a chunk are
   sent. Each entity type's prompt section comes from its identity fields:
   what its scope means, which attributes identify it, which relations
   corroborate it, and which attributes only describe it.
2. **Extract.** One LLM call per chunk or batch returns entities, relations,
   events and facts, each with a verbatim quote. Each entity attribute
   comes back as a value plus the quote that states it.
3. **Validate in code.** Each item is kept or dropped with a reason:
   `NOT_IN_SCHEMA`, `NOT_AN_ENTITY`, `INVALID_PATTERN` (wrong endpoint types
   or direction, or an endpoint value outside a `where` list), `INVALID_ROLE`, `MISSING_REQUIRED`, `BAD_VALUE` (range or
   enum mismatch, or a value its quote does not state), `QUOTE_NOT_IN_CHUNK`,
   `NOT_A_NAME` (a phrase such as "quy chế này" that resolves to nothing).
   Drops are counted per type and reason in the run record, never
   discarded silently.
4. **Resolve.** Entities merge only within one type and a compatible
   scope, and never across a veto. Glossary entries and checked hints come
   first, then keys, then the type's name rule, then fuzzy candidates in
   the same scope that an LLM confirms
   ([engine brief §2.6](engine-brief.md#26-resolve-entities-e8)). Each
   candidate kept apart is recorded with both values and quotes. Events
   merge within a document by time and compatible roles, and across
   documents only on their `identity`.
5. **Write.** Items carry the pack name and version. For a relation type
   with `one_at_a_time`, decided on 2026-10-04:
   - The engine orders the two relations by `valid_from`, falling back to
     `observed_at`. The newer one closes the older one's interval, and the
     older one becomes `superseded`. Nothing is deleted.
   - When both start on the same date, or the order cannot be known, both
     become `conflicting`. The run record lists the pair for review, and
     retrieval returns both with their sources.

   Facts of a type with `version_key` get the same treatment within their
   version group ([engine brief §3.2](engine-brief.md#32-version-groups-e3)).
   Entities with `document_link` get a `TEXT_IN` edge to the matching
   document. An endpoint whose `where` attribute is unset is kept and
   counted in the run record, because the text often omits the category.
6. **Retrieve.** Type and relation filters and the `retrieval` hints shape
   graph-guided retrieval.
7. **Expose to agents.** Added on 2026-10-04. Agents call tools better when
   they know the type names. Every schema-discovery precedent read does this
   (Neo4j MCP `get_neo4j_schema`, LangChain `sql_db_schema`, dbt MCP
   `get_model_details`). KG agents also invent relation names in tool
   arguments (Graph Explorer, ACL 2026 Findings)
   ([snapshot](../research/2026-10-04-schema-for-agents.md)).
   - **Enums in tool specs.** `as_tools()` and the MCP server generate the
     allowed entity, relation, event and fact types from the merged pack. An
     invalid value returns an error that lists the valid ones.
   - **`describe_schema(detail="summary" | "type", name=None)`.** Decided
     on 2026-10-04: agents see just enough to call tools, so context stays
     short. By default the summary gives, per type:
     - the name and a one-line description;
     - endpoints, `where` constraints and time kind for relations;
     - roles for events and facts;
     - enum values.

     Examples and competency questions appear only for types marked
     `agent_visible: true`. `detail="type"` returns one type in full,
     within the same visibility rule. The summary has a token budget; when
     a stack exceeds it, examples go first, then descriptions shorten, and
     the summary points to `detail="type"`. The budget stays well under
     10k tokens, the size at which Claude Code warns about a tool result.
   - **Load-time lint.** Agent-visible text that reads like an instruction
     to the model ("ignore", "you must", URLs, tool names) raises a warning
     when the pack loads, and fails in `strict` mode.
   - **Version stamp.** Each response carries the pack name, version and a
     hash of the merged stack, so an agent knows when to read again.
   - **MCP resource.** The MCP server mirrors the summary as a resource. Most
     MCP clients do not let the model read resources on its own, so the tool
     is the path agents rely on.

## Designing a schema

Every iteration runs on a sample of 20–50 documents, so each change is
cheap. Only a frozen version runs on the full corpus.

1. **Pick the nearest default pack**, such as `core` + `finance`.
2. **Write 20–50 competency questions** with the domain expert. They double
   as the golden set. Humans write them; automatic question generation is
   weak (Bench4KE, BERTScore F1 0.57–0.60).
3. **Coverage check**, with no LLM call: map each question to the types and
   relations it needs and list the gaps.
4. **Draft the missing parts.** The LLM proposes types and relations one
   question at a time, and a discovery-mode run over the sample surfaces
   types nobody listed. A person accepts or rejects each proposal. Drafts
   from questions cover most needs but often get relation endpoints wrong
   (Lippolis et al.).
5. **Trial run in strict mode** on the sample. The report shows:
   - items per type and relation, and types with zero hits;
   - drops per type and reason, with examples;
   - merged entities, likely duplicates and hub entities;
   - per question, whether the graph holds a path and whether the answer is
     right;
   - prompt tokens added by the schema, and projected cost on the corpus.
6. **Edit and repeat** steps 3–5.
7. **Freeze a version** and run the full corpus. Watch the drop rate over
   later runs: a rising rate means new documents contain things the pack
   does not describe.

## v1 packs

Three default packs ship in v1. Each comes with competency questions,
synthetic test documents with expected items, and a coverage check that
runs in CI. Schemas and reasoning are in [v1-packs.md](v1-packs.md); the
draft files are in [packs/](packs/).

| Pack | For | Adds |
|---|---|---|
| `core` | every corpus | `Person`, `Organization`, `Place`, `Work`, `Product`, `Metric`, `Concept`; `Event`; `Definition` and `ReportedFigure` facts (`Statement` off by default); six relations |
| `enterprise-docs` | internal documents | `Policy` and `Procedure` (versioned), `Project`, `System`; `Meeting`, `Decision`; `ActionItem`, `Requirement`; ownership, implementation, scope, supersession and usage relations |
| `finance` | company and market disclosures | `lei` on `Organization`; `Instrument`; `Acquisition`, `RatingAction`, `CorporateAction`; normalization fields on `ReportedFigure`; ownership, subsidiary, issuance, listing, regulation and fund-management relations |

Industry packs, such as banking, are user packs, not default packs. They
extend `enterprise-docs` and add their own types, like campaigns, customer
segments and product terms
([v1-packs.md](v1-packs.md#industry-packs-such-as-banking)).

## Later packs

Surveyed on 2026-10-03; standards and licenses are in
[graph-schema-design.md](../reference/graph-schema-design.md#standards-and-licenses).
Each needs its own questions and test documents before it ships.

| Pack | Adds (examples) | Reference standards |
|---|---|---|
| legal-regulatory | Provision, Case, DefinedTerm; Obligation, Permission, Prohibition; amendments with effective dates | Akoma Ntoso, ELI, CUAD |
| it-ops | Service, Host, Component, Environment, Runbook; Incident, Change | OpenTelemetry, CycloneDX, SPDX |
| cyber | ThreatActor, Malware, AttackPattern, Vulnerability, Indicator; Campaign, Attribution | STIX 2.1, ATT&CK |
| biomedical | Disease, Gene, Chemical, Variant, Phenotype, Pathway; Finding, Recommendation | Biolink, FHIR (no SNOMED CT or UMLS content) |
| science | Method, Task, Dataset, Metric, Venue; Result | SciERC, ORKG, CiTO |
| product-support | Variant, Feature, Part, Issue, Resolution; Ticket, Offer | schema.org (IRIs only) |
| supply-chain | Facility, Equipment, Part, Batch, Shipment; Failure | IOF Core, Brick, SAREF |
| news-events | `event_type` values on `Event`; Statement; occurrence vs report time | own names (ACE and ERE are licensed) |
| hr | Position, Occupation, Skill, Qualification; Employment; flags personal data | O*NET |
| public-sector | Service, Programme, Dataset | SEMIC Core Vocabularies |
| insurance | Policy, Coverage, Claim, Endorsement; LossEvent | own (ACORD is membership-only) |

## Out of scope (v1)
- OWL reasoning, inference rules, multiple inheritance.
- Bundling external vocabularies such as FIBO, ESCO or ATT&CK inside packs.
- Changing a pack automatically from LLM proposals without review.
- Selective re-extraction after a pack change. v1 records the pack version
  on every item so it can be built later.
- A visual schema editor. The app keeps the scope in the
  [SDK brief](sdk-platform-brief.md), which has none.
- Community packs. Where they live and who reviews them waits until after
  v1.

## Success criteria (v1)
1. `core`, `enterprise-docs` and `finance` each pass the coverage check for
   all their competency questions.
2. The compiled schema for any stack of shipped packs, including
   `[enterprise-docs, finance]`, has no `$ref`, `anyOf`, `oneOf`, `allOf` or
   `pattern` and at most 64 keys.
3. A trial run on each pack's synthetic test documents returns the expected
   items and a drop report with a reason for every dropped item.
4. A user extends `finance` with one new relation in their own pack, and the
   coverage check, trial run and full run pick it up with no code change.
5. Every entity, relation, event and fact names the pack and version that
   produced it.
6. The benchmark runs no schema, `core` only and `core` plus a domain pack
   on the same corpus and golden set.
7. An eval built from the competency questions compares four agent
   setups: no schema, enums only, enums plus the summary, and enums plus
   `describe_schema`.
8. A trial run drops a `LISTED_ON` whose object is an `Organization` with a
   category other than `exchange`, with reason `INVALID_PATTERN`.
9. A synthetic policy whose code matches an indexed document gets a
   `TEXT_IN` edge, and deleting that document removes the edge.
10. Two `OWNER_OF` relations on the same object with different start
    dates leave the older one `superseded`; with the same start date, both
    are `conflicting` and listed in the run record.
11. Each shipped pack's identity cases, and the engine's identity suite,
    give zero wrong merges.
12. Two synthetic companies, each with a same-titled policy, a
    same-named unit and a limit on the same metric, keep all three pairs
    apart, and neither company's limit supersedes the other's.

## Open questions
Resolved on 2026-10-04: `core` and `enterprise-docs` ship in M1 and
`finance` before the M4 benchmark; `one_at_a_time` supersedes
automatically and flags conflicts; category endpoint constraints are in
v1 (`where`); community packs wait until after v1; agents see a minimal
set of fields.

1. Vietnamese: whether packs carry Vietnamese aliases, examples and display
   labels, and whether that improves extraction. Measure in the first pilot.
2. How many types fit in one extraction pass before splitting pays off. No
   published measurement exists. `[enterprise-docs, finance]` puts 39 types
   in the prompt, before any user pack.
3. Whether any target LLM caps the number of enum values in a strict tool
   schema. A merged stack with a user pack can pass 50 types. Not verified.
4. The token budget of the `describe_schema` summary, and how a document's
   title and code are found for `document_link` (file metadata, first
   heading, a profile pattern). Engine brief.
