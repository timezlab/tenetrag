# Identify entities by scope, keys and vetoes declared in the pack

**Status:** accepted
**Date:** 2026-10-06
**Deciders:** Liam Lee (sessions 2026-10-05 and 2026-10-06)

## Context
The engine brief resolved entities by name, plus identity keys that
contain names, such as `[title, version_label]`. A test added a second
company to the running example: Công ty CP Beta's own "Quy chế công tác
phí", version 1. The resolver produced four wrong results:
- Beta's policy merged into Alpha's version 1.
- Both companies' "Phòng Tài chính" merged.
- Beta's 800,000 VND/day limit joined the version group of Alpha's
  limits, so Alpha's limit became `superseded`.
- One `TEXT_IN` edge set pointed the merged policy at both files.

Research ([homonyms](../research/2026-10-05-entity-homonyms.md),
[identity criteria](../research/2026-10-05-entity-identity-criteria.md))
found:
- **Engines.** Of the ten engines and libraries read in source, none keeps
  homonyms apart by attributes. They key on the name, or partition hard by
  tenant. Graphiti merges a single exact-name hit without an LLM call.
- **Theory.** An identity criterion has a sufficient side, which proves two
  things are the same, and a necessary side, which proves them different
  (OntoClean). Attributes that change over an entity's life, such as a
  role, cannot carry identity. A key can hold only within a context
  (conditional keys).
- **Practice.** Matchers describe each attribute by how many entities share
  a value, whether an entity has one value at a time, and whether the value
  lasts (Senzing). A missing value never counts against a match. Products
  penalize conflicts or send them to review rather than block.
- **Standards.** Every identifier standard read puts the issuer or parent
  inside the identity: ELI and Akoma Ntoso for documents, W3C ORG for
  units, Luật Doanh nghiệp 2020 for companies, ISIN for securities.

A suite of 60 synthetic homonym cases ran three rule sets. It had 57
cases at first, and three were added on 2026-10-06 (decision 5 and the
company registration veto):

| Rule set | Wrong merges |
|---|---|
| R0: the brief's resolver | 25 |
| R1: a first scoped proposal | 11 |
| R2: this decision | 0 |

Removing any single element of R2 makes at least one case worse. Adding an
attribute that changes over time as a veto (unit, title, end date, company
name) split cases that must merge.

## Decision
1. **Names are labels, not identity.** Each entity type in a pack declares:
   - `scope`: whose thing it is;
   - `identity`: keys, with the scope in front;
   - `vetoes`: attributes that block a merge when they differ;
   - `names`: how the name counts;
   - `corroborate` and `version_start`, for the name rules below;
   - `compare` and `unique` on key and veto attributes.

   Every other attribute only describes the entity.
2. **Attribute roles come from four questions.**
   - Is the value unique within a known scope?
   - Does it stay fixed for the entity's life?
   - Does an entity have one value at a time?
   - Do documents state it, in a form code can check?

   A key needs the first, second and fourth, as a minimal set. A veto needs
   the second, third and fourth. A name, a unit, a title, an end date or a
   status is never a veto.
3. **Scope is a path,** such as company › branch › unit. Its source order:
   1. the text, as a reference to another extracted entity;
   2. caller metadata;
   3. the document card's issuer, read from the letterhead with a quote;
   4. the profile's `default_issuer`;
   5. otherwise unknown.

   Sources 2–4 apply only where the pack's scope inherits from the
   document. `enterprise-docs` turns that on for internal documents, and
   `core` leaves it off, since a news publisher is not the employer of
   everyone it names. The source is recorded. A known, different scope
   blocks every resolution stage, including glossary and checked hints,
   except the global keys of decision 5. An unknown scope matches only
   when exactly one candidate exists, and the run record counts those
   merges.
4. **Vetoes block outright.** When both sides know a veto value and the
   values differ, the two never merge. A missing value is not a different
   one. Each blocked candidate is recorded with the attribute, both values
   and both quotes.
5. **Keys match surface values and aliases,** never names the LLM
   translated. A key or name that hits two entities is ambiguous: the
   mention becomes a new entity with `same_as` links to both.
   - A key made only of attributes unique everywhere (`unique: global`:
     a tax ID, an LEI, an ISIN, an email) is checked against every
     candidate that passes the vetoes, whatever its scope. The value alone
     proves identity, so an inherited scope that is wrong cannot split the
     pair.
   - A code that names its issuer (`unique: self_scoped`, such as
     "39/2016/TT-NHNN") does the same, and its mention inherits no scope
     from the document, since the code already says whose it is.
6. **Name rules per type:**
   - `key`: the name or an alias is a key within the scope.
   - `evidence`: the name alone never merges. A person's name merges when
     the mention and the candidate share a unit or a title. With no such
     context it goes to a listwise LLM confirmation. When unit or title
     differ, it becomes a new entity with `same_as`.
   - `versioned`: for governed documents. A mention with no version, code
     or date resolves to the version in force on the citing document's
     date.
   - `none`: the name is never matched.

   `Metric` and `Concept` are lexical: the term is the node, and each
   source's meaning is a `Definition` fact.
7. **Extraction follows the pack.** The prompt is compiled from these
   fields. Each attribute comes back as a value plus the quote that states
   it, and the scope as a reference. Code checks that the quote is in the
   chunk and that dates, codes and tax IDs match their quote, before any
   value is used. Each value is stored per source.
8. **Fact version keys can name `issuer`:** the scope of the fact's source,
   else the document's issuer. `Requirement` and `Definition` use it, so
   one company's limit never supersedes another's.
9. **Identity is tested.** Pack loading lints identity: a veto must be
   single-valued and cannot be a name or title, and keys of scoped types
   include the scope. Each shipped pack carries hard cases per type, pairs
   that must merge and pairs that must stay apart. CI requires zero wrong
   merges on them.

The per-type values are in
[engine brief §2.6](../product/engine-brief.md#26-resolve-entities-e8) and
the [draft packs](../product/packs/). The format is in
[domain-packs.md](../product/domain-packs.md#pack-format).

## Alternatives considered
- **A separate index per company.** Rejected: questions across companies
  become impossible, and units, people and systems still collide inside one
  company.
- **Name match plus LLM confirmation only,** as Graphiti does. Rejected:
  the LLM sees two same-named policies as one when nothing tells them apart,
  and an exact-name hit never reaches it.
- **Penalties instead of vetoes,** as nomenklatura scores and Reltio's
  negative rules do. Rejected: a strong match elsewhere still outweighs a
  conflict. Their vetoed features are noisy, such as addresses. Ours are
  rigid values that code checks against a quote.
- **Probabilistic scoring** (Fellegi–Sunter, Splink). Deferred: it needs
  labelled pairs per corpus. Revisit if fixed rules leave too many splits.
- **A separate `OrgUnit` type.** Rejected for v1: `Organization` keeps one
  type, and its scope applies by `category`.
- **A Work-level node above versions** (FRBR). Deferred: the dated-version
  rule resolves mentions without a version.
- **LLM-written entity summaries as identity evidence.** Rejected: costly,
  and they drift between runs.

## Consequences

**Better:**
- Same-named policies, units, people, systems and products of different
  organizations stay apart, and one company's facts never supersede
  another's.
- Every merge has a recorded reason (a key, a name rule, or an LLM
  verdict). Every blocked candidate is visible with its quotes.
- Labels tell homonyms apart, such as "Phòng Tài chính (Công ty CP Beta)",
  in retrieval output and agent tools.
- Identity becomes a measured property of the engine.

**Worse:**
- Extraction output grows: a quote per attribute, plus scope references.
- People with common names need more LLM confirmations, and some stay split
  with `same_as` until a unit, title, email or employee ID joins them.
- An extraction error in a veto value splits a true pair. The quote check
  bounds it, and `same_as` keeps the pair linked.
- An unknown scope with a single candidate can still merge wrongly when the
  real owner is not in the graph yet.
- Pack authors declare more, and must write hard cases.

**Must now be true:**
- `domain-packs.md` defines `scope`, `vetoes`, `names`, `corroborate`,
  `version_start`, `compare`, `unique`, the identity lint and identity
  cases. The draft packs use them.
- The engine brief's card, extraction, validation, resolution, versions,
  output, store protocol and tests follow this ADR.
- Stores keep per-attribute sources and blocked candidates, and delete them
  with their document.
- `find_by_identity` takes a scope, or "any scope" for the single-candidate
  rule.
- The run record counts unknown-scope merges, blocked candidates and
  ambiguous keys.
- The suite's 60 cases become engine tests in M1, and each shipped pack's
  identity cases run in CI.
- The seven rules found by the engine-flow demo and the three
  large-document rules are part of the brief: the subject hint and
  `is_name`, scope and veto conflicts blocking every step, translations
  never matching by name, `TEXT_IN` on version
  labels, the next free hash on an id collision, ten-word alias n-grams,
  a hint threshold measured in M1, confirmation batches of at most 50
  pairs, one unit per document, and degree by distinct neighbours.

## Revisit if
- The M1 trial with a real model shows low recall of identity attributes,
  or a high rate of quote-check failures on them.
- The labelled M1 sample shows too many splits for people or governed
  documents.
- The fallback for an `Organization` with no category misjudges units.
- Questions about a policy as a whole, across versions, fail without a
  Work-level node.
