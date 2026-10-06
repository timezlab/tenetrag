# Graph schema design — what engines, standards and papers show

**Verified:** 2026-10-03. Engine features were read in source at pinned
tags. Paper figures were checked against abstracts or paper HTML by a
fact-check lane, not against every table, so re-check a figure before
quoting it. Licenses were read on the owning site (a model summary of the
page, not byte-exact). Not legal advice. The design that uses these facts is
[domain-packs.md](../product/domain-packs.md) and
[ADR 0007](../decisions/0007-define-the-graph-schema-as-layered-domain-packs.md).

Raw lane reports (snapshots, not maintained):
[engine customization](../research/2026-10-03-schema-engine-customization.md),
[papers](../research/2026-10-03-schema-papers.md),
[practice](../research/2026-10-03-schema-practice.md),
[domain standards](../research/2026-10-03-schema-domain-standards.md),
[meta-model](../research/2026-10-03-schema-metamodel.md),
[fact-checks](../research/2026-10-03-schema-factchecks.md).

Domain evidence for the v1 packs (finance, banking, enterprise documents,
cross-domain types) is in [domain-schemas.md](domain-schemas.md).

Labels: **[peer-reviewed]** · **[preprint]** · **[vendor]** (written by the
company selling it) · **[source]** read in code · **[inferred]** our
reasoning.

## What engines offer

| Engine (pin) | How types are defined and enforced | Beyond the prompt | Schema assist |
|---|---|---|---|
| MS GraphRAG v3.2.0 | `entity_types` list in config, injected into the prompt; off-schema types kept | type is half the merge key | `prompt-tune` drafts types and prompts from samples |
| LightRAG v1.5.7 | free-text type guidance, `Other` fallback | merge keeps the most common type | — |
| LlamaIndex v0.14.25 `SchemaLLMPathExtractor` | literal types, `strict=True` by default; triples checked against `kg_validation_schema` | Pydantic validation; drops are silent | — |
| neo4j-graphrag 1.22.0 | `GraphSchema` with node types, relationship types, patterns, typed properties, key/unique/existence constraints | `GraphPruning` returns each dropped item with a reason (`NOT_IN_SCHEMA`, `INVALID_PATTERN`, `MISSING_REQUIRED_PROPERTY`…); resolver merges only same-label nodes | `SchemaFromTextExtractor` |
| Graphiti v0.30.2 | Pydantic entity and edge types per call; `edge_type_map` keyed by label pair | `SearchFilters` by node label and edge type | — |
| cognee (ba3631f) | Pydantic graph model or OWL ontology; strict mode drops unmatched nodes and logs counts | fuzzy canonicalization of names and types | — |
| RAGFlow v1.0.0-rc1 | YAML template; unknown types kept, missing type becomes `other` | type feeds merge preference | — |
| youtu-graphrag (d982b5a) | JSON schema used as a hint | — | LLM appends new types to the schema file with no review |

Defaults: MS GraphRAG ships `["organization", "person", "geo", "event"]`
(`config/defaults.py:42`); LightRAG ships 11 types with one-line
definitions (Person, Creature, Organization, Location, Event, Concept,
Method, Content, Data, Artifact, NaturalObject) plus `Other`
(`lightrag/prompt.py:17-34`) [source].

**Not found in any of 13 engines** [source]: a schema version recorded on
each extracted item, selective re-extraction after a schema change, schema
design from target questions, and a propose → trial → report → review →
freeze loop. The pieces exist apart (neo4j-graphrag's pruning report,
Graphiti's filters); nobody joins them.

## Components of a schema definition

Formalisms compared: PG-Schema, Neo4j `GRAPH TYPE`, OWL, SHACL, SKOS, the
Wikidata data model, LinkML, JSON Schema/Pydantic, neo4j-graphrag, Graphiti,
OntoGPT. Cells for OWL, SHACL and SKOS rest on prior knowledge, not a
reading of the specs this round.

| Component | Who has it | TenetRAG use |
|---|---|---|
| Entity type with definition and examples | all; definitions and examples are first-class in SKOS, Wikidata, LinkML, OntoGPT | extraction prompt |
| Type hierarchy | PG-Schema, OWL, SKOS, Wikidata, LinkML; Neo4j label implication | `is_a` (single parent) |
| Aliases | SKOS, Wikidata, LinkML, OntoGPT | prompt; resolution |
| Relation type with endpoint types | PG-Schema, Neo4j `GRAPH TYPE`, SHACL, LinkML, neo4j-graphrag patterns, Graphiti `edge_type_map` | structured output; validation |
| Cardinality (single-valued at a time) | OWL, SHACL, LinkML, PG-Keys; Wikidata partly | supersede or flag contradictions |
| Attributes with datatypes and units | nearly all | structured output; validation |
| Enums / controlled vocabularies | OWL, SHACL, SKOS, Wikidata, LinkML, JSON Schema | taxonomy labels |
| Identity keys | PG-Keys, Neo4j, LinkML `identifier`/`unique_keys`, neo4j-graphrag; OWL `hasKey` | entity resolution |
| Valid time and observation time | Graphiti only (four timestamps); Wikidata has valid-time qualifiers only | engine-owned fields |
| Evidence (source chunk, quote) | Wikidata references and PROV-O carry a source, no quote; OntoGPT spans only for grounded entities | engine-owned fields |
| N-ary records (events, facts) | OWL n-ary pattern, Wikidata qualifiers, LinkML classes, OntoGPT nested classes | event and fact types with roles |
| Open vs closed | PG-Schema `OPEN`/`STRICT`/`LOOSE`, Neo4j open graph type, SHACL `sh:closed`, neo4j-graphrag `additional_*` | `mode: strict` or `discovery` |
| Versioning and deprecation | Wikidata deprecated rank; LinkML `deprecated` and replacement slots | pack `version`, `deprecated`, `renamed_from` |
| External mappings | OWL, SHACL, SKOS, Wikidata, LinkML `*_mappings` | `mappings` to standard IRIs |
| Retrieval hints | none | own extension |
| "Not an entity" list | none | own extension |

## Formalisms and tools: verified facts

- **PG-Schema** (Angles et al., SIGMOD 2023, read in full):
  - Node and edge types; types can be `ABSTRACT`. Element types are closed by
    default; `OPEN` opens the label set or the property set.
  - Graph types are `STRICT` (everything typed) or `LOOSE`.
  - Inheritance by combining types (`personType & salariedType`).
  - PG-Keys express keys, cardinality, participation and denial constraints
    (`FOR (x : personType) EXCLUSIVE MANDATORY SINGLETON x.id`).
  - No time or provenance features. [peer-reviewed]
- **Neo4j `GRAPH TYPE`**: preview in 2026.02, not for production. Label
  implication, endpoint enforcement, key, uniqueness and type constraints,
  an open mode. No documented cardinality, versioning or dates. [vendor]
- **LinkML** (v1.12.0-rc1, latest stable v1.11.1 of 2026-05-20; about one
  minor release a quarter) [source]:
  - Licenses: toolkit Apache-2.0; `linkml_runtime` CC0-1.0; metamodel CC0
    (its `pyproject.toml` says MIT).
  - `linkml` has about 28 hard dependencies, including `rdflib`, `pyshex`,
    `pyjsg` and `antlr4-python3-runtime<4.10`.
  - `jsonschemagen` emits `anyOf` for optional class references, multi-class
    ranges, inlined dicts and `any_of`; `oneOf` for `exactly_one_of`; it
    always emits `$defs`/`$ref`. `--no-include-null` removes only the null
    unions. `pydanticgen` wraps optional slots in `Optional[...]`, which
    Pydantic renders as `anyOf`.
  - The metamodel has `identifier`, `unique_keys`, `aliases`,
    `exact_mappings`, `deprecated`, `is_a`, `mixins`, `slot_usage`,
    min/max cardinality, `rules`, `annotations`. It has no temporal or
    evidence qualifiers on slots.
- **OntoGPT / SPIRES** (BSD-3-Clause) [source]:
  - The prompt lists each slot of a LinkML class, using its `prompt`
    annotation or `description`; enum values become "Must be one of".
  - Nested classes are extracted by a separate LLM call per nested value.
  - Grounding maps strings to ontology IDs through OAK annotators; ungrounded
    strings get an auto prefix; values copied from template examples are
    flagged as likely hallucinations.
  - Text spans exist only for grounded named entities; relations and other
    values carry no evidence.
- **RDF 1.2 Concepts** (triple terms, `rdf:reifies`): still a Candidate
  Recommendation (snapshot 2026-04-07) on 2026-10-03.

**Consequence** [inferred]: LinkML is the closest fit as a vocabulary, but
its dependency weight, its `$ref` and `anyOf` output (which some target
platforms reject in structured output) and its lack of time and evidence
make it unsuitable as the runtime format. TenetRAG uses its own YAML with
LinkML field names and compiles flat JSON Schemas itself
([ADR 0007](../decisions/0007-define-the-graph-schema-as-layered-domain-packs.md)).

### Statement models mapped to TenetRAG relation and fact records

| Source concept | TenetRAG field |
|---|---|
| Wikidata subject, property, value | `subject`, `predicate`, `object` or `value` |
| Wikidata qualifiers start time, end time, point in time | `valid_from`, `valid_to`, point time |
| Wikidata references stated in (P248), reference URL (P854) | `doc_id` |
| Wikidata retrieved (P813) | `observed_at` |
| Wikidata rank preferred / deprecated | `status` current / superseded |
| (no Wikidata equivalent) | `chunk_id`, `quote` |
| Nanopublication assertion | the relation or fact itself |
| Nanopublication provenance | document, chunk, quote, extraction run |
| Nanopublication publication info | `recorded_at`, run id, pack version |
| RDF 1.2 reifier | `fact_id` |

## What the evidence says

| Rule | Finding | Source |
|---|---|---|
| Give every type a definition and examples | Zero-shot average F1 55.3 with guidelines vs 42.3 without; definitions and representative candidates are complementary; ambiguous or very coarse labels still fail. Fine-tuned Code-LLaMA models, so transfer to prompted LLMs is [inferred]. | GoLLIE, [arXiv 2310.03668](https://arxiv.org/abs/2310.03668), ICLR 2024 [peer-reviewed] |
| Show the LLM only the relevant part of a large schema | Schema-retriever refinement: +4.8 (WebNLG), +5.3 (REBEL), +4.6 (Wiki-NRE) F1 with GPT-3.5, on schemas of 159 and 200 relations; canonicalization cut 529 induced relations to 200 at 0.956 precision. | EDC, [arXiv 2404.03868](https://arxiv.org/abs/2404.03868), EMNLP 2024 [peer-reviewed] |
| | Retrieving and pruning the schema per input: "up to an 8.8% increase in micro-F1, a 47% reduction in latency, and a 48% reduction in token costs" on healthcare and e-commerce data. | SchemaRAG, [arXiv 2607.00008](https://arxiv.org/abs/2607.00008), ACL 2026 Industry [peer-reviewed] |
| Draft from competency questions, then review | Memoryless CQbyCQ modelled 0.91 of CQs, Ontogenia 0.84 (10 ontologies, 100 CQs); the most common flaw is multiple domains or ranges; o1-preview with Ontogenia is comparable to or better than students. | Lippolis et al., [arXiv 2503.05388](https://arxiv.org/abs/2503.05388) [preprint; workshop version at ELMKE 2025] |
| Humans write the questions | Six CQ-generation systems against 843 gold CQs from 17 projects: BERTScore F1 0.57–0.60. | Bench4KE, [arXiv 2505.24554](https://arxiv.org/abs/2505.24554) [preprint] |
| Do not judge a schema trial by gold F1 alone | Closed ontology (6 entity types, 96 relations) on DocRED: triple F1 39.9 (Claude Opus 4.5), 39.3 (Gemini 3 Pro), 21.7 (GPT-5.1), 4.2 (Mistral 7B); 61.5 % of predicted triples were absent from the incomplete gold. "Automatic triple F1 should therefore be interpreted as a lower bound." Manual review covered 10 documents. | Ilves, Barbu, Übi, [KG-LLM @ LREC 2026](https://aclanthology.org/2026.kallm-1.21/) [peer-reviewed workshop] |
| Model qualified facts as n-ary records | Hyperedges beat StandardRAG by +7.45 F1 (Medicine), +6.46 (Agriculture), +2.37 (CS), +6.47 (Legal); graph baselines "often underperform StandardRAG". No reified-binary ablation. | HyperGraphRAG, [arXiv 2503.21322](https://arxiv.org/abs/2503.21322), NeurIPS 2025 [peer-reviewed] |
| A domain schema helps, but by how much is open | Ontology-guided extraction alone adds +3.17 F1 on Naive RAG (75.60 → 78.77); the full system's 78.92 vs 69.71 is against LightRAG. | OMD-GraphRAG, [arXiv 2603.25152](https://arxiv.org/abs/2603.25152) [preprint] |
| | +55 % fact recall and +40 % correctness are best-case relative gains (about 12 % on wheat, 0 % on news) with no ablation without the ontology. Do not cite as evidence that the ontology causes the gain. | OG-RAG, [EMNLP 2025](https://aclanthology.org/2025.emnlp-main.1674/) [peer-reviewed] |
| Induced schemas make usable drafts | 92 % semantic alignment with human-crafted schemas (BERTScore-type, on FB15kET, YAGO43kET, wikiHow typing). | AutoSchemaKG, [ACL 2026](https://aclanthology.org/2026.acl-long.942/) [peer-reviewed] |

**Not measured anywhere we found:** the effect of the number of types,
hierarchy depth, endpoint constraints or typed attributes on LLM
extraction; expert-written vs LLM-drafted schemas on downstream QA; event
or fact records vs binary edges on temporal QA; schema versioning and
selective re-extraction; any of this for Vietnamese. The often-quoted
"5–15 entity types" has no paper behind it. TenetRAG's benchmark variants
(no schema, `core` only, `core` + domain pack) are the planned evidence.

## Practitioner guidance

Rules that several independent sources agree on (counts are rough):

1. Start small and curated, then grow from trial runs (Cognee, Neo4j,
   Graphiti docs).
2. One type with attributes beats near-duplicate types: one `Employment`
   with a position attribute, not `CEOEmployment` (Graphiti docs). Semantic
   Arts moves fine distinctions into taxonomies that experts maintain; their
   starter ontology gist has about 100 classes and almost as many
   properties, client core ontologies reach 400–600 concepts, and they have
   not seen a firm need more than about 1,000 [vendor, opinion].
3. Constrain which relation connects which type pair, and enforce it in code
   (Graphiti `edge_type_map`, neo4j-graphrag patterns, WhyHow).
4. Canonicalize LLM labels against the schema (Cognee fuzzy match, EDC,
   neo4j-graphrag pruning).
5. Keep the lineage tier (document, chunk) apart from the domain tier (AWS
   graphrag-toolkit, Neo4j lexical graph).
6. Put retrieval semantics in the schema, such as which relations give
   context (Barrasa, AI Engineer 2025) [single source].
7. LLM-drafted ontologies are a starting point at best: "Most people are
   better editors than authors" (Semantic Arts, June 2025) [vendor].

| Symptom | Cause | Fix | Source |
|---|---|---|---|
| One concept under many labels | free-form LLM labels | canonical vocabulary plus fuzzy match | Cognee [vendor] |
| Edge-type explosion | over-granular types | one type plus attributes | Graphiti docs [vendor] |
| Entities silently dropped | strict required properties | report each drop with its reason; use `required` sparingly | neo4j-graphrag [source] |
| Outdated clauses retrieved | no validity intervals | intervals plus version and event records; filter by time in retrieval | legal GraphRAG write-up, 2026 [opinion] |
| Matching precision drops | ontology too broad | small curated schema | Cognee [vendor] |
| Types invented without review | auto-append of LLM-proposed types | discovery queue with a human gate | youtu-graphrag [source] |

## Standards and licenses

Rule for every pack: TenetRAG writes its own type names and definitions;
external standards appear only as IRIs under `mappings`.

| Standard | Fits | License (checked 2026-10-03) | What a pack may carry |
|---|---|---|---|
| schema.org | core | CC BY-SA 3.0 | IRIs only; never copy descriptions (share-alike) |
| gist (Semantic Arts) | core | CC BY 4.0 | names, definitions with attribution |
| W3C ORG, PROV-O | core | W3C Document License | IRIs and own wording |
| OWL-Time | core | W3C Software and Document License (permissive) | anything, keep the notice |
| FIBO (EDM Council) | finance | MIT | anything, keep the notice; too large to use whole |
| GLEIF LEI Level 1 and 2 | finance | CC0 | anything; do not imply GLEIF endorsement |
| Akoma Ntoso (OASIS) | legal | OASIS copyright, RF on Limited Terms | names, definitions with the OASIS notice |
| ELI | legal | not found | IRIs only |
| SEMIC Core Vocabularies | public sector | CC BY 4.0 | with attribution |
| O*NET | HR | CC BY 4.0 | with the required attribution sentence |
| ESCO | HR | not verified on the owning site | IRIs only |
| Biolink Model | biomedical | Apache-2.0 | with NOTICE |
| HL7 FHIR | biomedical | CC0 (SNOMED content excluded) | anything; no HL7 endorsement |
| SNOMED CT, UMLS | biomedical | licensed | nothing; codes only as user data |
| STIX 2.1 | cyber | OASIS, Non-Assertion IPR | type names; no spec prose |
| MITRE ATT&CK | cyber | royalty-free with the MITRE notice | IDs and names with the notice |
| OpenTelemetry semantic conventions, CycloneDX | IT | Apache-2.0 | with NOTICE |
| SPDX specification | IT | CC BY 3.0 | with attribution |
| IOF Core | supply chain | MIT | anything, keep the notice |
| Brick, SAREF | buildings, industry | BSD-3-Clause (SAREF via ETSI Forge) | keep the notice; be careful with ETSI TS prose |
| ORKG data | science | CC0, except Papers With Code data (CC BY-SA) | CC0 parts freely |
| CiTO | science | CC BY 4.0 | with attribution |
| ACORD | insurance | membership | nothing |
| ACE 2005, ERE | news events | LDC, paid | nothing; own event names |
| IFRS Taxonomy | finance | IFRS Foundation terms: no commercial use, no translation, no direct amendment (checked 2026-10-04) | nothing bundled; citing element names as mappings is not addressed, so ask the Foundation first |
| BIS publications, incl. the Basel Framework | banking | free "limited extract" of at most 400 words or two tables and 10 % of a publication, cited, non-commercial (2026-10-04) | short cited quotes; own definitions |
| IMF FSI Compilation Guide | banking | IMF copyright; reuse terms not read | citations only; own definitions |
| ECB BIRD, EBA DPM, BIAN | banking | not found (2026-10-04); "free of charge online" is not a licence | IRIs only |
| ISO 20022 | finance | not verified (terms page blocked) | IRIs only |
| ISO 4217, ISO 10383 (MIC) code lists | finance | lists free from the registration authorities; standard texts sold [secondary] | code values |
| ISO 10962 (CFI), ISO 6166 (ISIN) | finance | standard texts sold; ISIN data may carry fees [secondary] | own enums; codes only as user data |
| UK Open Banking open data, FDX, Berlin Group | banking | conflicting pages; FDX limited and non-sublicensable; Berlin Group CC BY-ND 4.0 [secondary] | nothing |
| SKOS | enterprise | W3C Document License | property names and own wording |
| Apache Ossie (formerly Open Semantic Interchange) | enterprise | Apache-2.0, incubating (2026-10-04) | field names, with NOTICE |

### Annotated datasets as evidence of extractable types

| Dataset | Types | License |
|---|---|---|
| SciERC | 6 entity types (Task, Method, Metric, Material, OtherScientificTerm, Generic), 7 relations | not found |
| CUAD | 41 contract clause categories, 510 contracts | CC BY 4.0 |
| REFinD | 22 financial relations over 8 entity pairs | paper CC BY-NC-SA 4.0; data license not found (2026-10-04) |
| FinRED | 29 relations | CC BY 4.0 per the paper; repo states none (2026-10-04) |
| FiNER-139 | 139 XBRL tags | CC BY-SA 4.0 |
| BioRED | genes, diseases, chemicals, variants and more | US Government work |
| CASIE | 5 cyber event types | not found |
| VLSP 2016 / 2018 NER (Vietnamese) | PER, ORG, LOC (+ MISC in 2016) | not checked |
| VLSP 2020 RE (Vietnamese) | LOCATED, PART–WHOLE, PERSONAL–SOCIAL, ORGANIZATION–AFFILIATION over PER, ORG, LOC | not stated |

More finance, enterprise and NER inventories (FinDKG, FinReflectKG, Few-NERD,
PhoNER_COVID19, AMI, EnterpriseRAG-Bench) are in
[domain-schemas.md](domain-schemas.md#datasets-for-tests-and-benchmarks).
Use these inventories as facts about what text supports. Do not ship their
texts, labels as data, or guidelines.

## Gaps

- Not read: OWL, SHACL and SKOS specs; Noy & McGuinness and the OOPS!
  pitfall catalogue in full; MedGraphRAG, KG-RAG/SPOKE, SAC-KG, KnowCoder,
  Docs2KG, NeOn-GPT, OntoChat; the 2025 LLM KG-construction survey
  ([arXiv 2510.20345](https://arxiv.org/abs/2510.20345)).
- KGGen's venue and SciERC, MAVEN, CASIE, FinRED, ESCO and ELI licenses were
  not verified.
- No first-hand production report with before/after numbers on a schema
  change or its re-index cost.
