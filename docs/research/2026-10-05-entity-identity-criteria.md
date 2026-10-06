# What identifies a node: criteria for identity attributes

> **Snapshot, 2026-10-05 — not maintained.** Follows
> [2026-10-05-entity-homonyms.md](2026-10-05-entity-homonyms.md), whose
> section 6 proposal this revises. Three lanes (papers, practice and
> standards, open-source matcher code) and a 57-case identity suite run in
> the session scratchpad (`identity-suite/suite.py`, not in the repo).
> Nothing here is decided: section 8 waits for the author's approval. Every
> example is synthetic, except one public circular number.
> **Update 2026-10-06:** section 8 was accepted as
> [ADR 0016](../decisions/0016-identify-entities-by-scope-keys-and-vetoes.md).
> The maintained rules are in [engine brief §2.6](../product/engine-brief.md#26-resolve-entities-e8)
> and [domain-packs.md](../product/domain-packs.md#identity-fields).
> Three cases were added on 2026-10-06 (60 in all), and global keys now
> skip the scope check; R2 still has zero wrong merges.

Labels: **[source]** read in code at the cited path · **[primary]** official
doc, spec or law text · **[secondary]** summary or vendor page ·
**[peer-reviewed]** / **[book]** / **[preprint]** · **[observed]** seen in
the suite run · **[inferred]** our reasoning.

## 1. Question

The author asked whether the scope / identity / distinct_on / profile
attributes proposed earlier the same day:
- are enough to tell every homonym apart;
- are minimal;
- really identify the node;
- avoid wrong merges, which could become an edge no other engine has.

To answer, we need a test that decides, per attribute, whether it belongs in
identity and in which role.

## 2. What the literature says identity is

- **Sufficient and necessary conditions.** An identity criterion has two
  sides: conditions sufficient for equality, and conditions entailed by
  equality, so that a difference proves distinctness. Full criteria are often
  hard to state, and analysis may use only the necessary side ("if two things
  do not have the same essential properties they are not identical").
  Guarino & Welty, *An Overview of OntoClean*, Handbook on Ontologies (2004),
  pp. 154–155 [book; read].
  - In our terms, a key is the sufficient side and a veto is the necessary
    side.
- **Rigidity.** Properties that can change without the thing changing (a
  role, a department, a job title) are anti-rigid and cannot carry identity.
  Each entity falls under one sortal that supplies its identity criterion.
  Same source, p. 156.
  - So identity is defined per type, and attributes that change over time
    stay out of keys and vetoes.
- **Minimal keys.** A key is a property set under which all resources are
  distinguishable. A minimal key has no subset that is a key. Supersets of
  keys are keys. Soru, Marx & Ngonga Ngomo, ROCKER, WWW 2015
  ([arXiv 1705.04380](https://arxiv.org/abs/1705.04380)) [peer-reviewed;
  definitions read].
  - This gives a mechanical test: drop one attribute and see whether
    anything stops being told apart.
- **Conditional keys.** VICKEY mines keys that hold only in part of the
  data, and improves linking by up to 47 points per its abstract.
  Symeonidou et al., ISWC 2017
  ([HAL](https://hal.archives-ouvertes.fr/hal-01647597)) [peer-reviewed;
  abstract only].
  - "A unit's name is unique within its parent" is a conditional key, and
    `scope` is the condition.
- **Keys come with comparators.** Matching dependencies and relative
  candidate keys say which attributes to compare and how (exact, normalized,
  similar). Fan, Jia, Li & Ma, VLDB 2009 [peer-reviewed; abstract only].
- **Hard and soft constraints.** Dedupalog separates hard constraints
  (cannot-link) from soft ones. Arasu, Ré & Suciu, ICDE 2009
  [peer-reviewed; abstract only].
- **Time.** *Disagreement decay* is the chance that an entity changes an
  attribute value within Δt. *Agreement decay* is the chance that two
  different entities share a value within Δt. Birth date has disagreement
  decay 0; a balance has 1. Requiring both name and affiliation to agree
  splits true entities; requiring only the name merges distinct ones. Li,
  Dong, Maurino & Srivastava, *Linking temporal records*, PVLDB 4(11), 2011
  ([PDF](https://ifi.uzh.ch/dbtg/Staff/peili/paper506-li-final.pdf))
  [peer-reviewed; pp. 1–4 read].
- **Unconstrained identity links go wrong often.** Estimates of erroneous
  `owl:sameAs` links in Linked Data range from 2.8 % to 20 %. In one
  250-link sample, three experts accepted only 73, 132 and 181 links. Raad
  et al., *The sameAs problem* survey
  ([arXiv 1907.10528](https://arxiv.org/abs/1907.10528)) [survey; numbers
  secondhand from it].
- **Merges distort analysis, and Asian names drive most errors.**
  Initial-based name disambiguation changes network statistics, and Asian
  names account for most misidentifications. Kim & Diesner, JASIST 2016
  ([arXiv 1502.06306](https://arxiv.org/abs/1502.06306)) [peer-reviewed;
  abstract only].
- **Common values are weak evidence.** Winkler's frequency-based weights
  make agreement on a common value count for less [secondary; exact report
  not identified].
- **Vietnamese surnames.** Nguyễn is 31.5 % of Vietnamese, per a 2022
  figure on Wikipedia; other sources say 38–40 % [secondary]. No full-name
  collision statistic was found.
- **Uneven-cost evaluation.** Generalized merge distance lets a merge cost
  more than a split. Menestrina, Whang & Garcia-Molina, VLDB 2010
  [peer-reviewed; abstract only].

## 3. What matching systems do

| System | Strong identifiers | What blocks a match | Missing value | Common names |
|---|---|---|---|---|
| Senzing (template config 4.4.0, third-party copy) | features with frequency class F1 (tax ID, national ID, passport, LEI) | rules carry a disqualifier `DIFF_EXCL`: an *exclusive* feature scored unlikely or no-chance | no score, so no veto | frequency classes F1 / FF / FM / FVM / NAME per feature type |
| nomenklatura logic-v2 (OpenSanctions) | typed identifiers (LEI, ISIN, INN…) weighted 0.95–0.98 | none hard: country −0.2, DOB −0.15/−0.25, gender −0.2; these qualifiers cannot create a match | penalty only when both sides have values | family-name weight only |
| Splink 5.0.0 | exact levels | no veto; m = 0 is clamped; blocking rules act as the gate | neutral (Bayes factor 1) | `log2(u) − log2(max(tf_l, tf_r, floor))` |
| Reltio MDM | match rules | a *negative rule* demotes a merge to review | `nullValues` operator | — |
| ServiceNow IRE | identifier entries | none; on duplicates the oldest CI wins | — | — |
| Graphiti v0.30 | none; exact normalized name | none; a single exact hit merges without the LLM | — | entropy gate on fuzzy only |

Sources:
- Senzing: field values from `sz-rust-sdk-configtool/tests/fixtures/g2config_template.json` [source, third-party copy of the template]. Behaviour classes described on [Senzing's principle-based matching page](https://senzing.com/principle-based-matching/) [secondary]. In that copy, EMAIL is F1 but not exclusive, NAME is not exclusive, and DOB is exclusive and stable.
- nomenklatura: `nomenklatura/matching/logic_v2/model.py:44-117`, `compare/countries.py:12`, `compare/dates.py:54-78` [source].
- Splink: `splink/internals/comparison_level.py:671-731` [source].
- [Reltio negative rule](https://docs.reltio.com/en/explore/get-a-crash-course/get-ready-to-turn-your-data-into-action/learn-about-multidomain-mdm/reltio-match-and-merge/match-group-elements---description-and-configuration/negative-rule) [primary].
- [ServiceNow duplicate CIs](https://www.servicenow.com/docs/r/8K~WUyyBmjUR0pLPxM8yeA/mHpV4r7JA3P3H4ZqscV_TQ) [primary].
- Graphiti: `dedup_helpers.py:236-249` at b7fc30f [source].

Two more:
- Wikidata allows equal labels, but never the same label *and* description in one language ([Help:Label](https://www.wikidata.org/wiki/Help:Label)) [primary].
- FollowTheMoney marks each property `matchable` or not, and descriptive properties are not matchable (`followthemoney/schema/LegalEntity.yaml`) [source].

What follows [inferred]:
- Every system uses the same three behaviours:
  - how many entities share a value (frequency);
  - whether an entity has one value at a time (exclusivity);
  - whether the value lasts for the entity's life (stability).
- No product read hard-blocks a merge on a conflict: they penalize, or demote to review. A hard veto is stricter than all of them. Section 7 argues why that fits a fact graph.

## 4. Identifiers in standards and Vietnamese law

| Type | Rigid identifier | Unique within | Changes over time |
|---|---|---|---|
| Company | mã số doanh nghiệp: one per enterprise, never reused (Luật Doanh nghiệp 2020, Điều 29) [secondary]; LEI, ISO 17442, "only ever one entity" ([GLEIF](https://www.gleif.org/en/about-lei/iso-17442-the-lei-code-structure)) [secondary] | country; world for LEI | name, address, legal form |
| Branch, dependent unit | 13-digit tax code N1–N10 + 001–999 (Thông tư 105/2020/TT-BTC, Điều 5) [secondary]; that N1–N10 is the parent's code is [inferred] | the parent | name |
| Department, team | none | the parent organization (W3C ORG) | name, parent |
| Person | none for a name; employee ID, work email | the employer's systems | name, unit, title |
| Place | mã đơn vị hành chính: unique, kept for the unit's life, not reused (Quyết định 19/2025/QĐ-TTg, 34 provinces from 2025-07-01) [secondary] | the level | name, parent, mergers |
| Legal document | number / year / type abbreviation – issuing body (Luật Ban hành VBQPPL) [secondary]; ELI adds point in time and version [secondary, not opened] | the issuing body | amendments, versions |
| Internal document | number per issuer per year (Nghị định 30/2020, previous snapshot) | the issuer | version, status, end date |
| Security | ISIN, not reused within 10 years (ASX paper, 2013) [secondary] | world | ticker (recycled; [SEC 34-77123](https://sec.gov/files/rules/sro/nms/2016/34-77123.pdf), 90 days) |
| Product | GTIN: brand owner prefix plus item ([GS1](https://gs1.org/1/gtinrules/en/new-product)) [secondary] | the brand owner | — |

Not verified:
- the EU Joint Practical Guide on static and dynamic references;
- ServiceNow dependent-CI identity;
- Akoma Ntoso naming, beyond the previous snapshot;
- whether merged provinces got new codes.

## 5. Four questions per attribute

The theory (section 2) and practice (section 3) reduce to four questions for
each attribute of an entity type:

| Question | Literature | Practice |
|---|---|---|
| U: is it unique within a known scope? | ROCKER discriminability; VICKEY conditional keys | Senzing frequency F1 |
| R: does it stay fixed for the entity's life? | OntoClean rigidity; disagreement decay ≈ 0 | Senzing stability |
| E: does an entity have only one value at a time? | Dedupalog hard constraints | Senzing exclusivity |
| X: do documents state it, and can code check it? | gap: no paper measures extraction coverage | — |

The answers give the role [inferred]:

| Role | Needs | Examples | Never |
|---|---|---|---|
| **key** (sufficient) | U + R + X, as a minimal set within scope | `[scope, code]`, registration_id, ISIN | names of types whose names repeat (Person) |
| **veto** (necessary) | R + E + X; known on both sides and different → never merge | issued_on, version_label, employee_id, LEI | names (aliases, renames), unit, title, end date, status |
| **evidence** | a value many entities share (U fails) | a person's name, a short company name | deciding a merge alone |
| **profile** | anything else | effective dates, status, category | identity decisions |

Rules that follow:
- **Keys must be minimal; vetoes need not be.** A veto only removes
  candidates. Each extra veto costs a false split when extraction misreads
  it, and a split is recoverable with `same_as`. So a veto earns its place
  when it is rigid, single-valued and checkable, and a hard case or a
  standard needs it.
- **Every key attribute declares a comparator**: code (case, spaces, "số",
  Đ→D), digits only, lower-case email, date (Fan et al.).
- **Scope is part of every key of a scoped type**, unless the value carries
  its own issuer, such as "39/2016/TT-NHNN".
- **Missing is not different** (Senzing, nomenklatura, Splink all agree).

## 6. Gaps in the earlier proposal

The suite (section 9) ran the earlier proposal, R1, against 57 cases.
R1 merged 11 cases that must stay apart [observed]:

| Gap | Cases | Fix |
|---|---|---|
| Scope is flat (company only), so two branches' "Phòng Khách hàng doanh nghiệp" merge | UNIT-2 | scope is a path (company › branch › unit), known exactly or only to a higher level |
| A person's name is a key; common names merge | PER-1, PER-5 | name is evidence; keys are employee ID and email; employee ID is a veto; a name match needs a matching unit or title |
| Rigid identifiers are missing as vetoes | UNIT-7 (founding date), ORG-5 (LEI), INS-5 (ISIN) | add them as vetoes |
| Types not covered | WRK-2, PRD-1, PLC-1, INS-1, INS-2 | scope for Work (issuer), Product (provider), Place (parent place); temporal key for tickers |

It also split, or sent to the LLM, cases that should merge:
- **A mention without a version becomes ambiguous** (POL-3, POL-4, POL-10). Fix: resolve it to the version in force on the citing document's date.
- **No comparators** (ORG-4, POL-6), so "0105 550 001" and "Số 12/2025/QD-HDQT" split.
- **Rename statements are unused** (ORG-3, UNIT-6), so every rename goes to the LLM.
- **Strong keys are missing.** Without email, employee ID, LEI and branch tax code (PER-4, PER-8, ORG-6, UNIT-11), those cases fall back to the LLM or split.

## 7. Why hard vetoes, when products use penalties

- **A wrong merge spreads; a wrong split does not.** A wrong merge corrupts
  facts, which is why the earlier test superseded Alpha's limit with Beta's.
  It also mixes `TEXT_IN` files and labels, and the error spreads through
  traversal. A wrong split leaves two nodes that `same_as` still joins, and
  retrieval can follow that link [inferred].
- **Vetoes here are narrow.** Products penalize because their features
  are noisy (addresses, phone numbers). Our vetoes are limited to rigid,
  single-valued values that code checks against a quote: dates, codes, tax
  IDs [inferred].
- **Blocked merges stay visible.** Reltio's review queue is the useful part
  of its design. A blocked candidate is recorded with the attribute, both
  values and both quotes, so a reviewer or a user rule can override it.
- **The run record counts blocked candidates**, the same way it counts
  unknown-scope merges.

## 8. Revised proposal (R2, awaiting approval)

Pack format sketch:

```yaml
Policy:
  scope: {from: issuer}                # whose thing it is; first part of every key
  attributes:
    code:           {range: str,  identity: veto, compare: code}
    title:          {range: str}
    version_label:  {range: str,  identity: veto}
    issued_on:      {range: date, identity: veto}
    effective_from: {range: date}      # profile
    effective_to:   {range: date}      # profile: changes when a policy is extended
    status:         {range: DocStatus} # profile
  identity:
    keys: [[scope, code], [scope, title, version_label], [scope, title, issued_on]]
    name: versioned    # a mention with no version means the version in force on the citing date
Person:
  scope: {from: employer}
  attributes:
    employee_id: {range: str, identity: veto, compare: upper}
    email:       {range: str, compare: lower}
  identity:
    keys: [[scope, employee_id], [email]]
    name: evidence     # a name match needs corroboration, else LLM with profiles, else same_as
    corroborate: [unit_at, title_at]   # MEMBER_OF / HOLDS_POSITION at the mention's date
```

Per type:

| Type | scope | keys | vetoes | name |
|---|---|---|---|---|
| Company | — | registration_id · lei | registration_id, lei | the full registered name is a key; short names are evidence |
| Org unit | parent path | registration_id (branches) | registration_id, established_on | key within the parent |
| Person | employer | [scope, employee_id] · email | employee_id | evidence + unit or title at the date |
| Policy, Procedure | issuer | [scope, code] · [scope, title, version_label] · [scope, title, issued_on] | code, version_label, issued_on | versioned: no version → in force on the citing date |
| Work | issuer | code if it carries its issuer · [scope, code] | code, issued_on | key within the issuer |
| Project | owner | [scope, code] | code | key within the owner |
| System | owner | — | — | key within the owner |
| Product | provider | — | — | key within the provider |
| Place | parent place | — | — | key within the parent |
| Instrument | — | isin · [exchange, ticker] listed on the date | isin | not identity |
| Metric, Concept | — | — | — | the term is the node; meanings are `Definition` facts per source |

Resolution order:
1. Type, scope and vetoes filter the candidates.
2. Keys match on surface and alias values, never on LLM-proposed translations.
3. The name rule for the type applies (key, evidence, versioned or none).
4. Fuzzy candidates within scope go to a listwise LLM confirmation.
5. Otherwise the mention becomes a new entity.

Two hits at any step mean a new entity plus `same_as`. Unknown scope matches only a single candidate, as before.

Pack lint at load:
- A veto attribute must be declared rigid and single-valued, and a name
  attribute can never be a veto.
- A key of a scoped type includes `scope`, unless the pack marks the code
  as carrying its issuer.
- Every type ships hard cases: pairs that must merge and pairs that must
  stay apart.

Left out on purpose, because documents rarely state them:
- System asset IDs;
- product GTINs;
- administrative codes.

A structured-data pack can add them.

## 9. The suite

[observed] 57 synthetic cases: 29 that must stay apart, 28 that must merge.
Each case has existing entities, one mention, and the expected referent.

| Outcome | R0 (brief) | R1 (earlier proposal) | R2 (revised) |
|---|---|---|---|
| correct | 20 | 34 | 55 |
| LLM decides, right candidate offered | 7 | 6 | 2 |
| soft split (`same_as`) | 0 | 3 | 0 |
| hard split | 2 | 3 | 0 |
| LLM sees a pair that must stay apart | 3 | 0 | 0 |
| **wrong merge** | **25** | **11** | **0** |

R2's two LLM cases:
- UNIT-9: an English unit name in the same company.
- PER-7: a bare common name with no unit or title. R1 merged this one directly and happened to be right.

**Minimality check.** Removing any single element of R2 makes at least one
case worse: each scope, each key and each veto, plus the person-name rule and
the dated-version rule. Some examples:
- dropping the founding-date veto lets the re-created "Phòng Đầu tư" merge
  into the dissolved one (UNIT-7);
- dropping the LEI veto lets a same-named foreign company merge (ORG-5);
- dropping the dated-version rule turns POL-3 and POL-4 into `same_as`.

The first run had nine elements no case needed. Six (LEI, branch tax code,
employee ID, the composite title keys, code and version vetoes) got a
realistic case. Three (asset ID, GTIN, administrative code) were dropped.

**Over-specification check.** Adding an attribute that changes over time as a
veto breaks merges that must happen:

| Added veto | Breaks |
|---|---|
| unit | PER-3 (moved unit) |
| title | PER-2 (promoted) |
| `effective_to` | POL-8 (extended) |
| company name | ORG-2, ORG-3, ORG-6 (renamed) |

## 10. Limits

- **The cases were written alongside R2,** so they can be biased toward it.
  Each case is a documented homonym class (sections 2–4), but the real test
  is a labelled sample from a corpus in M1. Report merges and splits
  separately, with merges costed higher (generalized merge distance).
- **The suite models the rules pairwise.** It is not the engine, and it does
  not simulate the LLM: "LLM decides" means the right candidate was offered.
- **Some pairs have identical evidence and different truths.** For example,
  "Phòng Pháp chế" with no letterhead and one known candidate, when the
  document is really from a company not yet in the graph. No rule gets both
  right, and the single-candidate rule picks the merge. The run record's
  unknown-scope merge count makes this visible.
- **An extraction error in a veto value splits a true pair.** Code checks
  dates and codes against quotes, which bounds this. The rate needs
  measuring in M1.
- **Among the ten engines and libraries read, none declares per-type scope,
  vetoes and comparators** (previous snapshot, section 2). That supports
  identity as a TenetRAG strength. It is not a survey of every product.
