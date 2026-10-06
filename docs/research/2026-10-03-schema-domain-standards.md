# Domain standards and datasets for default schema packs

> **Snapshot, 2026-10-03 — not maintained.** Two web lanes (set A: generic, finance, legal, public sector, HR, insurance, enterprise docs; set B: biomedical, science, news, cyber, IT, product, supply chain). Starter schemas here are lane drafts, not decisions. The maintained,
> re-verified summary is in [graph-schema-design.md](../reference/graph-schema-design.md); where they differ, the maintained doc
> wins. Local paths were removed before publishing.
>
> **Errata and later resolutions:**
> - Licenses re-checked on the owning sites the same day (see the license
>   fact-check in [2026-10-03-schema-factchecks.md](2026-10-03-schema-factchecks.md)):
>   GLEIF CC0 confirmed; W3C ORG and PROV-O fall under the W3C Document License,
>   OWL-Time under the permissive W3C Software and Document License; O*NET CC BY 4.0
>   with a required attribution sentence; IOF Core MIT, Brick BSD-3, SAREF BSD-3
>   (ETSI Forge), CycloneDX Apache-2.0, SPDX spec CC BY 3.0, ORKG CC0 except Papers
>   With Code data, CiTO CC BY 4.0, Akoma Ntoso OASIS notice, CUAD CC BY 4.0,
>   FiNER-139 CC BY-SA 4.0, BioRED US Government work.
> - Unverified after the re-check: ESCO, ELI, OpenAlex CC0, SPDX license-list CC0,
>   SciERC, MAVEN, CASIE and FinRED licenses. REFinD may be CC BY-NC-SA 4.0.
> - VLSP 2020 relation types are LOCATED, PART–WHOLE, PERSONAL–SOCIAL and
>   **ORGANIZATION–AFFILIATION**, over PER, ORG and LOC only.
> - MS GraphRAG and LightRAG default entity types were checked in source; see
>   [2026-10-03-schema-engine-customization.md](2026-10-03-schema-engine-customization.md).

## Set A

### Domain-pack schema grounding (domains 0-6 + Vietnamese aside) — 2026-10-03

Labels: [primary] read this session on the owning site; [secondary] search snippet only; [inferred] my prior knowledge or inference, NOT verified this session.

#### Summary table
| Domain | Anchor standard | License | Shippable? | Starter size |
|---|---|---|---|---|
| 0 Generic | schema.org + gist + PROV-O/OWL-Time/ORG (as inspiration) | schema.org CC BY-SA 3.0 [primary]; gist CC BY 4.0 [primary]; W3C ORG/PROV/Time: W3C doc license [inferred] | Names/short own definitions yes; copy no verbatim schema.org text (SA) | 10 ent / 14 rel |
| 1 Finance | FIBO (MIT [primary]), GLEIF LEI L1/L2 (CC0 [inferred; gleif page 404]) | MIT / CC0 | Yes (MIT needs notice if copying text) | 12 ent / 16 rel |
| 2 Legal | ELI, Akoma Ntoso (OASIS), FRBR, LKIF | ELI: EU reuse CC BY 4.0 [inferred]; AKN OASIS [inferred]; LKIF [unverified] | Use concepts, write own definitions | 11 ent / 14 rel |
| 3 Public sector | SEMIC Core Vocabularies, DCAT | CC BY 4.0 (c) EU [primary for Core Person] | Yes with attribution | 10 ent / 12 rel |
| 4 HR/skills | ESCO, O*NET, schema.org Occupation | ESCO CC BY 4.0 [secondary]; O*NET CC BY 4.0 [secondary] | Yes with attribution; do not bundle taxonomies, link by URI | 9 ent / 11 rel |
| 5 Insurance | ACORD | Membership/proprietary [secondary] | NO - write own | 11 ent / 13 rel |
| 6 Enterprise | schema.org Event/Action, AMI/QMSum as evidence | schema.org CC BY-SA; AMI CC BY 4.0, QMSum MIT [secondary] | Own definitions | 10 ent / 13 rel |

#### 0 Generic default
Standards: schema.org (Google/Microsoft/Yahoo/Yandex; CC BY-SA 3.0 + W3C patent policy; [primary schema.org/docs/terms.html]). gist (Semantic Arts; CC BY 4.0; ~100 classes, ~100 properties; top classes Person, Organization, Agreement, Event, Place etc.; minimalist upper ontology [primary github]). W3C ORG (Organization, Membership, Role, Post, hasMember, reportsTo), PROV-O (Entity, Activity, Agent, wasDerivedFrom, wasAttributedTo), OWL-Time (Instant, Interval) [inferred]. Wikidata core: instance of, part of, country, occupation, position held (with start/end time qualifiers), employer, member of, headquarters location [inferred]. Tool defaults: MS GraphRAG default types organization/person/geo/event; LightRAG person/organization/location/event/concept/etc.; neo4j LLM Graph Builder free-form [inferred, verify before citing].
Fit: schema.org too big (800+ types) -> take ~10 names only. gist best conceptual fit for enterprise. PROV/OWL-Time map to our provenance and valid time natively (we implement them in the engine, not the pack).
Licensing: Facts (type names) are not copyrightable in practice [inferred, not legal advice]; write our own one-line definitions; if schema.org IRIs are emitted, cite them as links only; avoid copying schema.org description text (CC BY-SA share-alike would taint docs).
Starter: entities Person, Organization, Place, Event, Document(Work), Product, Concept, Role/Position, Agreement, Money-less (amounts are attributes). Relations: Person-[MEMBER_OF/EMPLOYED_BY]->Org (time-varying), Person-[HOLDS_ROLE]->Role-[AT]->Org (time-varying), Org-[PART_OF]->Org (tv), Org-[LOCATED_IN]->Place (tv), Event-[OCCURRED_AT]->Place, Event-[PARTICIPATED_IN by]-Person/Org, Doc-[MENTIONS], Doc-[AUTHORED_BY], Org-[PARTY_TO]->Agreement, X-[RELATED_TO] (fallback), Org-[OWNS]->Org (tv), Person-[KNOWS]. Claim type: Statement(subject, predicate, object, asserted_by). Not entities: dates, amounts, percentages, titles as free text.
IRIs: schema:Person, schema:Organization, schema:Place, schema:Event, schema:CreativeWork, schema:Product, org:Role, org:Post, org:memberOf, org:subOrganizationOf, gist:Agreement, prov:Entity.
CQs: who held role X at org Y in year Z? Which org is part of which parent? Which events happened at place P between dates? Which docs mention person P? Who authored doc D? Which agreements is org O party to?

#### 1 Finance
Standards: FIBO, EDM Council, MIT license, 10 domains BE, BP, CAE, DER, FBC, FND, IND, LOAN, MD, SEC (+ACTUS) [primary github]; huge (thousands of classes) -> too big/abstract for LLM, use as IRI target only. GLEIF Level 1 (who is who: legal name, jurisdiction, legal form, status) and Level 2 (who owns whom: IS_DIRECTLY_CONSOLIDATED_BY, IS_ULTIMATELY_CONSOLIDATED_BY, IS_INTERNATIONAL_BRANCH_OF, IS_FUND-MANAGED_BY, IS_SUBFUND_OF, IS_FEEDER_TO) [primary page confirms L1/L2 files; relation names + CC0 license inferred, verify at gleif.org]. ISO 20022 (public repository; usage terms unverified), XBRL/IFRS/US-GAAP taxonomies (IFRS taxonomy has restrictive IFRS Foundation license [inferred]; us-gaap is free to use [inferred]) - do not ship; FIGI (OMG/Bloomberg, open license [inferred]).
Datasets: FiNER-139: 1.1M sentences, 139 XBRL tags, CC-BY-SA-4.0 [secondary]. FinRED: 6,767 instances, 29 relation types (from Wikidata-style, e.g. subsidiary, owned by, product or material produced, headquarters location, founded by, chairperson, CEO) [secondary count; list inferred]. REFinD: 29K instances, 22 relations, 8 entity pairs: PERSON-TITLE, PERSON-ORG, PERSON-UNIVERSITY, PERSON-GOV_AGENCY, ORG-GPE, ORG-DATE, ORG-ORG, ORG-MONEY [secondary]. FinQA/TAT-QA: show numeric facts with period + source (revenue, net income) [inferred]. FinDKG schema [not checked - gap].
Starter entities: LegalEntity(LEI), Person, Instrument/Security(ISIN/FIGI), Fund, Regulator, Exchange, Jurisdiction, Product, Event(corporate action), Report(filing), Rating, Metric(ReportedFigure as claim). Relations: ORG-[SUBSIDIARY_OF]->ORG (tv, share pct attr), ORG-[OWNS_STAKE_IN]->ORG (tv), PERSON-[OFFICER_OF {title}]->ORG (tv), PERSON-[DIRECTOR_OF]->ORG (tv), ORG-[ISSUED]->INSTRUMENT, ORG-[LISTED_ON]->EXCHANGE (tv), ORG-[REGULATED_BY]->REGULATOR (tv), ORG-[COUNTERPARTY_OF], ORG-[LENDS_TO]->ORG, ORG-[ACQUIRED]->ORG, ORG-[FILED]->REPORT, ORG-[HEADQUARTERED_IN]->PLACE (tv), FUND-[MANAGED_BY]->ORG (tv), INSTRUMENT-[RATED_BY]->RATING. Claim/event types: ReportedFigure(metric, value verbatim, period, unit), RatingAction, Acquisition, Default, Dividend, SanctionAction. Identifier for resolution: LEI > ISIN/FIGI > registration number + jurisdiction > normalised name. Not entities: amounts, ratios, dates, tickers (attribute).
IRIs: fibo-be-le-lei:LegalEntity, fibo-fnd-pas-fpas:... (verify exact IRIs before shipping), gleif L2 relationship types.
CQs: who is ultimate parent of X in 2024? which officers left in a period? which instruments does X have outstanding? what was reported revenue for FY and which doc? who regulates X? which entities hold >10% of Y over time? what rating changes occurred in last year?

#### 2 Legal / regulatory
Standards: Akoma Ntoso (OASIS LegalDocML; XML; license [inferred OASIS IPR, verify]), ELI (EU Publications Office; ontology based on FRBRoo: LegalResource, LegalExpression, Format; properties: is_about, based_on, cites, amends, repeals, in_force, date_document, jurisdiction [secondary snippet confirms FRBRoo basis; property list inferred]), LKIF Core (Amsterdam; ~Norm, Legal_Role, Legal_Action, Legal_Person, Obligation, Permission, Prohibition [inferred]), LegalRuleML (OASIS), FRBR work/expression/manifestation. FRO (Financial Regulation Ontology) [not verified].
Datasets: CUAD: 510 contracts, 13,000+ labels, 41 clause categories, CC BY 4.0 [primary]. ContractNLI Apache 2.0, 17 hypotheses [secondary]. MAUD CC BY 4.0 [secondary]. LEDGAR (SEC provisions, ~100 labels) license unverified.
Starter entities: LegalInstrument(Work), Provision(Article), Obligation, Permission, Prohibition, Party(Person/Org), Regulator, Jurisdiction, Concept(Defined term), Agreement, Case. Relations: PROVISION-[PART_OF]->INSTRUMENT, INSTRUMENT-[AMENDS|REPEALS|CITES|IMPLEMENTS|BASED_ON]->INSTRUMENT (dated), OBLIGATION-[IMPOSED_ON]->PARTY, OBLIGATION-[DERIVED_FROM]->PROVISION, PROVISION-[DEFINES]->CONCEPT, AGREEMENT-[HAS_PARTY]->PARTY, AGREEMENT-[GOVERNED_BY]->JURISDICTION, ORG-[SUBJECT_TO]->INSTRUMENT (tv), CASE-[INTERPRETS]->PROVISION. Time-varying: in_force, applies_from/to (legal validity vs our valid time). Claim types: Obligation (deontic modality, subject, action, condition, deadline), Exception, Penalty. Identifier: ELI/CELEX/ECLI/official citation. Not entities: dates, fines, article numbers (attribute).
CQs: which provisions impose obligations on X? what amended Y and when was it in force? which controls satisfy requirement R? what is the termination clause and notice period of agreement A? which regulators supervise X? which text version applied on date D?
License: write own definitions; use ELI/AKN/LKIF as IRI mapping hints only; do not bundle ontology files.

#### 3 Public sector
SEMIC Core Vocabularies (EU; CC BY 4.0, (c) European Union [primary Core Person repo]): Core Person, Core Business, Core Location, Core Public Organisation, Core Criterion and Core Evidence, CPSV-AP (public services). DCAT (W3C) for datasets. Small, designed for interoperability: good fit. Starter: PublicOrganisation, Person, Service, Agency, Legislation, Procedure, Location, Dataset, Programme, Event(decision), Role. Relations: ORG-[PROVIDES]->SERVICE, ORG-[PART_OF]->ORG (tv), SERVICE-[REQUIRES]->EVIDENCE/CRITERION, SERVICE-[BASED_ON]->LEGISLATION, ORG-[RESPONSIBLE_FOR]->PROGRAMME, PERSON-[HEADS]->ORG (tv), ORG-[LOCATED_AT]->LOCATION, DATASET-[PUBLISHED_BY]->ORG. Identifiers: official org code/tax ID, legislation ELI. CQs: which agency provides service S? what evidence is required? who heads agency A in 2025? which decrees established programme P?
Datasets: none found (gap).

#### 4 HR/skills
ESCO (EU Commission; CC BY 4.0 for EU-owned content, third-party parts may need permission [secondary]; occupations pillar, skills pillar 13,485 concepts [secondary], multilingual incl. Vietnamese? [unverified]). O*NET (USDOL; CC BY 4.0 [secondary]). schema.org JobPosting/Occupation/Person (CC BY-SA 3.0). HR Open Standards (license unverified). Starter: Person, Organization, Position/Role, Occupation, Skill, Qualification, Department, Place, Event(training), Employment (claim). Relations: PERSON-[EMPLOYED_AS]->POSITION (tv), POSITION-[IN]->DEPARTMENT/ORG, PERSON-[HAS_SKILL]->SKILL (observed time), POSITION-[REQUIRES_SKILL]->SKILL, PERSON-[HOLDS_QUALIFICATION]->QUAL, PERSON-[REPORTS_TO]->PERSON (tv), POSITION-[CLASSIFIED_AS]->OCCUPATION(ESCO URI), DEPT-[PART_OF]->ORG. Not entities: salary, headcount, dates. Datasets: skill-extraction sets (SkillSpan, etc.) not verified - gap.
CQs: who reports to X? which positions require skill S? who held position P in 2023? which people hold qualification Q?
Personal data caution [inferred]: people data = PII; pack should flag.

#### 5 Insurance
ACORD: membership/participation program required for standards access [secondary acord.org]; treat as proprietary; do not copy. No open ontology verified (gap). Own starter: Policy, Insured(Person/Org), Insurer, Broker, Coverage, Claim, Peril/Loss event, Risk/InsuredObject, Premium (attr), Endorsement, Reinsurance treaty. Relations: INSURER-[ISSUES]->POLICY, POLICY-[COVERS]->RISK, POLICY-[HAS_COVERAGE]->COVERAGE, POLICY-[HELD_BY]->INSURED, CLAIM-[UNDER]->POLICY, CLAIM-[ARISES_FROM]->LOSS_EVENT, BROKER-[PLACED]->POLICY, POLICY-[AMENDED_BY]->ENDORSEMENT (tv), TREATY-[REINSURES]->POLICY/PORTFOLIO, COVERAGE-[EXCLUDES]->PERIL. Time-varying: policy period, coverage, endorsement effect. CQs: what perils does policy P exclude? which claims were filed under P and status? who is broker of P? what was the limit on date D?

#### 6 Internal enterprise knowledge
Evidence: AMI corpus (CC BY 4.0 for signals/transcripts and some annotations; has dialogue acts, action items, decisions annotations [secondary]); QMSum MIT, 232 meetings, 1,808 query-summary pairs [secondary]; ICSI not checked. schema.org Event/Action (CC BY-SA). Own starter: Meeting, Decision, ActionItem, Person, Team, Project, Policy, Procedure(Step), Document, System, Risk, Topic. Relations: MEETING-[PRODUCED]->DECISION, DECISION-[SUPERSEDES]->DECISION (tv), ACTIONITEM-[ASSIGNED_TO]->PERSON, ACTIONITEM-[PART_OF]->PROJECT, ACTIONITEM-[DUE]=attr, POLICY-[APPLIES_TO]->TEAM/SYSTEM (tv), POLICY-[OWNED_BY]->PERSON/TEAM (tv), PROCEDURE-[IMPLEMENTS]->POLICY, PERSON-[ATTENDED]->MEETING, PROJECT-[OWNED_BY], DOCUMENT-[SUPERSEDES]->DOCUMENT (tv), RISK-[AFFECTS]->PROJECT, PERSON-[MEMBER_OF]->TEAM (tv). Claim types: Decision, Commitment, Status update. CQs: what was decided about X and when; which decisions were superseded; open action items for person P; who owns policy Q; which procedure implements policy R.

#### Vietnamese aside
VLSP 2016 NER: PER, ORG, LOC, MISC (flat) [secondary]. VLSP 2018 NER: PER, ORG, LOC with nested levels [secondary]. VLSP 2021 NER: 14 main types + 26 sub-types [secondary; list not retrieved]. VLSP 2020 RelEx: 4 relation categories over PER/ORG/LOC, 1,056 docs, 5,900 relation instances [secondary]; category names (commonly cited LOCATED, PART-WHOLE, PERSONAL-SOCIAL, AFFILIATION) not confirmed this session. Licenses of VLSP datasets: unverified (usually research-use registration).

#### Gaps
FinDKG, FRO, LegalRuleML, HR Open, ISO 20022 licenses, GLEIF CC0 on source (404), exact IRIs, ESCO language coverage, VLSP exact lists and licenses, GraphRAG/LightRAG defaults not verified from source this session.


## Set B

### Domain-pack grounding research, set B (2026-10-03)

Label key: [primary] = fetched this session from the owning source; [secondary] = search-result summary; [inferred] = model prior or my design, NOT verified this session. Verify [inferred] items before relying on them.

#### Summary table

| Domain | Anchor standard | License | Shippable (names/defs/IRIs)? | Starter size |
|---|---|---|---|---|
| Biomedical | Biolink Model (+ FHIR for clinical; BioRED for data) | Biolink Apache-2.0 [primary]; FHIR CC0 [primary]; SNOMED affiliate, UMLS license [secondary] | Biolink and FHIR yes. SNOMED/UMLS: no, IDs only as user-supplied literals | 12 ent / 16 rel |
| Scientific lit | SciERC types + OpenAlex/CiTO/ORKG | OpenAlex CC0, CiTO CC-BY 4.0, ORKG CC0 [inferred]; SciERC license unknown | Yes with attribution (verify) | 9 / 12 |
| News/events | ACE/ERE-style event types, SEM, Wikidata | ACE 2005 LDC proprietary [secondary]; Wikidata CC0 [inferred]; MAVEN license unverified | Write own type names; do not copy ACE guidelines text | 9 / 12 |
| Cyber | STIX 2.1 + ATT&CK + CASIE | STIX: OASIS non-assertion IPR [primary]; ATT&CK: royalty-free, must reproduce MITRE notice [primary] | Type names yes (interop); ATT&CK content needs notice | 12 / 16 |
| Enterprise IT/SWE | OpenTelemetry semconv + CycloneDX/SPDX | OTel Apache-2.0 [primary]; CycloneDX Apache-2.0 [secondary]; SPDX spec CC-BY-3.0, [secondary] | Yes with attribution | 12 / 16 |
| Product/support | schema.org Product/Offer/Review + GoodRelations | schema.org CC-BY-SA 3.0 [primary]; GoodRelations CC-BY 3.0 [inferred] | Share-alike risk: use as IRI mapping only, write own definitions | 10 / 13 |
| Manufacturing/supply chain | IOF Core, SAREF, Brick | IOF Core MIT [secondary]; SAREF/ETSI Forge BSD-3 [secondary]; Brick BSD-3 [secondary] | Yes with notices | 12 / 15 |

#### 1. Biomedical and healthcare

Standards
- Biolink Model: NCATS/Biolink consortium, github.com/biolink/biolink-model, Apache-2.0 [primary]. Roughly 300+ classes and 200+ predicates [inferred]; too big in full, but a clean top-level (Gene, Protein, Disease, ChemicalEntity/SmallMolecule, Drug, PhenotypicFeature, Pathway, Publication, ...) and predicates (treats, causes, interacts_with, biomarker_for, affects, subclass_of...) is a good source of IRIs (biolink:...).
- FHIR: HL7, CC0 spec [primary]; derivatives must not claim HL7 endorsement. Resources useful: Patient, Condition, MedicationStatement, Observation, Procedure, Encounter, Practitioner, Organization. Too clinical-record-shaped for free text, use as a mapping target only.
- SNOMED CT: SNOMED International affiliate license; free in member countries, but implementer use is outside HL7 agreement [primary FHIR page; secondary NLM]. UMLS: no-charge NLM license but sub-vocabularies carry their own terms [secondary]. Red flag: do not ship concept names, SNOMED IDs/definitions, or Semantic Network text in the SDK; store codes as user-supplied attributes.
- MeSH (NLM, public-domain-style terms) [inferred], Hetionet (CC0) [inferred], PrimeKG (MIT) [inferred], SPOKE [inferred]. Use only as inspiration for metagraph types.
Datasets
- BioRED (NCBI): 600 PubMed abstracts, entity types gene, disease, chemical, variant, species, cell line; 8 relation types (Association, Positive/Negative Correlation, Bind, Cotreatment, Comparison, Drug_Interaction, Conversion) [inferred; fetch failed]. Public NLM data.
- ChemProt (chemical-protein, 5 classes), DDI Corpus (drug-drug 4 types), MedMentions (UMLS-linked, CC0 [inferred]), n2c2/i2b2 (data use agreement required, not redistributable) [inferred].
Starter schema
- Entities: Disease, Gene, Protein, Chemical (incl. Drug), Variant, Organism, Phenotype (symptom/sign), Procedure, Anatomy, Pathway, Publication (trial/study), Organization.
- Relations: Chemical -[TREATS]-> Disease; Chemical -[CAUSES_ADVERSE_EFFECT]-> Phenotype; Chemical -[INTERACTS_WITH]-> Chemical|Gene|Protein; Gene -[ASSOCIATED_WITH]-> Disease; Variant -[VARIANT_OF]-> Gene; Variant -[ASSOCIATED_WITH]-> Disease|Phenotype; Gene -[ENCODES]-> Protein; Gene|Protein -[REGULATES]-> Gene|Protein; Protein -[PARTICIPATES_IN]-> Pathway; Disease -[HAS_SYMPTOM]-> Phenotype; Chemical|Procedure -[CONTRAINDICATED_FOR]-> Disease; Publication -[REPORTS]-> Claim; Organization -[SPONSORS]-> Publication; Chemical -[INHIBITS|ACTIVATES]-> Protein; Disease -[SUBCLASS_OF]-> Disease; Organism -[HOST_OF]-> Disease.
- Identifiers: gene symbol + organism (or HGNC/NCBI Gene ID), PubMed ID/DOI, drug INN name or ATC/RxNorm code, variant HGVS string, user-supplied SNOMED/ICD codes as attributes.
- Time-varying: approval status, guideline recommendation, treatment relations in a patient record, trial phase, sponsor roles.
- Claims: Finding (with direction, effect size, population, p-value verbatim), Recommendation, Contraindication.
- Not entities: dosage, lab values, dates, sample size, p-values, species strain (attributes).
- Competency questions: which drugs are reported to treat X; what adverse effects are linked to drug Y in which papers; which genes/variants are associated with disease Z; which interactions exist between A and B; which guideline recommendations changed since a date; which studies report a conflicting result on claim C.
Licensing for us: ship Biolink-aligned names (Apache-2.0; include NOTICE/attribution). Write our own definitions; no SNOMED/UMLS text.

#### 2. Scientific and technical literature

- SciERC (UW, Luan et al., 2018): 500 abstracts, 6 entity types (Task, Method, Metric, Material, OtherScientificTerm, Generic), 7 relations (Compare, Part-of, Conjunction, Evaluate-for, Feature-of, Used-for, Hyponym-of) [secondary, search summary of arXiv 1808.09602]. License not found; check before copying beyond type names.
- SciREX (AllenAI): document-level, Dataset/Method/Metric/Task, n-ary result tuples [secondary]. GitHub allenai/SciREX; license not verified.
- OpenAlex entities: Work, Author, Institution, Source, Topic, Funder, Publisher; CC0 data [inferred]. ORKG: research contributions, comparisons, CC0 data [inferred]. CiTO (SPAR): citation functions (cites, usesMethodIn, extends, disagreesWith, supports), CC-BY 4.0 [inferred]. CS-KG [inferred].
Starter: Entities: Paper, Author, Institution, Venue, Task, Method, Dataset, Metric, Result (n-ary node), Funder. Relations: Author -[AUTHORED]-> Paper; Author -[AFFILIATED_WITH]-> Institution (time-varying); Paper -[PUBLISHED_IN]-> Venue; Paper -[CITES]-> Paper (with CiTO function attribute: uses, extends, contradicts, supports); Paper -[PROPOSES]-> Method; Method -[USED_FOR]-> Task; Method -[EVALUATED_ON]-> Dataset; Result -[ACHIEVED_BY]-> Method; Result -[ON_DATASET]-> Dataset; Result -[MEASURED_BY]-> Metric; Method -[IMPROVES_ON]-> Method; Method -[PART_OF]-> Method; Paper -[FUNDED_BY]-> Funder; Dataset -[CREATED_BY]-> Paper.
Identifier: DOI (fallback arXiv ID), ORCID, ROR. Not entities: score values (attributes of Result), year, page numbers. Claims: Finding, Limitation. Time: affiliations, Result is dated by publication.
CQs: which methods are evaluated on dataset D and with what metric values; who cites paper P to contradict it; what is the state of the art on task T as of date; which authors moved institutions; which papers share datasets.

#### 3. News, geopolitics and events

- ACE 2005 (LDC2006T06): LDC proprietary, paid [secondary]; 7 entity types (PER, ORG, GPE, LOC, FAC, WEA, VEH), 8 event types/33 subtypes (Life, Movement, Transaction, Business, Conflict, Contact, Personnel, Justice) [secondary/inferred]. ERE/Rich ERE also LDC [inferred]. MAVEN: 4,480 Wikipedia docs, 118,732 mentions, 168 event types [secondary]; license not verified. CAMEO: 20 root codes, ~300 types, used by GDELT/ICEWS [inferred]. SEM (Simple Event Model): actor, place, time, event [inferred].
- Fit: ACE 8 top-level types are an ideal compact event inventory; 168 MAVEN types too many for a default.
Starter: Entities: Person, Organization, GovernmentBody (or fold into Organization), Location (GPE), Facility, Event, Law/Policy, Product/Weapon, Document/Statement. Relations: Person -[MEMBER_OF]-> Organization (time-varying); Person -[HOLDS_ROLE_AT]-> Organization (time-varying, role attribute); Organization -[LOCATED_IN]-> Location; Event -[HAS_PARTICIPANT]-> Person|Organization (role attribute: agent, target, victim); Event -[OCCURRED_AT]-> Location; Event -[CAUSED]-> Event; Event -[PART_OF]-> Event; Organization -[ALLIED_WITH|OPPOSES]-> Organization (time-varying); Organization -[SANCTIONS]-> Organization; Person|Organization -[STATED]-> Statement; Statement -[ABOUT]-> Entity|Event; Organization -[PARENT_OF]-> Organization.
Event types (attribute, own names): Conflict, Contact/Diplomacy, Transaction, Movement, Justice, Personnel, Life, Business, Policy. Identifier: Wikidata QID (user optional) + normalized name + country. Not entities: dates, casualty counts, amounts. Time: all roles and alliances; events have occurrence time vs report time.
CQs: who participated in event E and in what role; which events led to E; who held office X in a year; which statements did actor A make about topic T; what events occurred in location L between dates.
Licensing: write own event type names; no ACE guideline text; CAMEO codes are free to cite but unverified here.

#### 4. Cybersecurity

- STIX 2.1 (OASIS CTI TC): Copyright OASIS 2022, Non-Assertion IPR mode, portions US Government [primary]. SDOs: Attack Pattern, Campaign, Course of Action, Grouping, Identity, Incident, Indicator, Infrastructure, Intrusion Set, Location, Malware, Malware Analysis, Note, Observed Data, Opinion, Report, Threat Actor, Tool, Vulnerability [primary]. SROs: Relationship, Sighting [primary]. Relationship types include uses, targets, indicates, attributed-to, mitigates, delivers, exploits-like variants [primary partial].
- ATT&CK: royalty-free non-exclusive license for research, development and commercial use; must reproduce the MITRE copyright notice and license text [primary]. Technique IDs (T####) are good identifiers.
- CASIE: 1,000 English news articles, 5 event types (Databreach, Phishing, Ransom, Discover, Patch), 20 argument roles [secondary]. UCO, CVE/CWE/CPE: not verified [inferred]; CVE terms of use allow free use with attribution to MITRE [inferred].
Starter: Entities: ThreatActor, IntrusionSet (campaign group), Campaign, Malware, Tool, AttackPattern (technique), Vulnerability (CVE), Software (CPE-like product), Organization (victim/vendor), Indicator (IOC literal), Infrastructure, Incident, Location. Relations: ThreatActor -[USES]-> Malware|Tool|AttackPattern; Campaign -[ATTRIBUTED_TO]-> ThreatActor; Campaign|ThreatActor -[TARGETS]-> Organization|Location|Software; Malware -[EXPLOITS]-> Vulnerability; Vulnerability -[AFFECTS]-> Software; Indicator -[INDICATES]-> Malware|Campaign|ThreatActor; Course of action -[MITIGATES]-> AttackPattern|Vulnerability (fold CourseOfAction as entity if needed); Malware -[COMMUNICATES_WITH]-> Infrastructure; Incident -[AFFECTED]-> Organization; Software -[PATCHED_BY]-> Patch (attribute-level) ; Malware -[VARIANT_OF]-> Malware; Organization -[VENDOR_OF]-> Software.
Identifiers: CVE ID, ATT&CK ID, malware name + aliases, hash for file IOCs. Not entities: IP/domain/hash as literals attached to Indicator. Time-varying: attribution, targeting, patch status, CVSS. Claims: Attribution claim (confidence verbatim), Vulnerability disclosure, Breach event.
CQs: which actors use technique T; which CVEs does malware M exploit; which organizations were targeted by campaign C in a period; which software versions are affected and patched; which indicators are tied to actor A; which sources attribute campaign C and with what confidence.

#### 5. Enterprise IT and software engineering/operations

- OpenTelemetry semantic conventions: Apache-2.0 [primary]; resource attributes service.name, service.version, host.name, k8s.* (cluster, namespace, pod, deployment), cloud.*, deployment.environment [inferred]. CycloneDX (ECMA-424, Apache-2.0 [secondary]): component, service, dependency, vulnerability, license. SPDX 3.0: CC-BY-3.0 spec [secondary], with the SPDX license list IDs [inferred]. CSDM/ITIL: ServiceNow CSDM is proprietary documentation, so write our own CI classes [inferred]. CodeOntology, incident postmortem schemas: not verified.
Starter: Entities: Service, Application, Host (node), Container/Pod, Database, Component (library/package), Repository, Team, Person, Incident, Change (deploy/release), Alert, Runbook/Document, License, Environment. (trim to 15.) Relations: Service -[DEPENDS_ON]-> Service|Database|Component; Service -[RUNS_ON]-> Host|Pod; Service -[OWNED_BY]-> Team; Person -[MEMBER_OF]-> Team (time-varying); Change -[DEPLOYED_TO]-> Environment; Change -[MODIFIES]-> Service; Incident -[AFFECTS]-> Service; Incident -[CAUSED_BY]-> Change|Component|Incident; Incident -[RESOLVED_BY]-> Change|Runbook; Alert -[TRIGGERED_FOR]-> Service; Component -[LICENSED_UNDER]-> License; Component -[HAS_VULNERABILITY]-> (CVE; cross-pack link); Repository -[CONTAINS]-> Component|Service; Runbook -[DOCUMENTS]-> Service.
Identifiers: service.name + environment, PURL for components, repo URL, incident ID, SPDX license ID. Not entities: versions, hostnames if ephemeral (attribute), severity, timestamps. Time-varying: dependencies, ownership, deployments, runs-on. Claims: Root cause statement, Mitigation, Action item.
CQs: what depends on service S; who owns S now and who owned it a year ago; which incidents followed change C; which components under license L are used by S; what runbook resolved prior incidents of type T; which services are affected by vulnerable component X.

#### 6. Product, e-commerce, customer support

- schema.org (CC-BY-SA 3.0 [primary]): Product, Offer, Review, Organization, Brand, AggregateRating, Rating. Share-alike: shipping verbatim schema.org text may impose SA on that text; red flag for a permissive SDK. Mitigation: map to schema.org IRIs (facts, not expression) and write our own definitions [inferred; get legal view]. GoodRelations (CC-BY 3.0 [inferred]); GS1 Web Vocabulary (GS1 license, not verified; GTIN is a standard identifier). Support KG (LinkedIn, arXiv 2404.17723) and product-manual KGs: not fetched this session; treat as unverified.
Starter: Entities: Product, ProductVariant (SKU), Brand, Organization (seller/manufacturer), Component/Part, Feature, Issue (symptom/problem), Resolution (fix/procedure), Ticket, Customer (role; privacy care), Review, Offer, Document (manual/FAQ), Category. Relations: Product -[MADE_BY]-> Brand; Brand -[OWNED_BY]-> Organization; Product -[HAS_VARIANT]-> ProductVariant; Product -[HAS_FEATURE]-> Feature; Product -[HAS_PART]-> Part; Product -[COMPATIBLE_WITH]-> Product; Product -[REPLACES]-> Product; Issue -[AFFECTS]-> Product|Part; Issue -[RESOLVED_BY]-> Resolution; Issue -[CAUSED_BY]-> Issue|Part; Ticket -[REPORTS]-> Issue; Ticket -[RESOLVED_WITH]-> Resolution; Review -[ABOUT]-> Product (with sentiment, rating attributes); Offer -[OFFERS]-> ProductVariant (price valid_from/to); Document -[DOCUMENTS]-> Product|Resolution.
Identifier: GTIN/SKU/MPN, ticket ID. Not entities: price, rating, color, dimensions (attributes). Time-varying: price offers, compatibility, product status (discontinued), brand ownership. Claims: Review opinion, Known-issue statement, Warranty term.
CQs: what fixes exist for issue I on product P; which products are compatible with X; what was the price of SKU S in a month; which issues recur across tickets; which feature do reviews criticize most; which manual section covers procedure R.

#### 7. Manufacturing, engineering, supply chain

- IOF Core: MIT, copyright Open Applications Group; current repo iofoundry/ontology (core/); builds on BFO 2020; releases through 202603 [secondary]. SAREF (ETSI): ETSI Forge BSD-3-Clause unless noted [secondary]. Brick: BSD-3 [secondary]; RealEstateCore, ISO 15926, IEC CIM, SAREF4INMA: not verified. Heavy BFO-based formalism is too abstract for LLM extraction; use class names only.
Starter: Entities: Organization (supplier/customer/manufacturer), Facility (plant/warehouse), Equipment (machine/asset), Product (item/material), Part/Component, Process (operation/work order), Specification/Standard, Batch/Lot, Shipment, Contract/PurchaseOrder, Sensor/Measurement point, Location, Failure/Defect, Document. Relations: Organization -[SUPPLIES]-> Organization (time-varying, with product attribute); Organization -[OPERATES]-> Facility; Facility -[LOCATED_IN]-> Location; Facility -[HOUSES]-> Equipment; Equipment -[PRODUCES]-> Product; Product -[COMPOSED_OF]-> Part (BOM); Process -[USES]-> Equipment|Material; Process -[PRODUCES]-> Batch; Batch -[SHIPPED_IN]-> Shipment; Shipment -[FROM|TO]-> Facility; PurchaseOrder -[ORDERS]-> Product; Equipment -[SUFFERED]-> Failure; Failure -[CAUSED_BY]-> Part|Process; Product -[CONFORMS_TO]-> Specification; Sensor -[MEASURES]-> Equipment.
Identifier: GLN/DUNS/LEI for orgs, serial/asset tag, part number, batch ID. Not entities: quantities, tolerances, dates. Time-varying: supplier relationships, equipment location, certification, BOM revision.
CQs: who supplies part P and which plants use it; what is affected if supplier S fails; which batches used part lot L; what failures recurred on equipment type E; which standard governs product Q; BOM of product X as of date.

#### Licensing red flags
1. SNOMED CT and UMLS: affiliate/NLM license, FHIR notes SNOMED is outside its CC0 grant. Do not ship.
2. n2c2/i2b2 clinical datasets: DUA, no redistribution [inferred]. ACE 2005/ERE: LDC paid [secondary].
3. schema.org CC-BY-SA 3.0 share-alike [primary]: avoid copying text.
4. ATT&CK: must carry MITRE notice [primary]. STIX/OASIS: non-assertion IPR, copyright retained [primary], so name interop is fine, copying spec prose is not.
5. SPDX spec CC-BY-3.0 and Biolink/OTel Apache-2.0: attribution/NOTICE duties.
6. SciERC, SciREX, MAVEN licenses unverified.

#### Gaps
Not verified this session: Hetionet/PrimeKG/SPOKE, CS-KG, ORKG, OpenAlex, CiTO, GoodRelations, GS1, UCO, CVE/CWE, CodeOntology, ISO 15926, SAREF4INMA, RealEstateCore, IEC CIM, CAMEO/GDELT/ICEWS terms, the LinkedIn support-KG paper, BioRED details (fetch 404), per-dataset licenses. Starter relation lists are my design [inferred], and are not tested against annotated text. Mapping IRIs per type were not individually checked.
