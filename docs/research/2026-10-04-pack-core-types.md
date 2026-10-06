# Cross-domain types for the core pack

> **Snapshot, 2026-10-04 — not maintained.** Academic lane; low-to-medium confidence, several gaps listed at the end. The maintained,
> re-verified summary is in [domain-schemas.md](../reference/domain-schemas.md); where they differ, the maintained doc
> wins. Local paths were removed before publishing.
>
> **Errata and later resolutions:**
> - Few-NERD: data CC BY-SA 4.0, code Apache-2.0.
> - PhoNER_COVID19: 10 types confirmed; research and education use only, no redistribution.
>   The sentence count and error analysis were not re-checked.
> - arXiv 2510.14271 is "Less is More: Denoising Knowledge Graphs For Retrieval Augmented
>   Generation" (DEG-RAG); the 40 % pruning result is confirmed.
> - MS GraphRAG's claim extraction is off by default, confirmed in its configuration docs.

## r4 — Core entity/relation types for TenetRAG `core`: literature report
*2026-10-04 · ~14 sources actually opened · confidence: LOW-MEDIUM. Q1 (partly), Q2 (partly), Q7 are evidenced. Q3, Q4, Q6, Q8 are mostly gaps. Labels: [primary] = read on the owning source this session; [secondary] = search snippet or third-party summary; [inferred] = my reasoning, not verified.*

### 1. Summary
- Person / Organization / Location are the only types that every inventory I read shares. Few-NERD says "most of the widely used NER datasets" have 4-18 coarse types, and its 8 coarse types are Person, Location, Organization, Art, Building, Product, Event, Miscellaneous [primary, S1]. Vietnamese NER sets (VLSP 2016/2018, PhoNER) also centre on PER/ORG/LOC [primary, S2].
- Catch-all `Miscellaneous` is a standard coarse type in Few-NERD [primary] and `MISC` in VLSP 2016 [secondary]. I found no direct measurement of hub-node or precision damage from a `Concept`-style type. The evidence on KG noise is indirect (generic nodes, duplicates) [secondary, S9].
- MS GraphRAG's prompt examples use ORGANIZATION, PERSON, GEO, EVENT and take `{entity_types}` as a parameter [primary, S4]. LightRAG's older prompt default is organization, person, geo, event, category [secondary, S6]. Newer LightRAG configs list Person, Creature, Organization, Location, Event, Concept, Method, Content, Data, Artifact, NaturalObject [secondary, S6]. Neither default was confirmed against current code.
- W3C ORG models a person-in-role as an n-ary `Membership` (agent + organization + role, with `memberDuring`) and a separate `Post` that exists without an occupant [primary, S7]. Wikidata P39 "position held" has an office item as object and qualifiers start/end time, replaces/replaced by, employer and others [primary, S8].
- MS GraphRAG ships claim extraction off by default: "Off by default, because claim prompts really need user tuning" [primary, S5]. This supports `Statement` off by default as an engineering precedent. It is not a measurement of cost or noise.
- Event type count: MAVEN (207 types in the version cited by one snippet) vs ACE05 (33 types). Older models lose about 10-14 F1 points going from ACE to MAVEN [secondary, S10]. I found no controlled study of LLM accuracy against schema size.
- Pruning about 40% of entities and relations from LLM-built KGs left four GraphRAG variants better on QA [primary abstract, S9]. This suggests extra low-value nodes hurt, and is the nearest evidence for the literal-node question. It does not isolate literals.
- gist is CC BY 4.0 and names "person, organization, and agreement" as foundational everyday concepts [primary, S11]. I could not confirm a formal top-class list.
- Vietnamese: VLSP 2021 has 14 main types and 26 subtypes [primary, S3]. I could not read the type list from the paper. A third-party app lists 41 labels that appear to be the VLSP 2021 set [secondary, S12].

### 2. Sources
| # | Source | Status |
|---|---|---|
| S1 | Ding et al. 2021, Few-NERD, ACL 2021 — https://arxiv.org/abs/2105.07464 | read PDF p1-4 |
| S2 | Truong, Dao, Nguyen 2021, COVID-19 NER for Vietnamese (PhoNER_COVID19), NAACL 2021 — https://arxiv.org/abs/2104.03879 | read PDF p1-4 |
| S3 | VLSP 2021 NER overview, JCSCE (VNU) — https://jcsce.vnu.edu.vn/index.php/jcsce/article/view/362 | abstract only |
| S4 | MS GraphRAG docs + prompt — https://microsoft.github.io/graphrag/index/default_dataflow/ ; https://github.com/microsoft/graphrag/blob/main/packages/graphrag/graphrag/prompts/index/extract_graph.py | read |
| S5 | MS GraphRAG config — https://microsoft.github.io/graphrag/config/yaml/ | read |
| S6 | LightRAG defaults, via search — https://huggingface.co/spaces/retopara/ragflow/blame/cd19d72d5d1be9c11bf4ff38e7e51d406fa3925c/graphrag/light/graph_prompt.py and https://github.com/HKUDS/LightRAG | secondary; README had no list |
| S7 | W3C Organization Ontology — https://www.w3.org/TR/vocab-org/ | read |
| S8 | Wikidata P39 — https://www.wikidata.org/wiki/Property:P39 | read |
| S9 | "Less is More: Denoising KGs for RAG" (Deg-Rag), arXiv 2510.14271 — https://arxiv.org/html/2510.14271v1 | read; preprint |
| S10 | MAVEN / ChatGPT event-extraction snippets — https://arxiv.org/pdf/2410.09418 , https://arxiv.org/abs/2303.03836 | secondary; S10b read: https://arxiv.org/html/2410.09418v2 |
| S11 | gist — https://www.semanticarts.com/gist/ | read |
| S12 | VLSP 2021 label list, third-party app — https://huggingface.co/spaces/Linhz/ViMNer/blob/db296e29b41b0c97353739fc9d4b48d2484b8672/Model/NER/app_NER.py | secondary |
| S13 | VLSP 2018 nested NER, Vietnamese NER sets — https://arxiv.org/pdf/1803.08463 | snippet only |
| S14 | Vaucher et al. 2021, Quotebank, WSDM — https://zenodo.org/records/4277311 | snippet only |
| S15 | VLSP 2020 RelEx overview — https://aclanthology.org/2020.vlsp-1.17 | metadata only |
| S16 | UniversalNER, arXiv 2308.03279 — https://arxiv.org/abs/2308.03279 | abstract only |
| S17 | IFLA LRM / LRMoo — https://isko.org/cyclo/lrm | snippet only |

### 3. Findings per question

#### Q1. Coarse types and catch-alls
- OntoNotes has 18 types, 7 of them value types. CoNLL-03 has 4 types. WNUT'17 has 6 [primary, S1]. Few-NERD deliberately excludes value types (Cardinal, Day, Percent) and keeps only named entities [primary, S1]. This matches our "money/date/percentage are attributes" rule.
- Few-NERD merged Country/Province/City into one `GPE` type because they are "difficult to distinguish only based on context" [primary, S1]. This supports one `Place` type with a kind enum.
- Few-NERD added `Person-Scholar` because annotators found many person mentions whose meaning was occupation-like [primary, S1]. This shows that role-like types leak into Person. It also supports "fine distinctions are enum values".
- Few-NERD's own example shows a name flipping type by context: "London" is Art-Music, not Location [primary, S1]. Any type set will see this for Work vs Place vs Organization.
- PhoNER: the best model's largest error group is confusion between LOCATION and ORGANIZATION. Of 353 errors on validation, 69 had the right span but the wrong label, largely for that reason [primary, S2]. Org vs Place ambiguity is real in Vietnamese news.
- Catch-alls: `Miscellaneous` exists in Few-NERD and VLSP 2016 [primary/secondary]. I found no paper that measures its precision or hub effect.
- Indirect evidence from the Deg-Rag work: GraphRAG and LightRAG leave many duplicate entity variants (morphology, casing, multilingual, abbreviation) and merge by string matching only [primary abstract/body, S9]. Removing 40% of entities and relations improved four graph-RAG approaches [primary, S9, preprint, single-paper]. Search snippets also say that frequently mentioned, non-critical entities such as courts and juries inflate the graph [secondary, S9 search].
- [inferred] A `Concept` type with an open definition will act as the hub-prone catch-all, because LLMs put every abstract noun into it. Keep it only with a strict gate: a defined term, introduced by a `DEFINES` relation or a glossary-style definition, or named by a domain pack. Not "any abstract noun". Allow it at index time only when the item has a definition span as evidence.
- UniversalNER shows LLM-distilled open-type NER handles tens of thousands of types zero-shot and beats ChatGPT by 7-9 F1 on 43 datasets [primary abstract, S16]. It does not say which coarse types are most reliable. I did not read the per-type tables.
- Not researched: Wikidata and schema.org top classes, GLiNER, ACE, CoNLL type lists beyond Few-NERD's description.

#### Q2. Person / role / organization
- W3C ORG argues for an explicit n-ary `Membership` because it can be annotated with duration, salary, contract and so on [primary, S7]. `Post` exists independently of who fills it and is useful for structure before assignments [primary, S7].
- Wikidata P39: object is an office item. Qualifiers cover start/end/point in time, replaces/replaced by, employer, jurisdiction. The page says to use a specific office item when one exists or its creation is justified, and distinguishes P39 from P106 occupation [primary, S8].
- For "who held position X at T", a successor-aware office (Post) node wins: one lookup by office and date. A title string on an edge needs fuzzy matching on `title` text. That matters more in Vietnamese, where the same office has several surface forms [inferred].
- For LLM extraction a flat edge with an attribute is simpler: one output record per mention. A Post node needs a canonical post to link to, and the LLM often cannot resolve it from one chunk [inferred]. I found no paper that compares the two on extraction accuracy [gap].
- [inferred] Proposal: keep `HOLDS_POSITION` as a relation with `title` (verbatim) plus an optional `position` key (normalized text), interval time, and an optional `of` endpoint (the Organization). Let the engine or domain pack promote repeated `(org, normalized position)` pairs to a `Post` entity later. Do not add `Post` to core now.

#### Q3. Events
- ACE05 has 33 event types, GENEVA 115, RAMS 139 [primary, S10b]. MAVEN has 117,200 event mentions and 207 types (snippet figure; the original paper says 168, so check the version) [secondary, S10; note the discrepancy with your brief's 168].
- Older supervised models drop about 10 F1 going from ACE05 to MAVEN: DMCNN 69.1 to 59.0, MOGANED 75.7 to 61.7 [secondary, S10]. Scale and type count are confounded.
- Re-evaluating with semantic matching raises LLM event-argument F1 by over 51.92% and trigger-detection F1 by over 30.74%, so exact-match scores understate LLMs. The most frequent failure mode is WrongType: the span is right but the type is wrong [primary, S10b]. That paper does not link errors to type count.
- A snippet says ChatGPT reaches about 51% of a supervised model's performance on complex scenarios [secondary, S10]. I did not verify it.
- Not found: CAMEO, EventKG, controlled scaling of types, a formal event/relation boundary. [inferred] Since WrongType dominates, a small coarse `event_type` enum plus verbatim trigger text should cost less than many types. A rule of thumb for the boundary: a dated happening with 2+ participants or an independent time/place is an Event. A durable state between two entities is a relation.

#### Q4. Statements and quotations
- GraphRAG ships claim extraction off by default because "claim prompts really need user tuning" [primary, S5]. Docs say claim extraction needs prompt tuning to be useful [primary, S4].
- Quotebank: 235M speaker-attributed quotations from 196M English news articles, extracted with Quobert, a distantly supervised framework [secondary, S14]. PARC3 annotates source, cue and content and sits on the Penn Treebank, which is not free [secondary]. A French set, FRACAS, exists (arXiv 2309.10604) [secondary].
- Cost and noise of extract-all-statements: no measured figure found. [inferred] The cost is one more extraction pass and it multiplies nodes. Default off, enabled by a domain pack, matches the GraphRAG precedent.

#### Q5. Works and documents
- LRM/LRMoo have Work, Expression, Manifestation, Item [secondary, S17]. LRM is the consolidation of FRBR, FRAD and FRSAD [secondary].
- No evidence found on whether a generic `Work` helps GraphRAG or how often it is extracted correctly. [inferred] A single `Work` (no W/E/M split) is enough. Separate it from the engine `Document` by identity: `Document` is an indexed source file; `Work` is anything the text mentions. A `Work` may link to a `Document` via an optional `indexed_as` edge when the cited work is also in the corpus. Few-NERD's `Art` coarse type (Music, Film, Written art and so on) shows that cited works recur in open NER [primary, S1, Figure 1].

#### Q6. Agreement
- gist lists "person, organization, and agreement" as foundational concepts on its homepage [primary, S11]. I did not confirm gist's formal class hierarchy.
- [inferred] Agreement is cross-domain, but a contract is also a `Work`. Prefer a `Work` kind enum value (`contract`) plus a `PARTY_TO` relation over a new top type, unless the pack needs obligations as n-ary claims. No extraction-accuracy evidence found.

#### Q7. Vietnamese inventories
- VLSP 2016: PER, ORG, LOC, MISC [secondary, S13]. VLSP 2018: nested entities in three levels (level-1 contains no entity; level-2 contains only level-1 entities; level-3 deeper), with the same type family [secondary, S13]. A snippet from the 2021 overview says 2016 and 2018 published "only three main entity categories: person, organization and location" [secondary]. The two snippets disagree on whether MISC is in the set, and I did not resolve this.
- VLSP 2021: 14 main types and 26 sub-entity types [primary abstract, S3]. A third-party app lists these labels [secondary, S12]: PERSON, PERSONTYPE; LOCATION (GPE, GEO, STRUC); ORGANIZATION (MED, SPORTS, STOCK); EVENT (CUL, GAMESHOW, SPORT, NATURAL); PRODUCT (COM, LEGAL, AWARD); SKILL; ADDRESS; IP; EMAIL; PHONENUMBER; URL; MISCELLANEOUS; DATETIME (DATE, TIME, DATERANGE, TIMERANGE, DURATION, SET); QUANTITY (NUM, PER, DIM, CUR, TEM, AGE, ORD). That is 15 top-level labels including PERSONTYPE. A sub-list of about 26 exists inside this set, but I did not verify it against the paper.
- PhoNER_COVID19: 10 types: PATIENT_ID, PERSON_NAME, AGE, GENDER, OCCUPATION, LOCATION, ORGANIZATION, SYMPTOM&DISEASE, TRANSPORTATION, DATE. 10,027 sentences, 34,984 entities, no nested entities [primary, S2]. Even the 2021 sets keep date/quantity as entity types, so literals-as-nodes is a dataset choice, not a necessity.
- Relation labels: VLSP 2020 RelEx has four non-overlapping relation categories, 1,056 documents and 5,900 instances [secondary, S15]. I could not read the category names or the license.

#### Q8. Literals as nodes
- Few-NERD excludes value types on purpose [primary, S1]. No study isolates "numbers/dates as nodes hurt GraphRAG". The Deg-Rag pruning result is the nearest evidence [primary, S9]. [inferred] Keeping literals as attributes with verbatim text, time and source is safe.

### 4. Proposed `core` changes
1. **Keep `Concept`, but gate it.** Require a definition span or a pack-defined list; add it to the not-an-entity guidance: "no bare abstract nouns". Reason: catch-all noise and duplicates in GraphRAG-style graphs [S9, partly inferred].
2. **`Place` gets a `kind` enum** (country, region, city, site, other) instead of subtypes. Source: Few-NERD GPE merge [S1].
3. **Add an Org/Place disambiguation line to the extraction guidance:** institutions named by city are Organization; the same name used as a location is Place. Source: PhoNER LOC/ORG errors [S2].
4. **Keep `HOLDS_POSITION` as a relation** with verbatim `title`, an optional normalized `position`, and interval time. Do not add `Post` to core. Source: S7, S8, with the extraction-cost argument [inferred].
5. **Keep a single `Event` with `event_type` enum** (small, pack-extensible) and a verbatim trigger. Source: WrongType finding [S10b]; the rest is [inferred].
6. **Ship `Statement` as off by default,** pack-enabled. Source: GraphRAG claims default off [S5].
7. **Add a `kind` enum to `Work`** (law, contract, report, publication, other). Do not add `Agreement` or an FRBR split. Source: S17, S11, [inferred].
8. **Keep money/date/percentage/number/duration out of entities,** and add `quantity` and `address-like` identifiers (URL, email, phone) to the not-an-entity list. Reason: Few-NERD excludes value types [S1]; VLSP 2021 has these as types, so packs may need them as attributes.
9. **Add `Product` kind enum (product, service)** and leave `Product` otherwise as is. Source: Few-NERD Product [S1].

### 5. Cross-domain competency questions (all [inferred])
1. Who held position X at date T, and who replaced them?
2. Which organizations is person P a member of, and over what period?
3. Which organization issued work W, and what term does W define?
4. Where is organization O located, and what is it part of?
5. What events involved organization O between T1 and T2, and what do the sources say?
6. Which works mention concept C, and how do they define it?
7. What changed about entity E between two documents (dated facts and their evidence)?
8. (Statement pack enabled) What did speaker S say about topic X, and in which document?

### 6. Licenses (only what I confirmed)
- gist: CC BY 4.0 [primary, S11].
- PhoNER_COVID19: released "for research or educational purposes" per the paper [primary, S2]. The GitHub license file was not read.
- Few-NERD: paper is on arXiv under the arXiv non-exclusive license; the dataset license was not confirmed. [inferred] I recall CC BY-SA 4.0, unverified.
- PARC3: built on Penn Treebank, "not freely available" [secondary, S14 search].
- Quotebank: on Zenodo (doi 10.5281/zenodo.4277311); the license was not read.
- OntoNotes 5.0 and ACE: LDC; not checked.
- VLSP 2016/2018/2021 and RelEx, UniversalNER, MAVEN, CoNLL-2003: not verified.

### 7. Gaps
- Not searched or not read: Wikidata and schema.org top classes; GLiNER; ACE/OntoNotes type lists beyond Few-NERD's description; MAVEN primary paper; CAMEO; EventKG; PARC3 and quote-extraction methods in depth; FRBR in KG extraction; Agreement in any KG; any literal-as-node ablation.
- No source compares Post-node and edge-attribute extraction for LLMs.
- No measurement of Concept/Misc hub nodes.
- VLSP 2021 type list is unverified against the paper. PDFs of the VLSP 2021 overview and RelEx were not opened.
- The MAVEN type count differs between sources (168 in your brief, 207 in a snippet); check the paper.
- Preprints used: S9 (Deg-Rag). Few-NERD (ACL 2021) and PhoNER (NAACL 2021) are peer-reviewed per my recall, not verified this session.
