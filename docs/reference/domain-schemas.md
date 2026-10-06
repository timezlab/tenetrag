# Domain schemas — what finance, banking, enterprise and cross-domain sources show

Verified 2026-10-04. This page holds the evidence behind
[v1-packs.md](../product/v1-packs.md). Licenses are in
[graph-schema-design.md](graph-schema-design.md#standards-and-licenses),
and the raw lane reports are the 2026-10-04 snapshots listed in
[docs/index.md](../index.md#research-snapshots).

Labels: **[primary]** means read on the owning source (the paper page, the
repository or the official site). **[secondary]** means a search snippet or
a third-party summary. **[inferred]** means our reasoning. Many papers were
read at abstract or HTML level only, because their PDFs would not parse.

## Finance

### Finance type inventories

| Source | Entity types | Relations or events | Venue |
|---|---|---|---|
| [REFinD](https://arxiv.org/abs/2305.18322) | 8 entity-pair types (Person–Title, Person–Org, Org–GPE, Org–Money, …) | 22 relations over ~29K instances from SEC filings, incl. subsidiary_of, acquired_by, shares_of, has_title | SIGIR 2023 [primary] |
| [FinRED](https://arxiv.org/abs/2306.03736) | untyped | 29 relations derived from Wikidata (CEO, product produced, HQ location, …) | FinWeb @ WWW 2022 [primary] |
| [FinDKG](https://arxiv.org/html/2407.10909) | 12: ORG, ORG/GOV, ORG/REG, GPE, PERSON, COMP, PRODUCT, EVENT, SECTOR, ECON IND, FIN INST, CONCEPT | 15: Has, Announce, Operate In, Introduce, Produce, Control, Participates In, Impact, Positive Impact On, Negative Impact On, Relate To, Is Member Of, Invests In, Raise, Decrease | ICAIF 2024 [primary] |
| [FinReflectKG](https://arxiv.org/html/2508.17906) | 10: ORG, PERSON, COMP, PRODUCT, SEGMENT, FIN_METRIC, RISK_FACTOR, EVENT, REGULATORY_REQUIREMENT, ESG_TOPIC | 10: Has_Stake_In, Operates_In, Produces, Impacts, Involved_In, Impacted_By, Discloses, Complies_With, Supplies, Partners_With; S&P 100 10-Ks for 2024 | ICAIF 2025 [primary] |
| [KPI-EDGAR](https://arxiv.org/abs/2210.09163) | KPI with value and year | KPI-to-value and KPI-to-year links | ICMLA 2022 [primary, abstract] |
| [Doc2EDAG / ChFinAnn](https://arxiv.org/abs/1904.07535) | — | 5 document-level events: equity freeze, repurchase, shareholding increase, decrease, pledge | EMNLP 2019 [primary abstract; event list secondary] |
| DuEE-Fin | — | 13 events, incl. acquisition, financing, bankruptcy, listing, executive change | Baidu release [secondary] |

- **Recurring types** (three or more sources): organizations, people with a
  title or role, places, products, subsidiary/control/stake relations and
  acquisitions. Money, dates and percentages appear only as values. [primary,
  our count]
- **Single-source types:** segment, risk factor, ESG topic and regulatory
  requirement (FinReflectKG); sector and economic indicator (FinDKG). Vague
  relations such as "Impact" and "Relate To" do not fit evidence-backed
  facts. [inferred]
- **Numbers.** FiNER-139 tags numbers by context, not by token. KPI-EDGAR
  treats "the correct value–year pair" as the hard part. Both keep metric,
  value and period together. No paper read covers scale, currency,
  restatement or segment handling. [primary; gap]
- **Questions.**
  - [FinanceBench](https://arxiv.org/abs/2311.11944) has 10,231 questions.
    GPT-4-Turbo with a retrieval system answered 81 % of them wrongly or
    refused. [primary]
  - FinQA asks for multi-step arithmetic, TAT-QA mixes tables and text,
    DocFinQA has a 123k-word average context, and SEC-QA spans several
    documents. [primary, abstracts]
  - Arithmetic belongs outside the graph. The graph supplies the figures
    with their period and source. [inferred]
- **Schema versus no schema.** No controlled finance comparison was found.
  FinReflectKG reports schema-guided results only. [primary]
- **Control.** In the Bank of Italy work, company control and ultimate
  controllers are derived by rules over a share-ownership graph, not
  extracted. [secondary]

### Finance and banking standards

- **FIBO** ([repo](https://github.com/edmcouncil/fibo), MIT) [primary]:
  - Domains: BE, BP, CAE, DER, FBC, FND, IND, LOAN, MD and SEC. There is no
    banking module.
  - FBC holds the shared business concepts, in DebtAndEquities,
    FinancialInstruments, FunctionalEntities and ProductsAndServices.
  - FunctionalEntities defines institution kinds such as `Bank`,
    `CommercialBank`, `CentralBank`, `CreditUnion` and `MortgageCompany` as
    subclasses. TenetRAG uses `OrgCategory` values for these.
  - Accounts: `fibo-fbc-pas-caa:DepositAccount` (with demand and time
    deposit accounts) is in ClientsAndAccounts.rdf.
  - Loans: `fibo-loan-ln-ln:Loan` with `SecuredLoan`, `CollateralizedLoan`
    and `GuaranteedLoan` is in LOAN/LoansGeneral/Loans.rdf.
  - Standalone collateral and guaranty classes were not located.
- **GLEIF Level 2** (RR-CDF 2.1) has exactly six relationship types
  [primary]:
  - `IS_DIRECTLY_CONSOLIDATED_BY`
  - `IS_ULTIMATELY_CONSOLIDATED_BY`
  - `IS_INTERNATIONAL_BRANCH_OF`
  - `IS_FUND-MANAGED_BY`
  - `IS_SUBFUND_OF`
  - `IS_FEEDER_TO`

  Records carry status, periods, qualifiers (such as the accounting
  standard) and quantifiers. Consolidation is accounting-based, not an
  ownership percentage.
  ([format](https://www.gleif.org/en/about-lei/common-data-file-format/relationship-record-cdf-format))
- **ECB BIRD** logical data model v1.2 [primary,
  [PDF](https://ecb.europa.eu/stats/ecb_statistics/reporting/html/BIRD_Introduction_to_the_LDM_V1.2.pdf)]:
  - Chapters: parties and groups; instruments and credit facilities;
    financial and physical collateral; securities and derivative positions;
    securitisation and covered bonds; rating systems (issue and issuer).
  - It models one reporting agent's snapshot at a reference date, and
    separates solo from consolidated reporting.
  - This is the best banking-side concept list found. Its license was not
    found.
- **BIAN** Service Landscape 11.0 lists 322 service domains, and a later
  version about 340. It is banking-only, and its terms of reuse were not
  found. [primary for 11.0, secondary for later]
- **Industry data models** cover banking, markets and often insurance in
  one enterprise model [secondary]:
  - IBM's FSDM has nine concepts: Involved Party, Arrangement, Condition,
    Product, Location, Classification, Event, Resource Item, Business
    Direction Item.
  - Teradata FSLDM is a single model.
  - Microsoft's financial-services data model has a banking-core submodel.
  - Only their subject-area names are public.
- **Bank metric definitions vary** by source, jurisdiction and edition:
  - The IMF Financial Soundness Indicators guide (2019 edition, which maps
    from the 2006 one) uses "interest margin to gross income" and
    "noninterest expenses to gross income". Common usage is net interest
    margin over earning assets, and cost-to-income. [primary contents;
    secondary definitions]
  - The LCR is HQLA over 30-day net outflows, at least 100 %, with national
    discretion. [primary,
    [BIS LCR30](https://www.bis.org/basel_framework/chapter/LCR/30.htm)]
  - Non-performing exposure definitions were harmonised by the BCBS only in
    2017. [secondary]
  - The CASA ratio has no standard-setter definition. [secondary]

## Banking

- **Public case studies** of bank LLM and RAG systems describe policy and
  procedure lookup, and knowledge bases for advisors. No public case
  confirms committee minutes, campaign briefs or KPI glossaries as indexed
  corpora. [secondary]
- **Bank graph work** that was found runs on structured data: KYC,
  transactions, data lineage and regulatory data governance. It is not
  LLM-extracted document graphs. Neo4j's KYC and transaction models hold
  names, birth dates, passport numbers and device data. [primary]
- **No separate document schema.** No standard, vendor or open-source
  project was found that ships a banking document schema separate from
  finance. [secondary]
- **Bank-specific items are few.** Product terms, KPI definitions, limits
  and covenants share one shape: subject, feature or measure, value, scope,
  period, source. That shape is a few fact types, not a taxonomy. Customer,
  account and transaction data is personal, structured data that belongs in
  SQL. [inferred]

## Enterprise documents

### Meetings and decisions

- **AMI corpus** (CC BY 4.0) [primary,
  [license](https://groups.inf.ed.ac.uk/ami/corpus/license.shtml)].
  Decision-related dialogue acts are defined through the extractive summary
  that supports the abstractive decisions summary. Action items are derived
  from the "actions" summary, not annotated as fields. [secondary]
- **Owner, due date and status** are not annotated as fields in any public
  meeting corpus found, and no LLM accuracy for them was found. [gap]
- **QMSum** queries ask for overall content, speakers' opinions and reasons
  for proposals. That supports a verbatim `rationale` on decisions.
  [secondary]
- **Decision logs and RAID logs** share the same small core of fields:
  - Decision logs: decision, date, decision-maker, status, rationale,
    options considered.
  - RAID logs: risk, assumption, issue or dependency; owner; status;
    probability; impact; review date.

  [secondary: template vendors]

### Obligations, definitions and versions

- **Deontic classes.** ComplianceNLP uses obligation, permission,
  prohibition and recommendation. [primary,
  [arXiv 2604.23585](https://arxiv.org/html/2604.23585)]
- **Requirements text.** EARS patterns (event-driven WHEN, state-driven
  WHILE, optional WHERE) support an optional condition on requirements.
  [secondary]
- **Definitions and acronyms.** DEFT (SemEval-2020 Task 6) treats a
  definition as a relation between a term and its gloss. SDU@AAAI-21 covers
  acronym identification and disambiguation. No peer-reviewed work on
  extracting KPI formulas was found. [secondary]
- **Versions.** [VersionRAG](https://arxiv.org/abs/2510.08109) scored 90 %,
  against 58 % for naive RAG and 64 % for GraphRAG. The test set was 100
  questions over 34 versioned documents, and the paper is a preprint.
  "Version conflation" is the named failure mode. [primary]
- **Enterprise benchmark.**
  [EnterpriseRAG-Bench](https://arxiv.org/html/2605.05253) (data MIT) has
  about 500K synthetic documents from nine tools and 500 questions in ten
  categories, among them 20 conflicting-information questions. It has no
  "as of a date" category. [primary]

### Products, glossaries and semantic layers

- **Enterprise knowledge products publish generic types.** None lists
  policy, procedure or metric.
  - Atlassian Teamwork Graph: calendar event, comment, conversation,
    document, message, space, project, work item, customer organization,
    deal, and development objects.
    [primary](https://developer.atlassian.com/platform/teamwork-graph/object-types/)
  - Glean describes content, people and activity. [secondary]
- **Viva Topics** typed topics as project, event, organization, location,
  product, creative work and field of study [secondary]. It was retired on
  2025-02-22, and its AI-generated topic pages are no longer available
  [primary, [Microsoft Learn](https://learn.microsoft.com/en-us/viva/topics/)].
  No cause was given.
- **Glossary term fields** converge on name, definition, acronym, synonym,
  related term, parent, owner or expert, and status:
  - Purview: Draft → Published → Expired.
  - Atlan: Verified, Draft or Deprecated.
  - SKOS adds scope, change and history notes.

  [primary: [Purview](https://learn.microsoft.com/en-us/purview/unified-catalog-glossary-terms-create-manage),
  [Atlan](https://docs.atlan.com/product/capabilities/governance/glossary/how-tos/bulk-upload-terms-in-the-glossary),
  [SKOS](https://www.w3.org/TR/skos-reference/)]
- **Metric definitions** in semantic layers:
  - dbt has five metric types: simple, cumulative, derived, ratio and
    conversion. Their fields are expression, numerator, denominator, filter
    and window. [primary,
    [dbt](https://docs.getdbt.com/docs/build/metrics-overview)]
  - Databricks metric views have source, filter, dimensions, measures and
    joins. [primary]
  - Snowflake semantic views have facts, dimensions, metrics and verified
    queries. [primary]
  - The Open Semantic Interchange is now **Apache Ossie** (Apache-2.0,
    incubating). Its metric fields are name, expression, description,
    datatype and AI context. [primary,
    [announcement](https://ossie.apache.org/updates/ossie-enters-apache-incubator/)]
- **No versioned definitions.** None of the glossary or metric
  specifications read keeps a definition as dated versions. Each holds one
  current definition plus a status. [inferred from those read; Collibra and
  Alation not read]

## Cross-domain types

- **Coarse NER types.** [Few-NERD](https://github.com/thunlp/Few-NERD) has
  8 coarse and 66 fine types; the data is CC BY-SA 4.0. It leaves out value
  types such as cardinals, days and percentages, and merges country,
  province and city into one class because context rarely separates them.
  Person, organization and location are the only types every inventory
  shares. [primary]
- **Vietnamese NER.**
  - [PhoNER_COVID19](https://github.com/VinAIResearch/PhoNER_COVID19) has
    10 entity types, under research and education use only, with no
    redistribution. [primary] Its paper reports location–organization
    confusion as the largest error group. [primary, not re-checked]
  - VLSP 2021 NER has 14 main types and 26 subtypes; its label list was not
    verified. [primary abstract]
- **Positions.** W3C ORG models membership as an n-ary `Membership` with a
  role and a duration, plus a `Post` that can exist without an occupant.
  Wikidata P39 uses an office item with start, end and replaces qualifiers.
  No paper compares these shapes for LLM extraction. [primary]
- **Events.** Type counts vary from ACE 2005's 33 to GENEVA's 115 and RAMS's
  139. In one LLM event-extraction study, the most common error was a
  correct span with the wrong type. [primary, single paper] No study of
  accuracy against the number of types was found. [gap]
- **Source statements** (TenetRAG facts, MS GraphRAG claims). MS GraphRAG:
  "Off by default, because claim prompts really
  need user tuning." [primary,
  [config](https://microsoft.github.io/graphrag/config/yaml/)]
- **Graph noise.** Removing 40 % of the entities and relations in LLM-built
  graphs improved four graph-RAG methods (DEG-RAG, "Less is More",
  preprint). [primary,
  [arXiv 2510.14271](https://arxiv.org/html/2510.14271)]

## Datasets for tests and benchmarks

Default packs ship synthetic test documents. These datasets serve as type
evidence or as candidates for the M4 benchmark. Check each license before
any use.

| Dataset | Use | License (checked 2026-10-04) |
|---|---|---|
| EnterpriseRAG-Bench | enterprise QA benchmark | MIT (data) |
| AMI | meeting decisions and actions | CC BY 4.0 |
| FinanceBench | finance QA; 150-question open sample | cc-by-nc-4.0 on Hugging Face; repo states none |
| VersionQA (VersionRAG) | versioned-document QA | not checked |
| FinRED | finance relations | CC BY 4.0 per the paper; repo states none |
| REFinD, FinDKG | finance relations, temporal KG | paper CC BY-NC-SA 4.0; data license not found |
| Few-NERD | coarse types | CC BY-SA 4.0 |
| PhoNER_COVID19 | Vietnamese NER | research and education only, no redistribution |

## Gaps

- **Licenses not found:** BIRD, EBA DPM, BIAN, ISO 20022 (terms page
  blocked), the IMF FSI guide, the current US GAAP taxonomy, and the UK Open
  Banking open-data licence (conflicting pages).
- **Not read:** IBM BFMDW and Teradata subject areas from primary pages;
  Collibra, Alation and Unity Catalog glossary fields; Notion, Slack, Google
  Workspace and Writer models.
- **No measurements:**
  - LLM extraction accuracy for meeting action items (owner, due date,
    status);
  - scale, currency or restatement handling in finance extraction;
  - schema versus no schema on finance;
  - accuracy as the number of types grows.
- **Unconfirmed corpora:** no public confirmation that banks index committee
  minutes, campaign briefs or KPI glossaries. Those question types are
  inferred.
