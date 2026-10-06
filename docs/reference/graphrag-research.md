# GraphRAG research — what the evidence says

**Verified:** 2026-10-02. Read in full: MaGiX. Read as abstract or HTML
text: the rest. Figures were copied from those pages and some went through a
summarizer, so re-check a figure against the paper's table before quoting it.
Code-level details of the engines named here:
[graphrag-engines.md](graphrag-engines.md).
Raw lane reports (snapshots, not maintained): [papers](../research/2026-10-02-papers.md),
[MaGiX full read](../research/2026-10-02-magix.md),
[AWS graphrag-toolkit and a retrieval-flow review](../research/2026-10-02-aws-graphrag-toolkit.md),
[query strategies](../research/2026-10-04-query-strategies.md) (2026-10-04).

Labels: **[peer-reviewed]** · **[preprint]** · **[vendor]** (authored by the
company selling it) · **[inferred]** our reasoning.

## Where graphs help and where they do not

| Question type | Finding | Source |
|---|---|---|
| Single-hop fact | Vanilla RAG matches or beats graph methods. NQ F1: RAG 64.78, KG-GraphRAG 50.27, Community-Local 63.01 (Llama 3.1-8B). Fact retrieval on a novel corpus: RAG 60.92, MS GraphRAG 49.29. | Han et al. [arXiv 2502.11371](https://arxiv.org/abs/2502.11371) [preprint]; GraphRAG-Bench [arXiv 2506.05690](https://arxiv.org/abs/2506.05690) [preprint] |
| Triples instead of chunks | Triple-only context is clearly worse: MultiHop-RAG accuracy 48.51 vs 67.02 for RAG. | Han et al. |
| Multi-hop / reasoning | Graph methods win modestly: HippoRAG 2 53.38 vs RAG 42.93 on complex reasoning; Community-Local 69.01 vs 67.02 on MultiHop-RAG. | GraphRAG-Bench; Han et al. |
| Temporal (news-time comparisons) | Larger gain from a low base: 50.60 vs 30.70 on MultiHop-RAG temporal queries. Not versioned facts or as-of queries. | Han et al. |
| Global summarization | Community methods win (64.40 vs 51.30) at 40–50× the prompt tokens (up to ~4×10⁴ vs ~879). | GraphRAG-Bench |
| Hybrid graph + chunks | More robust than either alone: +6.4 % over the best single method (Llama 70B). | Han et al. |
| Agent-driven search | Multi-round agentic search over dense RAG narrows the gap to GraphRAG; GraphRAG keeps an edge on complex multi-hop and is more stable. | RAGSearch [arXiv 2604.09666](https://arxiv.org/abs/2604.09666) [preprint] |
| Cross-lingual Vietnamese ↔ English | Dense BGE-M3 far exceeds GraphRAG-Local and LightRAG on retrieval recall; HippoRAG 2 is slightly above dense; MaGiX is best. See [MaGiX](#cross-lingual-vietnamese--english-magix). | MaGiX [peer-reviewed] |
| Enterprise hybrid search | Vector (0.50) + BM25 (0.35) + KG neighbour expansion (0.15) via RRF (k = 60), then cross-encoder rerank: P@10 0.69 (+15 pts over dense only), R@10 0.79. No ablation separating BM25 from KG. | DocuSearch [arXiv 2609.01617](https://arxiv.org/abs/2609.01617) [preprint, one telecom corpus] |
| Enterprise code-migration data | Vector + graph traversal fused by RRF: up to +15 % and +4.35 % over vector baselines (LLM judge). | Practical GraphRAG [arXiv 2507.03226](https://arxiv.org/abs/2507.03226) [preprint] |

**Untested anywhere:** entity-centric aggregation with provenance ("every
decision and definition about X"), as-of queries over edited documents with
conflicting definitions, and knowledge graphs over Vietnamese enterprise
documents. Conclusions for those come from extrapolation. Our own golden set
is the only direct evidence we will have.

## Evaluation pitfalls in the literature

- **LLM-judge bias.** Position, length and trial biases, plus questions
  unrelated to the corpus, inflate reported GraphRAG gains. Under a bias-
  controlled protocol the gains are "much more moderate". Han et al. also
  found that swapping summary order flips judgments. Sources: Zeng et al.
  [arXiv 2506.06331](https://arxiv.org/abs/2506.06331) [preprint]; Han et al.
- **Weak baselines.** Cost reductions (KET-RAG, E2GraphRAG, MiniRAG,
  LazyGraphRAG) are measured against full MS GraphRAG, the most expensive
  baseline. None compares against a tuned hybrid BM25 + dense RAG.
- **Self-built benchmarks and single runs.** T-GRAG
  ([arXiv 2508.01680](https://arxiv.org/abs/2508.01680)) evaluates on its
  own Time-LongQA. post-graph-rag
  ([arXiv 2608.24921](https://arxiv.org/abs/2608.24921)) reports single runs,
  compares against other papers' published numbers, and uses a newer answering
  model than its baselines.
- **Vendor memory benchmarks.** Zep reports DMR 94.8 % vs MemGPT 93.4 % and
  up to +18.5 % on LongMemEval ([arXiv 2501.13956](https://arxiv.org/abs/2501.13956)) [vendor].
  A third-party unified evaluation could not finish Zep's memory construction
  on LongMemEval within two days on 8 A100s and reports poor token-cost
  scaling from update overheads ([arXiv 2604.01707](https://arxiv.org/abs/2604.01707)) [preprint].

## Cross-lingual Vietnamese ↔ English: MaGiX

Nguyen Manh Hieu et al., "MaGiX: A Multi-Granular Adaptive Graph
Intelligence Framework for Enhancing Cross-Lingual RAG", Findings of EMNLP
2025, pp. 5202–5219 ([PDF](https://aclanthology.org/2025.findings-emnlp.279.pdf))
[peer-reviewed]. Hanoi University of Science and Technology, VNU-UET,
University of Oregon. No code link in the paper.

**Method.**
- **Extraction.** LightRAG-style LLM triples.
- **Entity descriptions.** Each entity keeps one contextual attribute
  description per chunk it appears in, and is not merged into a single
  summary. Each description is embedded as `name ‖ attribute`.
- **Cross-synonym edges.** Two entities get a synonym edge when any pair of
  their attribute embeddings exceeds a threshold, and the edge is called
  cross-synonym when they are in different languages. Entities are linked,
  never merged.
- **Retrieval.**
  1. Seeds are the top attribute and edge-description embeddings, mapped to
     their chunks.
  2. Expansion follows synonym edges.
  3. Chunks are ranked by a min-max-normalized weighted sum of three scores:
     chunk similarity, attribute similarity and triple similarity.
- **Embedding.** A fine-tuned multilingual model (SimCSE, then contrastive
  training on synthetic bilingual pairs).

**Recall@10, query in one language, passages in the other (vi→en / en→vi):**

| | ZaloWikiQA | ZaloLegal2021 | NQ | PopQA | MuSiQue |
|---|---|---|---|---|---|
| BGE-M3 dense | 76.29 / 75.92 | 64.17 / 61.95 | 81.62 / 81.63 | 45.15 / 46.22 | 46.58 / 44.86 |
| GraphRAG-Local | 18.24 / 32.80 | 18.76 / 16.06 | 22.99 / 19.47 | 17.12 / 18.14 | 17.25 / 15.44 |
| LightRAG-Local | 17.05 / 27.17 | 16.61 / 16.61 | 23.11 / 27.71 | 23.32 / 26.65 | 20.30 / 22.01 |
| HippoRAG 2 | 79.27 / 75.26 | 66.19 / 60.23 | 84.56 / 84.14 | 49.45 / 48.49 | 55.53 / 50.98 |
| MaGiX | 81.32 / 85.45 | 68.02 / 65.26 | 87.79 / 87.27 | 50.65 / 50.85 | 60.37 / 58.43 |

**Ablation (vi→en, NQ / PopQA / MuSiQue).**
- Starting point: LightRAG at 23.11 / 23.32 / 20.30.
- Granular per-chunk descriptions: 78.90 / 49.10 / 48.86. This is the
  largest gain.
- Cross-synonym edges: 80.73 / 49.20 / 51.21.
- Composite score: 88.58 / 50.08 / 56.96.
- Fine-tuned embedding: 87.79 / 50.65 / 60.37. A small gain, and a slight
  drop on NQ.

Removing chunk similarity from the composite score costs the most (87.79 →
73.91 on NQ).

**Caveats.**
- The cross-lingual sets are machine translations (Gemini 2.0 Flash) of
  Wikipedia and legal QA, not enterprise documents.
- Answer quality is LLM-judged win rates (Grok-3).

**What it suggests for us** [inferred]:
- Keep per-chunk statements instead of merged descriptions.
- Rank by chunk similarity first.
- Link cross-language aliases by embedding name plus context.
- Treat a strong dense baseline as the bar any graph retriever must clear.

## Temporal knowledge

- **Bi-temporal edges** (Zep/Graphiti, [arXiv 2501.13956](https://arxiv.org/abs/2501.13956)) [vendor]:
  - The time a fact holds is kept separate from the time the system learned it.
  - Contradicted edges are invalidated, not deleted.
  - The design fits our need. Its default of hiding older facts does not.
- **Temporal grounding at synthesis** (post-graph-rag) [preprint, single run]:
  - Validity intervals are rendered into the answer prompt.
  - The paper reports a temporal-reasoning score rising from 0.496 to 0.881.
- **Dated event units** (DyG-RAG, [arXiv 2507.13396](https://arxiv.org/abs/2507.13396)) [preprint]:
  - The retrieval unit is an event with a temporal anchor.
  - Traversal is time-aware.
  - This matches decisions recorded in meeting minutes [inferred].
- **No benchmark tests "as of date D" over edited documents with conflicting
  definitions.**

## Indexing cost

| Method | Claim | Evidence |
|---|---|---|
| LazyGraphRAG | Indexing cost equal to vector RAG and 0.1 % of full GraphRAG; global-query quality comparable at > 700× lower query cost | [Microsoft blog](https://www.microsoft.com/en-us/research/blog/lazygraphrag/) [vendor]; one news corpus, 100 synthetic queries, LLM judge; no public code |
| KET-RAG | LLM extraction only on a budgeted "skeleton" of chunks; > 10× lower indexing cost than MS GraphRAG | [arXiv 2502.09304](https://arxiv.org/abs/2502.09304) [preprint] |
| E2GraphRAG | spaCy entity graph plus summary tree; up to 10× faster indexing than GraphRAG | [arXiv 2505.24226](https://arxiv.org/abs/2505.24226) [preprint]; English spaCy |
| Practical GraphRAG | Dependency-parse graph reaches 94 % of LLM extraction quality (61.87 vs 65.83) | [arXiv 2507.03226](https://arxiv.org/abs/2507.03226) [preprint]; English |
| HippoRAG 2 | 2 LLM calls per chunk (NER, then triples); no training | [arXiv 2502.14802](https://arxiv.org/abs/2502.14802) [peer-reviewed, ICML 2025] |

The cheap-extraction results rest on English NLP tools. A Vietnamese
equivalent needs its own tagger or parser and its own evaluation.

## Knowledge-graph construction and entity resolution

- **Extract, define, canonicalize** (EDC, [arXiv 2404.03868](https://arxiv.org/abs/2404.03868),
  EMNLP 2024) [peer-reviewed]: extract open triples first, then
  canonicalize relations. The verbatim text survives the extraction step.
- **Schema induction** (AutoSchemaKG, [arXiv 2505.23628](https://arxiv.org/abs/2505.23628),
  [ACL 2026](https://aclanthology.org/2026.acl-long.942/)) [peer-reviewed]:
  - The abstract reports 92 % semantic alignment with human-crafted schemas
    (corrected 2026-10-03; an earlier version of this page said 95 %, a
    figure that appears only in the paper's introduction).
  - It is web-scale and English.
  - Schema design evidence in general:
    [graph-schema-design.md](graph-schema-design.md).
- **LLM entity matching.**
  - Search snippets report pairwise F1 up to 98.95 % against 91.33 % for
    rules. No primary paper was read.
  - The reported failures are cross-script transliteration and inconsistent
    dates or identifiers.
- **Vietnamese NER** (En-ViMedNER, [arXiv 2608.29890](https://arxiv.org/abs/2608.29890),
  biomedical) [preprint; finding taken from a search snippet]: few-shot LLMs
  improve with prompting but stay below supervised encoders.
- **What identifies an entity.** Read for
  [ADR 0016](../decisions/0016-identify-entities-by-scope-keys-and-vetoes.md);
  details and labels in the
  [identity criteria snapshot](../research/2026-10-05-entity-identity-criteria.md#2-what-the-literature-says-identity-is).
  - An identity criterion has a sufficient side, which proves two things
    the same, and a necessary side, which proves them different. Properties
    that change while the thing stays, such as a role or a department,
    cannot carry identity (OntoClean, Guarino & Welty 2004) [book]. Our
    keys are the sufficient side and our vetoes the necessary side.
  - A minimal key has no subset that is also a key (ROCKER,
    [arXiv 1705.04380](https://arxiv.org/abs/1705.04380), WWW 2015)
    [peer-reviewed]. Keys can hold only within part of the data (VICKEY,
    ISWC 2017) [peer-reviewed; abstract only]. "A unit's name is unique
    within its parent" is such a key, and the scope is its condition.
  - Requiring name and affiliation to agree splits true entities, and
    requiring only the name merges distinct ones (Li et al., *Linking
    temporal records*, PVLDB 2011) [peer-reviewed].
  - Unconstrained identity links go wrong often: estimates of wrong
    `owl:sameAs` links range from 2.8 % to 20 % (Raad et al.,
    [arXiv 1907.10528](https://arxiv.org/abs/1907.10528)) [survey].
  - Generalized merge distance lets a wrong merge cost more than a wrong
    split (Menestrina et al., VLDB 2010) [peer-reviewed; abstract only].
- **Gaps:**
  - No study of Vietnamese entity resolution or diacritic variants.
  - No paper measures how often documents state the attributes a key
    needs, or how well an LLM extracts them.
  - No 2024–2026 benchmark for extracting decisions or action items from
    written minutes. The AMI decision-detection work targets speech
    transcripts.

## Other retrieval ideas (abstract level)

| Idea | Core | Fit note [inferred] |
|---|---|---|
| HippoRAG 2 | Personalized PageRank over entity + passage nodes; LLM filter on seed facts | Runs on edge tables with scipy; best graph method on GraphRAG-Bench reasoning |
| Dense X Retrieval ([arXiv 2312.06648](https://arxiv.org/abs/2312.06648), EMNLP 2024) | Propositions as the retrieval unit beat passages and sentences | Propositions are LLM rewrites; link each to its verbatim source span |
| RAPTOR ([arXiv 2401.18059](https://arxiv.org/abs/2401.18059), ICLR 2024) | Recursive cluster-and-summarize tree; +20 % absolute on QuALITY with GPT-4 | Generative summaries lose verbatim figures; edits force re-clustering |
| Think-on-Graph 2.0 ([arXiv 2407.10805](https://arxiv.org/abs/2407.10805)) | Training-free loop alternating KG and document retrieval | Several LLM calls per query; the agent loop belongs to the caller |
| StructRAG ([arXiv 2410.08815](https://arxiv.org/abs/2410.08815)) | Picks a structure (table, graph, catalogue…) per question at inference time | Suggests table-shaped output for entity-centric questions |
| DRIFT ([Microsoft blog](https://www.microsoft.com/en-us/research/blog/introducing-drift-search-combining-global-and-local-search-methods-to-improve-quality-and-efficiency/)) | Community-report primer, then local follow-ups; 78 % / 81 % win rates vs local search | Vendor, LLM judge, one dataset; needs community reports |
| PathRAG ([arXiv 2502.14902](https://arxiv.org/abs/2502.14902)) | Flow-pruned relational paths as prompt text | LLM-judge evidence only |
| G-Retriever, GFM-RAG | GNN retrievers | Need training and a GPU; no fit for SQL storage |

Surveys for placing concepts: Han et al.
[arXiv 2501.00309](https://arxiv.org/abs/2501.00309) (query processor,
retriever, organizer, generator, data source) and Peng et al.
[arXiv 2408.08921](https://arxiv.org/abs/2408.08921) (G-Indexing,
G-Retrieval, G-Generation).

## Query strategies

**Verified:** 2026-10-04, mostly from abstracts and HTML summaries. The
HyDE and Jagerman et al. tables were not read. Re-check a figure before
quoting it. Decision: [ADR 0010](../decisions/0010-offer-query-strategies-as-opt-in-benchmarked-options.md).

| Strategy | Finding | Source |
|---|---|---|
| HyDE | Beats unsupervised Contriever and is comparable to fine-tuned retrievers on web search, QA and fact checking; also tested on Swahili, Korean and Japanese (abstract) | Gao et al. [arXiv 2212.10496](https://arxiv.org/abs/2212.10496) [peer-reviewed] |
| Query2doc | BM25 MS MARCO dev MRR@10 18.4 → 21.4; TREC DL19 nDCG@10 51.2 → 66.2. Over distilled dense retrievers (SimLM, E5) only +0.4 to +1.9. LLM step over 2,000 ms against 16 ms for BM25 | Wang et al. [arXiv 2303.07678](https://arxiv.org/abs/2303.07678) [peer-reviewed] |
| Why expansion fails | Gains depend on the LLM knowing the answer: Q2D on BM25 +3.93 with knowledge, +1.29 without; Contriever on BioASQ −10.02 nDCG@10 without knowledge. Ambiguous queries get worse | Abe et al. [arXiv 2505.12694](https://arxiv.org/abs/2505.12694) [peer-reviewed, SIGIR 2025 short] |
| Knowledge leakage | Gains track generated sentences that the gold evidence entails, which points to memorization (abstract) | Yoon et al. [arXiv 2504.14175](https://arxiv.org/abs/2504.14175) [peer-reviewed] |
| Multi-query, union of rewrites | With BGE, a cross-encoder and MMR: +12.5 to +13.8 HIT@10 on EnterpriseRAG-Bench, +1.6 to +1.8 on HotpotQA, −2.4 on AmbigNQ. Single rewrites underperform alone. A confidence gate keeps about half the gain with the LLM on under 40 % of queries (abstract) | Shanian et al. [arXiv 2609.05637](https://arxiv.org/abs/2609.05637) [peer-reviewed, EMNLP 2026 Industry; ID from a summary] |
| Decomposition, IRCoT | Up to +21 retrieval recall and +15 QA points on multi-hop sets, over BM25; an iterative agent loop (abstract) | Trivedi et al. [arXiv 2212.10509](https://arxiv.org/abs/2212.10509) [peer-reviewed] |
| Questions per chunk at index time (HyPE) | Up to +42 points context precision and +45 points claim recall over standard retrieval on six datasets; zero query latency. Baselines and embedders not verified; venue metadata inconsistent (abstract) | Vake et al. [arXiv 2607.29402](https://arxiv.org/abs/2607.29402) [single paper] |
| Temporal constraint parsing | Splitting a query into content plus a time constraint, then filtering, beats off-the-shelf retrievers on time-sensitive sets (abstracts; no figures verified) | MRAG [arXiv 2412.15540](https://arxiv.org/abs/2412.15540), TimelyRAG [arXiv 2609.11572](https://arxiv.org/abs/2609.11572) [preprints] |
| Cross-lingual | Retrievers prefer evidence in the query's language; the apparent English preference is mostly where the evidence sits. Pivoting to English is not a safe default (abstract) | DELTA [arXiv 2601.02956](https://arxiv.org/abs/2601.02956) [peer-reviewed, ACL 2026 Findings] |

**What it suggests for us** [inferred]:
- Our hybrid retrieval with modern multilingual embedders already narrows
  the gap HyDE and Query2doc address. A private corpus is their worst case,
  since the LLM cannot know its figures.
- The cheapest strategies with a good fit are temporal parsing into a date
  filter, keyword and entity extraction for entity linking, and a bilingual
  query variant fused with the original.
- Multi-query helps on hard questions and hurts on simple or ambiguous
  ones, so it stays opt-in and is reported per question type.
- **Gaps:** no HyDE or Query2doc test with bge-m3, multilingual-e5 or
  Qwen3-Embedding; no Vietnamese query-expansion study; no isolated test of
  LightRAG-style keyword extraction.

## Inputs for the engine brief [inferred]

These are candidate directions, not decisions. The engine brainstorm settles
them ([brief, open question 1](../product/sdk-platform-brief.md)).

1. **Chunks stay the ground truth and are always returned.** Graph context
   augments them and never replaces them.
   - Sources: Han et al., the MaGiX chunk-score ablation, RAGFlow rc1
     resolving compiled rows back to chunks.
2. **The default path is hybrid.** Lexical plus dense chunk retrieval fused
   by RRF, then entity-seeded graph expansion, with an optional reranker.
   - The benchmark baseline should include this hybrid as well as naive
     vector, because no published graph result beats a tuned hybrid.
   - This changes the wording of brief success criterion 5 and of
     [ADR 0001](../decisions/0001-build-own-graphrag-core.md)'s baseline.
3. **The fact row is the unit of knowledge.**
   - One row per statement per chunk.
   - The verbatim quote is checked against the chunk.
   - Typed values keep their raw text.
   - Entity "descriptions" are derived from facts at read time, not merged
     by an LLM.
   - Sources: MaGiX granular gain, RAGFlow rc1 evidence gate, SAG
     `value_raw`, pitfalls in GR, LR and RF.
4. **Time is data, not text.**
   - `valid_from`/`valid_to` are filled only when stated.
   - The document date and ingest time are kept separately.
   - Supersession is computed, never destructive, and ordered by stated date
     and then document date.
   - It is recomputed when a document is deleted.
   - Queries return every version with the newest flagged.
   - Sources: Graphiti interval logic, post-graph-rag columns, cognee
     functional relations.
5. **Entity resolution is staged, blocked and incremental.**
   - Exact, then trigram or MinHash, then LLM on the residue.
   - A digit guard, an alias table and reversible merges.
   - Cross-language aliases are linked by name-plus-context embeddings
     rather than merged.
   - Per-update cost must not grow with the whole graph (the Zep critique).
   - Decided on 2026-10-06: a name alone never identifies an entity. Each
     type declares a scope, keys and vetoes
     ([ADR 0016](../decisions/0016-identify-entities-by-scope-keys-and-vetoes.md)).
6. **Communities are optional.** Our questions are entity-centric and
   temporal. The only measured community win is global summarization, at
   40–50× the tokens.
   - If they are built, build them lazily or only for touched communities.
   - This touches ADR 0001's pipeline list and brief milestone M5.
   - Decided on 2026-10-05: clustering by default, reports opt-in
     ([ADR 0011](../decisions/0011-cluster-by-default-and-make-community-reports-opt-in.md)).
7. **Retrievers beyond the default:**
   - PPR (HippoRAG 2) for multi-hop questions.
   - Graph tools for agents: find an entity, neighbours, facts about an
     entity as of a date, sources of a fact.
   - RAGSearch shows agentic multi-round retrieval recovers much of the
     graph gain, and our consumers are agents.
8. **Cost.**
   - About 2 LLM calls per chunk is the norm (HippoRAG 2, post-graph-rag).
   - An extraction budget, if offered, must not choose chunks by
     centrality, because unique decisions are the least central chunks
     (KET-RAG pitfall).
9. **Evaluation.**
   - Reference-based deterministic metrics come first. LLM judges are used
     only with order swaps.
   - The golden set must include as-of, conflicting-version and
     cross-language questions (a Vietnamese query over English documents and
     the reverse), since no public benchmark covers them.
10. **What a node is, and how a subgraph reaches chunks.** From a review of
    a proposed graph-first flow; detail and the proposed flow diagram are in
    the [snapshot](../research/2026-10-02-aws-graphrag-toolkit.md#9-review-of-the-proposed-flow).
    - Nodes are entities with identity, typed by the profile, plus typed
      event nodes (meeting, decision, acquisition).
    - Statements are fact rows attached to edges or entities, not nodes.
      Dates, numbers and value ranges are columns, never nodes.
    - Entry runs two branches: entity linking (alias, trigram, name
      embedding) and hybrid chunk search whose hits seed entities. A
      graph-only entry misses queries without a named entity and facts the
      extractor missed.
    - Subgraph to chunks is a provenance join ranked by the query vector
      (LightRAG's default `VECTOR` pick). One extra vector query from a text
      rendering of the subgraph catches extraction misses (AWS
      `EntityNetworkSearch`).
    - No LLM sits in this step; the calling agent iterates through graph
      tools.
    - Return only edges whose evidence lies in the returned chunks, and
      penalize hub entities when expanding.
    - Engines compared step by step against this flow:
      [graphrag-engines.md](graphrag-engines.md#retriever-flows-compared).
11. **A query-strategy stage before retrieval entry.** Added on 2026-10-04
    by [ADR 0010](../decisions/0010-offer-query-strategies-as-opt-in-benchmarked-options.md).
    - Strategies return query variants, filters or extra vectors, fused
      through RRF. The original query is always kept.
    - All are off by default. Temporal parsing feeds the step-3 time filter.
      Keyword extraction feeds step-1 entity linking.
    - Evidence: [query strategies](#query-strategies).
12. **One `GraphStore` for SQL and Cypher.** Added on 2026-10-04 by
    [ADR 0008](../decisions/0008-build-databricks-and-open-branches-in-parallel.md).
    - Store methods return candidate ids and records. Normalization, RRF,
      tie-breaks, PageRank and supersession ordering stay in the engine.
    - The per-hop fan-out cap maps to `LATERAL … LIMIT` in Postgres and to
      a scoped `CALL … LIMIT` per hop in Neo4j
      ([neo4j-platform.md](neo4j-platform.md#modelling-and-traversal)).
13. **Vietnamese and English in one corpus.** Added on 2026-10-04 from a
    review of the first test corpus with the author.
    - Source text is never translated. Code applies only lossless
      normalization: Unicode NFC and tone-mark placement (`hoà` = `hòa`).
      Diacritics are kept, so `lãi`, `lại` and `lai` stay distinct.
    - Numbers and units: the extraction model returns typed values (money,
      percentage, date) beside the verbatim text. The corpus writes
      `2.000.000 VND` and `17,500,000 VND`, `0,2%` and `5.5%`, so no single
      locale parses it. Code checks that the value matches the digits in
      the quote after applying unit words such as nghìn, triệu and tỷ; a
      mismatch drops the item as `BAD_VALUE`.
    - Entities: one node per thing in any language, with a canonical name
      in the graph language and aliases in both. The surface form must
      occur in the chunk, as quotes must; a translated name is only an
      alias.
    - Merge on a language-neutral identity key (a document number, a tax
      code) or an LLM confirmation. Otherwise link the pair with a
      candidate `SAME_AS` edge that traversal can follow and a reviewer can
      confirm. MaGiX links rather than merges
      ([MaGiX](#cross-lingual-vietnamese--english-magix)).
    - Fuzzy matching applies to entity names only. On short common words,
      one edit separates `lãi` from `lại`.
