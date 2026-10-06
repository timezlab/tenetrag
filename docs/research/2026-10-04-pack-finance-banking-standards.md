# Finance and banking standards and industry data models

> **Snapshot, 2026-10-04 — not maintained.** Web lane on FIBO, GLEIF, ISO identifiers, ISO 20022, BIAN, BIRD, industry models, open banking, XBRL, BIS and IMF. The maintained,
> re-verified summary is in [domain-schemas.md](../reference/domain-schemas.md); where they differ, the maintained doc
> wins. Local paths were removed before publishing.
>
> **Errata and later resolutions:**
> - GLEIF: the official spelling is `IS_FUND-MANAGED_BY` (hyphen), not `IS_FUND_MANAGED_BY`.
> - BIAN: 322 service domains is Service Landscape 11.0 (2022); a later version has about
>   340 [secondary]. Reuse terms were not found.
> - FIBO: `DepositAccount` is in FBC/ProductsAndServices/ClientsAndAccounts.rdf; `Loan`,
>   `SecuredLoan`, `CollateralizedLoan` and `GuaranteedLoan` are in LOAN/LoansGeneral/Loans.rdf.
>   Standalone collateral and guaranty classes were not located.
> - IFRS Taxonomy: direct amendments are forbidden, while additions and extension taxonomies
>   are allowed only as necessary; citing element names is not addressed.
> - BIRD: the EPL-2.0 license found belongs to the separate Eclipse Free BIRD Tools, not to
>   the BIRD model.

## Finance and banking standards for a TenetRAG banking pack (research r4)

Date: 2026-10-04. Labels: [primary] = read on the owning source this session (WebFetch output is summarized by a small model, so quotes are paraphrase-grade); [secondary] = search snippet or third party; [inferred] = my reasoning.

### 1. Summary

- FIBO repo license is MIT [primary]. We may carry IRIs plus short own-words mappings freely, and could copy labels or definitions with the MIT notice. Our rule (own names, IRIs under `mappings`) is stricter than needed. Keep it anyway.
- FIBO has no "banking" module. Banking sits in FBC (FunctionalEntities, ProductsAndServices incl. ClientsAndAccounts) and LOAN. Markets sit in SEC, DER, MD, CAE, IND [primary directory listing; split is inferred].
- GLEIF Level 2 has exactly six relationship types, all entity-to-entity, none banking- or markets-specific [primary]. LEI data is CC0 1.0 [primary], with a non-endorsement and no-IP-claim condition.
- BIRD (ECB) has the best banking-side model: parties and groups, instruments, credit facilities, collateral, securitisation, covered bonds, ratings. It also covers securities positions [primary, TOC]. Its license was not verified.
- IFRS Taxonomy terms forbid commercial use (including data services and research databases), translation and rebranding [primary]. Treat as IRI-only, and possibly not even that for commercial distribution. Ask the IFRS Foundation.
- BIS lets you quote a "limited extract" (max 400 words or two tables, max 10% of the publication) with citation [primary]. Non-commercial reuse is allowed; commercial extract reproduction needs authorization. Short definition quotes with citation are safe.
- IBM, Teradata and Oracle model banking and insurance in one unified warehouse; none splits banking from markets as a top-level boundary [secondary]. Only the subject-area names are usable.
- BIAN is banking-only, with 322 service domains and a Business Object Model [primary]. Its license and membership terms are not verified.
- The finance draft lacks banking concepts: deposit and loan product/contract, account, facility, collateral, guarantee, credit exposure, prudential metrics, and the solo vs consolidated reporting basis [inferred from standards].
- Standards treat banking and capital markets as separable specializations over a shared core (party, contract, instrument, reporting basis). That supports a separate `banking` pack on top of a shared base [inferred].

### 2. Table

| Standard | Scope | Banking vs markets split | Key concepts for pack types | License | May carry |
|---|---|---|---|---|---|
| FIBO | OWL ontology, 10 domains | Banking in FBC + LOAN; markets in SEC/DER/MD/CAE/IND [inferred from dirs] | Bank, CentralBank, CreditUnion, LoanContract, Collateral, Guaranty, InterestRate | MIT [primary] | IRIs; short labels with MIT notice |
| GLEIF L2 | Entity relationships | Neutral | 6 relation types, status, periods, qualifiers | CC0 data [primary] | Types, field names, data |
| ISO identifiers | LEI, ISIN, CFI, MIC, currency | Markets-leaning (ISIN, CFI, MIC) | Identifier attributes | Mixed (see 3.3) | Code values per RA terms; not standard text |
| ISO 20022 | Business model + messages | Payments and securities both | Party, Account, Agreement (names not verified) | "Free reproduce" under IPR policy [secondary] | IRIs; verify terms page |
| BIAN | Banking capability map | Banking-only | Service domains, BOM (Payment, Facility, Collateral, Party, Product) [secondary] | Not verified | IRIs only |
| ECB BIRD | Reporting LDM | Banking-centric; securities included | Parties, instruments, facilities, collateral, securitisation, ratings | Not verified | IRIs only until verified |
| EBA DPM | Reporting data points | Banking supervision | Templates, data points | Not verified for EBA | IRIs only |
| FSLDM / IBM / OFSAA / MS | Warehouse models | Unified FS | Party, Arrangement, Product, Event, Location, etc. | Proprietary | Subject-area names only |
| UK Open Data API | Product open data | Retail/SME banking | Product attributes (fees, rates, eligibility) | "Open Licence" (see 3.8) | Verify before use |
| FDX / Berlin Group | Data-sharing APIs | Retail banking access | Account, transaction | FDX click-through; Berlin CC BY-ND [secondary] | IRIs only |
| IFRS / US GAAP taxonomy | Reporting elements | Neutral | Financial statement items | IFRS non-commercial [primary]; US GAAP unverified | IRIs only |
| IMF FSI, BIS | Bank metrics definitions | Banking | CAR, NPL, LCR, NIM | IMF unverified; BIS limited extract [primary] | Cited short definitions |

### 3. Findings per standard

#### 3.1 FIBO (EDM Council)
- License is MIT; repo is edmcouncil/fibo, open community model since Jan 2020, standardized by OMG, DCO required for contributors [primary: https://github.com/edmcouncil/fibo].
- Domains: BE, BP, CAE, DER, FBC, FND, IND, LOAN, MD, SEC [primary, same URL].
- FBC has four subfolders: DebtAndEquities, FinancialInstruments, FunctionalEntities, ProductsAndServices. Its README calls the content "business concepts common to finance areas, such as loans, securities, and corporate actions" [primary: https://github.com/edmcouncil/fibo/tree/master/FBC]. So FBC is a shared layer, not bank-only.
- ProductsAndServices holds ClientsAndAccounts.rdf and FinancialProductsAndServices.rdf [primary: https://github.com/edmcouncil/fibo/tree/master/FBC/ProductsAndServices]. I did not read their class lists, so I cannot name the deposit and account classes.
- FunctionalEntities (FinancialServicesEntities.rdf) defines institution types. Depository: Bank, CommercialBank, CentralBank, SavingsAssociation, CreditUnion. Non-depository: BrokerageFirm, FinanceCompany, MortgageCompany, InsuranceCompany, ClearingHouse, CentralSecuritiesDepository, TrustCompany, BankHoldingCompany, DevelopmentBank, MoneyServicesBusiness, plus BusinessIdentifierCode [primary: https://raw.githubusercontent.com/edmcouncil/fibo/master/FBC/FunctionalEntities/FinancialServicesEntities.rdf]. This matches our `OrgCategory`, and it shows FIBO models institution kinds as subclasses, where we use an enum.
- LOAN has LoansGeneral, LoansSpecific, RealEstateLoans. It covers loan contracts across commercial, small business, auto, education and mortgage, with party obligations, credit/risk and security agreements [primary: https://github.com/edmcouncil/fibo/tree/master/LOAN].
- LOAN concepts include LoanContract, Collateral, Guaranty/guarantor, commitment, prepayment penalty, lender, servicer, property valuation [secondary: https://dil-edmcouncil.atlassian.net/wiki/spaces/LOAN/pages/8782345/Concept+Map+of+LOAN+structure+from+FIBO+red].
- IND has EconomicIndicators, ForeignExchange, Indicators, InterestRates, MarketIndices [primary: https://github.com/edmcouncil/fibo/tree/master/IND]. Interest rates and indicators are shared by both worlds.
- CAE, SEC, DER, MD: only the names are confirmed. I did not open their content.

#### 3.2 GLEIF
- Level 2 (RR-CDF 2.1) has six types: IS_DIRECTLY_CONSOLIDATED_BY, IS_ULTIMATELY_CONSOLIDATED_BY, IS_INTERNATIONAL_BRANCH_OF, IS_FUND_MANAGED_BY, IS_SUBFUND_OF, IS_FEEDER_TO [primary: https://gleif.org/en/about-lei/common-data-file-format/relationship-record-cdf-format].
- Record fields: StartNode, EndNode (LEI or ISO 17442-compatible ID), RelationshipType, RelationshipStatus (ACTIVE/INACTIVE/NULL), RelationshipPeriods (accounting, relationship or filing), RelationshipQualifiers (e.g. accounting standard), RelationshipQuantifiers (value, method, unit), Registration (dates, status, validation source, managing LOU) [primary, same URL].
- Consolidation is accounting-based, not an ownership percentage. Reporting exceptions are published as a third file [primary: https://www.gleif.org/en/lei-data/gleif-concatenated-file/download-the-concatenated-file]. Files dated 2026-10-04 hold about 3.4M LEI records and 672K relationship records.
- License: LEI data under CC0 1.0 Universal [primary: https://www.gleif.org/en/meta/lei-data-terms-of-use]. Conditions: acquire no IP in LEIs, do not imply GLEIF endorsement, as-is, with a liquidated-damages clause for breach of the terms. Note this is more than plain CC0, so cite the terms of use and include a non-endorsement line.

#### 3.3 ISO identifiers
- LEI (ISO 17442): the data is free and CC0 [primary, 3.2]. Whether the standard text is paywalled was not confirmed.
- ISO 4217: machine-readable lists are free at currency-iso.org; ISO sells PDFs [secondary: https://help.iso.org/en/articles/376283-iso-4217-international-currency-codes-for-clarity-and-consistency-in-global-trade].
- ISO 10383 MIC: list free from the ISO 20022 site in CSV, XML, XLS; standard text is sold [secondary: https://iso20022.org/market-identifier-codes].
- ISIN (ISO 6166): ANNA and national agencies may charge for issuance, and licences may govern redistribution of ISIN data [secondary: https://www.finextra.com/blogposting/11977/mifir-how-isins-work-4]. Carrying the format and field in the schema is fine; bundling ISIN data sets is a risk [inferred].
- CFI (ISO 10962): the standard is sold (~EUR 70) [secondary: https://tienda.aenor.com/p/norma-iso-10962-2021-081140]. Use our own `Instrument.kind` enum and map to CFI by IRI or code string at most.

#### 3.4 ISO 20022
- Terms-of-use page returned 403 (not read). Snippet: site material "intended to be used and reproduced freely" under the ISO 20022 IPR policy; contributors grant third parties a non-exclusive royalty-free license [secondary: https://iso20022.org/terms-use]. The business model defines business components and elements and their relationships [secondary: https://iso20022.org/node/196].
- I could not verify the component list (Party, Account, Agreement). Use only as mapping targets.

#### 3.5 BIAN
- Service Landscape 11.0 has 322 service domains, about 5000 service definitions, 250 semantic APIs, a Business Capability Model and a Business Object Model; access is through portal.bian.org [primary: https://bian.org/deliverables/service-landscape/bian-service-landscape-11-0/].
- BOM lists objects such as Payment, Document, Facility, Collateral, Party, Product [secondary: Wikipedia and search summary, https://en.wikipedia.org/wiki/Banking_Industry_Architecture_Network]. A free HTML version exists for non-members [secondary: https://bian.org/deliverables/service-landscape/].
- License text and membership rules: NOT found. Do not copy anything.

#### 3.6 ECB BIRD and EBA DPM
- BIRD LDM v1.2 (Dec 2022, 88 pp) is a "highly normalised" model of what must be reported, from one reporting agent's view, as a snapshot at a reference date. It distinguishes consolidated, solo and foreign-branch reporting agents [primary: https://ecb.europa.eu/stats/ecb_statistics/reporting/html/BIRD_Introduction_to_the_LDM_V1.2.pdf].
- TOC chapters: Parties and Groups; Instruments and Credit facilities; Collateral (financial, physical); Securities, exchange-tradable derivatives and positions; Securitisation, covered bond programs and other credit transfers; Cash and non-financial assets/liabilities; Rating systems (issue, issuer, numeric); Reference data [primary, same PDF]. This is the single most useful banking-side concept list found.
- Same document says the LDM is also published on the BIRD website and GitHub. Licence: NOT verified (bird.ecb.europa.eu returned 503). BIRD is voluntary and users stay responsible for their reports [secondary: https://www.regnology.net/en/resources/regulatory-topics/banks-integrated-reporting-dictionary-bird/].
- EBA DPM: a methodology and data dictionary that drives EBA XBRL taxonomies; DPM 2.0 only from Dec 2025 [secondary: https://eba.europa.eu/sites/default/files/2024-12/8fdac0fc-ddf7-4244-831c-20be53b2605a/EBA%20and%20EIOPA%20taxonomy%20architecture%20v2.0-20241218.pdf]. The permissive license I found (perpetual, royalty-free, sub-licensable) is EIOPA's, not the EBA's [secondary: https://eiopa.europa.eu/system/files/2019-09/eiopa_dpm_and_taxonomy_license.pdf]. Do not assume it applies to the EBA.

#### 3.7 Proprietary industry models (names only)
- IBM BFMDW FSDM: nine concepts: Involved Party, Arrangement, Condition, Product, Location, Classification, Event, Resource Item, Business Direction Item [secondary: https://www.ibm.com/support/pages/node/712957, search summary]. Your list omitted Business Direction Item. Business areas include ALM, investment management, payments, profitability, regulatory compliance, relationship marketing, risk, wealth.
- Teradata FSLDM: covers retail and commercial banking, brokerage, investment, cards, P&C and life insurance; "10 major subject areas", 2,500 entities [secondary: https://www.teradata.com/Industries/Financial-Services/logical-data-model]. I could not confirm the Party/Agreement/Campaign/Channel names from a primary page.
- Oracle OFSDF: staging and reporting models; subject areas such as Accounts with dimensions product type, party type, account rating [secondary: https://docs.oracle.com/en/industries/financial-services/ofs-analytical-applications/data-foundation-cloud/24c/dfcug/subject-area.html].
- Microsoft: only generic "industry data models" and pre-built schemas for banking, insurance and capital markets were found [secondary: search summary]. Specific entity names not found.
- Finding [inferred]: these models treat banking and markets as one enterprise model, with a product/arrangement hierarchy.

#### 3.8 Open banking product data
- UK Open Data API: v2.1.0 Sept 2017, v2.2.0 listed [secondary]; spec covers products, branches and ATMs; repo github.com/OpenBankingUK/opendata-api-spec-compiled.
- Licence is conflicted. The openbanking.org.uk/open-licence page fetched as MIT-license text [primary but unexpected, https://www.openbanking.org.uk/open-licence/]; search says "Open Licence v2.0" [secondary]. Treat as UNVERIFIED and check the repo LICENSE.
- Product attribute lists (fees, rates, eligibility) were not read.
- FDX: spec free to implement, but the license agreement is "limited, revocable, non-exclusive, non-transferable, non-sublicensable" [secondary: https://financialdataexchange.org/wp-content/uploads/2026/08/FDX-API-License-Agreement-July-15-2026-Final-II.pdf]. Do not copy.
- Berlin Group NextGenPSD2: CC BY-ND 4.0 [secondary: search summary]. No-derivatives bars adapted copies. IRIs and reading only.

#### 3.9 XBRL taxonomies
- IFRS Taxonomy [primary: https://ifrs.org/content/dam/ifrs/about-us/legal-and-governance/legal-docs/taxonomy/taxonomy-terms-and-conditions.pdf]. Allowed: view, use as-is, create instances, create taxonomies "not for Commercial Use", distribute in full for personal/professional use with attribution. Forbidden: commercial use (includes "investment analysis", "data services", "research database", "educational services and materials"), translation, rebranding, amendments. Copyright is the IFRS Foundation's. Not free for an SDK.
- US GAAP taxonomy: an old (2008) XBRL US notice allows royalty-free use in US GAAP reporting and unchanged incorporation in explanatory works [secondary: search snippet]. Current FASB terms not verified.

#### 3.10 IMF FSI and BIS
- BIS: limited extract (max 400 words or 2 tables/graphs, max 10% of publication) free with BIS cited; more needs written permission; BIS Data Portal statistics have separate terms; translations must carry a not-official disclaimer [primary: https://www.bis.org/terms_conditions.htm].
- IMF FSI Compilation Guide 2019: copyright IMF; reuse terms NOT read [secondary: https://www.imf.org/external/np/sta/fsi/eng/guide/]. The guide is also sold.
- Practice [inferred]: store our own metric definitions, with a `source` IRI or citation. Never paste the standard text. Basel Framework text is covered by the BIS terms above.

### 4. Concepts a banking pack needs that `finance` lacks [inferred, built from FIBO LOAN/FBC, BIRD, IBM FSDM]
- Entities: `Account` (current, savings, loan, card) with a holder role; `Facility` (credit line, with limit, drawn, undrawn); `LoanContract` (principal, rate, maturity, repayment); `Deposit`; `Collateral` (financial vs physical); `Guarantee` (guarantor, beneficiary); `Branch` and `Channel`; `Segment` and `Counterparty`; `Product` as a bank offering with `ProductTerms` (fees, rates, eligibility), which the finance `Instrument` does not model.
- Relations: `SECURED_BY`, `GUARANTEED_BY`, `LENDS_TO`, `HOLDS_ACCOUNT_AT`, `BRANCH_OF`, `OFFERED_VIA`, `PART_OF_GROUP`. `SUBSIDIARY_OF` and `OWNS_STAKE` exist already; add consolidation basis (accounting vs prudential) as in GLEIF and BIRD.
- Claims and events: `PrudentialMetric` (CAR, NPL ratio, LCR, NIM) as a specialization of `ReportedFigure`, with scope (solo or consolidated), accounting basis and reference date. Add `CreditRatingAssignment` (issue vs issuer, BIRD), `Securitisation`, `CampaignLaunch`, `ProductChange`, `RegulatoryAction`.
- Enums: `ConsolidationBasis`, `ReportingScope`, `CollateralKind`, `AccountKind`, `FacilityKind`, `ChannelKind`, with `OrgCategory` extension (central_bank, credit_union, savings, mortgage_lender, clearing).
- Gap in `finance`: no reporting-basis or snapshot-date discipline, which BIRD treats as fundamental.

### 5. Gaps
- Not read or not verified: ISO 20022 terms page (403), BIRD licence (503), BIAN licence and membership, EBA DPM licence, IMF reuse terms, current FASB taxonomy terms, Open Data API licence (conflicting), FDX and Berlin Group terms (snippets only), ISO standard paywalls for 17442, 6166, 10383 (RA-side only).
- FIBO: class lists for FinancialProductsAndServices, ClientsAndAccounts, CAE, SEC, DER, MD and the exact deposit, account and guaranty class names not read.
- Open Data product attribute lists, Teradata FSLDM subject-area names, Microsoft entity names, ISO 20022 business component list: not found.
- Disconfirming search for the "separable" conclusion was not run; it rests on directory structure and secondary summaries.

leads: confirm the BIRD and EBA licences by email or the repo; check BIAN terms; read FIBO FBC class lists in the FIBO viewer.
