# Fact-checks: pack papers, standards and licenses

> **Snapshot, 2026-10-04 — not maintained.** Two adversarial fact-check lanes run against load-bearing claims of the other 2026-10-04 lanes. The maintained,
> re-verified summary is in [domain-schemas.md](../reference/domain-schemas.md); where they differ, the maintained doc
> wins. Local paths were removed before publishing.
>
> **Errata and later resolutions:**
> - WebFetch returns a model summary of each page, so quotes are near-verbatim, not
>   byte-exact. Not legal advice. Both lanes lacked a file tool; their reports were saved
>   from the session record unchanged.

## Papers and benchmarks

Report (the lane had no file tool). Caveat: the CC BY-NC-SA 4.0 shown on arXiv pages (claims 1 and 3) is the paper-text license, not necessarily the dataset license. WebFetch summarised the pages, so quotes are near-verbatim extracts, not raw text.

1. FinDKG: PARTLY. Confidence high on types, low on dataset license.
- https://arxiv.org/html/2407.10909 Table 2 gives 12 entity types: "ORG, ORG/GOV, ORG/REG, GPE, PERSON, COMP, PRODUCT, EVENT, SECTOR, ECON IND, FIN INST, CONCEPT". EVENT is an entity type.
- Table 1 gives 15 relations: Has, Announce, Operate In, Introduce, Produce, Control, Participates In, Impact, Positive Impact On, Negative Impact On, Relate To, Is Member Of, Invests In, Raise, Decrease. Control and Invests In are included.
- https://arxiv.org/abs/2407.10909 shows ICAIF '24 and CC BY-NC-SA 4.0. That is the paper license; I did not check the data repo.

2. FinReflectKG: CONFIRMED. Confidence high.
- https://arxiv.org/html/2508.17906 lists 10 entity types: ORG, PERSON, COMP, PRODUCT, SEGMENT, FIN_METRIC, RISK_FACTOR, EVENT, REGULATORY_REQUIREMENT, ESG_TOPIC.
- It lists 10 relations: Has_Stake_In, Operates_In, Produces, Impacts, Involved_In, Impacted_By, Discloses, Complies_With, Supplies, Partners_With.
- Data is "annual SEC 10-K filings of all the S&P 100 companies for the year 2024".
- Venue: "6th ACM International Conference on AI in Finance (ICAIF '25), November 15-18, 2025, Singapore". This comes from the HTML; the abs page shows only q-fin.CP.

3. REFinD and FinRED: PARTLY. Confidence medium.
- https://arxiv.org/abs/2305.18322: "~29K instances", "22 relations amongst 8 types of entity pairs". The DOI 10.1145/3539618.3591911 is SIGIR 2023 proceedings.
- REFinD's CC BY-NC-SA 4.0 is the arXiv paper license. I found no dataset license (the NTUYG/REFinD GitHub guess returned 404).
- FinRED: https://arxiv.org/pdf/2306.03736 shows 29 relations and CC BY 4.0 linked to the GitHub repo. The FinRED GitHub README (https://github.com/soummyaah/FinRED) states no license. Venue is FinWeb at WWW'22.

4. FinanceBench: PARTLY. Confidence high.
- https://arxiv.org/abs/2311.11944: "10,231 questions about publicly traded companies" and "GPT-4-Turbo used with a retrieval system incorrectly answered or refused to answer 81% of questions". Both confirmed.
- 10,231 is the paper's full set. The public repo https://github.com/patronus-ai/financebench holds only "an open source sample of 150 annotated examples". Its README states no license and the LICENSE URL returned 404.
- Hugging Face metadata (https://huggingface.co/datasets/PatronusAI/financebench) lists cc-by-nc-4.0.

5. VersionRAG: CONFIRMED, not peer-reviewed. Confidence medium.
- https://arxiv.org/abs/2510.08109: "VersionRAG achieves 90% accuracy, outperforming naive RAG (58%) and GraphRAG (64%)". VersionQA has "100 manually curated questions across 34 versioned technical documents".
- The page names no venue, so it is a preprint. Absence of a venue on the page is not proof that none exists.

6. EnterpriseRAG-Bench: CONFIRMED, with a license split. Confidence high.
- https://arxiv.org/html/2605.05253: about 500K documents from 9 sources (Slack, Gmail, Linear, Google Drive, HubSpot, Fireflies, GitHub, Jira, Confluence). The 500 questions in 10 categories match your counts exactly.
- Dataset license is MIT, per https://huggingface.co/datasets/onyx-dot-app/EnterpriseRAG-Bench and https://github.com/onyx-dot-app/EnterpriseRAG-Bench. The paper itself is under the arXiv non-exclusive license.

7. ComplianceNLP: CONFIRMED. Confidence high.
- https://arxiv.org/html/2604.23585: "Obligation, Permission, Prohibition, and Recommendation", a four-class sentence-level deontic classification.

8. Microsoft GraphRAG claim extraction: CONFIRMED. Confidence high.
- https://microsoft.github.io/graphrag/config/yaml/: "Whether to enable claim extraction. Off by default, because claim prompts really need user tuning."

9. Few-NERD: CONFIRMED on type counts; license is CC BY-SA 4.0. Confidence medium-high.
- https://github.com/thunlp/Few-NERD: "8 coarse-grained types, 66 fine-grained types". Dataset is CC BY-SA 4.0 and code is Apache 2.0.
- I did not verify the eight coarse type names.

10. PhoNER_COVID19: PARTLY. Confidence medium.
- https://github.com/VinAIResearch/PhoNER_COVID19 confirms 10 entity types.
- It has no standard open license. It carries an "AS IS" warranty disclaimer, requires research or educational use only, and forbids redistribution. Treat it as restricted.
- The 10,027 sentence count and the LOCATION vs ORGANIZATION error group are unverified.

11. AMI: PARTLY. Confidence medium-high.
- https://groups.inf.ed.ac.uk/ami/corpus/license.shtml: "The AMI corpus and its annotations are released under the Creative Commons Attribution 4.0 license". CC BY 4.0 is confirmed.
- Decision annotation is real but worded differently. Decision-related dialogue acts are those in the extractive summary that support a decision in the abstractive decisions summary, so they are defined through the extractive summary, not linked directly. Source: Fernandez et al. 2008, https://staff.fnwi.uva.nl/r.fernandezrovira/papers/2008/08-interspeech-decisions-final.pdf, seen only as a search snippet.

12. arXiv 2510.14271: CONFIRMED. Confidence high.
- https://arxiv.org/html/2510.14271: "while removing 40% of the entities and relations in LLM-generated KGs, Deg-Rag consistently improves the performance of four representative Graph-based RAG approaches."
- The actual title is "Less is More: Denoising Knowledge Graphs For Retrieval Augmented Generation", not "When to prune". The method is DEG-RAG.

Disconfirming queries: for the license claims (1, 3, 4, 6, 10) I checked dataset repos and Hugging Face besides arXiv, which exposed the paper-license vs dataset-license gaps. For claim 12 I checked the title against the claim's and it did not match. For claim 4 I checked the README and LICENSE URL for a CC BY-NC mention. There was none, and Hugging Face disagrees with the README's silence.


## Standards and licenses

### r4 fact-check: standards claims (2026-10-04)

NOTE: I had no file-write tool, so (local path removed) was NOT written. This message is the report.

#### 1. FIBO — PARTLY (bonus part incomplete)
Confidence: high on the folder facts, medium on the bonus.
- MIT: CONFIRMED. The repo page shows an MIT badge. I did not read the LICENSE file itself. [github.com/edmcouncil/fibo](https://github.com/edmcouncil/fibo)
- Top-level domains: CONFIRMED. BE, BP, CAE, DER, FBC, FND, IND, LOAN, MD and SEC are all present. An `/etc` folder also exists.
- FBC subfolders: CONFIRMED. DebtAndEquities, FinancialInstruments, FunctionalEntities and ProductsAndServices. [FBC](https://github.com/edmcouncil/fibo/tree/master/FBC)
- ProductsAndServices: CONFIRMED, with one omission. It holds ClientsAndAccounts.rdf and FinancialProductsAndServices.rdf, and also MetadataFBCProductsAndServices.rdf.
- FunctionalEntities: CONFIRMED. The file FBC/FunctionalEntities/FinancialServicesEntities.rdf defines `fibo-fbc-fct-fse:Bank`, `CommercialBank`, `CentralBank` and `CreditUnion`. Quote: "CreditUnion – A not-for-profit depository institution promoting thrift among members". [raw rdf](https://raw.githubusercontent.com/edmcouncil/fibo/master/FBC/FunctionalEntities/FinancialServicesEntities.rdf)
- LOAN: CONFIRMED. Subfolders are LoansGeneral, LoansSpecific and RealEstateLoans. [LOAN](https://github.com/edmcouncil/fibo/tree/master/LOAN)
- Bonus, resolved:
  - Deposit account: `fibo-fbc-pas-caa:DepositAccount`. Related classes are `DemandDepositAccount`, `TimeDepositAccount` and `Account`. File: FBC/ProductsAndServices/ClientsAndAccounts.rdf.
  - Loan: `fibo-loan-ln-ln:Loan`. File: LOAN/LoansGeneral/Loans.rdf. The same file defines `SecuredLoan`, `CollateralizedLoan` and `GuaranteedLoan`.
- Bonus, not resolved: the standalone Collateral and Guaranty classes and their module files.
  - Loans.rdf does not define them. The fetch tool's own summary says it "references these from external ontologies".
  - A search suggests old IRIs such as `.../LOAN/Loans/LoansCollateral/`. I could not confirm this and it may be stale.
  - Label this UNVERIFIED. Look in FND or LOAN with the FIBO viewer.
- Disconfirming query: "FIBO DepositAccount Loan Collateral Guaranty class spec.edmcouncil.org" returned only Open Risk Manual pages, which sit behind a login. They were not usable.

#### 2. GLEIF — PARTLY (spelling suspicion CONFIRMED; the claim of "exactly six" is also CONFIRMED)
Confidence: high.
- The RR-CDF 2.1 RelationshipType enum has 6 values, spelled exactly:
  1. `IS_DIRECTLY_CONSOLIDATED_BY`
  2. `IS_ULTIMATELY_CONSOLIDATED_BY`
  3. `IS_INTERNATIONAL_BRANCH_OF`
  4. `IS_FUND-MANAGED_BY`
  5. `IS_SUBFUND_OF`
  6. `IS_FEEDER_TO`
  - Item 4 uses a hyphen. `IS_FUND_MANAGED_BY` is wrong. [GLEIF RR-CDF 2.1](https://www.gleif.org/en/about-lei/common-data-file-format/relationship-record-cdf-format)
- CC0: CONFIRMED. Quote: "The data available through the Access Service are provided under the CC0 licence". [LEI Data Terms of Use](https://www.gleif.org/en/meta/lei-data-terms-of-use). The concatenated-files page also says they are "released under a CC0 license".
- Non-endorsement: CONFIRMED. Users must not create the impression that data or services are "provided or supported or authorized or granted or otherwise associated by or with GLEIF". They must also not suggest that their products "are services or products of GLEIF or any LOU". The GLEIF trademark and logo need separate permission.
- Disconfirming query: "...IS_FUND-MANAGED_BY..." returned GLEIF text using the hyphen form. No source used the underscore form.

#### 3. IFRS Taxonomy — PARTLY
Confidence: high. I read the primary PDF: [Terms and Conditions of Use, IFRS Taxonomy Materials](https://ifrs.org/content/dam/ifrs/about-us/legal-and-governance/legal-docs/taxonomy/taxonomy-terms-and-conditions.pdf)
- Commercial use ban: CONFIRMED. Quote: "You may not use the Materials or part of the Materials for Commercial Use." Examples listed are reporting software, accounting software, tagging software, investment analysis, data services, research database, "educational services and materials" and "any other commercial product".
- Translation: CONFIRMED. Prohibited use (d) is "translate into another language (but for clarity this does not mean other Formats or programming languages)".
- Amendment: PARTLY. The ban applies to direct edits. Quote: "make any Amendments to the Materials without the prior written permission". "Additions" (overriding files or references) and Extension Taxonomies are allowed "only in so far as is necessary".
- The ban is on "Commercial Use", defined as use "for the purpose of generating monetary or other commercial benefit". Free non-commercial use is permitted. Allowed uses include:
  - view and use "as is";
  - create Instances;
  - create taxonomies and classifications, "not... to be used or distributed for Commercial Use".
- Citing IFRS element names or IRIs: NOT addressed explicitly. The terms say nothing about referencing identifiers. Clause 6B says all rights in "elements, identifiers" stay with the Foundation or XBRL International. "Materials" covers "all files and their content".
  - Citing names or IRIs as mapping references in a free, non-commercial OSS tool is plausible. It is not a clear safe harbour.
  - Bundling taxonomy files, or shipping them in a product intended for profit, is the risky part. A bank internal tool is arguably "commercial benefit".
  - Safest route: email taxonomy@ifrs.org for written confirmation. This is my inference, not a finding.
- Disconfirming query: "IFRS taxonomy terms commercial use prohibited translation amendment" returned only the same T&Cs, with no exemption for identifiers.

#### 4. BIS — CONFIRMED
Confidence: high. [bis.org/terms_conditions.htm](https://www.bis.org/terms_conditions.htm)
- Quote: "a 'limited extract' means any extract of not more than 400 words of text or two tables or graphs and the underlying data..., and in any case not exceeding 10% of the relevant publication". The BIS must be cited as source.
- Caveats: the page limits free use to non-commercial purposes. BIS statistics fall under separate terms. Translations must be marked unofficial.
- I ran no separate disconfirming query for this claim.

#### 5. OSI / Apache Ossie — CONFIRMED (repo check failed)
Confidence: medium-high.
- Primary: [ossie.apache.org announcement](https://ossie.apache.org/updates/ossie-enters-apache-incubator/). It gives "Apache License, Version 2.0", incubating, and the spec fields Name, Expression, Description, Datatype, AI_context.
- Rename reason: the old name clashed with other "OSI" projects. Search results date incubator acceptance to June 2026.
- Field casing and structure not verified: the fetch gave a field list, not the schema.
- GitHub: `github.com/open-semantic-interchange` shows "no public repositories". The code has probably moved to Apache, so that repo cannot be used to check the spec. I did not locate the Apache repo.
- Disconfirming check: the old org page. It gives no contradiction, only absence of evidence.

#### 6. BIAN — UNVERIFIABLE (terms)
Confidence: low.
- 322 service domains: CONFIRMED for Service Landscape 11.0 (Dec 2022), headline "All 322 service domains completed". [BIAN 11.0](https://bian.org/deliverables/service-landscape/bian-service-landscape-11-0/)
- STALE: a secondary source says version 14 has 340 domains. "About 322" is out of date for 2026.
- The Business Object Model is part of the Information Architecture.
- Licence: I could not read BIAN's terms. The `/terms-and-conditions/` URL returned 404, and searches found nothing. A secondary source says the landscape, BOM and APIs are "free of charge online". That is not a licence grant.
- Do not assume permissive reuse. Check bian.org legal pages or ask BIAN directly before copying names or definitions into a schema pack.

#### 7. ECB BIRD / EBA DPM — UNVERIFIABLE
Confidence: low.
- ECB BIRD pages: "accessed free of charge". The page has no BIRD-specific licence text. [ECB BIRD](https://www.ecb.europa.eu/stats/ecb_statistics/reporting/bird/html/index.en.html)
- `bird.ecb.europa.eu` returned 503.
- The `DGSbird/BIRD-data-models` repo shows no licence in the fetched text. [repo](https://github.com/DGSbird/BIRD-data-models)
- The only licence found is Eclipse Public License 2.0 for the separate Eclipse Free BIRD Tools. That is not the BIRD model licence. Do not transfer it.
- EBA DPM: no licence text found. DPM is now under the ECB/EBA/EIOPA DPM Alliance (MoU, March 2024). The claim that it differs from BIRD is unverified.
- ECB reuse policy generally follows Decision ECB/2024/... (not read). Treat that as unverified.

#### 8. Viva Topics — CONFIRMED (wording nuance)
Confidence: high. [Microsoft Learn](https://learn.microsoft.com/en-us/viva/topics/)
- Quote: "Viva Topics has been retired as of February 22, 2025."
- "Topic pages that were generated entirely by AI and machine learning algorithms will no longer be available." This is not literally "deleted". User-published pages became standard SharePoint pages.
- Disconfirming query: I searched for a different date or an extension and found none.
