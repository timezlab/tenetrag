# Graph schema meta-model: components across formalisms

> **Snapshot, 2026-10-03 — not maintained.** Web lane comparing PG-Schema, Neo4j, OWL, SHACL, SKOS, Wikidata, LinkML, JSON Schema, neo4j-graphrag, Graphiti and OntoGPT, followed by a code-research verification lane. The maintained,
> re-verified summary is in [graph-schema-design.md](../reference/graph-schema-design.md); where they differ, the maintained doc
> wins. Local paths were removed before publishing.
>
> **Errata and later resolutions:**
> - Cells marked `*` or inferred in the first part were not verified. The
>   verification lane (second part) read PG-Schema in full, LinkML and OntoGPT in
>   source, and the RDF 1.2 status page.
> - LinkML: toolkit Apache-2.0, runtime CC0-1.0, metamodel CC0 (its pyproject says
>   MIT). Its JSON Schema and Pydantic generators do emit `anyOf`/`oneOf` for
>   optional refs, unions and boolean slot expressions.
> - RDF 1.2 Concepts was still a Candidate Recommendation on 2026-10-03.

## Part 1: meta-model lane

### Schema meta-model research (2026-10-03)

Verified this session (fetched): PG-Schema abstract (arXiv 2211.10962), Wikidata data model + Help:Sources, nanopub guidelines working draft, RDF 1.2 Concepts (CR snapshot 2026-04-07), Neo4j GRAPH TYPE blog (v2026.02 preview), LinkML schema element index + generators list, OntoGPT README.
NOT verified (priors, labelled inferred): PG-Schema full-paper details (PDF fetch failed), OWL/SHACL/SKOS specs, neo4j-graphrag/Graphiti cells beyond the brief, LinkML license/maturity, Pydantic anyOf behaviour of generators.

#### Verified facts
- PG-Schema: multi-inheritance PG-types, constraints from PG-Keys, aimed at GQL DDL (abstract only) - arxiv.org/abs/2211.10962
- Neo4j GRAPH TYPE: Preview in 2026.02, not for production; node/rel types, label implication (Crew implies Person), endpoint enforcement, auto-generated key/unique/type constraints, OPEN (extra props/labels allowed). No cardinality/versioning/dates documented. Property type constraints are Enterprise.
- Wikidata: statement = subject/property/value + qualifiers + references + rank (normal/preferred/deprecated); special values no-value / unknown-value; property constraints (since 2017) separate from data. References: stated in (P248), reference URL (P854), retrieved (P813), publication date (P577), archive URL/date, title; sources generally mandatory.
- Nanopub: Head + Assertion + Provenance (how/who/when/where from) + PublicationInfo (attribution, timestamp of the nanopub itself); distinct URIs; trusty URIs for integrity.
- RDF 1.2: triple term + reifier via rdf:reifies; CR snapshot 2026-04-07, not expected Rec before 2026-05-05 (check whether now Rec).
- LinkML: classes, slots, types, enums, subsets, mixins, identifiers/keys, unique_keys, rules, annotations, is_a, prefixes/mappings, patterns; 30+ generators incl. JSON Schema, Pydantic, SHACL, OWL, SQL DDL, SQLAlchemy.
- OntoGPT/SPIRES: walks LinkML schema recursively, one class per prompt with only that class's fields; grounds via OAK annotators; ungrounded get AUTO: prefix; BSD-3-Clause.

#### Checklist (S=supported, P=partial, N=no; * = inferred from priors)
Cols: PGS/GQL | Neo4j | OWL | SHACL | SKOS | Wikidata | LinkML | JSONSch/Pydantic | n4j-graphrag | Graphiti | OntoGPT
- Entity type: S|S|S|S|P(concept)|S(item+instance of)|S|S|S|S|S
- Hierarchy/inheritance: S(verified)|P(label implication, verified)|S|P(sh:node)|S(broader)|S(subclass of)|S(is_a, mixins)|P|N*|N*(Pydantic only)|S
- Definition/examples: P|N|P(annotations)|P(sh:description)|S(definition, example)|S(description)|S(description, examples)|P(description)|P(description)|S(docstrings feed prompt*)|S
- Aliases: N|N|P(labels)|N|S(altLabel)|S(aliases)|S(aliases)|N|N*|N|S
- Relation type + direction: S|S|S|S|P(semantic rels)|S|S|P|S|S|S
- Domain/range: S(endpoint types)|S(GRAPH TYPE, verified)|S(semantics, not validation)|S(sh:class)|N|P(constraints)|S(domain/range)|P|S(Pattern)|S(edge_type_map)|S
- Cardinality/functional: S(PG-Keys*)|N(not documented)|S|S(minCount/maxCount)|N|P(single-value constraint)|S(multivalued, min/max)|P|N*|N|P
- Symmetric/inverse/transitive: N|N|S|N|P(related)|P(inverse prop)|P(inverse, symmetric via rules*)|N|N|N|N
- Attributes + datatypes/units: S|S|S|S|N|S(datatypes, quantity unit)|S(types, unit)|S|S(PropertyType)|S|S
- Enums/controlled vocab: P|P|S(oneOf)|S(sh:in)|S|S|S(enums + dynamic enums from ontologies)|S(enum)|P|P|S
- Identity keys: S(PG-Keys)|S(UNIQUENESS/KEY)|P(owl:hasKey)|P|N|S(external-id props)|S(identifier, unique_keys)|P(none native)|S|P(name-based)|S(grounding IDs)
- Required fields: S|S(existence)|P|S|N|P|S(required)|S|S|P|S
- Valid time / obs time: N|N|P(OWL-Time)|N|N|P(qualifiers only, no obs time)|N(user-modelled)|N|N|S(valid_at/invalid_at/created_at/expired_at)|N
- Provenance/evidence: N|N|S(PROV-O)|N|N|S(references)|N(modelled)|N|N|P(episodes)|P
- N-ary/events/claims: P|N|S(pattern, W3C note)|P|N|S(qualifiers)|S(class)|S(nested)|N|P(edge attrs)|S(nested classes)
- Negative constraints: N|N|P(disjoint)|P(sh:not)|N|P|P(rules)|P(not)|N|N|N
- Open/closed: S(OPEN/STRICT*)|S(open GRAPH TYPE, verified)|open-world|S(sh:closed)|N|open|P|S(additionalProperties)|S(additional_*)|N|N
- Versioning/deprecation: N|N|P(owl:deprecated)|N|P(historyNote)|S(deprecated rank)|P(version, deprecated)|N|N|N|N
- Namespaces/mappings: N|N|S|S|S|S(external ids)|S(prefixes, *_mappings)|N|N|N|S
- Retrieval hints: N everywhere (our own extension)

#### Pipeline use + LLM benefit
- Entity type name+description+examples: extraction prompt; benefit [secondary: SPIRES per-class prompting; inferred generally]
- Domain/range: structured output enum of allowed (from,to) + validation/pruning; benefit mainly as validator, [inferred]
- Identity keys: resolution only (not prompt) ; keys must be extractable attributes
- Cardinality/functional: contradiction detection / supersession at write; not prompt
- Enums: structured output + validation; strong benefit [inferred, widely used]
- Time: extraction fields (valid_from/to, precision, as_written text) + obs time set by pipeline not LLM
- Evidence: chunk_id + quote in output, verified by code; confidence optional
- N-ary: event types with typed roles = reify as node with role edges; flat roles keep <=64 keys
- not_entities: prompt + validator
- Strictness mode: validation/review queue
- Version: lifecycle (re-extract on pack bump; rename map)

#### Recommendation
Own small YAML meta-model, LinkML-shaped vocabulary (names: classes/slots/enums/is_a/identifier/range/required/multivalued/aliases/description/examples/mappings) so a later LinkML exporter/importer is cheap. Do not adopt LinkML wholesale: no temporal/evidence/mode/retrieval semantics, its generators emit anyOf/union-heavy JSON Schema [inferred, verify], heavy dependency, and we must compile our own flat <=64 key schemas anyway. Do not adopt OWL/SHACL: reasoning not needed. Exporters to build: Pydantic/JSON Schema (flat), SQL DDL; later SHACL/LinkML.

v1 required: entity types (desc, examples, aliases, parent single-inheritance), relation types (from/to lists, direction), attributes+datatypes+enums, identity keys, required, valid-time config per relation/event (interval|point, precision), evidence required globally, event types with roles, not_entities, mode strict|discovery, pack version.
v1 optional: cardinality (one_at_a_time), units, mappings (external IRIs), retrieval hints, deprecated/renamed_from.
Later: symmetric/inverse, transitive, disjointness, rules, multi-inheritance/mixins, rank (preferred/deprecated), no-value/unknown-value.
Our fact record fixed (not pack-defined): fact_id, subject, predicate, object|value, valid_from, valid_to, valid_precision, observed_at, recorded_at, doc_id, chunk_id, quote, confidence, status.

#### Mapping Wikidata/nanopub -> fact record
- statement subject/property/value -> subject/predicate/object
- qualifiers start time/end time/point in time -> valid_from/valid_to/point
- reference stated in / URL -> doc_id (+uri); retrieved (P813) -> observed_at; no quote field in Wikidata -> add quote+chunk_id
- rank deprecated/preferred -> status superseded/current
- no value/unknown value -> later; absence of fact otherwise
- nanopub assertion -> fact triple; provenance -> doc/chunk/quote/extractor run; publicationInfo -> pipeline run id, recorded_at, pack version
- RDF 1.2 reifier -> fact_id (fact is addressable)


## Part 2: verification lane (LinkML, OntoGPT, PG-Schema, RDF 1.2)

#### Schema-format verification: findings (2026-10-03)
Notes file: (local path removed). It is only a short index, not the full report. This message is the full report.
Clones are in (local path removed). Nothing was installed or run. The PG-Schema text is at (local path removed).
Pins: linkml @ v1.12.0-rc1 (7ca47cc), linkml-model @ 6f382ad, ontogpt @ v1.2.0 line (9224d33).

##### 1. LinkML licenses and maturity
- **Repo layout.** `linkml/linkml` is now a uv monorepo with `packages/linkml` and `packages/linkml_runtime` (root `pyproject.toml` `[tool.uv.workspace]`). [verified-source]
- **Toolkit license.** `packages/linkml/pyproject.toml:19` says `license = "Apache-2.0"`, and the root LICENSE is the Apache text. [verified-source]
- **Runtime license.** `packages/linkml_runtime/pyproject.toml:15` says CC0-1.0. [verified-source]
- **Metamodel license is inconsistent.** The `linkml-model` LICENSE file is CC0 1.0, and `meta.yaml:32` points to the CC0 URL. `linkml-model/pyproject.toml:9` says `license = "MIT"`, while its classifier says CC0. Treat the license as CC0, but the metadata is inconsistent. [verified-source]
- **Releases.**
  - The latest tag is v1.12.0-rc1 (2026-10-02). The latest stable is v1.11.1 (2026-05-20).
  - Stable releases in the last 12 months: v1.9.5 (2025-10-22), v1.9.6 (2025-11-18), v1.10.0 (2026-02-24), v1.11.0 (2026-05-13), v1.11.1 (2026-05-20). There were many rc tags in between.
  - Cadence is about one minor release per quarter, preceded by 3–5 rcs. [verified-source, tags]
  - The `linkml-model` stable tags are v1.10.0 (2026-02-20) and v1.11.0 (2026-05-07). Its latest tag is v1.12.0-rc1 (2026-10-01).
  - `linkml-runtime` standalone stopped at v1.9.5 (Dec 2025). It is now inside the monorepo.
- **Activity.** I counted about 1,300 commits since 2025-10-03 and about 25 distinct authors in the last 3 months. [verified-source, approximate: the clone was shallow]
  - Top authors by commit count: Corey Cox, Nico Matentzoglu, Tim Fliss, Silvano Cirujano Cuesta, Sage Hrke, Kevin Schaper.
  - `linkml-model` is thin: Nico Matentzoglu has 14 commits since Oct 2025, and the next authors have 4 or fewer.
  - Core maintainers are the LBL group (Mungall, Moxon, Patil, Miller, among others).
- **`linkml` dependencies.** `packages/linkml/pyproject.toml:40-70` lists about 28 hard dependencies. [verified-source]
  - Heavy ones: `pyshex`, `pyshexc`, `pyjsg`, `antlr4-python3-runtime<4.10`, `rdflib>=7.6`, `sqlalchemy`, `openpyxl`, `graphviz`, `jinja2`, `pydantic>=2.13`, `jsonschema[format]`, `watchdog`, `sphinx-click`, `openapi-spec-validator`, `pydantic-settings`.
  - So the answer to your rdflib/pyshex question is yes, both are pulled in.
- **`linkml-runtime` dependencies** (`packages/linkml_runtime/pyproject.toml:37-53`): `rdflib>=7.6`, `pyoxigraph`, `curies`, `prefixmaps`, `prefixcommons`, `jsonasobj2`, `json-flattener`, `jsonschema`, `pydantic`, `pyyaml`, `requests`, `click`, `hbreader`, `deprecated`. It is still RDF-heavy, but lighter than `linkml`.

##### 2. Do the generators emit anyOf/oneOf?
All paths are under `packages/linkml/src/linkml/generators/`.

**jsonschemagen.py** [verified-source]
- **Optional class refs.** `ref_for(required=False)` wraps in `anyOf: [{$ref}, {type:null}]` (lines 331-339).
  - A multi-class range, such as an inlined range with a type designator or `include_range_class_descendants`, gives `anyOf` of `$ref`s (line 331; descendants chosen at 786-808).
- **Inlined dict ranges.** An inlined-as-dict range with an identifier uses `additionalProperties: {anyOf: [...]}` (lines 896-908).
- **Boolean slot expressions.**
  - `any_of` gives `anyOf` (967-972).
  - `exactly_one_of` gives `oneOf` (979-981).
  - `all_of` gives `allOf` (974).
  - `none_of` gives `not.anyOf` (984).
  - The same operators work at class level (626-646) and in anonymous classes (705-718). Class rules also add `allOf` (622-624).
- **Optional scalars.** These become `type: ["string","null"]`, a type array rather than `anyOf` (line 938-940). Optional multivalued slots become `["array","null"]` (347).
- **Enums.** They are emitted as separate `$defs` entries: `{type: string, enum: [...]}` (735-766), referenced via `$ref` (line 780). The enum itself has no anyOf.
- **Non-inlined class ranges.** These collapse to the range's identifier type, a plain string (810-812).
- **`$defs`/`$ref`.** Always emitted (230-236, 325). There is no inline-everything mode.
- **Options.**
  - `include_null` (default True; CLI `--include-null/--no-include-null`, lines 448 and 1317) removes the null from optional scalars, arrays and refs. It drops the `anyOf [ref, null]` for optional refs, but not the `anyOf` from `any_of` or from multi-class ranges.
  - There is no flatten/inline option. `--inline` (1234) only affects `start_schema`.
  - `include_range_class_descendants` controls descendant unions.
- **Consequence.** A plain schema (single ranges, no boolean expressions, no type designators, `--no-include-null`) emits no anyOf/oneOf. It still uses `$defs`/`$ref` and type-array `["x","null"]` unless `include_null` is off. [inference: whether your platform accepts `$ref` and type arrays is untested]

**pydanticgen.py** [verified-source]
- It emits Python `Union[...]` for `any_of` ranges (600-615), polymorphic class ranges (~782), array representations (630) and inlined simple dicts (649).
- It wraps every non-required, non-identifier slot in `Optional[...]` (654).
- Pydantic's `model_json_schema()` renders `Optional[X]` as `anyOf: [X, null]`. [inference: that is Pydantic behavior, not read here]
- No flatten option was found.

##### 3. Metamodel features
Pinned to `linkml-model/linkml_model/model/schema/`. All items below are verified-source.
- `identifier` (`meta.yaml:1897`). The slot is the class identifier. It is automatically required, unique document-wide, inherited, and allows referencing.
- `unique_keys` (`meta.yaml:1312`). Named compound keys, mapped to `owl:hasKey`.
- `aliases` (`meta.yaml:285`). Synonyms on an element. `structured_aliases` is at 275.
- Mapping slots (`mappings.yaml`). They are defined with space-separated names: `mappings`, `exact mappings`, `close mappings`, and so on.
  - Python and JSON names use underscores, e.g. `exact_mappings`.
  - Slot URIs are `skos:exactMatch` and the like.
- `deprecated` (`meta.yaml:305`). A string, not a boolean.
- `deprecated_element_has_exact_replacement` (`mappings.yaml:93`, space-named slot). It holds a URI or CURIE replacement, mapped to IAO:0100001. A `possible_replacement` variant is at line 100.
- `is_a` (`meta.yaml:517`) and `mixins` (`meta.yaml:558`). Mixins are secondary parents (alias "traits").
- `slot_usage` (`meta.yaml:1032`). Refines a slot within a class.
- `minimum_cardinality` (`meta.yaml:1677`) and `maximum_cardinality` (`meta.yaml:1688`). They apply to multivalued slots, and min must not exceed max.
- `rules` (`meta.yaml:1203`). Class rules, mapped to `sh:rule`.
- `annotations` (`annotations.yaml:21`). Free tag/text pairs, with the semantics of OWL annotations.
- `in_subset` (`meta.yaml:343`). Subset membership.
- **Temporal or provenance on slots: none.**
  - Grep for temporal/provenance/evidence/qualifier across `schema/*.yaml` found only the `meta.yaml:618` comment that version identifiers sort temporally.
  - Element-level `created_on` and `last_updated_on` exist (`meta.yaml:414-423`), but they describe the schema element, not a data value.
  - The only route is free-form `annotations` or modelling the structure yourself.

##### 4. OntoGPT/SPIRES
- **License.** LICENSE is a BSD-style text, and `pyproject.toml:10` says `BSD-3`. [verified-source]
- **Prompt construction.** `src/ontogpt/engines/spires_engine.py` `get_completion_prompt` (lines 499-548).
  - The header is "From the text below, extract the following entities in the following format".
  - It loops over `sv.class_induced_slots`.
  - For each slot, the prompt text comes from the `prompt` annotation, else `slot.description`, else a fallback ("semicolon-separated list of {name}s").
  - Enum values are appended as "Must be one of: ...".
  - Each line is rendered as `slot_name: <prompt>`.
  - The output format is pseudo-YAML, parsed by `_parse_response_to_dict` (550) and `_parse_line_to_dict` (687).
- **Nested classes.**
  - Inlined or identifier-less ranges, and any range when `self.recurse` is set or the range has more than 2 slots, trigger `_extract_from_text_to_dict(v, slot_range)` per value (~line 744-752). That is a separate LLM call per nested value.
  - Otherwise a separator split is used (`" - "`, `":"`, ...).
  - `ground_annotation_object` (820) also recurses on dict values.
- **Grounding.**
  - `knowledge_engine.py:504-545` `normalize_named_entity` runs the class's annotators (`groundings`, 702).
  - If grounding fails and `auto_prefix` is set, it returns `f"{auto_prefix}:{quote(text)}"` (line 538-539).
  - `_auto_add_ids` (806-817) assigns `{auto_prefix}:{uuid4}` to missing identifier slots.
  - It also flags values that match the template examples as `LIKELY HALLUCINATION`.
  - The exact `AUTO` string depends on `auto_prefix`. I did not trace where it is set to `"AUTO"`. [inference]
- **Evidence spans.**
  - Spans exist only for grounded named entities: `get_spans` (line 927) calls `parse_utils.py:111` `get_span_values`.
  - That is a case-insensitive regex search of the entity label in the input, returning all matches as inclusive `"start:end"` strings on `NamedEntity.original_spans`.
  - There is no per-value evidence. Ungrounded values and relations carry no span. [verified-source]

##### 5. PG-Schema
I fetched the arXiv v4 PDF with curl and pdftotext. It is the SIGMOD 2023 version (Proc. ACM Manag. Data 1(2), Art. 198, June 2023). The grammar is at `pgs.txt:436-466`. [verified-doc]
- **Types.**
  - Node type: `(personType : Person { name STRING, OPTIONAL birthday DATE })`.
  - Edge type: `(: A) -[ T : Label {props} ]-> (: B)`.
  - Types can be `ABSTRACT`.
  - Label specs combine `&`, `|` and `?`.
- **Closedness.**
  - Element types are closed by default.
  - `OPEN` appears either outside the braces, which opens the label set, or inside the braces, which opens the property set. The two are independent.
  - Example: `(suspiciousType : Suspicious OPEN { reason STRING, OPEN })`.
- **Graph types.** `CREATE GRAPH TYPE g STRICT|LOOSE [IMPORTS ...] { ... }`.
  - `STRICT` requires every node and edge to be typed.
  - `LOOSE` allows partial typing.
  - This is separate from OPEN/closed (lines 552-559).
- **Properties.** These are `key BASETYPE`. `OPTIONAL` marks a property as optional.
- **Inheritance.** It is done by reuse in the label spec: `(employeeType : personType & salariedType)`.
  - Compatible properties are merged.
  - A base type that is open makes the derived type open.
  - Edge types can inherit from other edge types.
- **PG-Keys.** `FOR p(x) [EXCLUSIVE] [MANDATORY] [SINGLETON] q(x, y...)`.
  - Example: `FOR (x : personType) EXCLUSIVE MANDATORY SINGLETON x.id`.
  - `WITHIN` marks the output being constrained.
  - The same syntax covers foreign keys, participation constraints, CHECKs and denial constraints.
- **Time and provenance.** No temporal or provenance features. A grep for temporal/provenance/timestamp returned nothing. `DATE` is only a base property type.

##### 6. RDF 1.2 Concepts
- It is still a **Candidate Recommendation Snapshot, dated 07 April 2026**. [verified-doc]
- I fetched https://www.w3.org/TR/rdf12-concepts/ twice (WebFetch and curl).
- The page says: "not expected to advance to Recommendation any earlier than 05 May 2026."
- As of today it has not become a Recommendation.

##### Gaps
- I did not trace where `auto_prefix` is set to `AUTO` in OntoGPT.
- I did not run the generators. Their behavior on a concrete schema is read from source only.
- The commit and author counts come from a shallow clone and are approximate.
- Whether your platform accepts `type: [x, "null"]`, `$ref` or `$defs` is untested.
