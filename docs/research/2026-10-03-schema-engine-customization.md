# Schema customization in GraphRAG engines: source-level report

> **Snapshot, 2026-10-03 — not maintained.** Code-research lane on how 13 engines let users define, enforce and evolve a graph schema. The maintained,
> re-verified summary is in [graph-schema-design.md](../reference/graph-schema-design.md); where they differ, the maintained doc
> wins. Local paths were removed before publishing.
>
> **Errata and later resolutions:**
> - Default entity types were checked in source afterwards and are appended below
>   (MS GraphRAG v3.2.0 and LightRAG v1.5.7).
> - Paths are relative to each repo root; for llama_index and LightRAG they are
>   relative to the engine checkout used in round 1.

### Schema customization in existing GraphRAG engines — findings

**Pins:** MS GraphRAG v3.2.0, LightRAG v1.5.7, llama_index v0.14.25, neo4j-graphrag 1.22.0, graphiti v0.30.2, cognee commit ba3631f (nearest tag cognee-mcp-v0.5.6), ragflow v1.0.0-rc1, KAG fdab15b, autoschemakg d0a1666, youtu-graphrag d982b5a, itext2kg v1.1.0, kg-gen 6259b4c, sag f80ee6c plus the zleap_sag 0.13.0 sdist. The AWS files are loose snapshots with no git pin, so their version is unknown. "Not found" means I searched for the feature and it was absent, not that I read every file.

Paths are relative to (local path removed) . For llama_index and LightRAG the prefix is (local path removed).

| Engine | 1 Define / strict? / off-schema | 2 Relation constraints | 3 Typed attrs | 4 Beyond prompt | 5 Schema assist | 6 Evolution / versioned | 7 Violation report |
|---|---|---|---|---|---|---|---|
| MS GraphRAG | `entity_types: list[str]` config. Open: the list is only injected into the prompt. Off-schema types are kept. | None | None | Type is half of the merge key `groupby(["title","type"])`. Nothing else. | `prompt-tune` generates domain, persona, entity types and prompts. It writes files, and a human can edit them. | Not found. Nothing recorded. | None |
| LightRAG | Free-text `entity_types_guidance` in `addon_params`. Open, with an `Other` fallback. Types are lowercased. | None | None | Merge takes the most common type. The old `ENTITY_TYPES` env var now raises. | None | Not found | Warns and drops only malformed types. |
| LlamaIndex Schema extractor | Literal-typed `possible_entities` / `possible_relations`, `strict=True` by default. Off-schema triplets are dropped. | `kg_validation_schema` triples, enforced in code. | Props are names only, no types. | Pydantic validation at extraction. | None | Not found | Silent `continue` |
| LlamaIndex Dynamic extractor | `allowed_*` lists are initial hints. The LLM may invent types. | None | Names only | None | The LLM expands the ontology as it goes. | Not found | None |
| neo4j-graphrag | `GraphSchema` with `NodeType`, `RelationshipType`, `Pattern`. `additional_*` flags choose strict or open. | `patterns` enforced by `GraphPruning`. | `PropertyType.type` is a Neo4j type enum (DATE, FLOAT, etc.). | UNIQUENESS/EXISTENCE/KEY constraints enforced in pruning and exported. Resolver only merges nodes with the same label. | `SchemaFromTextExtractor` (LLM) and `SchemaFromExistingGraphExtractor`. | `save`/`from_file` JSON/YAML. No version field found. | `PruningStats` lists items with a `PruningReason` enum. |
| Graphiti | Pydantic `entity_types` and `edge_types` passed per call. Off-schema entities fall back to generic `Entity`. | `edge_type_map[(src_label, tgt_label)]` offers allowed edge types to the LLM. | Pydantic fields extracted by a second LLM call. | `SearchFilters.node_labels` and `edge_types`. | None | Schema is not stored with the graph. Stale edge attributes are cleared on re-resolve. | None |
| Cognee | Custom Pydantic `graph_model`, or RDF/OWL ontology resolver. `ontology_mode="strict"` drops unmatched nodes. | Ontology subgraph used. Edge domain/range check not verified. | Pydantic models | Fuzzy ontology matching canonicalizes names and types. | None found | Not found | Strict mode logs drop counts and retained percentage. |
| RAGFlow rc1 | YAML template with `entity.fields[]` (type, description, rule) and `relation.fields[]`. Open: unknown types are kept, a missing type becomes `other`. | Direction rules are prose only. | Optional `output_fields`, prompt-only. | Type feeds merge preference and the heuristic that repairs missing parent edges. | Not found | Not found. Row ids hash (content, doc, template_id). | None |
| KAG | OpenSPG `.schema` DSL committed to a server. Typed properties and relations. | Declared in schema. Enforcement is server-side, outside this repo. | Property types and constraint classes (enum, regex, not-null, multi-value). | Schema drives extraction and index settings. | None | `SchemaClient` session and `commit()`. No version tracking found. | Not found |
| AutoSchemaKG | Free-form triples. | None | None | None | Post-hoc LLM concept induction writes CSV. No human step. | Not found | None |
| youtu-graphrag | `schemas/*.json` with Nodes, Relations, Attributes as string lists. Open: used as a "recommend" prompt. | None | None | None | LLM proposes `new_schema_types`, appended to the file automatically. | File mutated in place. No version. | None |
| itext2kg, kg-gen | Labels normalized, not constrained. Pydantic used only for output structure. | None | None | None | None | Not found | None |
| SAG / zleap_sag | `entity_types` config. Types are rows in an `entity_types` table with scope global/source/article. Off-schema entities dropped. | None | Typed value columns and `value_constraints`. | Per-type `weight` and `similarity_threshold`. | None | `append` or `replace` seeding. Table not versioned. | Counters plus a warning log. |
| AWS lexical-graph | Preferred classifications are a prompt hint only, and the LLM may add new ones. | None | None | Data versioning only (`VALID_FROM`), not schema versioning. | `DOMAIN_ENTITY_CLASSIFICATIONS_PROMPT` proposes 5 classes from samples. | New classes carry forward to later calls. | None |

**Evidence per cell**

- MS GraphRAG:
  - Type list: `packages/graphrag/graphrag/config/models/extract_graph_config.py#L37`.
  - Merge key: `index/operations/extract_graph/extract_graph.py#L108`.
  - Prompt-tune: `api/prompt_tune.py#L123-L175`.
- LightRAG:
  - Guidance: `lightrag/prompt.py#L17-L30`.
  - Validation: `lightrag/operate.py#L661`.
  - Env var raise: `lightrag/lightrag.py#L1257`.
- LlamaIndex: strict at `.../transformations/schema_llm.py#L111-L112`, triple check at `#L325-L340`.
- neo4j-graphrag:
  - Property types: `components/schema.py#L79`.
  - Constraints: `components/schema.py#L97`.
  - Pruning reasons: `components/graph_pruning.py#L40`.
  - Pattern enforcement: `components/graph_pruning.py#L327`.
  - Resolver: `components/resolver.py#L74`.
  - Schema from text: `components/schema.py#L1566`.
- Graphiti:
  - Edge type signatures: `graphiti_core/utils/maintenance/edge_operations.py#L457-L486`.
  - Attribute extraction: `node_operations.py#L786-L835`.
  - Stale attribute comment: `edge_operations.py` near line 815.
  - Search filters: `search/search_filters.py#L56-L98`.
- Cognee:
  - Strict drop: `modules/ontology/construct_data_points_and_edges_with_ontology.py#L171`.
  - Drop log: same file, `#L245`.
- RAGFlow:
  - Template: `api/db/init_data/compilation_templates/knowledge_graph.yaml#L11-L80`.
  - Fallback to `other`: `internal/ingestion/component/knowledge_compiler/structure/graph.go#L22-L24`.
  - Type merge: same file, `#L116`.
- KAG: `knext/schema/client.py#L100`, `kag/builder/component/extractor/schema_constraint_extractor.py#L335`.
- youtu-graphrag: `models/constructor/kt_gen.py#L411-L463`.
- SAG:
  - `zleap_sag-0.13.0/src/zleap/sag/config.py#L314-L316` (docstring says only defined types are kept).
  - `modules/extract/schema.py#L494` (the filter).
  - `modules/extract/processor.py#L254-L262` (stats and warning).
  - `db/models.py#L674-L715` (weight, threshold, value constraints).
  - `modules/extract/parser.py#L552` (value types).
  - `core/storage/repositories/entity_repository.py#L118` (`type_weight`).
- AWS: `src_indexing_prompts.py#L176`, `storage-model.mdx#L56`.

**Key findings**

1. **A customizable schema is already table stakes, and several engines go well past prompt injection.**
   - Strict enforcement in code is found in llama_index [verified: `schema_llm.py#L325`], neo4j-graphrag [verified: `graph_pruning.py#L327`], cognee strict mode [verified: `construct_data_points_and_edges_with_ontology.py#L171`] and SAG [verified: `schema.py#L494`].
   - Prompt-only schemas are MS GraphRAG, LightRAG, RAGFlow, youtu-graphrag and AWS. These are the weakest.
2. **Schema-driven validation and pruning with a user report exists.** neo4j-graphrag is the most complete:
   - Typed properties, existence/key/unique constraints, and pattern enforcement.
   - A `PruningStats` object with per-item reasons, and a label-scoped resolver [verified: `graph_pruning.py#L40-L62`, `resolver.py#L74`].
3. **Schema-driven resolution and retrieval is partial.** Resolution is label-scoped in neo4j-graphrag, ontology-canonicalized in cognee, and per-type weight/threshold in SAG. Retrieval filtering by type or edge type is verified in Graphiti [verified: `search_filters.py#L56`]. SAG's per-type weight reaches retrieval as `type_weight` [verified: `entity_repository.py#L118`]. I did not trace the others.
4. **Schema as a versioned artifact: not found in any engine.** neo4j-graphrag has JSON/YAML save and load but no version field. SAG records only a DB schema version, which is not the user's entity-type schema. AWS versions data, not schema.
5. **Selective re-extraction when the schema changes: not found in any engine.** The incremental hooks I found work on the data side only (MS GraphRAG `update_*` workflows, AWS versioning). Graphiti has an incidental behavior: on re-resolve it clears attributes left by a prior schema [verified: `edge_operations.py` near line 815]. LightRAG dropped its `ENTITY_TYPES` env var, so config no longer carries types [verified: `lightrag.py#L1257`].
6. **Human-in-the-loop design from sample documents exists only in a weak form.**
   - MS GraphRAG prompt-tune writes editable prompt files from samples, but there is no review loop.
   - neo4j-graphrag `SchemaFromTextExtractor` outputs a saveable `GraphSchema` [verified: `schema.py#L1566`]. A human review step is [inferred] from the save/load API and examples.
   - AutoSchemaKG, youtu-graphrag and AWS induce schema automatically with no human gate.
7. **Design from target questions: not found.** I searched for question-driven or query-driven schema in the repos listed above and found no code. This is a possible differentiator. I did not search outside these repos.
8. **The real gap is the lifecycle.** Strict enforcement with pruning reports exists, but only as separate pieces. No engine combines a versioned schema, a lineage link from items to the schema version, impact analysis, and selective re-extraction.

**gaps:** I did not read the OpenSPG server code (KAG constraint enforcement), so KAG's relation and constraint enforcement is [inferred]. I did not check whether cognee verifies edge domain/range. Per-type merge rules in RAGFlow, KAG and Graphiti beyond what is cited are unread. I did not run a disconfirming search for "schema versioning" in docs or issues, since the brief said source only.

## Engine default entity types (verified in source, 2026-10-03)
- MS GraphRAG v3.2.0: `DEFAULT_ENTITY_TYPES = ["organization", "person", "geo", "event"]`
  — packages/graphrag/graphrag/config/defaults.py:42
- LightRAG v1.5.7: `PROMPTS["default_entity_types_guidance"]` — 11 types + `Other` fallback:
  Person, Creature, Organization, Location, Event, Concept, Method, Content, Data, Artifact, NaturalObject
  — lightrag/prompt.py:17-34 (each type has a one-line definition with examples)
- neo4j-graphrag 1.22.0: no default type list; `additional_node_types`/`additional_relationship_types`
  default factories decide openness — src/neo4j_graphrag/components/schema.py:469-472
