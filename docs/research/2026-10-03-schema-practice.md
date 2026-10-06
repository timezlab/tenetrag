# Schema design practice for LLM-extracted knowledge graphs

> **Snapshot, 2026-10-03 — not maintained.** Web lane on vendor and practitioner guidance; coverage is partial. The maintained,
> re-verified summary is in [graph-schema-design.md](../reference/graph-schema-design.md); where they differ, the maintained doc
> wins. Local paths were removed before publishing.
>
> **Errata and later resolutions:**
> - The Semantic Arts PDF that this lane could not parse was later read in full;
>   the note is appended at the end.
> - "Start with 3–5 types" and "30+ types cause high error rates" come from a
>   search-result paraphrase of unknown origin. Treat them as unverified.
> - The Neo4j node/relationship/property decision table was seen only through
>   third-party mirrors.

## Schema design practice for LLM-extracted KGs (2026-10-03). Coverage: partial, see Gaps.
Labels: primary | secondary | opinion | measured | inferred. "Fetched" = page body read; "snippet" = search snippet only.

### 1. Vendor/framework guidance
- Graphiti/Zep (fetched, primary, undated docs): PascalCase types, snake_case attributes; make attributes optional; typed fields (datetime/int) not strings; atomic fields; descriptive docstrings/field descriptions "specific and actionable"; avoid excessive granularity (one `Employment` with position attribute, not CEOEmployment/EngineerEmployment); edge_type_map restricts edges per entity pair; unmapped pairs keep free predicate; schema can evolve by adding attributes without breaking history. https://help.getzep.com/graphiti/core-concepts/custom-entity-and-edge-types
- Neo4j GraphRAG python blog (fetched, primary, 2025): strict for well-defined domains; required properties drop entities lacking them; FREE / EXTRACTED / strict modes; "start simple for exploration, add constraints incrementally"; save inferred schema and refine rather than rebuild; pruning logs reasons to guide iteration. https://neo4j.com/blog/developer/unleashing-the-power-of-schema/
- Cognee (fetched, primary, vendor blog, undated): label fragmentation ("car manufacturer"/"automobile maker"/"vehicle producer") degrades retrieval; ontology + fuzzy match (difflib, default cutoff 80%) canonicalizes; recommends small hand-curated ontology "a few dozen classes", warns broad ontologies (Wikidata) reduce matching precision. https://www.cognee.ai/grounding-ai-memory
- MS GraphRAG auto-tuning (fetched, primary): LLM generates domain-adapted prompts from sample (default 15 text units; up to 300 chunks embedded for selection); entity types either given or auto-discovered, auto-discovery recommended when data is broad/randomized; step "optional, highly encouraged". https://microsoft.github.io/graphrag/prompt_tuning/auto_prompt_tuning/
- AWS graphrag-toolkit (fetched blog, primary, 2025): 3 tiers: lineage (source/chunk), summarization (topic/statement/fact), entity-relationship. Statement = unit of context returned. Topics = local connectivity within source; facts = global cross-source connectivity. Rationale: avoid overwhelming connectivity that dilutes relevance yet keep links for non-obvious relations. https://aws.amazon.com/blogs/database/introducing-the-graphrag-toolkit/
- Barrasa/Neo4j (AI Engineer talk page, fetched, primary, 2025): ontology = implementation-agnostic shared domain description used for both structured mapping and extraction; also used at retrieval: tag "contextualizing" relationships via subPropertyOf so retrievers follow chosen edges (acted_in yes, directed no); store ontology in DB so traversal policy is data not code. https://ai.engineer/talks/why-your-agent-s-brain-needs-a-playbook-practical-wins-from-using-ontologies
- WhyHow (snippet only): schema = entities, relations, patterns; advocates schema-constrained, use-case-specific graphs. https://github.com/whyhow-ai/schemas/blob/main/README.md
- Not reached: Memgraph, Kuzu, Stardog, Ontotext, Enterprise Knowledge, Spanner Graph, Databricks, TrustGraph, FalkorDB docs.

### 2. Graph modeling rules
- Neo4j modeling skill (snippet only, via third-party mirrors of neo4j-contrib/neo4j-skills; secondary): decision table: identity entry point -> node; directed link -> relationship; link with own properties or >2 participants -> intermediate node; scalar always returned with parent -> property; low-cardinality category used to filter -> label; supernode/high-fanout detection is part of guidance. Unverified against original.
- Time: legal-GraphRAG write-up (fetched, opinion, Substack, 2026): valid_from/valid_to on nodes/edges; amendments create new version nodes (ClauseVersion) linked to AmendmentEvent; do temporal reasoning in retrieval layer, not LLM; naive retrieval blends outdated and future clauses; prefers LPG over RDF reification. https://sergeyvasiliev.substack.com/p/temporal-semantics-in-graphrag-for
- Dual time (valid vs observed) with observation time given to LLM as context: from search snippet of temporal-KG literature (arXiv 2510.22590 ATOM; not fetched). inferred/secondary.
- RELATED_TO fallback: snippet mentions tools collapsing domain predicates into RELATED_TO; no quantified source found. opinion.

### 3. Classic ontology method
- Noy & McGuinness 101, OOPS! pitfall catalogue, competency questions: located but only snippets read (https://protege.stanford.edu/conference/2004/cft/101.html; https://scitepress.org/Papers/2013/45179/pdf/index.html). LLM-CQ work: arXiv 2409.08820, 2403.08345 (snippets).
- Semantic Arts (snippet): gist ~100 classes; "Most people are better editors than authors" (supports LLM-draft then human edit); they are not leaning on LLMs for ontology design. PDF "Building an Ontology with LLMs" could not be parsed by fetch (saved at (local path removed) unread).

### 4. Anti-patterns reported
- Over-engineering: "30 entity types and 50 relationship types produces high extraction error rates"; start with 3-5 core types (search-result paraphrase of unknown origin; opinion, unverified).
- Entity dedup skipped -> "false sense of completeness"; only 65.8% of answer entities exist in constructed graphs (tianpan.co 2026-04, fetched; secondary citing research, number measured-by-others; blog has no schema specifics).
- KG decay: drift, duplicates, contradictions (Neo4j NODES AI 2026 abstract, Joshua Yu; no numbers; fetched). Proposes giant-component growth monitoring, GDS dedup.
- Label fragmentation: Cognee above.

### 5. Tooling
- MS GraphRAG prompt-tune; Neo4j SchemaFromText + pruning logs; EDC (EMNLP 2024, abstract fetched: open extract -> LLM define schema -> canonicalize, plus trained schema retriever allowing larger schemas than fit in prompt); Neo4j LLM Graph Builder. No per-type quality report tooling or schema diff/migration tooling found.

### 6. Schema size
- EDC abstract: large schemas exceed context; retrieve relevant schema elements per chunk (primary, paper). Snippets: benchmarks 4/7/45 relation types; some methods emit out-of-schema relations even when schema in prompt. No measured "reliable N types" threshold found.

### Consolidated design rules (n = independent sources agreeing)
1. Start small, curated, iterate from trial runs (Cognee, Neo4j, Graphiti granularity, tianpan opinion): 4.
2. Prefer one generic type + attribute over type proliferation (Graphiti; Neo4j label-vs-property table inferred): 2.
3. Constrain which edge types connect which node-type pairs (Graphiti edge_type_map, Neo4j patterns, WhyHow patterns): 3.
4. Typed, optional, atomic attributes with action-oriented descriptions (Graphiti; Neo4j required-props tradeoff): 2.
5. Canonicalize LLM labels against the schema vocabulary (Cognee, EDC, Neo4j pruning): 3.
6. n-ary facts -> intermediate/event node (Neo4j skill snippet; legal temporal write-up): 2.
7. Time as validity interval + versions/events, filter in retrieval not LLM (legal write-up; Graphiti-style bitemporal): 2.
8. Layered lexical/provenance tier separate from domain tier (AWS; Neo4j lexical pattern): 2.
9. Store retrieval semantics in schema (which edges are contextualizing) (Barrasa): 1.
10. Monitor graph health continuously (Neo4j NODES): 1.

### Anti-pattern table
| Symptom | Cause | Fix | Source |
|---|---|---|---|
| Same concept, many labels | free LLM labels | canonical vocabulary + fuzzy match | Cognee |
| Unreliable typing at scale | 30+ types in prompt | start 3-5, grow after sample validation (opinion) | tianpan/snippet |
| Type explosion CEOEmployment | over-granular edges | one type + attributes | Graphiti |
| Entities silently dropped | strict required props | log prune reasons, relax | Neo4j |
| Outdated clauses retrieved | no temporal filter | validity intervals + versions | legal write-up |
| Dead-end queries | 65.8% answer-entity coverage | dedup, hybrid with vectors | tianpan |
| Matching precision drops | ontology too broad | small curated ontology | Cognee |

### Disagreements
- Free discovery (MS auto-tune for broad data) vs strict curated schema (Cognee, Neo4j for defined domains): depends on domain breadth.
- Semantic Arts skeptical about LLM-authored ontologies vs EDC/Neo4j schema-from-text automation.

### Gaps
No first-hand production write-up with before/after numbers on schema changes or re-index cost; no schema-size threshold measurement; most vendor claims undated or unverified; Noy/OOPS/NeOn not deep-read; Memgraph/Stardog/Ontotext/Databricks/Spanner not covered; PDFs (EDC full, Semantic Arts) unparsed.


## Dave McComb (Semantic Arts), "Building an Ontology with LLMs", June 2025 (4-page PDF, read in full 2026-10-03)
Source: semanticarts.com PDF (copy saved by the practice lane under the session tool-results dir). Vendor opinion, no measurements.
- Their practice does not use LLMs to design ontologies; an LLM-built financial reporting ontology (based on gist) "would have tossed out every line".
- Concedes a market for one-click ontology drafts: "Most people are better editors than authors."
- Small is beautiful: gist ~100 classes + ~100 properties (~200 concepts).
- Move many distinctions out of the ontology into taxonomies maintained by SMEs; "many thousands of distinctions in taxonomies" without growing the model.
- Client core ontologies: gist doubled/tripled to 400–600 concepts; no firm needed more than ~1000 concepts (classes + properties).
- Firms in the same industry share ~70–80% of core concepts; claims no useful industry ontologies found yet.
- Recommends LLMs for extraction from text, not ontology authoring.
