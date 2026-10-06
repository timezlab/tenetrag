# Define the graph schema as versioned, layered domain packs

**Status:** accepted
**Date:** 2026-10-04
**Deciders:** Liam Lee (session 2026-10-03 to 2026-10-04)

## Context
Defining the graph is the hardest part of building GraphRAG for a domain,
and it takes domain knowledge. The author wants users to pick a default
schema for their field and adapt it, with tooling that makes a good schema
cheap to reach.

Research on 2026-10-03 is summarized in
[graph-schema-design.md](../reference/graph-schema-design.md):
- A customizable type list is table stakes. All 13 engines read in source
  offer one, but most only inject it into the prompt. None records a schema
  version on extracted items, re-extracts selectively after a schema change,
  or designs a schema from target questions.
- Type definitions with examples improve extraction (GoLLIE). Showing the
  LLM only the relevant part of a large schema raises F1 and cuts tokens
  (EDC, SchemaRAG). LLM-drafted schemas need human review (Lippolis et al.).
  How much a domain schema helps downstream QA is not settled: the cleanest
  ablation found is about +3 F1.
- Some target platforms reject `$ref`, `anyOf`, `oneOf`, `allOf` and
  `pattern` in structured output and cap a schema at 64 keys
  ([databricks-platform.md](../reference/databricks-platform.md)).
- LinkML is the closest existing format, but it pulls about 28 dependencies,
  its generators emit `$ref` and `anyOf`, and it has no time or evidence
  qualifiers.
- Several domain standards carry licenses that forbid copying their text
  into a permissive SDK (schema.org share-alike, SNOMED CT, ACORD, LDC
  corpora).

## Decision
1. **The schema is a domain pack**: a versioned YAML file with entity types,
   relation types, event types, fact types, attributes, enums, identity
   keys, a "not an entity" list, competency questions, and optional
   retrieval hints and standard mappings. The full format is in
   [domain-packs.md](../product/domain-packs.md).
2. **Three layers of ownership.**
   - The engine owns the evidence layer: Document and Chunk nodes, and on
     every relation, event and fact the fields `valid_from`, `valid_to`,
     `observed_at`, `recorded_at`, `doc_id`, `chunk_id`, `quote`, `status`
     and the pack version. No pack can remove or redefine them.
   - Packs define the domain: entity types, relations with endpoint types
     and a time kind, and n-ary event and fact types with typed roles. A
     fact is what one source states, so two sources that disagree give two
     facts.
   - Fine distinctions are enum values (taxonomies), not new types: a bank
     is an `Organization` with `category: bank`.
3. **Packs stack.** `core` is always present. A domain pack declares
   `extends: core`; a user pack extends one or more domain packs. A child
   pack adds types, adds fields to inherited types and adds enum values.
   Conflicting definitions fail with a `ConfigError`. Removing or renaming
   goes through `deprecated` and `renamed_from`.
4. **The pack drives four places**, not only the prompt:
   - extraction: the prompt and a compiled structured-output schema;
   - validation in code, with every dropped item reported with a reason;
   - entity resolution, through each type's identity keys;
   - retrieval, through type filters and optional hints.
5. **Strict by default.** In `discovery` mode, types the LLM proposes go to a
   review queue. The SDK never adds a type to a pack on its own.
6. **Format.** Own YAML using LinkML field names where they exist
   (`description`, `examples`, `aliases`, `is_a`, `identifier`, `range`,
   `required`, `exact_mappings`, `deprecated`). No runtime dependency on the
   `linkml` package. The SDK compiles each pack into flat JSON Schemas:
   type names become enums, attributes become key/value lists, no `$ref`,
   `anyOf`, `oneOf`, `allOf` or `pattern`, at most 64 keys per call. A pack too large for one call is
   split into passes or narrowed per chunk.
7. **Index-time vs query-time** ([ADR 0005](0005-index-time-vs-query-time-parameters.md)):
   the pack's extraction and resolution content is index-time; its
   `retrieval` section is query-time. The pack name and version replace
   "entity types" in the profile.
8. **Licensing.** TenetRAG writes every type name and definition in its
   default packs. External standards appear only as IRIs under `mappings`.
   No SNOMED CT, UMLS, ACORD or LDC content.
9. **v1 ships three packs: `core`, `enterprise-docs` and `finance`.** Each
   comes with competency questions and synthetic test documents. Other
   domains (legal-regulatory, it-ops, cyber, biomedical and the rest in the
   catalog) come later or from the community. Industry packs such as
   banking are user packs that extend `enterprise-docs`; an adopter keeps
   its own outside this repository.

## Alternatives considered
- **A type list injected into the prompt** (MS GraphRAG, LightRAG).
  Rejected: off-schema output leaks into the graph unseen, and the list
  cannot drive validation, resolution or retrieval.
- **Adopt LinkML as the runtime format.** Rejected for the dependency weight,
  the `$ref` and `anyOf` output and the missing time and evidence semantics. Keeping
  its field names leaves a LinkML exporter cheap to add later.
- **OWL or SHACL.** Rejected: the SDK needs validation and prompting, not
  reasoning, and contributors would face a steep format.
- **One flat schema per user, no layering.** Rejected: cross-domain links
  and cross-pack entity resolution need shared `Person` and `Organization`
  types, and every user would start from a blank page.
- **Let the LLM induce the schema with no review** (youtu-graphrag,
  AutoSchemaKG). Rejected as the default: drafts are useful, but types
  appear unreviewed and drift. Induction stays available as a draft step.
- **Ship many packs in v1** (all 13 domains surveyed). Rejected: a default
  pack is only credible with its own questions and test documents, and
  untested packs would set a low bar.
- **Include `legal-regulatory` in v1.** Considered; the author chose `core`,
  `enterprise-docs` and `finance` for the first release.
- **A default `banking` pack, or commercial types in `enterprise-docs`.**
  Rejected on 2026-10-04: a bank's internal documents fit `core` plus
  `enterprise-docs`, and a draft banking layer added only campaigns,
  segments, product terms and vocabulary. No standard or vendor found
  separates a banking document schema from finance. These types live in
  user packs ([v1-packs.md](../product/v1-packs.md#industry-packs-such-as-banking)).
- **Call source statements "claims"**, as MS GraphRAG does. Rejected on
  2026-10-04: the author chose "fact" as the plainer word. An edge between
  two entities is called a relation.

## Consequences

**Better:**
- Users start from a tested pack and edit it, instead of authoring a schema
  from nothing.
- Every dropped extraction has a reason, so schema problems show up in a
  trial on sample documents rather than after a full, paid index run.
- Shared `core` types let finance items and internal-document items meet on
  the same `Organization` and `Person` nodes.
- Recording the pack version on every item prepares selective
  re-extraction, which no engine offers today.

**Worse:**
- The SDK owns a schema compiler, a merge step and a validator that a
  prompt-only design would not need.
- Attributes as key/value lists move type checking from the LLM's
  structured output into our validator.
- Each default pack is a maintenance commitment: definitions, questions,
  test documents and mappings.

**Must now be true:**
- Every entity, relation, event and fact row records the pack name and
  version that produced it.
- A `packs` module loads, merges, checks and compiles packs. It imports only
  the standard library, Pydantic and PyYAML, and `engine` may import it
  ([ARCHITECTURE.md](../../ARCHITECTURE.md)).
- Compiled extraction schemas contain no `$ref`, `anyOf`, `oneOf`, `allOf`
  or `pattern` and at most 64 keys, enforced by a test.
- Each shipped pack has competency questions, synthetic test documents and
  a coverage check that runs in CI.
- No default pack contains text copied from schema.org or any other
  share-alike or licensed source. A NOTICE file lists attributions for any
  reused permissive content.
- The benchmark can run three schema variants on one corpus: no schema,
  `core` only, and `core` plus a domain pack.

## Revisit if
- The benchmark shows `core` plus a domain pack does not beat `core` alone
  on the target question types.
- Target LLM platforms lift the `$ref`, `anyOf` and key-count limits, which would
  allow richer compiled schemas.
- A pack format gains real adoption among GraphRAG tools, making an
  importer worth more than our own YAML.
