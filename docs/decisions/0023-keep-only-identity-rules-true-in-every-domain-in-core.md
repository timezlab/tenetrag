# Keep only identity rules true in every domain in `core`

**Status:** accepted; amends [0016](0016-identify-entities-by-scope-keys-and-vetoes.md)
**Date:** 2026-10-16
**Deciders:** Liam Lee (audit of `core`, 2026-10-16)

## Context
A child pack only adds to what it inherits
([research R3 of 002](../../specs/002-packs-and-corpus/research.md#r3-stacking)).
It can put keys in front, add vetoes and add values to a scope's `when`.
It cannot remove a scope, a key or a veto, change `names` or a time
kind, or add a description or examples to an inherited type. Every rule
in `core` therefore binds every pack built on it.

On 2026-10-16 six agents each wrote child packs over `core` for one
area: people and organizations; law, government and places; science and
health; technology and industry; finance and time; and meaning across
domains (negation, plans, symmetry). Every child pack loaded, so a child
can add every type its domain needs. But some of `core`'s rules were
wrong for some domains, and no child pack could undo them:
- **Person was scoped by employer.** A known, different scope blocks
  every resolution stage (ADR 0016, decision 3). A person who changed
  jobs became two people with no link. ADR 0016 itself says a unit or a
  title is never a veto, because it changes. An employer changes too,
  and a scope blocks harder than a veto.
- **Event merged on `[time, title]`.** Two companies' "Đại hội đồng cổ
  đông thường niên" on one day became one event. `Meeting` had the same
  flaw inside one company: two departments' weekly meetings on one
  Monday merged on `[time, title]`, and two meetings one person chaired
  on one day merged on `[time, chair]`.
- **Every `is_a` subtype took its parent's time.** A child could not
  declare a conference that runs for days under the point-time `Event`.
- **Statement had no time,** so it took the fact default, an interval.
  A statement is made at a moment.
- **A global email key** merged two people who sign from one shared
  mailbox.
- **Name corroboration compared text.** "Phòng Tài chính" of Alpha and of
  Beta, or the title "Giám đốc" at two companies, corroborated two
  different people. It also ignored time.
- **Product's provider** could only be an organization.
- **Core relations had no description,** and `Place`, `Product` and
  `Concept` had no examples. A child cannot add either.
- **domain-packs.md's stacking list** did not match the code.

## Decision
1. **`core` holds only the identity and time rules that hold in every
   domain.** A rule that holds only in some domains goes in the pack for
   those domains. A child can tighten identity but never loosen it, so a
   rule that is wrong in one domain is wrong in every stack that
   inherits it.
2. **A scope taken from an attribute that changes over an entity's life
   stays only where the name rule needs it.**
   - `Person` has `names: evidence`, so a shared name never merges alone.
     Its employer scope added splits, not safety. `core`'s `Person` has
     no scope.
   - `enterprise-docs` states the full employer scope, inherited from the
     document, since an employee ID is unique only within its employer.
   - `Product`, `Place` and organization units keep their scopes. Their
     names are keys, so without a scope a "Galaxy" of two providers, or
     two communes of one name, would merge. The cost, a split when the
     parent changes, is listed under Worse.
3. **Stacking: a child pack may add a whole scope** (`role` and `to`,
   with `inherit` and `when` if wanted) to an inherited entity type that
   has none. It only keeps more entities apart. Adding `corroborate`,
   which makes merges easier, a `where`, or a `when` to a scope that had
   none still fails with `stack.added-identity`.
4. **Person:**
   - `born_on` is a veto. A birth date is fixed for life, single-valued,
     and stated in a form code can check against its quote.
   - Two dates of different precision compare at the coarser one, for
     every date veto: 1980 and 1980-05-12 do not differ.
   - `email` stays a global key, with a guard for types with
     `names: evidence`: a key hit merges only when the two names agree.
     They agree when every word of the shorter name, compared without
     case or diacritics, is in the longer one, and an initial matches a
     word that starts with it. Otherwise the mention becomes a new entity
     with a `same_as` link of origin `key_name_conflict`. A mention with
     no name merges.
   - A shared unit is a `MEMBER_OF` to the same resolved organization. A
     shared title is a `HOLDS_POSITION` with the same title at the same
     resolved organization. When both sides date the link and the
     intervals do not overlap, it does not corroborate.
   - Without a scope, a job change gives a `same_as` link (`same_name`),
     not a split with no link.
5. **Events:**
   - `core`'s `Event` has no `identity`, so plain events never merge
     across documents. A child type adds an identity with a role.
   - `Meeting` merges on `[time, title, chair]`.
   - An `is_a` subtype may state its own time. The parent's time is the
     default. An inherited type still keeps its time.
   - `Statement` is a point.
6. **Works** keep their issuer scope for every kind, and the description
   says the issuer is who issued or wrote the work, not a publisher. A
   code with no four-digit year, such as "15/QĐ-HĐQT", restarts its
   numbering every year. It is a key only when both sides know the issue
   year and the years match. Otherwise the candidate gets a `same_as`
   link (`ambiguous_key`).
7. **Products:** the provider is an organization or a person, and
   `OFFERS` can start at a person. The description says the provider is
   the maker or operator, not a reseller.
8. **Text a child cannot add:** every `core` relation has a description,
   every `core` entity type has examples, and `Concept` excludes named
   products, systems, documents and organizations.

The values are in [core.yaml](../../src/tenetrag/packs/shipped/core.yaml)
and [enterprise-docs.yaml](../../src/tenetrag/packs/shipped/enterprise-docs.yaml),
the engine rules in
[engine brief §2.6 and §2.7](../product/engine-brief.md#26-resolve-entities-e8),
and the questions left open in
[domain-packs.md](../product/domain-packs.md#open-questions).

## Alternatives considered
- **Let a child pack override inherited rules.** Rejected: a stack would
  then mean different things in different orders, and no pack could
  rely on the identity it declared.
- **Move `email` out of `core`.** Rejected: emails identify people in
  news and filings too. The name guard handles shared mailboxes.
- **Drop the scope for publications** with `when: {kind: [...]}`.
  Rejected: an unscoped publication's title would be a global key, and
  two books with one title would merge. A split costs less than a wrong
  merge.
- **Make every scope from a changing attribute soft,** a link instead of
  a block. Deferred: without the time a scope held, a soft scope merges
  two units of one name under two parents. Dated scopes are an open
  question.

## Consequences

**Better:**
- A person who changes jobs stays linked by `same_as`.
- Two companies' same-day AGMs, and two units' same-titled meetings,
  stay apart.
- A domain pack can declare events that last, and scope a type `core`
  left unscoped.
- The stacking rules in the docs match the code.

**Worse:**
- Under `core` alone, two same-named people of different companies get a
  `same_as` link instead of a block. Retrieval that follows `same_as`, at
  weight 0.5, can mix them. `enterprise-docs` keeps the block.
- A plain `Event` reported by two documents gives two nodes.
- The engine gains four rules: the name guard on key hits,
  corroboration by resolved organization and overlapping time, dates
  compared at the coarser precision, and codes without a year.
- A wrong `born_on` splits a true pair, as any veto can. The quote check
  bounds it.
- These limits stay, and no child pack can lift them:
  - A place moved under another parent (the 2025 province mergers), a
    unit moved under another branch, or a product taken over by another
    provider splits, with no link.
  - `registration_id` is unique only within one country's register, so
    a corpus that crosses borders can collide.
  - A work with several issuers, such as a joint circular, a contract
    or a paper with many authors, has one scope. Mentions that name
    different issuers split.
  - `Decision` still merges two decisions that one body made on one
    subject on one day.

**Must now be true:**
- domain-packs.md lists the stacking rules the code applies, including
  the added scope, `is_a` time, and the fields a child cannot add to.
- The engine brief's §2.6 table and rules and its §2.7 table follow this
  ADR. v1-packs.md describes the new identity of `core` and
  `enterprise-docs`.
- Research R3 and R11 and the data model of
  [002](../../specs/002-packs-and-corpus/): PER-6 moves to the
  `enterprise-docs` cases, where the employer scope keeps its outcome.
  Four Person cases are added: a `born_on` veto, a job change linked by
  `same_as`, a shared mailbox, and one employee ID at two companies. A
  `same_as` outcome may now expect `merge`, as a split that keeps a link.
- ADR 0016's status notes this amendment.

## Revisit if
- The M1 sample shows `same_as` links that mix same-named people in
  `core`-only corpora.
- Scopes carry the time they held, so a moved place or unit can merge.
- A domain shows a rule in `core` that still does not hold for it.
