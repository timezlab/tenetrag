# Should banking be a separate pack? Corpora, questions and domain splits

> **Snapshot, 2026-10-04 — not maintained.** Web lane; public evidence on bank corpora is thin, so many findings are secondary or inferred. The maintained,
> re-verified summary is in [domain-schemas.md](../reference/domain-schemas.md); where they differ, the maintained doc
> wins. Local paths were removed before publishing.
>
> **Errata and later resolutions:**
> - A national example of a changed minimum capital ratio was removed before publishing.
> - This lane recommends folding banking into the other packs with an example user pack
>   over `[enterprise-docs, finance]`. The maintained decision in
>   [v1-packs.md](../product/v1-packs.md#industry-packs-such-as-banking): banking is a user
>   pack, kept by the adopter, that extends `enterprise-docs` and adds `finance` when the corpus
>   has filings, ratings or securities. Campaigns, segments and product terms moved there too.

## Banking pack split: research report (2026-10-04)

Labels: [primary] = read on the owning source this session. [secondary] = search snippet or third-party summary. [inferred] = my reasoning.
Evidence is thin in places. Most public bank RAG material says "policies and procedures" and rarely lists question taxonomies or committee-minute corpora. Where I could not verify, I say so.

### 1. Summary
- Verified public use is dominated by **employee policy and procedure lookup** and wealth-advisor knowledge bases. Credit-committee, ALCO and campaign-brief corpora are not documented in any case I could find. [secondary]
- Graph work at banks that I could verify is mostly **structured data** (KYC, transactions, data lineage, RDF regulatory/data governance), not LLM-extracted document graphs. That supports keeping Customer, Account and Transaction out of the pack. [primary/secondary]
- Nobody in the models I checked ships a document-graph "banking" schema distinct from "finance". Industry models split by **function** (FIBO: FBC, LOAN, DER, CAE, IND, BE) or are one integrated model across banking and insurance (Teradata). Microsoft has a banking-core submodel, but it is an operational data model. [secondary]
- KPI definitions do vary by name, denominator, jurisdiction and over time. Examples: "NIM" vs the IMF's "interest margin to gross income"; Basel I/II/III capital aggregation; LCR national discretion. This supports versioned `Definition` claims. [primary/secondary]
- Most bank-specific needs reduce to **one or two new claim types plus enums**, not a pack. Candidates: `ProductTerm`, `Definition`, `Limit/Threshold`. Several are not bank-specific. [inferred]
- Recommendation: **(b)**, folded into `finance` and `enterprise-docs`, with no `banking` pack in v1. Ship banking as a worked **example user pack** that extends `[enterprise-docs, finance]`. Confidence: medium (about 65%).

### 2. Case-study table

| Organization | Documents indexed | Questions | Source |
|---|---|---|---|
| Central Bank of Bosnia and Herzegovina (journal paper, 2026) | Internal Word/PDF repositories; HR policies and procedures | Semantic document search; HR policy chatbot (offline, on-prem RAG) | [reference-global](https://reference-global.com/article/10.2478/jcbtp-2026-0014) [secondary: snippet only; fetch failed] |
| Reserve Bank of Australia | Internal corporate knowledge; "interrogating large text sets" | Staff knowledge management; summarising public submissions | [RBA AI Transparency Statement](https://www.rba.gov.au/about-rba/our-policies/ai-transparency-statement.html) [secondary: snippet]. The "Policies + AI" name and policy-RAG detail came only from a search summary; I did not verify them. |
| Chiba Bank (Japan) | Internal policy knowledge base | Natural-language policy queries (Gemini Pro) | [bestpractice.ai summary of a Google Cloud case](https://bestpractice.ai/ai-use-cases/financial-services/human-resources/deploy-ai-for-japanese-regional-bank-employee-productivity-and-policy-access) [secondary: aggregator, undated] |
| Morgan Stanley (wealth/investment bank) | Over 100,000 internal documents (research, strategies, analyst content) | Advisor Q&A on strategies, research and processes | [OpenAI story via search snippets](https://openai.com/index/morgan-stanley/) (403 on fetch) [secondary]; the "98% of advisor teams" figure is self-reported [secondary] |
| HSBC (Connected Data London 2024 talk) | Enterprise data and regulatory requirements (GDPR, OCC, BCBS 239, PRA) in an RDF graph | How graphs improve regulatory reporting and data governance | [talk page](https://connected-data-london-2024.heysummit.com/talks/leveraging-knowledge-graphs-for-enhanced-regulatory-compliance-in-finance-by-hsbc) [primary: abstract only, not a document-QA case] |
| Neo4j KYC GraphRAG demo (2025-08) | **Synthetic** graph of 8,000 customers, accounts, devices, IPs, transactions | "Show 5 watch-listed customers in suspicious rings"; shared addresses; write a summary | [Neo4j blog](https://neo4j.com/blog/developer/graphrag-in-action-know-your-customer/) [primary]. It is structured data, not documents. |
| Neo4j transaction/account data model | Structured: Customer, Account, Transaction, Passport, Face, Email and others | Fraud/AML | [Neo4j data model](https://neo4j.com/developer/industry-use-cases/data-models/transactions/transactions-base-model/) [primary] |
| Vendor templates (credit policy and exception memo agent; credit memo automation) | Underwriting documents checked against credit policy criteria (LTV, DSCR, loan size) | Credit-policy exception checks, memo drafting | [Stack AI](https://www.stack-ai.com/templates/how-to-build-a-credit-policy-and-exception-memo-agent) [secondary: vendor marketing, not a bank case] |

Not found: public Stardog, Ontotext, Glean, Databricks or AWS bank case studies with a document and question inventory. Searches surfaced only generic Ontotext/Neo4j claims (BCBS 239, GDPR, AML). [secondary]

### 3. Findings per question

**Q1. Corpora and questions.**
- The verified pattern is employee-facing policy and procedure RAG, and advisor knowledge bases (table). [secondary]
- Document types in your list that I could **not** confirm in any public case: product T&Cs, ALCO and credit-committee minutes, campaign briefs, complaints, KPI glossaries. These may exist inside banks, but I have no citation. [inferred]
- Regulatory-change and regulation-to-control mapping appear in the HSBC talk (BCBS 239, GDPR, PRA) and in Ontotext/Neo4j positioning. [primary/secondary]
- KYC and adverse-media work is done on **structured** graphs. The Neo4j demo uses a synthetic customer graph, not documents. [primary]

**Q2. Types beyond current packs.** See the verdict table in section 4. The reasoning is [inferred] from the question types you listed, not from a verified bank corpus.
- Product features, KPIs with formulas, risk appetite thresholds and covenants all share one shape: *subject, measure or feature, comparator, value, unit, scope (segment, channel, currency), effective period, source*. That is a small number of claim types, not a banking taxonomy.
- Regulations and circulars are `Work` or `Policy` with a `kind` enum, plus existing `SUPERSEDES` and `APPLIES_TO`.
- Committees are `Organization` (category: committee) plus existing `Meeting` and `Decision` events.

**Q3. How others split the domain.**
- Teradata FS-LDM covers retail and commercial banking, brokerage, cards and insurance in a **single integrated model**. [secondary: vendor page snippets](https://www.teradata.com/Industries/Financial-Services/logical-data-model)
- Microsoft Cloud for Financial Services data model has submodels: Banking core, Retail banking core, Loan onboarding, Property and casualty, SMB, Common, Document. So banking is a submodel, but this is an operational (transactional) data model. [secondary: search snippet; the Learn page I fetched was only the overview](https://learn.microsoft.com/en-us/dynamics365/industry/financial-services/overview-data-model)
- FIBO is organised by function, not sector. Modules are BE, BP, CAE, DER, FBC, FND, IND, LOAN and MD. Loans and mortgages are a domain, "banking" is not. [secondary: search snippet](https://spec.edmcouncil.org/fibo/working-group.html)
- Finance NER sets (FiNER-139) are XBRL-filing oriented, with numeric tags. They have no banking-only split. [secondary](https://arxiv.org/abs/2203.06482)
- Neo4j publishes data models by use case (transactions, data lineage), not by sector. [primary](https://neo4j.com/developer/industry-use-cases/data-models/)
- IBM BFMDW: no source found (gap).
- Answer: I found nobody shipping a "banking" schema separate from "finance" for document knowledge. The absence of evidence is not proof of absence. [inferred]

**Q4. Customer and transaction data.**
- Neo4j's own transaction model carries names, DOB, passport and licence numbers, face embeddings, device and IP data. That is the structured KYC and fraud use case. [primary]
- EDPB Opinion 28/2024 (2024-12-17): an AI model is anonymous only if extraction of personal data is negligible, case by case. Legitimate interest can be a legal basis, subject to a three-step assessment. [secondary: law-firm summaries](https://cms.law/en/lux/legal-updates/edpb-opinion-28-2024-key-takeaways-on-processing-personal-data-in-the-context-of-ai-models)
- I found no banking-specific regulator text on PII in LLM-built knowledge graphs (gap).
- Recommendation: **no** Account, Customer or Transaction types. Natural persons that appear in documents (signatories, officers, named counterparties) are covered by `Person`. Customer records and transactions stay in SQL, and the graph can hold an opaque external key at most. [inferred]
- This is consistent with the project rule that structured data stays in SQL.

**Q5. KPI definitions and variation.**
- **NPL.** IMF 2019 FSI Guide: past due 90+ days, or unlikely to be repaid without realising collateral, as a share of gross loans. [secondary: search summary of the Guide](https://imf.org/-/media/Files/Data/2019/2019-fsi-guide.ashx). The BCBS 2017 guidelines harmonised "non-performing exposure" and forbearance, which implies national definitions differed before. [secondary](https://www.bis.org/publications/201704-guidelines-prudential-treatment-problem-assets-definitions-non-performing-exposures-and-forbearance)
- **CAR.** The 2019 IMF Guide is a revision of the 2006 Guide. Its table of contents lists Table 1.2 "Mapping from the 2006 Guide" and a chapter on "Aggregation of Capital Components under Different Basel Accords". [primary: I read the contents pages of the PDF](https://imf.org/-/media/Files/Data/2019/2019-fsi-guide.ashx) Search summaries say capital follows Basel I, II or III by country. [secondary] (A national example of a changed minimum ratio was removed before publishing.)
- **LCR.** HQLA divided by total net cash outflows over 30 days, minimum 100%. National discretion exists (for example LCR31, for jurisdictions with insufficient Level 1 assets). [primary](https://www.bis.org/basel_framework/chapter/LCR/30.htm)
- **NIM.** Commonly net interest income over average earning assets. The IMF FSI instead uses "interest margin to gross income", a different ratio. [secondary](https://en.wikipedia.org/wiki/Net_interest_margin) [secondary: IMF via search summary]
- **Cost-to-income.** Commonly operating expenses over operating income. The IMF FSI uses "noninterest expenses to gross income", and business model changes typical levels. [secondary](https://nairametrics.com/what-is-cost-to-income-ratio)
- **CASA.** Current plus savings deposits over total deposits. I found only explainers (mostly Indian), no standard-setter definition. [secondary](https://www.oliveboard.in/blog/casa-ratio/)
- Verdict: the same KPI name can mean different formulas by institution, standard and edition. That is the case for `Definition` claims carrying `formula`, `denominator basis`, `source` and `valid_from`/`valid_to`. [inferred]
- I did not read the text of IMF chapter 7 (the core FSIs). The 2003, 2006 and 2019 editions' wording is therefore not compared line by line.

### 4. Type-by-type verdict

| Item | Verdict | Notes |
|---|---|---|
| Interest rate, fee, tenor, eligibility, limits on a product | **New claim: `ProductTerm`** (product, feature enum, value, unit, qualifier, period) | Not bank-only: any product with terms. Avoid one type per feature. [inferred] |
| Product itself | Existing `Product` with `category` enum (deposit, loan, card, ...) | |
| Customer segment, channel | **Enum values** on the `ProductTerm`/`APPLIES_TO` qualifier; `Concept` (kind: segment) if it needs its own identity | |
| Campaign / promotion | **`Event` or `Project` with `kind: campaign`**, plus a `ProductTerm` for the offer | Weakest evidence; no case found. [inferred] |
| Branch | `Place` or `Organization` with `category: branch` | |
| KPI (NIM, CASA, CIR, NPL, LDR, CAR, LCR) | `Concept` (kind: metric) + **new `Definition` claim** (formula, basis, valid period) | Values are `ReportedFigure`. Computed values stay in SQL. |
| Credit facility, collateral, covenants, limits | **Covenant** = `Requirement` claim; **limit** = attribute or threshold claim; **facility** = *maybe one new entity*, only if contract documents are in scope; collateral = `Concept`/attribute | Facility balances and drawn amounts are SQL. [inferred] |
| Risk appetite statement | **`Threshold` claim** (metric, comparator, value, scope, period) or `Requirement` with a numeric field | Same shape as covenant. Can share one type. [inferred] |
| Regulation / circular | `Work` with `kind: regulation` or `circular`; use existing `SUPERSEDES`, `APPLIES_TO`, `REGULATED_BY` | |
| Committee | `Organization` with `category: committee`; existing `Meeting` and `Decision` | |
| Customer, Account, Transaction | **Out of scope (SQL)** | PII; see Q4 |
| KYC / adverse media subjects | `Person`/`Organization` plus an evidence-backed `Statement`; screening lists stay outside | Only if documents are the source. |

Net new: roughly 2 to 4 types (`ProductTerm`, `Definition`, `Threshold`, maybe `Facility`). The rest are enums.

### 5. Recommendation (confidence: medium, about 65%)

| Criterion | (a) separate `banking` | (b) fold into `finance`/`enterprise-docs` | (c) split `markets` + `banking` |
|---|---|---|---|
| Distinct types | 2 to 4, mostly generic | Same, no extra pack | Same, plus a rename |
| Distinct questions | Policy and product lookups overlap `enterprise-docs` | Fits | Fits |
| Overlap with `finance` filings | Large: bank filings use `ReportedFigure`, `REGULATED_BY`, `RatingAction`, CAR/NPL | Natural | Splits that overlap in two |
| Maintenance | Third pack and a tested `extends` diamond | Lowest | Highest: rename plus migration |
| Untested-pack risk | High: no verified corpus | Low | High |

- **Choose (b).** Evidence for a distinct banking corpus is weak (Q1), type count is small (Q2), nobody else ships the split (Q3), and the largest bank-specific pieces (customers, accounts, transactions) are out of scope (Q4).
- Where to put the pieces: generic ones (`Definition`, `Threshold`, `ProductTerm`) go in `enterprise-docs` or `core`, not `finance`, since insurers, telcos and any other product-selling organization need them. Only bank-flavoured **enums** (product categories, KPI kinds, committee categories) go in `finance`. [inferred]
- Ship a `banking` example pack under `examples/` that extends `[enterprise-docs, finance]`. It exercises multi-pack `extends` without a v1 support promise.
- Revisit (a) when a real corpus shows more than about 8 banking-only types, or when questions need competency sets that `finance` filings do not cover.
- Biggest risk to this call: bank-internal corpora (credit committee, ALCO, campaigns) may need more structure than I could verify. Test with synthetic documents before deciding.

### 6. Gaps
- No public case study confirms ALCO or credit-committee minutes, campaign briefs, complaints or KPI-definition documents as RAG corpora. Questions are [inferred] from the brief.
- No Stardog, Ontotext, Glean, Databricks or AWS bank case studies with document and question detail. Microsoft and Neo4j sources are data models and demos, not document corpora.
- IBM BFMDW not found. Teradata and Microsoft detail is from snippets.
- IMF Guide: I read only the contents pages; the definitions come from search summaries. The 2006-to-2019 changes are not itemised.
- The Bosnia and Herzegovina central bank paper and the RBA "Policies + AI" detail are snippet-level.
- No banking-regulator source on PII in LLM-built graphs; only the EDPB opinion via law-firm summaries.
- CASA has no standard-setter definition.
- Two fetches failed (the IMF 2003 PDF text and OpenAI's Morgan Stanley page).
