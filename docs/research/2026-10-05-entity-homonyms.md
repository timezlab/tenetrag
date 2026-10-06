# Same name, different thing: entity identity beyond the name

> **Snapshot, 2026-10-05 — not maintained.** Three lanes (engine source,
> identity standards, papers), two checks of Vietnamese law, and a prototype
> run on the synthetic engine-brief corpus. Nothing here is decided yet:
> the proposal in section 6 waits for the author's approval, and the
> maintained summaries ([graphrag-engines.md](../reference/graphrag-engines.md),
> [graphrag-research.md](../reference/graphrag-research.md)) are not updated.
> Every example is synthetic (Công ty CP Alpha, Công ty CP Beta).
> Section 6 is revised in [2026-10-05-entity-identity-criteria.md](2026-10-05-entity-identity-criteria.md).
> **Update 2026-10-06:** decided, as revised, in
> [ADR 0016](../decisions/0016-identify-entities-by-scope-keys-and-vetoes.md).

Labels: **[source]** read in code at the cited path · **[primary]** official
spec or law text · **[secondary]** summary, aggregator or vendor page ·
**[peer-reviewed]** / **[preprint]** papers · **[observed]** seen in the
prototype run · **[inferred]** our reasoning.

## 1. Question

A test of the engine brief's resolver (§2.6) added D6: company Beta's own
"Quy chế công tác phí, phiên bản 1". It produced four wrong results:
- Beta's policy merged into Alpha's v1 at stage 1, because `[title,
  version_label]` matched.
- Both companies' "Phòng Tài chính" merged at stage 2 (exact name).
- Beta's 800,000 VND/day limit joined the version group of Alpha's
  limits, so Alpha's 2,000,000 became `superseded` from 2025-04-01.
- One `TEXT_IN` edge set pointed the merged policy at both files.

The author's position: a node should be identified by descriptive attributes
(what it governs, who issued it, when, effective dates), not by its name.
The research question: how do engines, standards and papers keep homonyms
apart, and what should TenetRAG do?

## 2. Engines and record-linkage libraries (code lane)

Versions read: Graphiti v0.30.2, LightRAG v1.5.7, graphrag v3.2.0, cognee
main @ b32d8af, neo4j-graphrag-python 1.22.0, itext2kg v1.1.0, kg-gen main @
6259b4c, mem0 main @ abb81c8, Splink v5.0.0, dedupe main @ 3f61e79.

| System | Identity | Context beyond the name | Hard scope |
|---|---|---|---|
| Graphiti | normalized name, then MinHash fuzzy, then LLM | Only at the LLM step: attributes, labels, a 120-character summary, episode text | `group_id` limits candidate search |
| LightRAG | entity name string | none | storage `workspace` |
| MS GraphRAG | `(title, type)` | none | one index per corpus |
| cognee | uuid5 of the lowercased name | none | dataset or user permissions [inferred] |
| neo4j-graphrag | label plus property value, or similarity of listed properties | only the properties you list | `filter_query` and per-label matching |
| iText2KG / ATOM | `(name, label)`, then `0.8·name + 0.2·label` embedding at ≥ 0.8 | none | none |
| kg-gen | embedding clusters, then an LLM duplicate check on strings | none | none |
| mem0 | normalized text, or cosine ≥ 0.95 | none | `user_id` / `agent_id` / `run_id` |
| Splink | Fellegi–Sunter score over many attributes, term-frequency adjustment | yes | blocking rules act as gates; no cannot-link API |
| dedupe | learned classifier over fields | yes | "distinct" pairs are training labels, not constraints |

Findings:
- No engine separates homonyms from context alone. The ones that avoid
  cross-tenant merges partition hard: Graphiti `group_id`
  (`graphiti_core/utils/maintenance/node_operations.py` ~418–450), mem0
  `user_id` (`mem0/memory/main.py` ~605–650), LightRAG `workspace`
  (`lightrag/lightrag.py:418`) [source].
- Graphiti merges a single exact-name hit with no LLM call and no look at
  attributes (`dedup_helpers.py::_resolve_with_similarity`). Two companies'
  "Finance Department" in one `group_id` would merge [source for the path,
  inferred for the consequence].
- When several existing nodes share the name, Graphiti escalates to the
  LLM instead of picking one. Its prompt (`prompts/dedupe_nodes.py`) has a
  same-name, different-thing example and answers "no match" when unsure.
  This is the best prompt pattern to port (Apache-2.0) [source].
- LightRAG keys entities by name only. Issue #329 (a person and a place
  both named Washington, merged) was answered as expected behaviour
  [source].
- MS GraphRAG groups by `(title, type)`. Issue #1718: one title with two
  types leaves two nodes, and `finalize_entities` drops one of them with
  its edges [source].
- neo4j-graphrag merges with `apoc.refactor.mergeNodes` and
  `properties:'discard'`, so a wrong merge loses the other node's
  properties [source].
- cognee re-keys two same-name entities found in one chunk with
  `(name, chunk id, ordinal)`, which keeps them apart
  (`cognee/modules/graph/utils/expand_with_nodes_and_edges.py` ~92–110)
  [source].
- Graphiti issue #1771 (a competing vendor's review) says the merge record
  is discarded. Not verified.

## 3. Identity standards (web lane, plus two checks)

| Standard | Identity of a document or unit | Where the scope lives |
|---|---|---|
| IFLA LRM / FRBR | Work (the policy) vs Expression (a version or language) vs Manifestation (a file) | the creator relationship of the Work [secondary] |
| Akoma Ntoso naming convention | Work IRI `/akn/{country}/{doctype}/{subtype}/{author}/{date}/{number}`; Expression adds `/{lang}@{version-date}`; Manifestation adds `.{format}` | inside the identifier: country, author, date [primary] |
| ELI | LegalResource (Work) `is_realized_by` LegalExpression; `passed_by`, `jurisdiction`, `date_document`, `first_date_entry_in_force` | jurisdiction and issuing body [secondary; URI template not verified] |
| schema.org `Legislation` | `legislationIdentifier`, `legislationJurisdiction`, `legislationPassedBy`, `legislationDate`, `legislationLegalForce` | passed-by and jurisdiction, separate from the name [primary] |
| W3C ORG | `org:OrganizationalUnit` only has meaning within its parent; `org:unitOf` / `org:hasUnit` | the parent organization [primary] |
| Wikidata | label plus description must be unique; identifier properties carry a distinct-values constraint | the description tells same-label items apart [primary] |
| Senzing, Fellegi–Sunter | attributes weighted by frequency, exclusivity and stability; agreement on a common value is weak evidence | outcomes include "possibly same", not only merge [secondary] |

Vietnamese law, checked separately:
- **Nghị định 30/2020/NĐ-CP (công tác văn thư).** Điều 8 lists the
  mandatory components of an administrative document, including the
  issuing body's name, số và ký hiệu, place and date of issue, and tên loại
  và trích yếu nội dung. Numbers run per issuing body per calendar year.
  Điều 2: the decree applies to state agencies and state-owned enterprises;
  political and social organizations apply it as appropriate. Private
  companies are not bound by it [secondary: thuvienphapluat, dulieuphapluat
  summaries]. Many private companies copy the layout [inferred, not
  measured].
- **Luật Doanh nghiệp 2020, Điều 38 and 41.** Registering a Vietnamese
  company name identical to a registered one is prohibited; confusing names
  are also prohibited, with exceptions for subsidiaries on some points
  [secondary: hethongphapluat.com].

What follows [inferred]:
- A document number such as "12/2025/QĐ-HĐQT" is unique only within its
  issuer and year, so `code` alone is not a safe identity key for internal
  documents. National legal codes such as "30/2020/NĐ-CP" embed the issuer.
- A company's full registered Vietnamese name is close to a national key.
  A unit name such as "Phòng Tài chính" is not.
- Every standard puts the issuer or parent inside the identity, and keeps
  version and language one level below the work.

## 4. Papers (academic lane)

- **Fellegi & Sunter (1969), JASA** [peer-reviewed; not re-read]: field
  agreement and disagreement get log-likelihood weights. Later
  term-frequency adjustment makes agreement on a common value ("Nguyễn Văn
  An", "Phòng Tài chính") weak evidence.
- **Bhattacharya & Getoor (2007), TKDD** [peer-reviewed; abstract only]:
  collective resolution with relational evidence beats attribute-only
  baselines. Implication: resolve issuers first, then the things they
  scope.
- **Peeters, Steiner & Bizer, EDBT 2025** ([arXiv 2310.11244](https://arxiv.org/abs/2310.11244))
  [peer-reviewed]: strong LLMs match entities with few or no examples, but
  the best prompt varies by model and dataset, so a regression set is
  needed.
- **Wang et al., ComEM, COLING 2025** ([arXiv 2405.16884](https://arxiv.org/abs/2405.16884))
  [peer-reviewed]: choosing among all candidates at once beats judging
  pairs one at a time.
- **Fan et al., BatchER, ICDE 2024** ([arXiv 2312.03987](https://arxiv.org/abs/2312.03987))
  [peer-reviewed; snippet only]: batching cuts LLM matching cost up to
  about 7× at comparable quality.
- **DEG-RAG, arXiv 2510.14271 (Oct 2025)** [preprint]: entity resolution on
  LLM-built graphs cuts entities by about 40 % and improves QA win rates
  (57.6 % for LightRAG on Agriculture). Type blocking worked best. It does
  not measure false merges, and each corpus is one domain.
- Gaps: no paper covers cross-organization homonyms in enterprise
  documents, scoped identity in GraphRAG, or over-merge vs under-merge cost
  for QA. No controlled result shows that more attributes in the prompt
  improve precision on hard negatives.

## 5. Prototype run (synthetic corpus)

`engine-demo/profile_test.py` (session scratchpad, not in the repo) extends
the engine-brief demo with:
- a card field `issuer`, read from the letterhead with a checked quote;
- a profile `default_issuer`;
- a `scope` on Policy, Person, System and Organization units (`category` in
  department, team, committee, business_unit);
- `scope` as the first part of identity keys, and as a discriminator.

It adds D6 (Beta's policy v1) and D7 (a notice with no letterhead that
mentions "Phòng Tài chính") [observed]:

| Check | Without scope | With scope, default issuer Alpha | With scope, no default issuer |
|---|---|---|---|
| Beta's policy v1 | merged into Alpha's v1 | new entity: "Quy chế công tác phí · v1 (Công ty CP Beta)" | same |
| Beta's Phòng Tài chính | merged into Alpha's | new; the extraction's ref to Alpha's unit is rejected | same |
| Requirement version groups | one group across companies | Alpha: 2,000,000 superseded 2026-01-15 by 2,500,000; Beta: 800,000 current | same |
| D7 "Phòng Tài chính" | Alpha's | Alpha's (scope from the profile) | new entity plus `same_as` to both units |
| D4 "Finance Department" | stage 3, LLM `same` | stage 3, LLM `same`, same scope | same |
| D1–D5 mention groups | 12 | 12, identical | not compared |

Two prototype bugs were found and fixed on the way:
- An identity key containing `name` let the LLM-proposed translation
  "Phòng Tài chính" merge "Finance Department" at stage 1 without
  confirmation. Fix: name keys stay at stage 2, which ignores translated
  names.
- With the issuer unknown, D3's "phiên bản 2" mention missed Alpha's v2,
  because the scope part of the key was missing and the digit guard blocked
  stage 3. Fix: with an unknown scope, match the other key parts across
  scopes and accept only a single hit.

One latent bug in the brief's demo was found by reading it: stage 1 takes
the first hit when an identity key matches two entities. A title-only
mention ("Quy chế công tác phí") would match both v1 and v2.

## 6. Proposal (awaiting approval)

Per entity type, the pack declares three groups of attributes:
1. **`scope`**: whose thing it is. For a policy, the issuer. For a unit,
   its parent organization. For a person, the organization of the
   document. It comes from the text first, then caller metadata, the card
   issuer, the profile default, else unknown. Its source is recorded.
2. **`identity`**: strong keys, with the scope in front, such as
   `[scope, code]` and `[scope, title, version_label]`. Equal keys merge.
3. **`distinct_on`**: discriminators, such as scope, code, version label
   and issue date. When both sides know a value and the values differ, the
   two never merge at any stage, including checked refs.

Rules:
- A known, different scope blocks stages 0–3. Cross-scope fuzzy
  candidates are counted, not sent to the LLM.
- An unknown scope matches only when exactly one candidate exists;
  otherwise the mention becomes a new entity with `same_as` candidates. The
  run record counts merges made with an unknown scope.
- An identity key that hits two entities is ambiguous, as at stage 2.
- Fact version keys include the scope, such as Requirement `[scope,
  metric, applies_to, condition]`.
- LLM confirmation is listwise. It shows each mention with all its
  candidates and their profiles, following Graphiti's negative-example
  prompt, and keeps them apart when unsure.
- Labels and retrieval output show the profile, such as "Phòng Tài chính
  (Công ty CP Beta)".

Rejected or deferred:
- A separate index per company: cross-company questions become
  impossible.
- LLM-written entity summaries as identity evidence: costly, and they
  drift.
- A Work-level node above versions (FRBR): `SUPERSEDES` and version
  groups cover v1. Revisit if version-less questions fail.
