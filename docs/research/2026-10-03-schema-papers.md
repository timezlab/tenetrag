# Schema design, induction and evaluation for LLM KG construction: papers

> **Snapshot, 2026-10-03 — not maintained.** Academic lane, mostly abstracts and summarized paper HTML. The maintained,
> re-verified summary is in [graph-schema-design.md](../reference/graph-schema-design.md); where they differ, the maintained doc
> wins. Local paths were removed before publishing.
>
> **Errata and later resolutions:**
> - AutoSchemaKG: the abstract says **92 %** semantic alignment, not 95 %; the 95 %
>   figure appears only in the v3 introduction. Venue confirmed: ACL 2026 long.
> - OG-RAG is **EMNLP 2025 main**, not a preprint. The +55 % recall and +40 %
>   correctness are best-case relative gains (about 12 % on wheat, 0 % on news),
>   and v1 has no ablation without the ontology.
> - OMD-GraphRAG: the 78.92 vs 69.71 gap is against **LightRAG**; the ontology
>   module alone adds +3.17 F1 on Naive RAG. No "UniAI-GraphRAG" title was found.
> - HyperGraphRAG: +7.45 F1 over StandardRAG is the **Medicine** domain only
>   (Agriculture +6.46, CS +2.37, Legal +6.47). Venue NeurIPS 2025 main.
> - EDC: refinement gains are +4.6 (Wiki-NRE) to +5.3 (REBEL) F1 with GPT-3.5.
> - Lippolis et al. (arXiv 2503.05388) is a preprint with a workshop version at
>   ELMKE 2025, not ESWC 2025. The wrong-inverse and class-cycle counts were not
>   re-checked.
> - Ilves et al. 2026 report **no** single-step vs two-step comparison. Triple F1:
>   Claude Opus 4.5 39.9, Gemini 3 Pro 39.3, GPT-5.1 21.7, Mistral 7B 4.2; 61.5 % of
>   predicted triples were absent from gold; manual review covered 10 documents.
> - SchemaRAG (ACL 2026 Industry) confirmed: "up to an 8.8% increase in micro-F1";
>   whether the 8.8 % is absolute or relative was not checked.

## Schema design/induction/evaluation for LLM KG construction and GraphRAG - findings (2026-10-03)

Reading depth: most entries were read as arXiv abstract pages or HTML summaries through a fetch-summarizer (not full-text reading). Numbers are marked [abs] (abstract-level) or [body] (summarized from the paper body). Nothing here came from tables read by me directly.

### Paper table
| Paper (URL) | Venue / status | Schema approach | Key quantitative finding | Relevance |
|---|---|---|---|---|
| EDC, Zhang & Soh, arXiv 2404.03868 | EMNLP 2024 | Open extract -> define -> canonicalize; optional schema retriever refinement | WebNLG F1 0.794 / REBEL 0.559 / Wiki-NRE 0.693 (EDC+R, GPT-3.5); refinement +4.8-5.3 F1; self-canonicalization precision 0.956 on WebNLG, 529->200 relations; tested schemas of 159/200/45 relations [body, summarized] | Retrieval of relevant schema subset works for 100-200 relation types |
| Text2KGBench, arXiv 2308.02357 (Mihindukulasooriya et al.) | ISWC 2023 | Ontology-given extraction benchmark; 7 metrics incl. ontology conformance, hallucination | LLMs: high ontology conformance, moderate fact accuracy (Vicuna-13B, Alpaca-LoRA-13B baselines) [abs/search snippet] | Metrics template (conformance, hallucination) |
| Ilves, Barbu, Ubi 2026, ACL Anthology 2026.kallm-1.21 | KG-LLM workshop @ LREC 2026 | Closed ontology: 6 entity types, 96 relation types; single-step vs two-step; DocRED; Gemini 3 Pro, GPT-5.1, Claude Opus 4.5, Mistral 7B | Automatic triple F1 systematically underestimates quality because valid triples are absent from incomplete gold [abs]. No numbers on 1- vs 2-step in the abstract | Gold-based F1 is unreliable for schema trial reports |
| SchemaRAG, arXiv 2607.00008 (Ho et al.) | ACL 2026 Industry | Retrieve/prune schema per input from metadata + few-shot examples | up to +8.8 micro-F1, -47% latency, -48% token cost; healthcare and e-commerce [abs] | Direct evidence for per-chunk schema subset retrieval |
| GoLLIE, arXiv 2310.03668 | ICLR 2024 | Guidelines (definitions + candidates) as code docstrings | zero-shot avg 55.3 F1 vs 42.3 baseline; "representative candidates" the most impactful part; definitions and candidates complementary; struggles on ambiguous/coarse labels and when gold conflicts with guidelines [body, summarized] | Definitions + examples matter; fine-tuned model, so transfer to prompted LLMs is an inference |
| Lippolis et al., Ontology Generation using LLMs (Memoryless CQbyCQ, Ontogenia), arXiv 2503.05388 | preprint (v1 Mar 2025; I did not verify later publication) | CQ + user story -> OWL, 10 ontologies / 100 CQs / 29 stories | CQbyCQ 0.91 CQs modelled (0.94 lenient); Ontogenia 0.84 (0.89); o1-preview + Ontogenia best; beats novice students; OOPS! flagged wrong inverses (0-25), class cycles (0-11), multiple domain/range (1-32) [body, summarized] | CQ-driven drafting works; pitfalls list for validators |
| Bench4KE, arXiv (Dec 2025), Lippolis et al. | preprint | CQ generation benchmark: 843 gold CQs from 17 ontology projects, 6 systems | BERTScore F1 0.57-0.60, cosine 0.16-0.32; LLM-judge depth 2.5-3.98/5 [body, summarized] | CQ generation from sources is hard and evaluation unstandardized |
| Retrofitting CQs, arXiv 2311.05662; Open-source LLM retrofit AAAI-SS 2024 | workshop/preprint | CQ from ontology triples | only seen via search snippets | CQ generation direction |
| OLLM, arXiv 2410.23584 | NeurIPS 2024 | Fine-tuned end-to-end taxonomy learning | outperforms subtask composition [search snippet] | Taxonomy only, no attributes/constraints |
| LLMs4OL 2024 overview, arXiv 2409.10146 | ISWC 2024 challenge | Term typing, taxonomy, relation tasks | biomedical/geographic ontologies hardest [snippet] | Weak for our needs |
| Ontology-grounded KGC under Wikidata schema, arXiv 2412.20942 (Feng, Wu, Meng) | KDD 2024 HI-AI workshop (CEUR 3841) | CQ -> relations -> align with Wikidata | "competitive" on benchmarks, no numbers read [abs] | Closest to CQ -> schema -> extraction pipeline |
| AutoSchemaKG, arXiv 2505.23628 | preprint v3; also listed at ACL 2026 long (preview.aclanthology.org 2026.acl-long.942, seen only in search results) | Dynamic schema induction, entities + events | 95% semantic alignment with human-crafted schemas; ATLAS 900M+ nodes [abs] | Induction viable for schema drafting |
| KGGen, arXiv 2502.09956 | NeurIPS 2025 | Schema-free extract + iterative clustering | MINE 66.07% vs GraphRAG 47.80% vs OpenIE 29.84% [abs/snippet] | Normalization helps; own benchmark, small |
| SPIRES/OntoGPT, Caufield et al. | Bioinformatics 2024 | LinkML schema, recursive prompt interrogation, ontology grounding | accuracy mid-range of RE methods; far better ID grounding than native LLM [abs] | Schema-as-LinkML, grounding of entities to ontology IDs |
| OG-RAG, arXiv 2412.15235 (Sharma et al.) | preprint | Expert-reviewed ontology -> hypergraph of facts | +55% fact recall, +40% correctness [abs]; paper has NO ablation isolating ontology vs no ontology [body, summarized] | Often cited as pro-ontology evidence but does not isolate it |
| Youtu-GraphRAG, arXiv 2508.19855 | preprint | Seed schema that expands during extraction | +16.62% accuracy, -90.71% tokens vs baselines, six benchmarks [abs]; schema vs no-schema ablation not verified | Schema-bounded design, schema evolves |
| OMD-GraphRAG / UniAI-GraphRAG, arXiv 2603.25152 | preprint | Predefined schema template in prompt | MultiHop-RAG F1 78.92, ~9.2 over open GraphRAG baseline, ~3 F1 per module [secondary summary, pith] | Weak-moderate; check whether it has a no-ontology ablation |
| HyperGraphRAG, arXiv 2503.21322 | NeurIPS 2025 | n-ary hyperedges | +7.45 F1 vs StandardRAG; binary-source Qs +8.6, n-ary Qs +5.3; ablations without hyperedge retrieval F1 35.4->26.4 [body, summarized] | n-ary helps; no like-for-like binary-extraction ablation seen |
| Zep/Graphiti, arXiv 2501.13956 | preprint | Bi-temporal KG, episodes, edge invalidation | DMR 94.8 vs 93.4 (MemGPT); LongMemEval up to +18.5% acc, -90% latency [abs] | Time model; vendor paper, no ablation vs non-temporal graph seen |
| GraphRAG-Bench (Xiang et al.), arXiv 2506.05690 | preprint v3 | Benchmark across 4 task levels | Vanilla RAG >= GraphRAG on simple fact retrieval; GraphRAG wins on complex reasoning/summarization; graph density correlates with performance (avg degree 13.31 medical, HippoRAG2) [body, summarized] | When graphs help |
| RAG vs GraphRAG, arXiv 2502.11371 (v3 Mar 2026) | preprint | Unified protocol | RAG better on single-hop/detail; GraphRAG on multi-hop; GFM-RAG recall 84.3 vs 71.8 but relevance 38.5 vs 62.9 (secondary snippet) | Graph noise hurts precision |
| LinkedIn KG-RAG customer service, arXiv 2404.17723 | preprint (SIGIR 2024 per my memory, unverified) | KG of historical issues keeping intra-issue structure | median resolution time -28.6% in ~6 months deployment [abs/snippet] | Domain structure schema; no schema ablation seen |
| FinDKG, arXiv 2407.10909 | preprint/Imperial | fine-tuned LLM (ICKG), 15 relation types, 13,645 entities | no schema ablation seen [snippet] | Small fixed relation set |
| LLM-empowered KG construction survey, arXiv 2510.20345 | preprint | Survey | PDF unreadable via fetcher; only skimmed | Likely the survey to read directly |

### Sub-question findings

#### 1. Schema-guided vs schema-free vs induce-then-canonicalize
- Evidence is mostly benchmarks measuring triple F1 against fixed gold schemas (Text2KGBench, EDC datasets), which structurally favour schema-given runs. A search snippet claims ontology-constrained beats unconstrained because "the LLM discovers a richer ontology than the target", but this penalty is a metric artifact (Ilves 2026 shows gold incompleteness underestimates F1).
- EDC: induce-then-canonicalize with schema retriever refinement gave +4.8-5.3 F1, and compresses the induced relation set (529->200) at 0.956 precision (WebNLG, GPT-3.5).
- AutoSchemaKG: induced schemas align 95% with human schemas (their metric); KGGen: clustering gives MINE 66 vs 48. Both are self-defined benchmarks.
- No paper found that holds the corpus fixed and compares hand-authored domain schema vs induced vs free on downstream QA with a clean ablation. OG-RAG (no ontology ablation), Youtu, OMD-GraphRAG are the nearest; only OMD claims module-level ablation.
- A blog (premai) claims "5-15 entity types, 10-20 relation types" beat open extraction; no paper behind it, treat as SEO-grade, unverified.

#### 2. Schema properties and extraction quality
- Natural-language definitions and representative examples: GoLLIE ablation shows both help and are complementary (fine-tuned 7-34B Code-LLaMA, ICLR 2024). Failure on ambiguous/coarse labels.
- Large schemas: EDC and SchemaRAG both retrieve a relevant subset. SchemaRAG: +8.8 micro-F1 and -48% tokens vs full schema (abstract; ACL 2026 Industry). A snippet reports LLM confusion with long schema context in moderately sized schemas (source unverified).
- Two-pass vs single-pass: Ilves 2026 compares them on a 6-entity/96-relation ontology but I could not read results.
- Direction, domain/range, typed attributes, hierarchy depth, negative examples: no controlled study found for LLM KG construction. OOPS! findings (multiple domains/ranges, wrong inverses) show LLMs themselves author these poorly. Text2KGBench measures domain/range conformance but results I saw were aggregate.

#### 3. Ontology engineering with LLMs
- Lippolis et al.: o1-preview + Ontogenia > novice students; expert review necessary; common errors listed above. Memoryless CQbyCQ (one CQ at a time, ~60% less context) scored at least as well as Ontogenia in the independent setting. Generated ontologies need merging and de-duplication.
- Bench4KE: automated CQ generation weak against gold (BERTScore ~0.6). Stakeholder-sourced CQs likely beat LLM-generated ones; not tested directly.
- OLLM / LLMs4OL cover taxonomy/term typing only.

#### 4. Evaluating a schema / KG for RAG
- Intrinsic: CQ coverage (Lippolis), OOPS! pitfalls, conformance/hallucination (Text2KGBench), schema-induction alignment (AutoSchemaKG). OntoQA/OQuaRE not retrieved in this pass.
- Extrinsic: GraphRAG-Bench and RAG-vs-GraphRAG show graph helps for multi-hop/reasoning, not for simple fact lookup; graph density and information density of corpus matter. Neither isolates schema quality as a factor.
- Gold-based triple F1 is unreliable (Ilves 2026).

#### 5. Time, evidence, n-ary
- HyperGraphRAG: n-ary hyperedges beat binary-edge GraphRAG/LightRAG and chunk RAG across four domains, gains also on binary-source questions. Not a controlled reification-vs-binary comparison within the same extractor.
- Zep: bi-temporal edges, large gains on LongMemEval temporal tasks, but no ablation vs non-temporal graph in what I read.
- OMD-GraphRAG claims gains on temporal queries (secondary).
- Event-centric graph prompts gave more grounded answers than generic triples (snippet, source not identified).
- Direct evidence that claim/event nodes beat plain binary edges for temporal QA: not found.

#### 6. Domain papers with schemas
- FinDKG: 15 relation types, fine-tuned extractor; LinkedIn: ticket-structure KG, -28.6% resolution time; OG-RAG: expert-reviewed agriculture ontology; none compared against a generic schema in what I read. MedGraphRAG, KG-RAG/SPOKE not retrieved (budget).

### Synthesis: evidence-based rules
1. Give each type a natural-language definition plus representative examples in the extraction prompt. [supported] GoLLIE (fine-tuned models); EDC schema definitions. Transfer to prompted frontier models is untested here.
2. When schema exceeds ~50-100 types, retrieve a relevant subset per chunk or per pass instead of putting the full schema in prompt. [supported] SchemaRAG (abstract), EDC (159-200 relation schemas handled via retriever; +4.8-5.3 F1).
3. Run an induce-then-canonicalize trial on sample docs to draft the schema and to surface missing/overlapping types. [supported] EDC, AutoSchemaKG (95% alignment), KGGen; benchmarks are self-reported.
4. Drive the draft from CQs; produce per-CQ fragments then merge (Memoryless CQbyCQ), and require human review of domain/range, inverses, hierarchy cycles and overlapping classes. [supported] Lippolis et al. (preprint).
5. Trial report should show conformance/hallucination rates, CQ coverage and type/relation frequency distribution; do not rely on gold-triple F1 alone. [supported] Text2KGBench metrics; Ilves 2026.
6. Prefer schema-bounded extraction over free extraction for downstream QA. [preliminary] only OMD-GraphRAG-style ablations and indirect evidence; OG-RAG lacks ablation.
7. Use n-ary/hyperedge or event/claim structure for facts with qualifiers (time, amount, source). [preliminary] HyperGraphRAG gains but not isolated against reified binary graph.
8. Bi-temporal edge metadata improves temporal memory tasks. [preliminary] Zep, vendor-reported.
9. Expect graph to help on multi-hop/aggregation and not on single-fact lookup, so keep chunk retrieval alongside graph. [supported] GraphRAG-Bench, RAG vs GraphRAG.
10. Keep schemas small (5-15 entity types) [speculative] only blog-sourced.
11. Vietnamese/multilingual schema effects: [no evidence found].

### Gaps / not found
- No controlled ablation of schema size, hierarchy depth, relation direction, domain/range, typed attributes on LLM KG extraction.
- No paper comparing expert vs LLM-drafted schemas on downstream GraphRAG QA.
- No evidence on schema versioning/selective re-extraction.
- Not retrieved: MedGraphRAG, KG-RAG/SPOKE, SAC-KG, iText2KG/ATOM, KnowCoder, Code4UIE, ChatIE, Docs2KG, GraphJudge, KARMA, NeOn-GPT, OntoChat results, OntoQA/OQuaRE, legal/regulatory GraphRAG, Vietnamese KG work. Full-text table verification of all numbers is pending.
