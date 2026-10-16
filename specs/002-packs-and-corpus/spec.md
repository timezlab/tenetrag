# Feature Specification: Domain packs and the synthetic corpus (M1, part 1)

**Feature Branch**: none; solo development on `main`, and Spec Kit finds
this feature through `.specify/feature.json`

**Created**: 2026-10-11

**Status**: Draft

**Input**: User description: "002 — Domain packs and the synthetic test corpus (M1, part 1 of 5). Scope: the pure `tenetrag.packs` module (load pack YAML, stack `extends`, check conflicts, compile flat structured-output schemas within the provider limits, check coverage against competency questions, give a pack hash that feeds the stage hashes); ship the `core` and `enterprise-docs` packs as package data from the drafts in docs/product/packs/; a synthetic bilingual (Vietnamese and English) corpus of 30–60 documents with a deterministic generator and planted answers, including the running example (Alpha D1–D5, Beta) and its golden questions; the identity cases of ADR 0016 as fixture data. Out of scope: the engine, stores, retrieval, the finance pack (M4). Work on main with no feature branch (solo dev; Spec Kit uses feature.json). No adopter data: the corpus is synthetic."

M1 runs TenetRAG end to end on local Neo4j and Postgres
([SDK platform brief](../../docs/product/sdk-platform-brief.md), milestone
table). It is split into five features, so that each one can be specified,
built and reviewed on its own. The numbers after 002 are planned, not yet
reserved:

| Feature | Contents |
|---|---|
| 002 (this one) | domain packs, the shipped `core` and `enterprise-docs` packs, the identity cases, the synthetic corpus |
| 003 | store protocols, the in-memory reference store, the contract suite, the Postgres and Neo4j stores |
| 004 | the index pipeline: scan and apply, extraction, validation, resolution, versions, edit and delete, run record, trace |
| 005 | `retrieve()`, `answer()`, `explain`, the agent methods, the core retrieval metrics |
| 006 | the CLI's `trace --html` and the frontend workspace |

This feature comes first because every later one reads a pack, and the
engine's tests run on the corpus and the identity cases. It makes no
store call and no model call.

Two kinds of people use it:
- **Pack authors**: a developer who indexes a corpus, working with a
  domain expert who edits YAML but writes no code. They pick a shipped
  pack, or write their own pack on top of one
  ([domain-packs.md](../../docs/product/domain-packs.md)).
- **Contributors**: the author and AI agents who build the rest of M1.
  They use the merged pack, the compiled schemas, the identity cases and
  the corpus as the engine's inputs and test oracles.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Load and check a pack stack (Priority: P1)

A pack author names a pack in their profile: a shipped pack, or their own
file that extends shipped packs. The SDK loads the pack and its
ancestors, merges them, and checks the result before anything is
indexed. A mistake fails at load, and the error lists every problem, each
with the file, the place in the pack and what to change. A correct stack
gives one merged, read-only description of the graph, which the rest of
the SDK reads.

**Why this priority**: extraction, validation, resolution, retrieval and
the agent tools all read the merged pack. A pack mistake found at load
costs a minute. Found after an index run, it costs the run.

**Independent Test**: load `core`, `enterprise-docs` and a test user pack
on top of `enterprise-docs`, and inspect the merged stack. Then load a
set of broken packs, each breaking one rule, and check that each fails
with that rule named.

**Acceptance Scenarios**:

1. **Given** a profile that names `enterprise-docs`, **When** the pack
   loads, **Then** the merged stack holds every type of `core` and
   `enterprise-docs` once, with the child's additions applied. For
   example, `Organization`'s scope condition lists the unit categories of
   both packs, and `Person`'s keys try `[scope, employee_id]` before
   `[email]`.
2. **Given** a user pack that extends `enterprise-docs` and adds one
   entity type, one relation and one enum value, **When** it loads,
   **Then** the three additions are in the merged stack, with no code
   change.
3. **Given** a user pack that changes the range of an inherited
   attribute, adds a `required` field to a type it did not define, or
   removes an inherited veto, **When** it loads, **Then** loading fails
   and names both packs, the path inside the pack and the broken rule.
4. **Given** a pack with two parents that define one attribute with two
   different ranges, **When** it loads, **Then** loading fails and names
   both sources. **Given** two parents with identical definitions,
   **Then** the definitions merge without a message.
5. **Given** a pack with a misspelt field (`vetos`), a type defined twice
   in one mapping, and a relation endpoint that names an undefined type,
   **When** it loads, **Then** one error lists all three problems.
6. **Given** a type that breaks an identity lint rule (a veto that is
   multivalued, a key of a scoped type without `scope`, a key that
   contains another key, or `names: versioned` without `version_start`),
   **When** the pack loads, **Then** loading fails and names the type and
   the rule. **Given** `names: evidence` without `corroborate`, **Then**
   the pack loads with a warning that names the type.
7. **Given** agent-visible text that reads like an instruction to a model
   (such as "ignore", "you must", a URL or a tool name), **When** the pack
   loads, **Then** the SDK warns, and loading fails when the stack's mode
   is `strict`.
8. **Given** a pack file with a YAML tag that would build an object,
   **When** it loads, **Then** loading refuses the file and runs nothing
   from it.
9. **Given** packs that extend each other in a cycle, **When** one loads,
   **Then** loading fails and names the cycle.

---

### User Story 2 - Compile schemas and stamp the pack (Priority: P1)

The engine asks the merged pack for the schema that an extraction call
returns. The compiled schema is flat and fits the structured-output
limits that model providers impose. The pack also gives a stamp: its
name, its version and a hash of the merged stack's content. Every
extracted item and every response will carry the stamp, and the hash
enters the index-time stage hashes, so that a pack change is detected.

**Why this priority**: a provider rejects a schema outside its limits,
and extraction stops. An undetected pack change leaves an index built
with one schema and read with another (constitution principle VII).

**Independent Test**: compile every stack of shipped packs and a test
user pack, check the output for forbidden constructs and count its keys.
Reformat a pack and compare hashes. Change one definition and compare
stage hashes.

**Acceptance Scenarios**:

1. **Given** any stack of shipped packs, **When** it is compiled,
   **Then** the schema has no `$ref`, `anyOf`, `oneOf`, `allOf` or
   `pattern`, has at most 64 keys, and lists the entity, relation, event
   and fact type names as enums.
2. **Given** a key limit lower than the schema's key count, **When** a
   stack is compiled, **Then** compiling fails with the key count and the
   parts of the schema that hold the most keys.
3. **Given** a chosen subset of extractable types, **When** it is
   compiled, **Then** the schema covers only those types, so that
   extraction can later run in passes.
4. **Given** `core`, whose `Statement` fact has `extract: false`, **When**
   it is compiled, **Then** `Statement` is absent from the schema. A child
   pack that switches it on brings it back.
5. **Given** a pack, **When** its keys are reordered, its comments and
   whitespace change, or its Vietnamese text is in decomposed Unicode
   form, **Then** its hash is unchanged. **When** one description
   changes, **Then** the hash changes.
6. **Given** a profile, **When** its pack changes, **Then** the extraction
   and resolution stage hashes change. **When** only the pack's
   `retrieval` hints change, **Then** no stage hash changes. **When** only
   a user pack's glossary changes, **Then** no stage hash changes, and the
   glossary's own hash does.
7. **Given** a shipped pack whose content was edited without a version
   bump, **When** the tests run, **Then** they fail and name the pack.

---

### User Story 3 - Check that a pack can answer its questions (Priority: P2)

Before indexing, a pack author checks the stack against its competency
questions. The coverage check makes no model call. For each question it
lists the types and relations the question needs that the stack lacks,
or defines but does not extract.

**Why this priority**: step 3 of the schema design workflow
([domain-packs.md](../../docs/product/domain-packs.md#designing-a-schema)).
It finds a missing relation before an index run, at no cost.

**Independent Test**: run the check on the shipped packs, which pass.
Then run it on a user pack with one question that needs an undefined
relation and one that needs `Statement`.

**Acceptance Scenarios**:

1. **Given** the `enterprise-docs` stack, **When** the check runs,
   **Then** all 14 competency questions pass: 6 from `core` and 8 from
   `enterprise-docs`.
2. **Given** a user question that needs a relation the stack lacks,
   **When** the check runs, **Then** the report names the question and
   the missing relation.
3. **Given** a user question that needs `Statement`, **When** the check
   runs on `core`, **Then** the report lists `Statement` as defined but
   not extracted.
4. **Given** a shipped pack with no competency questions, **When** the
   tests run, **Then** they fail.

---

### User Story 4 - Identity cases ship with each pack (Priority: P2)

Each shipped pack carries identity cases. A case is a small synthetic
situation: the entities already in the graph, one new mention, and the
right outcome. The 60 cases of the identity design
([ADR 0016](../../docs/decisions/0016-identify-entities-by-scope-keys-and-vetoes.md))
are recorded in the same form. In this feature the cases are checked
against the packs and for coverage. The engine runs them in feature 004,
where CI then requires zero wrong merges.

**Why this priority**: constitution principle VI requires every shipped
pack to ship identity cases. Writing them with the pack keeps the two
consistent, and the engine's resolver gets its test oracle before its
first line.

**Independent Test**: run the consistency and coverage checks over the
cases. Then remove the only case that names one veto, and check that the
coverage check fails and names that veto.

**Acceptance Scenarios**:

1. **Given** `core` and `enterprise-docs`, **When** the coverage check
   runs, **Then** every entity type that a pack defines with a scope, a
   key or a veto, or whose identity fields it changes, has at least one
   case that must merge and one that must stay apart, under that pack's
   stack.
2. **Given** the same packs, **When** the check runs, **Then** every key
   and every veto they declare is named by at least one case as an
   element the case depends on.
3. **Given** a case that names an attribute its type lacks in the case's
   stack, **When** the check runs, **Then** it fails and names the case
   and the attribute.
4. **Given** the recorded design cases, **When** they are counted,
   **Then** all 60 are present with their original ids (such as PER-1,
   UNIT-7, POL-3): 30 that must stay apart and 30 that must merge.
5. **Given** the cases, **Then** they include the D5 situation: two
   companies, each with a same-titled policy and a same-named unit, kept
   apart in both pairs, and a metric of the same name, which stays one
   entity. Their two limits on that metric are facts, kept apart by
   their version key, and the corpus states them (FR-037).

---

### User Story 5 - A synthetic bilingual corpus with planted answers (Priority: P2)

A contributor regenerates a corpus of 30 to 60 synthetic documents in
Vietnamese, in English and in both, from a fact table kept in the
repository. Each document comes with the items a correct extraction
returns. The corpus comes with golden questions, whose answers come from
the fact table and are therefore exact. The running example of the
engine brief, Công ty CP Alpha's D1 to D4 and Công ty CP Beta's D5, is
part of the corpus word for word.

**Why this priority**: the engine's unit tests, the backend contract
suite, pack trials and the M1 retrieval metrics all need documents with
known answers. An adopter's documents can never be used (constitution
principle I).

**Independent Test**: regenerate the corpus twice and compare bytes.
Check that every planted quote occurs in its document, that every
expected item fits the pack stack, and that every question type and
every competency question has golden questions.

**Acceptance Scenarios**:

1. **Given** the fact table, **When** the corpus is generated twice,
   **Then** the two outputs are byte-identical and match the committed
   corpus.
2. **Given** the generated corpus, **Then** D1 to D5 state the sentences,
   owners and dates of the
   [running example](../../docs/product/engine-brief.md#running-example),
   and the golden set holds Q-a, Q-b and Q-c with their expected answers.
   It also records that deleting D2 makes requirement r1 current again.
3. **Given** the corpus, **Then** every quote in an expected item or a
   golden answer occurs verbatim in its document's text.
4. **Given** the corpus, **Then** every expected item uses only types,
   roles and attributes that the shipped stack defines, has every
   required role, and connects only allowed endpoint types.
5. **Given** a fact table entry whose quote the rendered text does not
   contain, **When** the corpus is generated, **Then** generation fails
   and names the document and the quote.
6. **Given** the golden set, **Then** each of the eight question types has
   at least three questions, every competency question of `core` and
   `enterprise-docs` has at least one, and the hand-written questions are
   marked as such and survive regeneration.

---

### Edge Cases

**Loading and stacking**
- A pack that extends itself, or a longer cycle, fails and names the
  cycle.
- A stack of `[enterprise-docs, finance]`-style parents that share `core`
  loads `core` once.
- A user pack named like a shipped pack (`pack: core`) fails, since the
  name would hide the shipped pack.
- An empty pack file, or one whose top level is not a mapping, fails with
  the file named.
- A child that restates an inherited description word for word merges.
  One that changes it fails.
- A name used for two kinds of type, such as an entity and a fact both
  called `Policy`, fails.
- A `where` constraint on an attribute that is not an enum on every
  allowed type of that endpoint fails.
- A `version_key`, `document_link`, `corroborate`, `version_start`,
  `cardinality` or `during` entry that names a role, attribute or relation
  the type lacks fails.
- An enum value that two packs both add merges into one value.

**Glossary**
- A shipped pack with a glossary fails the tests: an adopter's terms stay
  in its private user pack.
- A glossary entry whose type the stack lacks fails at load.
- An alias that maps to two glossary entries of the same type fails at
  load, since resolution could not pick one.

**Compile and hash**
- The same stack compiles to byte-identical schemas on every run and
  every supported Python version.
- A stack with a user pack that pushes the type count past 50 still
  compiles within 64 keys, since types grow enums, not keys.

**Identity cases and corpus**
- An identity case for a type that no M1 pack defines (the design's
  Instrument cases) names the `finance` draft by path, so the engine
  suite can still run it.
- Generated text keeps Vietnamese diacritics in NFC form, Vietnamese
  number and date formats (2.000.000 VND, 10/01/2025), and LF line
  endings, so output is identical on every system.
- A hand-written golden question that cites a document the generator no
  longer produces fails the corpus check.

## Requirements *(mandatory)*

### Functional Requirements

**Loading and checking**

- **FR-001**: A profile MUST name its pack, either a shipped pack by name
  or a user pack file by path. With no pack named, the profile uses
  `core`.
- **FR-002**: A pack MUST load from YAML through safe loading, in the
  format of [domain-packs.md](../../docs/product/domain-packs.md#pack-format),
  including the identity fields. Unknown fields, wrong value types and
  duplicate mapping keys MUST be rejected. Loading never runs code or
  builds objects from the file.
- **FR-003**: `extends` MUST accept one parent or a list. A parent is a
  shipped pack by name or a user pack file by path. A shared ancestor
  loads once, and a cycle fails with the cycle named.
- **FR-004**: A child pack MUST be able to make exactly the changes that
  domain-packs.md lists under stacking: add types, attributes, roles,
  endpoint types, `where` values and enum values; put identity keys in
  front of inherited ones; add vetoes and scope `when` values; switch an
  inherited scope's `inherit` to `document`; add attributes to a
  `version_key`; switch `extract`.
- **FR-005**: Any other change to an inherited definition MUST fail,
  including: a changed range, time kind or description; a `required`
  field on a type the child did not define; a removed scope, key or veto;
  a changed `names` rule. The error names both packs, the path and the
  rule.
- **FR-006**: A pack with several parents MUST get their union. Identical
  definitions merge. Conflicting definitions fail with both sources named.
- **FR-007**: Loading MUST check every reference in the stack: each type,
  role, relation, attribute and enum that a definition or a glossary
  entry names exists; `is_a` names one existing parent; a `where`
  attribute is an enum on every allowed type of its endpoint; a type name
  is used by one kind only. What a competency question needs is checked
  by coverage (FR-026), not by loading.
- **FR-008**: Loading MUST apply the identity lint of
  [domain-packs.md](../../docs/product/domain-packs.md#identity-fields):
  a key of a scoped type that holds an attribute unique only within a
  scope includes `scope`; no key contains another key of its type; a veto
  is single-valued, has range `str`, `date` or `int`, and is not a name or
  a title; `names: versioned` has `version_start`. `names: evidence`
  without `corroborate` loads with a warning.
- **FR-009**: Agent-visible text that reads like an instruction to a
  model MUST raise a warning, and MUST fail loading when the stack's mode
  is `strict`.
- **FR-010**: A failed load MUST raise `ConfigError` listing every
  problem found, each with the pack file, the path inside the pack and
  what to change.
- **FR-011**: Pack text MUST be normalized to Unicode NFC at load, so
  that names, aliases and hashes do not depend on how the text was typed.
- **FR-012**: A glossary MUST be allowed only in user packs. Each entry
  names a type the stack has, and an alias maps to at most one entry per
  type.
- **FR-013**: The merged stack MUST be read-only once loaded, and MUST
  give the engine everything the pack declares: types and their
  descriptions, examples and attributes, identity fields, version keys,
  `document_link`, cardinality, `where` constraints, required fields,
  `not_entities`, retrieval hints, glossary and competency questions.

**Shipped packs**

- **FR-014**: The SDK MUST ship `core` version 1 and `enterprise-docs`
  version 1, built from the drafts in `docs/product/packs/`, and MUST load
  them with only the base install.
- **FR-015**: The shipped files MUST be the single source of truth for
  those two packs. The docs link to them instead of keeping copies. The
  `finance` draft stays in `docs/product/packs/` until M4.
- **FR-016**: A shipped pack's content MUST NOT change without a version
  change. A test pins the hash of each shipped pack version.
- **FR-017**: The shipped packs MUST load with no warning, carry no
  glossary and no adopter material, and pass the coverage check for all
  their competency questions.
- **FR-018**: A caller MUST be able to list the shipped packs with their
  versions.
- **FR-019**: The `finance` draft MUST load and compile as a test input,
  alone on `core` and in `[enterprise-docs, finance]`, so that the
  compile limits are checked on the largest planned stack. It is not
  shipped.

**Compile**

- **FR-020**: The SDK MUST compile the merged stack into flat
  structured-output schemas. Type, relation and role names become enums,
  and attributes and roles become key and value lists. The schema has no
  `$ref`, `anyOf`, `oneOf`, `allOf` or `pattern`, and at most 64 keys.
  The limit is a parameter, 64 by default. A schema past it fails to
  compile with the count and the parts of the schema that hold the most
  keys.
- **FR-021**: Compiling MUST accept the full stack or a chosen subset of
  its extractable types. Types with `extract: false` are left out.
- **FR-022**: The same stack MUST compile to byte-identical output on
  every run.

**Stamp and hashes**

- **FR-023**: The merged stack MUST have a content hash that ignores key
  order, comments, whitespace, file layout and Unicode normalization form,
  and changes when any definition changes.
- **FR-024**: The merged stack MUST give a stamp: the top pack's name and
  version, and the content hash.
- **FR-025**: The extraction and resolution stage hashes MUST include the
  pack's content hash, computed without its retrieval hints and its
  glossary. Retrieval hints enter no hash. The glossary has its own hash,
  which the engine uses per chunk
  ([engine brief §9](../../docs/product/engine-brief.md#9-configuration-added)).

**Coverage**

- **FR-026**: The coverage check MUST make no model call. For each
  competency question it reports each needed type or relation that the
  stack lacks, or defines with `extract: false`. Loading warns once for
  each question that fails the check.
- **FR-027**: A user pack MUST be able to add competency questions, and
  the check covers every question in the stack.

**Identity cases**

- **FR-028**: An identity case MUST record: an id; the pack stack it
  holds under; the entities already present, each with type, name,
  aliases, scope path and attribute values with their quotes; the
  mention, with the same fields plus the citing document's issuer, date
  and language; the expected outcome; and the identity elements (scope,
  keys, vetoes, name rule) the outcome depends on. A case kept apart by a
  veto also names the attribute expected to block.
- **FR-029**: The expected outcome MUST be one of: merge into a named
  existing entity; a new entity; a new entity with `same_as` links to
  named entities; or a model confirmation with the right candidate among
  those offered.
- **FR-030**: The 60 cases of the identity design MUST be recorded with
  their original ids. Cases added to meet FR-031, such as for
  `Procedure`, `Project` and `System`, get new ids in the same scheme.
- **FR-031**: For each shipped pack, the cases under its stack MUST
  cover every entity type the pack defines with a scope, a key or a veto,
  or whose identity fields it changes, with at least one case that must
  merge and one that must stay apart. Every key and veto the pack
  declares is named by at least one case.
- **FR-032**: A check MUST confirm that every type and attribute a case
  names exists in its stack, and that FR-031's coverage holds. It runs
  with the unit tests.

**Corpus**

- **FR-033**: A generator MUST write the corpus from a fact table kept in
  the repository: 30 to 60 documents, with at least 10 in Vietnamese, 10
  in English and 3 that mix both. The same fact table gives
  byte-identical output on every run and system.
- **FR-034**: The corpus MUST plant:
  - policy and procedure versions with issued and effective dates,
    supersession statements, and later mentions with no version;
  - meetings with chairs, attendees, decisions and action items with due
    dates and statuses;
  - two sources that define one metric differently, and a definition
    that changes over time;
  - figures with periods, units and basis, actual beside target;
  - two `OWNER_OF` statements on one object with different start dates,
    and two with the same start date;
  - a work or policy whose code or title matches another indexed
    document;
  - names written several ways: acronyms, both languages, short forms;
  - at least two companies with a same-titled policy, a same-named unit,
    a limit on the same metric, and a person of the same name.
- **FR-035**: The corpus MUST include the running example D1 to D5 as the
  engine brief states it, with Q-a, Q-b and Q-c in the golden set.
- **FR-036**: Each document MUST come with its metadata (id, language,
  issuer, the dates the text states) and its expected items, typed by the
  shipped stack, each with a verbatim quote.
- **FR-037**: The corpus MUST state the graph results a correct engine
  derives: which mentions across documents are one entity, version
  statuses (`current`, `superseded`, `conflicting`), supersession links,
  `TEXT_IN` links, and what changes when a named document is deleted.
- **FR-038**: The golden set MUST use the benchmark's golden-set fields
  (question, expected answer, expected sources, tags), with the question
  type, language, competency question and as-of date as tags. It covers
  the eight question types of
  [test-corpora.md](../../docs/reference/test-corpora.md#why-this-page-exists),
  at least three questions each, and every competency question of `core`
  and `enterprise-docs`. At least one question per type is hand-written,
  marked as such, and kept across regeneration.
- **FR-039**: Generation MUST fail, naming the document and the item,
  when a planted quote is not in its document's text or an expected item
  does not fit the stack.
- **FR-040**: The generated corpus MUST be committed under the test
  fixtures, and a check MUST fail when regenerating it gives different
  files.
- **FR-041**: The corpus and the identity cases MUST hold only fictional
  organizations, people and identifiers. The one exception is the codes
  of public legal documents, such as "39/2016/TT-NHNN", and the public
  authority that issues them, which a code's scope names.

**Architecture and docs**

- **FR-042**: The packs module MUST depend only on the standard library
  and the base dependencies. The engine may import it. The import rules
  enforce both, and pack problems raise `ConfigError`.
- **FR-043**: The docs MUST change with the code: `ARCHITECTURE.md` (the
  packs row is built), domain-packs.md and v1-packs.md (they link to the
  shipped files), test-corpora.md (where tier 1 lives), the engine brief's
  testing section (where the identity cases and the running example
  live), and the `AGENTS.md` status.

### Key Entities

- **Pack**: a named, versioned YAML file of types, enums, relations,
  events, facts, identity fields, retrieval hints and competency
  questions. Shipped, or written by a user.
- **Merged stack**: a pack with all its ancestors merged and checked.
  Read-only. It has a mode (`strict` or `discovery`), a stamp, and
  everything the engine reads.
- **Stamp**: the top pack's name and version, and the merged stack's
  content hash.
- **Compiled schema**: the flat structured-output schema for the whole
  stack or a subset of its extractable types.
- **Competency question**: an id, a text, and the types and relations it
  needs.
- **Coverage report**: per competency question, the needed names that are
  missing or not extracted.
- **Identity case**: existing entities, one mention, the expected outcome
  and the identity elements it depends on, under one pack stack.
- **Fact table**: the source of truth for the corpus. Documents,
  their facts, expected items and golden answers all come from it.
- **Corpus document**: rendered text, metadata and expected items.
- **Expected item**: an entity, relation, event or fact that a correct
  extraction returns from one document, with its quote.
- **Golden question**: a question, its expected answer, its expected
  sources and its tags.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `core` and `enterprise-docs` load with zero errors and zero
  warnings, and pass the coverage check for all 14 of their competency
  questions.
- **SC-002**: Every stack of shipped packs, the `finance` draft stack,
  and a test user pack that adds one type and one relation compile to
  schemas with none of the forbidden constructs and at most 64 keys.
- **SC-003**: Every loading, stacking and identity lint rule has a broken
  test pack that fails with that rule named: 100 % of the rules in
  FR-002 to FR-012.
- **SC-004**: Reordering, reformatting or decomposing the Unicode of a
  pack leaves its hash unchanged. Changing any one definition changes it.
  Changing only retrieval hints or the glossary changes no stage hash.
- **SC-005**: A user adds one relation and one competency question in
  their own pack, and loading, compiling and the coverage check pick both
  up with no code change.
- **SC-006**: Loading, checking and compiling the largest stack, the
  `finance` draft on `enterprise-docs`, takes under one second on a
  developer laptop.
- **SC-007**: The identity cases number at least 60. FR-031's coverage
  holds for both shipped packs, and the consistency check reports zero
  problems.
- **SC-008**: The corpus has 30 to 60 documents and meets FR-033's
  language mix. 100 % of planted quotes occur verbatim in their
  documents, and 100 % of expected items fit the stack.
- **SC-009**: The golden set has at least three questions per question
  type, and covers all 14 competency questions.
- **SC-010**: Two runs of the generator give byte-identical output, on
  every Python version in CI, and each run takes under 30 seconds.
- **SC-011**: A fresh install with no extras lists, loads and compiles
  the shipped packs, and all gates pass.

## Assumptions

- The corpus is rendered as Markdown in this feature. DOCX, PDF, PPTX and
  XLSX renderings, which test-corpora.md plans, arrive with the ingest
  parsers in feature 004. They need new dependencies, and nothing in this
  feature reads them. The fact table does not depend on the format, so a
  renderer can be added later. The running example's format labels (D1
  in DOCX, D2 in PDF) are kept as metadata until then.
- The 60 design cases were written in a throwaway script outside the
  repository, during the 2026-10-05 and 2026-10-06 design sessions. The
  script is recovered from the session record. If a case cannot be
  recovered word for word, it is rewritten from the case descriptions in
  the [identity criteria snapshot](../../docs/research/2026-10-05-entity-identity-criteria.md),
  keeping its id and its expected outcome.
- The design cases for Instrument belong to `finance`, which ships in
  M4. Until then they run under the `finance` draft, loaded by path as
  FR-019 already does, so no copy of its definitions can drift.
- In v1, any pack change except retrieval hints and the glossary counts
  as an extraction change, so it enters both the extraction and the
  resolution stage hashes. Selective re-extraction after a pack change is
  out of scope for v1
  ([domain-packs.md](../../docs/product/domain-packs.md#out-of-scope-v1)).
  Over-triggering a re-index is safe, and under-triggering is a
  correctness bug.
- A pack file path in a profile is relative to the profile file. A path
  in `extends` is relative to the pack file that holds it.
- The stack's mode is the one the top pack sets, else the nearest
  ancestor's. `discovery` mode is recorded here. Its review queue belongs
  to extraction in feature 004.
- A pack version is a positive integer, bumped on any change, as in the
  drafts.
- Later features own: the extraction prompt that the pack drives, the
  `describe_schema` summary and its token budget (feature 005), the trial
  run of the design workflow, and the engine runs of the identity cases
  and the corpus.
- The open questions of domain-packs.md stay open: Vietnamese aliases in
  packs, the number of types per extraction pass, and enum caps in
  provider schemas. The first two are measured with a real model in M1.
  Nothing here depends on their answers.
- Depends on M0: the profile and its stage hashes, safe YAML loading, and
  `ConfigError`.
- Estimate: about six working days for one developer with agents. The
  packs module takes two days, the shipped packs and the profile change
  half a day, the identity cases one day, and the corpus two and a half.
