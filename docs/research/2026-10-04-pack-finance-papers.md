# Finance information extraction, knowledge graphs and QA: papers for the finance pack

> **Snapshot, 2026-10-04 — not maintained.** Academic lane; many PDFs did not parse, so most facts are abstract- or HTML-level. The maintained,
> re-verified summary is in [domain-schemas.md](../reference/domain-schemas.md); where they differ, the maintained doc
> wins. Local paths were removed before publishing.
>
> **Errata and later resolutions:**
> - FinReflectKG venue confirmed from the paper HTML: ICAIF '25.
> - The CC BY-NC-SA 4.0 shown for REFinD and FinDKG is the arXiv **paper** license;
>   their data licenses were not found.
> - FinRED: CC BY 4.0 comes from the paper; the repository README states no license.
> - FinanceBench: 10,231 is the paper's full set; the public repository holds a
>   150-example sample, the README states no license, and Hugging Face lists cc-by-nc-4.0.

## Finance papers for the TenetRAG `finance` pack (2026-10-04)

Labels: [primary] = read on arXiv abs/HTML page this session (several PDFs would not parse, so many "primary" facts are abstract-level or HTML-level only); [secondary] = search snippet; [inferred] = my reasoning or prior knowledge, NOT verified.

### 1. Summary
- Schemas in finance IE are small. REFinD has 22 relations over 8 entity-pair types, FinRED has 29 relations, FinDKG has 15 relations and 12 entity types, FinReflectKG has 10 entity types and 10 relations. [primary]
- The real recurring core is: Organization (including subsidiaries and acquirers), Person with title or role, geopolitical location, Product, and money, date and percent as values (never entities).
- Recurring relations (3+ sources): subsidiary_of / Control, acquired_by / Acquisition, headquartered_in / located, has_title / employee_of / member_of (people and roles), product_produced, and invests_in / Has_Stake_In. [primary, see table]
- Numeric facts are the most structured part of the field. FiNER-139 tags 139 XBRL types (metric-like), and KPI-EDGAR links a KPI to a numeric value and a year. Both treat metric, value and period as a unit, which supports `ReportedFigure` as a claim with attributes, not as entities. [primary/secondary]
- Event extraction is document-level and concentrated on a few types: equity pledge, share repurchase, shareholding increase or decrease, equity freeze (ChFinAnn); DuEE-Fin adds acquisition, financing, bankruptcy, listing, losses, executive change, winning bid, interviewed. [secondary]
- No paper found gives a controlled schema-vs-schema-free comparison on finance. FinReflectKG says explicitly it has only schema-guided results. [primary]. Evidence that schema helps is general-domain and weak (small N). [secondary]
- Company control and ownership (Bank of Italy / Vadalog) is computed by rules over a share-ownership graph (integrated ownership, control, ultimate controller, close links). It is derived, not extracted. [secondary]
- Recommended: keep `OWNS_STAKE` as an interval relation, add `CONTROLS` as derived (not LLM-extracted), fold `Acquisition` / `RatingAction` / `CorporateAction` into enum-valued events, and add scale, currency, period type and a restated flag to `ReportedFigure`. [inferred, grounded in sources below]

### 2. Sources table
| Source | Entity types | Relation types | Event types | Size | Venue / review | License |
|---|---|---|---|---|---|---|
| FinRED (Sharma et al. 2022) [arXiv](https://arxiv.org/abs/2306.03736) | not typed (person, org, location examples) | 29 finance relations from Wikidata (e.g. CEO, product produced, HQ location) | none | ~7.8k sentences (5,699 train / 1,068 test) from 47,851 news articles + 4,713 earnings call transcripts | FinWeb @ WWW'22 workshop | CC BY 4.0 |
| REFinD (Kaur et al. 2023) [arXiv](https://arxiv.org/abs/2305.18322) | 8 pairs: Person-Title, Person-Org, Person-University, Person-GovAgency, Org-GPE, Org-Date, Org-Org, Org-Money | 22, incl. has_title, formed_in, founded_by, has_revenue_of, acquired_by, employee_of, member_of, subsidiary_of, shares_of, agreement_with, headquartered_in, operations_in, loss_of, profit_of, cost_of (listing partial) | none | 28,676 instances from SEC 10-X, 2016-17 | SIGIR '23 (peer-reviewed) | CC BY-NC-SA 4.0 |
| FinDKG (Li, Sanna Passino 2024) [arXiv](https://arxiv.org/abs/2407.10909), [HTML](https://arxiv.org/html/2407.10909) | 12: ORG, ORG/GOV, ORG/REG, GPE, PERSON, COMP, PRODUCT, EVENT, SECTOR, ECON IND, FIN INST, CONCEPT | 15: Has, Announce, Operate In, Introduce, Produce, Control, Participates In, Impact, Positive/Negative Impact On, Relate To, Is Member Of, Invests In, Raise, Decrease | EVENT is an entity type | 144k quadruples, 13,645 entities, 1999-2023, ~400k WSJ articles | ICAIF '24 (peer-reviewed) | CC BY-NC-SA 4.0 |
| FinReflectKG (Arun et al. 2025) [arXiv](https://arxiv.org/abs/2508.17906), [HTML](https://arxiv.org/html/2508.17906) | 10: ORG, PERSON, COMP, PRODUCT, SEGMENT, FIN_METRIC, RISK_FACTOR, EVENT, REGULATORY_REQUIREMENT, ESG_TOPIC | 10: Has_Stake_In, Operates_In, Produces, Impacts, Involved_In, Impacted_By, Discloses, Complies_With, Supplies, Partners_With | EVENT entity | S&P 100 10-Ks, FY2024; triple counts not found | arXiv v2; ICAIF 2025 per PDF metadata (single read, unverified) | not found |
| FiNER-139 (Loukas et al. 2022) [arXiv](https://arxiv.org/abs/2203.06482) | 139 XBRL tags, mostly numeric tokens | none | none | 1.1M sentences | ACL 2022 | CC BY 4.0 |
| KPI-EDGAR (Jacob et al. 2022) [arXiv](https://arxiv.org/abs/2210.09163) | KPI + numeric value / year / other attributes (joint NER+RE) | KPI-to-value, KPI-to-year style links | none | not found | ICMLA 2022 | not found |
| ChFinAnn / Doc2EDAG (Zheng et al. 2019) [arXiv](https://arxiv.org/abs/1904.07535) | 24 entity types [secondary](https://www.wizwand.com/dataset/chfinann) | role arguments | 5: equity freeze, share repurchase, shareholding decrease, increase, pledge [secondary] | 32,040 docs, 2008-18 [secondary] | EMNLP 2019 | repo data; license not verified |
| DuEE-Fin [secondary](https://arxiv.org/pdf/2302.08205) | 92 roles | roles | 13: listing, shareholder reduction/increase, acquisition, financing, repurchase, pledge, bankruptcy, losses, interviewed, winning bid, executive change (+ regulatory talk per another snippet) | 11,700 docs | Baidu release; no paper read | not found |
| HybridRAG (Sarmah et al. 2024) [arXiv](https://arxiv.org/abs/2408.04948) | n/a | n/a | n/a | earnings-call transcripts | preprint (workshop status not verified) | n/a |
| FinanceBench (Islam et al. 2023) [arXiv](https://arxiv.org/abs/2311.11944) | n/a | n/a | n/a | abstract says 10,231 questions; 150-case open sample (inferred from my memory: the open set is 150) | preprint | CC BY-NC-ND 4.0 |
| FinQA [arXiv](https://arxiv.org/abs/2109.00122) | n/a | n/a | n/a | size not on page (inferred ~8k) | EMNLP 2021 | not verified |
| TAT-QA [arXiv](https://arxiv.org/abs/2105.07624) | n/a | n/a | n/a | size not on page | ACL 2021 | CC BY 4.0 |
| ConvFinQA [arXiv](https://arxiv.org/abs/2210.03849) | n/a | n/a | n/a | not on page | EMNLP 2022 | not verified |
| DocFinQA [arXiv](https://arxiv.org/abs/2401.06915) | n/a | n/a | n/a | 7,437 questions, 123k-word avg context | preprint | not verified |
| FinDER [arXiv](https://arxiv.org/abs/2504.15800) | n/a | n/a | n/a | 5,703 query-evidence-answer triplets | ICLR 2025 workshop | CC BY 4.0 (paper) |
| SEC-QA [arXiv](https://arxiv.org/abs/2406.14394) | n/a | n/a | n/a | generator, not fixed set | preprint | not verified |
| Bank of Italy / Vadalog [secondary](https://virtusinterpress.org/OWNERSHIP-AND-CONTROL-OF-ITALIAN.html), [Temporal Vadalog](https://arxiv.org/html/2412.13019v1) | Company, Person (shareholders) | shareholding with share fraction; derived: integrated ownership, control, ultimate controller, close links | none | Italian companies KG (size not found) | Vadalog PVLDB '18 (cited in snippet) | n/a |

### 3. Findings per question

**Q1.** See table. REFinD, FinRED and FinDKG are sentence- or article-level and use flat, small label sets. Only FinDKG makes time first-class (timestamp = article date, quadruples). [primary]

**Q2. Core (3+ sources).** [primary, from the table; the counting is my own]
- Organization/company: all of REFinD, FinRED, FinDKG, FinReflectKG, plus Vadalog.
- Person with role/title: REFinD, FinRED (CEO), FinDKG, FinReflectKG, DuEE-Fin (executive change).
- Location/GPE: REFinD, FinRED, FinDKG.
- Product: FinDKG, FinReflectKG, FinRED.
- Subsidiary/control/stake: REFinD (subsidiary_of, shares_of), FinDKG (Control, Invests In), FinReflectKG (Has_Stake_In), Vadalog (control), ChFinAnn (shareholding events).
- Acquisition: REFinD (acquired_by), DuEE-Fin (acquisition), FinDKG (indirectly).
- Equity-holder events (pledge, repurchase, increase/decrease): ChFinAnn, DuEE-Fin, and likely Chinese datasets only [secondary].
**Niche:** SEGMENT, RISK_FACTOR, ESG_TOPIC, REGULATORY_REQUIREMENT (FinReflectKG); SECTOR, ECON IND (FinDKG); University (REFinD); winning bid, interviewed (DuEE-Fin). Impact-style relations (Impacts, Positive Impact On) are vague and not a good fit for evidence-backed fact graphs. [inferred]

**Q3. Question types and graph structure.** Benchmark pages read give only abstract-level descriptors: FinQA = multi-step numeric reasoning with gold programs; TAT-QA = span, multi-span, count, arithmetic over table+text; ConvFinQA = conversational chains; DocFinQA = long-context (123k words); FinDER = terse expert queries with abbreviations; SEC-QA = multi-document, RAG fails; FinanceBench = RAG with GPT-4-Turbo wrong or refused 81% [all primary, abstract-level]. The mapping below is [inferred]:
- Numeric lookup with period: `ReportedFigure(subject, metric, period, value)` claim, time = fiscal period.
- Ratio / growth: two or more ReportedFigures for same subject; computation done outside the graph (program-of-thought, as SEC-QA does).
- Cross-period comparison: figures linked by (subject, metric); needs normalized metric names and period keys.
- Multi-company comparison (SEC-QA): the same metric across many Organizations; needs entity resolution on name/ticker.
- Ownership or control chain: `OWNS_STAKE` interval edges plus multi-hop traversal; control derived by rules (Vadalog).
- Events (M&A, ratings, dividends): n-ary event with dated roles.
- People and roles: `HOLDS_POSITION` from core, with interval time.

**Q4. Numeric facts and time.**
- FiNER-139: numerals replaced by pseudo-tokens preserving shape and magnitude; tag depends on context, not token. [primary] Implication: keep value verbatim; classify the metric from context.
- KPI-EDGAR: link KPI to value and year; "correct numeric value/year pair" is a named challenge. [secondary/primary abstract] The value and period must stay attached.
- FinDKG: time = article date. [primary]. FinReflectKG: no explicit statement of how numbers/fiscal years are stored was found in the HTML read. [primary, absence only]
- Scale (thousands/millions), currency, restatements and segment/geography breakdowns: **not found in any paper I could read**. [gap] XBRL (the source of FiNER-139 tags) has contexts for period, scale and dimensions [inferred from prior knowledge, not verified this session].

**Q5. Schema vs schema-free.** No finance-specific controlled comparison found. FinReflectKG reports only schema-guided results (64.8% CheckRules compliance for the reflection mode) and lists schema-free as future work. [primary] General-domain: a small comparison (20 questions) found ontology-guided KGs with chunk information 18/20 (90%), while text-derived and RDB ontology KGs alone scored 15% and 20% [secondary](https://arxiv.org/pdf/2511.05991), preprint, N=20, not finance, not read in full. OMD-GraphRAG claims +9.21% retrieval accuracy [secondary](https://arxiv.org/pdf/2603.25152), preprint. FinanceBench-based graph work: 6% hallucination reduction, 80% fewer tokens, but GraphRAG on Gemini 2.5 Pro +2.1pp accuracy with +6.1pp hallucination [secondary](https://aclanthology.org/2025.genaik-1.6) (workshop, abstract-level). Label: `single-paper`, weak.

**Q6. Event types.** Recurring: equity pledge, share repurchase, shareholding increase/decrease, equity freeze (ChFinAnn); plus acquisition, financing, bankruptcy, listing, losses, executive change, winning bid (DuEE-Fin). [secondary] ChFinAnn and DuEE-Fin are explicitly document-level: arguments scatter across sentences and multiple events co-occur in one document. [primary: Doc2EDAG abstract]. Rating change and default are not among the dataset types I could verify. [gap]

### 4. Proposed `finance` changes
1. **Keep `Acquisition`, but make `seller` optional and add `status` enum (announced, completed, terminated).** Reason: acquisition recurs (REFinD, DuEE-Fin) and document-level extraction scatters arguments. [inferred from sources]
2. **Add `ShareholdingChange` event or fold into `OWNS_STAKE` with `change_kind` enum (increase, decrease, pledge, freeze).** Reason: the five ChFinAnn events are all stake events. Prefer enum, not new types. Source: Doc2EDAG, DuEE-Fin. [secondary]
3. **Merge `CorporateAction` repurchase into the same enum family**: `CorporateAction.kind` add `repurchase` (already `buyback`), `financing`, `listing`, `delisting`, `bankruptcy`. Source: DuEE-Fin. [secondary]
4. **Keep `RatingAction`.** I found no dataset in my reads that uses it, so it is a user-need decision, not a literature one. [inferred]
5. **`ReportedFigure`: add `scale` (units/thousands/millions/billions), `currency`, `period_kind` (fiscal_year, quarter, ytd, instant), `fiscal_year_end`, `is_restated` plus `supersedes` link, and optional `segment` / `geography` attributes.** Reason: KPI-EDGAR and FiNER-139 couple value with period; scale and restatement are not covered by the papers read, so this is design inference. [inferred]
6. **`CONTROLS` as a derived relation computed from `OWNS_STAKE` (threshold rule), not LLM-extracted; record `basis` enum (majority, voting, board, contract).** Source: Bank of Italy control/integrated ownership/close links. [secondary]
7. **`SUBSIDIARY_OF`: keep, mark as asserted-by-document; allow `OWNS_STAKE` percentage to evidence it.** Sources: REFinD, FinDKG Control. [primary]
8. **`Instrument`: keep, but `isin` identity should tolerate absence.** [inferred]
9. **Do not add** SEGMENT, RISK_FACTOR, ESG_TOPIC, SECTOR as types. Make segment a `ReportedFigure` attribute, sector an `Organization.sector` enum or `Concept`, risk factor a `Statement` with `topic`. Source: niche (single-source) in FinReflectKG, FinDKG. [primary]
10. **Executive change**: use core `HOLDS_POSITION` (interval) instead of a new event; extraction prompt should map DuEE-Fin-style "executive change" onto it. [inferred]
11. **Avoid vague impact relations** (Impacts, Relate To). [inferred]

### 5. Competency questions
1. What was X's revenue for fiscal year 2023, verbatim, with unit and scale?
2. How did X's net interest margin change from Q1 to Q2 of this year?
3. Which companies in the corpus reported a higher operating margin than Y in FY2024?
4. Who owns more than 25% of X, directly or through subsidiaries, and since when?
5. Who ultimately controls X (apply control rule across ownership chain)?
6. Which subsidiaries of X are in the corpus, and in which jurisdictions?
7. What acquisitions did X announce between two dates, and at what price and stake?
8. Which shareholders pledged, sold or increased holdings in X in the last year?
9. Did X announce a dividend, buyback or split, and what are the dates and amounts?
10. Who is X's CEO/CFO, and who held the role before?
11. Was the FY2022 figure for metric M later restated, and what is the current value?
12. What rating did agency A assign to X, and when did it change?

### 6. Licenses
- CC BY 4.0: FinRED, FiNER-139, TAT-QA, FinDER paper [primary abstract pages].
- CC BY-NC-SA 4.0 (non-commercial, share-alike): REFinD, FinDKG [primary]. Cannot be redistributed in a permissive repo.
- CC BY-NC-ND 4.0: FinanceBench paper page; dataset on Hugging Face (dataset licence not verified). [primary]
- Unknown / not verified: FinQA, ConvFinQA, DocFinQA, KPI-EDGAR, ChFinAnn, DuEE-Fin, FinReflectKG, SEC-QA, HybridRAG. Underlying SEC filings are public (my inference). Check each repo before using as fixtures.

### 7. Gaps
- Several PDFs would not parse; counts, relation lists and results for FinRED relation labels, REFinD (partial list), FinReflectKG triple counts, KPI-EDGAR size, HybridRAG numbers, FinQA/ConvFinQA sizes, and FinanceBench question categories were not read.
- Bellomarini's core papers (company control, close links) were not opened; only search snippets and the Temporal Vadalog paper abstract were read.
- No evidence on scale, currency, restatement, segment handling in papers; no controlled finance schema-vs-schema-free result.
- Rating change and default event datasets not located; 2025-2026 finance GraphRAG coverage limited to one workshop paper snippet.
- Not covered: EDT ("Trade the event"), restatement literature, XBRL taxonomy documentation.
