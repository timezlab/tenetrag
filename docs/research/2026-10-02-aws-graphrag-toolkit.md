# AWS graphrag-toolkit lexical graph, and a review of a graph-first retrieval flow

> **Snapshot, 2026-10-02 — not maintained.** Follow-up code research on
> awslabs/graphrag-toolkit `lexical-graph` v3.19.1 and LightRAG v1.5.7 chunk
> selection, read to review a proposed graph-first retrieval flow. The
> maintained summary is in
> [graphrag-engines.md](../reference/graphrag-engines.md) and
> [graphrag-research.md](../reference/graphrag-research.md#inputs-for-the-engine-brief-inferred);
> where they differ, the maintained doc wins. The review was prompted by a
> screenshot of a demo graph built from adopter documents. The screenshot is
> not reproduced, and every example here is synthetic.
>
> **Errata and later resolutions:**
> - The first, chat-only version of this review said the toolkit enters the
>   graph by name matching rather than by vector search. Source shows the
>   default is the reverse: vector search over chunks or topics first, then
>   the entities mentioned there (section 5). Name matching is the
>   non-default `EntityProvider`.

Pins: **AW** = `github.com/awslabs/graphrag-toolkit/blob/graphrag-lexical-graph/v3.19.1/`,
with `L/` = `lexical-graph/src/graphrag_toolkit/lexical_graph/` and
`D/` = `docs-site/src/content/docs/lexical-graph/`.
**LR** = `github.com/HKUDS/LightRAG/blob/v1.5.7/lightrag/`.
Labels: **[source]** read in code · **[docs]** project docs · **[observed]**
seen in one demo graph for one query · **[inferred]** our reasoning.

## 1. Question

The author's proposed flow:
- The graph holds precise, typed entities (date, person, product, meeting
  and so on), not sentences.
- Retrieval walks the graph first and returns a subgraph for the query.
- An LLM reads the subgraph and writes queries for a vector search over
  chunks. The alternative is an algorithm that maps the subgraph to chunks.
- A final vector search over chunks picks the exact chunks and trims
  surplus relations.

The trigger was the toolkit's demo, where retrieval returned statements
(whole sentences) and facts as graph nodes. The answer context was complete,
but it raised two questions: what a node should be, and whether such a graph
is clean enough to search.

## 2. The project

- `awslabs/graphrag-toolkit`: Apache-2.0, 445 stars, 106 forks, 30
  contributors, created 2024-11-15, last push 2026-09-30. It ships two
  packages, `lexical-graph` (this note) and `byokg` (bring your own KG), both
  at v3.19.1 (2026-08-26) [source].
- Graph stores: Amazon Neptune (Database and Analytics), Neo4j, FalkorDB
  (contrib). Vector stores: OpenSearch Serverless, Neptune Analytics,
  Postgres with pgvector, S3 Vectors. There is no Postgres graph store
  [source: `L/storage/`].
- Built on LlamaIndex. Multi-tenancy and metadata filtering are supported
  [docs].

## 3. Graph model

From `D/graph-model.mdx` [docs]:

| Tier | Nodes | Role |
|---|---|---|
| Lineage | `__Source__`; `__Chunk__` (text and embedding; previous, next, parent, child links) | Provenance |
| Summarisation | `__Topic__` (scoped to one source document), `__Statement__`, `__Fact__` | Units of context and connectivity |
| Entity-relationship | `__Entity__` (value and classification); `__RELATION__` edges | Entry points |

- A statement is "a standalone assertion or proposition" and "the primary
  unit of context returned to the question-answering LLM". The context is a
  set of statements grouped by source and topic.
- A fact is one triple. SPO facts link to subject and object entities. SPC
  (subject-predicate-complement) facts link to the subject only, for
  example `Neptune Analytics PURPOSE analyze graph data`. A distinct fact is
  one node across the corpus, and every fact `__SUPPORTS__` at least one
  statement.
- Topics connect statements within one source (local connectivity). Facts
  connect statements across sources (global connectivity).
- Statements can carry inline "details": triple-shaped items with no
  entity link.
- Chunks are always embedded. Topics, statements and facts are embedded
  optionally.
- The doc warns about topology itself: "If everything is linked to
  everything else, it becomes difficult to extract particularly relevant
  units of context from within a sea of irrelevancy."

## 4. Indexing

Two LLM calls per chunk, both in `L/indexing/prompts.py` [source]:

1. `EXTRACT_PROPOSITIONS_PROMPT` decomposes text into "context-independent
   propositions". Its rules include "Preserve original phrasing from the
   input text whenever possible", "Replace any acronyms with their full
   forms", replacing pronouns, and "Add a proposition per named entity that
   classifies that entity". Propositions are therefore LLM rewrites, not
   verbatim spans.
2. `EXTRACT_TOPICS_PROMPT` groups propositions into topics and extracts
   entities, `entity|RELATIONSHIP|entity` and `entity|ATTRIBUTE_NAME|value`.
   - "DO NOT treat numerical values, dates, times, measurements, or object
     attributes (e.g. size, colour) as entities."
   - Relation names are "all uppercase, with underscores", using "general
     and timeless relationship types".
   - Attributes end up as SPC facts, that is, as graph nodes.

- Entity classifications are seeded with a preferred list, and new ones
  are carried forward between calls. "Relationship values are currently
  unguided" [docs].
- Both prompts are in English and give no output-language instruction
  [source].

## 5. Retrieval

The recommended mode is traversal-based search. Its default combines
`ChunkBasedSearch` and `EntityNetworkSearch` [docs:
`D/traversal-based-search.mdx`].

**Entry: the entity network context** (`L/retrieval/query_context/`)
[source]:
1. **Keywords.** The default `ec_keyword_provider='vss'`
   (`keyword_vss_provider.py`):
   - Vector search over the topic index, or the chunk index when there is
     no topic index (top 3, diversity factor 5).
   - Then one LLM call (`IDENTIFY_RELEVANT_ENTITIES_PROMPT`) picks up to N
     named entities from the question and keywords from that context.
   - The `llm` mode instead extracts keywords from the question alone
     (`keyword_provider.py`).
2. **Entities.** The default `ec_entity_provider='vss'`
   (`entity_vss_provider.py`):
   - Vector search with the keywords over chunks or topics (top 3).
   - Then the entities mentioned by those hits' statements, scored by
     fact count.
   - The alternative `EntityProvider` (`entity_provider.py`) matches a
     normalized `search_str` exactly.
3. **Expansion and hub pruning** (`entity_context_provider.py`):
   - Neighbours are scored by number of facts.
   - An entity is kept only if its score is between 0.1× and 10× the top
     entity's (`ec_min_score_factor`, `ec_max_score_factor`).
   - Paths have up to `ec_max_depth=3` entities.
   - The top `ec_max_contexts=3` paths survive reranking; the default
     reranker is `tfidf`.

**Retrievers:**

| Retriever | Starts from | Then |
|---|---|---|
| `ChunkBasedSearch` | Vector search over chunks | Topics, statements and facts of those chunks |
| `EntityBasedSearch` | Entities in the entity network | Facts, statements, topics |
| `EntityNetworkSearch` (`L/retrieval/retrievers/entity_network_search.py`) | Each entity-network path rendered as text and used as a vector query over topics or chunks | Statements of the hits: content "similar to 'something different from the question being asked'" |
| `TopicBeamSearch` | Topic vector search | Beam search over topics (width 100, depth 6), then their statements |

- **Semantic-guided search is discouraged.** This mode embeds every
  statement. The docs list "High storage costs", "queries often taking
  minutes" and "Expected to be removed in future releases". The recommended
  setup builds only the chunk index [docs].
- **Result shape.** Results are grouped source → topic → statements. Each
  statement carries its facts, chunk id, score and the retrievers that found
  it [docs].
- **Default limits:** `max_statements=200`, `max_search_results=5`,
  `max_statements_per_topic=10`, `vss_top_k=10`
  (`L/retrieval/processors/processor_args.py`) [source].

## 6. Versions and delete

Sources: `D/versioned-updates.mdx` [docs], `L/versioning.py` [source].

- Versions are per document. A stable identity comes from caller-chosen
  metadata fields (`id_fields`). A new version is `valid_from` its
  extraction time (or a caller-supplied time), and the previous version gets
  `valid_to`.
- Delete removes the document's source, chunk, topic and statement nodes
  "and any orphaned facts and entities". There is no per-fact validity.

## 7. LightRAG related-chunk selection

[source]
- `_find_related_text_unit_from_entities` (LR `operate.py#L6136`) gathers
  each entity's `source_id` chunks, de-duplicates them across entities and
  counts occurrences. The same logic serves relations (`operate.py#L6387`).
- `KG_CHUNK_PICK_METHOD` defaults to `VECTOR`
  (`constants.py`: `DEFAULT_KG_CHUNK_PICK_METHOD = "VECTOR"`).
  - `pick_by_vector_similarity` (`utils.py#L5965`) ranks the candidate
    chunks by cosine to the query.
  - It keeps `related_chunk_number × entities / 2` of them; the default
    `related_chunk_number` is 5.
  - `WEIGHT` instead polls by occurrence count. `VECTOR` falls back to
    `WEIGHT` on an error or an empty result.
- `env.example`: "If reranking is enabled, the impact of chunk selection
  strategies will be diminished."

This is the proposed flow's last step, already shipped as a default.

## 8. What the demo graph showed

[observed] One query on one demo graph; the examples are synthetic
stand-ins.
- **One piece of knowledge appears as several nodes.** A product with five
  pricing tiers shows up as two statements ("Product X has five pricing
  tiers", "Product X uses a five-tier pricing scheme") and two SPC facts
  (`Product X TOTAL TIERS five`, `Product X RANGE tier 1 to tier 5`).
- **Attributes and conditions are fact nodes, not properties.**
- **Relation names are English uppercase** next to Vietnamese entity names.
- **The corpus owner is a hub.** The organisation whose documents these are
  is an entity that nearly every fact touches. Inside its own corpus it
  carries no information, yet it inflates every one-hop expansion. The
  toolkit's degree band (section 5) exists for this.
- **The canvas looks denser than the graph that is searched.** It draws all
  three tiers at once, while the retrievers walk the entity graph.

[inferred] The duplication follows from the design:
- Propositions are decontextualized rewrites, with an extra proposition per
  named entity.
- Attributes are stored as fact nodes.
- Facts appear to collapse only when their text is identical (from the
  doc's "a single node to represent this specific fact").

## 9. Review of the proposed flow

[inferred] A candidate direction for the engine brainstorm, not a decision.

**Verdict.** The direction is sound and close to shipped designs.
LightRAG's `VECTOR` pick is the final step, and `EntityNetworkSearch` turns
a subgraph into vector queries without an LLM. Three changes are proposed.

### 9.1 No LLM between subgraph and chunks

- The candidate chunks are the union of the provenance chunk ids of the
  subgraph's nodes, edges and claims. That is one SQL join.
- Rank the candidates by cosine to the query. The set is small (estimate:
  tens to hundreds), so exact cosine in memory needs no index.
- Add one vector query built from a text rendering of the subgraph, to
  catch facts the extractor missed.
- An LLM rewrite has four costs: an extra model call, non-deterministic
  output, the risk of invented terms, and difficulty caching or evaluating.
- The SDK's callers are agents, so the agent is the LLM in the loop. It
  needs tools: find an entity, neighbours, facts as of a date, sources of a
  fact. RAGSearch (see graphrag-research.md) found that agentic multi-round
  retrieval recovers much of the graph gain.

### 9.2 Graph-first is never the only path

- It fails in three cases:
  - queries with no named entity;
  - facts the extractor missed;
  - single-fact lookups, where plain RAG matches or beats graphs.
- Run hybrid BM25 + vector chunk search in parallel. Its hits seed entities
  through mentions, which is what the toolkit's default entry does. Fuse
  the two with RRF.
- This makes hybrid retrieval a branch of the default retriever, not only a
  benchmark baseline. That bears on the pending change to brief success
  criterion 5 and ADR 0001.

### 9.3 Node model

| Kind | What | Examples |
|---|---|---|
| Entity node | Has identity, can be resolved, typed by the profile | Product, Project, Person or Role, Organisation unit, Metric |
| Event node | Something that happened, with a date, participants and sources | Meeting, Decision, Definition |
| Not a node | Claim: verbatim quote, chunk id and offsets, attached to an edge or entity. Attribute: date, number, value range | "five pricing tiers" is an attribute or a claim |

- **Dates are not nodes.** A date node becomes a hub (every March document
  links to it). Time is a column used to filter as-of questions (Inputs
  item 4 in graphrag-research.md).
- **Claims keep what statements give without polluting the graph.**
  Claims give sub-chunk precision and sentence-level evidence. Unlike the
  toolkit's propositions, their quote is verbatim and checked against the
  chunk (RAGFlow rc1).

### 9.4 Trimming surplus relations

The final chunk ranking trims chunks, not edges. Three more filters:
- **When expanding:**
  - follow typed paths declared in the profile, for example Product →
    Decision → Meeting;
  - cap the number of hops;
  - penalize hubs, either with the toolkit's degree band or with an
    IDF-style weight (the inverse of the number of chunks mentioning the
    entity).
- **Score edges:** compare each edge's claims with the query and keep the
  top N.
- **Keep only evidence-backed edges:** after picking the top-k chunks, keep
  only edges whose evidence lies in those chunks. The returned graph and
  text then agree, and the app's retriever view can show edge → chunk →
  quote.

### 9.5 Proposed flow

```
query
 ├─ A. entity linking: alias/exact → trigram → name embedding (Vietnamese–English aliases)
 └─ B. hybrid chunk search: BM25 + vector → top chunks → entities mentioned in them
        ▼
 seed entities (A ∪ B)
        ▼
 expand 1–2 hops: type filter, time filter, hub penalty, edge scoring → subgraph
        ▼
 candidate chunks = provenance(subgraph) ∪ B's chunks ∪ vector(text of subgraph)
        ▼
 rank by query vector (+ optional reranker) → top-k
        ▼
 output: evidence-backed subgraph + chunks + quotes
```

### 9.6 Where cleanliness is decided

Cleanliness is decided at index time, by three things:
- the profile's entity and relation types;
- claim extraction with checked quotes;
- entity resolution.

The demo graph's main defect was duplication, and no retriever fixes that.
Suggested order for the brainstorm: data model, then extraction and
resolution, then retrieval.
