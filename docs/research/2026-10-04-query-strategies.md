# Pre-retrieval query strategies for RAG / GraphRAG — research report

> **Snapshot, 2026-10-04 — not maintained.** Academic lane; medium confidence, mostly abstract-level reads. The maintained,
> re-verified summary is in [graphrag-research.md](../reference/graphrag-research.md#query-strategies); where they differ, the maintained doc
> wins. Local paths were removed before publishing.
*2026-10-04 · ~35 sources (abstract/HTML-level reads; several fetches were abstract-only) · confidence: medium*

## Summary (10 lines)
1. No strategy has strong evidence for private, Vietnamese/English enterprise corpora; nearly all evidence is English web/Wikipedia QA.
2. HyDE/Query2doc gains are large for BM25 and unsupervised dense (Contriever), small for distilled/fine-tuned dense (Query2doc: +0.4 to +1.9 on SimLM/E5 vs +3 to +15 on BM25) [peer-reviewed, abstract+tables via ar5iv summary].
3. Gains depend on LLM knowledge: when the LLM lacks the knowledge, gains shrink and dense retrievers can drop (Contriever+Q2D on BioASQ: -10.02 nDCG@10 without knowledge vs -1.89 with) [peer-reviewed, SIGIR'25 short]. Yoon et al. (ACL Findings 2025) find gains track leakage of gold-entailed sentences [peer-reviewed].
4. Private corpora = the worst case for HyDE-style methods (LLM has not seen them); numeric, entity-specific and dated facts are exactly what a hypothetical document gets wrong [inferred from 3].
5. Multi-query/RRF, decomposition and rewriting help mostly on multi-hop / hard enterprise sets and can hurt on simple or ambiguous ones (EMNLP'26 Industry: +12.5-13.8 HIT@10 on EnterpriseRAG-Bench, +1.6-1.8 HotpotQA, -2.4 AmbigNQ with BGE + reranker) [peer-reviewed, abstract only].
6. Cheapest high-value items for this design: temporal-constraint parsing into filters (deterministic filter, graph already has dates), keyword/entity extraction for entity linking, cross-lingual query variant (translate or bilingual fusion), index-time question embeddings (HyPE-style, zero query latency).
7. A confidence-gated router captures ~half the rewriting gains at <40% of queries calling the LLM (same EMNLP'26 paper) [abstract only].
8. Graph-specific evidence for query rewriting is thin; GraphRAG evaluations themselves suffer LLM-judge bias and unrelated-question flaws (gains "much more moderate" under unbiased eval).
9. Recommendation: v1 = temporal parse, keyword/entity extraction, translation/bilingual variant, multi-query+RRF (opt-in), HyPE-style index-time questions (opt-in). Later = decomposition (agent-side), router. Do not ship HyDE as default; offer only as an experimental flag if at all.
10. Benchmark each strategy per question type with cost/latency columns and a no-LLM baseline using the strongest embedder + reranker; never conclude from LLM-judged win rates alone.

## Table
Labels: [PR] peer-reviewed, [PP] preprint, [V] vendor, [I] inferred. "Entry" = pre-retrieval query-side, before step 1/2 of the flow.

| Strategy | Mechanism | LLM calls | Plug-in point | Index/query-time | Evidence (gain, dataset, baseline) | Hurts when | Label |
|---|---|---|---|---|---|---|---|
| HyDE (Gao et al., ACL 2023, [2212.10496](https://arxiv.org/abs/2212.10496)) | LLM writes hypothetical answer doc; embed it (avg w/ query) | 1 (generation of ~long text; seconds) | Entry: replaces/augments query vector in step 2 and the step-4 ranking vector | Query-time | "Significantly outperforms unsupervised Contriever, comparable to fine-tuned" on web search, QA, fact verification; Swahili/Korean/Japanese tested (abstract; tables not read, PDF unreadable) | Strong dense retriever; LLM lacks the knowledge; numeric/entity-specific queries | [PR] abstract only |
| Query2doc (Wang et al., EMNLP 2023, [2303.07678](https://arxiv.org/abs/2303.07678)) | Few-shot (4) pseudo-doc appended to query; BM25 repeats query 5x | 1 | Entry: BM25 leg and dense leg | Query-time | BM25 MS MARCO dev MRR@10 18.4->21.4; DL19 51.2->66.2, DL20 47.7->62.9 nDCG@10; dense: DPR +1.4/+4.0, SimLM/E5 +0.4 to +1.9; >2000 ms LLM latency vs 16 ms BM25; bigger LLM better; BEIR mixed, entity tasks (DBpedia) best, some domain sets degrade | Distilled/strong dense; small LLM; domain mismatch | [PR] (numbers from ar5iv read) |
| LLM query expansion / CoT (Jagerman et al., [2305.03653](https://arxiv.org/abs/2305.03653)) | Prompt zero/few-shot, CoT, PRF-in-prompt; append terms to BM25 query | 1 | Entry: BM25 leg | Query-time | Beats Bo1/Bo2/KL on MS MARCO/BEIR with BM25; CoT best; hurts on some BEIR sets and with weaker models (Flan-T5, Flan-UL2, GPT-3.5); exact deltas not verified | Dataset where original queries are already precise; weak LLM | [PP] |
| MuGI (Zhang et al., [2401.06311](https://arxiv.org/abs/2401.06311)) | Many sampled pseudo-docs + query, balance weights, PRF | N samples | Entry | Query-time | Helps BM25 and dense, 23M-7B models (abstract); claims on strong rankers | Cost scales with N | [PP] abstract only |
| QE for strong cross-encoders (Li et al., [2311.09175](https://arxiv.org/abs/2311.09175)) | Keyword gen with reasoning + fusion (self-consistency, reciprocal rank weighting) | 1+ | Entry + fusion | Query-time | Prior: QE helps weak rankers, hurts MonoT5; with careful design MonoT5/RankT5 improved on BEIR/TREC DL (abstract) | Naive concatenation to strong rankers | [PP] abstract only |
| Failure analysis (Abe et al., SIGIR 2025 short, [2505.12694](https://arxiv.org/abs/2505.12694)) | Diagnostic of Q2E/Q2D/GaQR with GPT-3.5, Llama-3-8B | n/a | n/a | n/a | BM25 MS MARCO Q2D: +3.93 (LLM knows) vs +1.29 (doesn't); Contriever BioASQ Q2D -10.02 vs -1.89; ambiguous queries -0.49 R@100 vs +0.86 low-ambiguity (AmbigDocs, BM25+Q2E); popularity bias | Unknown-to-LLM, ambiguous queries | [PR] |
| Knowledge leakage (Yoon et al., ACL Findings 2025, [2504.14175](https://arxiv.org/abs/2504.14175)) | Fact-verification analysis | n/a | n/a | n/a | Gains occur when generated doc contains sentences entailed by gold evidence, i.e. memorized | Corpora the LLM never saw | [PR] abstract only |
| Multi-query / RAG-Fusion + RRF (Rackauckas, IJNLC 2024, [2402.03367](https://arxiv.org/abs/2402.03367)) | LLM makes N query variants, retrieve each, RRF | 1 (N queries in one call) + N retrievals | Entry: wraps steps 1-2; RRF already in flow | Query-time | Manual eval on product docs: more comprehensive, but some answers drifted off-topic; no latency numbers | Variants drift; simple queries | [PR-ish, small, manual eval] |
| Step-back (Zheng et al., ICLR 2024, [2310.06117](https://arxiv.org/abs/2310.06117)) | Ask abstract question first, retrieve both | 1 | Entry | Query-time | TimeQA +27%, MuSiQue +7%, MMLU Phys +7 / Chem +11 (with PaLM-2L; reasoning gains, retrieval not isolated) | Specific factual/numeric lookups (abstraction loses the anchor) [I] | [PR] abstract only |
| Decomposition / IRCoT (Trivedi et al., ACL 2023, [2212.10509](https://arxiv.org/abs/2212.10509)) | Interleave retrieval with CoT sentences; BM25; Flan-T5 / GPT-3 | 1 per hop (iterative) | Agent loop (caller), not inside retrieval | Query-time | Retrieval recall up to +21 pts, QA up to +15 pts on HotpotQA, 2Wiki, MuSiQue, IIRC (abstract; BM25 base) | Single-hop; latency multiplies | [PR] abstract only |
| SubQRAG ([2510.07718](https://arxiv.org/abs/2510.07718)) | Sub-question driven dynamic graph RAG | multi | Agent loop | Query-time | Not read | - | [PP] unverified |
| Rewrite-Retrieve-Read (Ma et al., EMNLP 2023, [2305.14283](https://arxiv.org/abs/2305.14283)) | Small T5 rewriter, RL from reader feedback | 0 LLM calls at query time (small model) but needs training + reader | Entry | Query-time, trained | "Consistent improvement" on open-domain/multiple-choice QA (abstract; numbers not read) | No training data/reader signal in your domain | [PR] abstract only |
| RL rewriters (DeepRetrieval, [2503.00223](https://arxiv.org/abs/2503.00223)) | RL with retrieval metric as reward; 3B model | 1 small | Entry | Query-time, trained | Literature search recall 65.07% (publication) / 63.18% (trials) vs GPT-4o/Claude-3.5 (search-engine boolean queries, not dense enterprise RAG) | Needs retriever-in-loop training | [PP] search-snippet figures only |
| Keyword extraction for graph entry (LightRAG, [2410.05779](https://arxiv.org/abs/2410.05779)) | LLM extracts low-level (entity) and high-level (theme) keywords; match entities / relations | 1 | Entry: feeds step 1 entity linking | Query-time (graph index-time) | Evaluated by LLM-judge win rates vs NaiveRAG/GraphRAG on UltraDomain (per memory of paper; not verified this session); no isolated ablation read | Vocabulary mismatch; judged by biased LLM eval | [PP] abstract only |
| Temporal query parsing (MRAG/TempRAGEval, [2412.15540](https://arxiv.org/abs/2412.15540); TimelyRAG [2609.11572](https://arxiv.org/abs/2609.11572); ChronoQA [2508.12282](https://arxiv.org/abs/2508.12282)) | Split query into content + time constraint; hard effective-date filter or semantic-temporal hybrid score | 0-1 (rule/regex or LLM) | Entry + step 3/4 filter | Query-time (needs dated facts at index-time) | MRAG "substantially outperforms" off-the-shelf retrievers on temporally perturbed sets (abstract, no figures verified); TimelyRAG uses rule-based hard filters (abstract only); off-the-shelf retrievers struggle with time | Ambiguous relative dates, doc date vs event date confusion [I] | [PP] abstracts only |
| Cross-lingual translation / bilingual fusion (DELTA, ACL 2026 Findings, [2601.02956](https://arxiv.org/abs/2601.02956)) | Leverage monolingual alignment instead of English pivoting; query-language-matched retrieval | 0-1 | Entry | Query-time | Outperforms English-pivot and mRAG baselines (abstract); finds English preference is largely evidence-distribution artifact; retrievers prefer same-language | Pivoting when evidence is in query language | [PR] abstract only |
| Conversational rewriting | Decontextualize with history | 1 | Entry | Query-time | Not researched this session | - | gap |
| Adaptive routing (Adaptive-RAG, NAACL 2024, [2403.14403](https://arxiv.org/abs/2403.14403)) | Small classifier -> no-retrieval / single / iterative | 0-1 small model | Router in front of everything | Query-time | Better efficiency/accuracy vs adaptive baselines on open-domain QA (abstract; numbers not read); labels from model outcomes + dataset bias | Distribution shift from Wikipedia QA | [PR] abstract only |
| Complementary rewriting + confidence gate (Shanian et al., EMNLP 2026 Industry, [2609.05637](https://arxiv.org/abs/2609.05637)) | 4 rewrite strategies; union; gate | 1-4 | Entry + router | Query-time | BGE + cross-encoder + MMR; EnterpriseRAG-Bench union +12.5-13.8 HIT@10; HotpotQA +1.6-1.8; AmbigNQ -2.4; gate gets ~half gain, LLM on <40% of queries (+1.92 F1) | Ambiguous/simple queries; individual methods underperform alone | [PR] abstract only |
| doc2query / HyPE (index-time) (Vake et al., IEEE Access 2025, [2607.29402](https://arxiv.org/abs/2607.29402)) | LLM generates questions per chunk at index; embed questions -> chunk; question-question match | N per chunk at index; 0 at query | Index-time (dense leg / extra vector) | Index-time (re-index to change) | Up to +42 pts context precision, +45 pts claim recall over standard (abstract; baselines/embedders not verified, 6 datasets) | Chunk facts not question-shaped (tables, numbers) [I]; index cost scales with chunks | [PR] abstract only |

## Findings by question

### Q2: Do HyDE/Query2doc gains vanish with strong dense retrievers?
- Query2doc's own tables: large for BM25, +0.4 to +1.9 for SimLM/E5 (distilled). [PR] This is the strongest direct evidence of shrinkage. Nothing I found tests bge-m3 / Qwen3-Embedding / multilingual-e5 with HyDE. gap.
- Survey (Li et al., [2509.07794](https://arxiv.org/abs/2509.07794), v3 May 2026) frames the trade-off between effectiveness, controllability and cost; read at abstract level only.
- Strong cross-encoders: expansion historically hurts, recoverable with keyword-style expansion + fusion ([2311.09175]) [PP].
- With BGE + cross-encoder reranker + MMR, individual rewrites underperform and only the union helps on hard enterprise data ([2609.05637]) [PR, abstract].

### Private corpora / hallucinated hypotheticals
- Abe et al.: LLM knowledge gap is the main cause of degradation; dense retrievers more fragile than BM25. Yoon et al.: gains partly memorization. Both imply benchmark gains overstate performance on unseen enterprise documents. Direct tests on private enterprise docs: none found except EnterpriseRAG-Bench (synthetic, [2609.05637]). [I] for the numeric/dated-figure risk: no paper isolates numeric queries.

### Multilingual / Vietnamese
- HyDE paper covers Swahili, Korean, Japanese only (abstract). No Vietnamese QE study found; Vietnamese legal retrieval work ([2409.13699](https://arxiv.org/abs/2409.13699)) uses HyDE-generated queries inside a BM25+dense candidate union, with no isolated ablation read. gap.
- DELTA ([2601.02956]) says retrievers prefer same-language matches and English pivoting is not a safe default [PR, abstract].

### Q3: Graph/KG evidence
- Little direct evidence of rewriting for entity linking inside GraphRAG. LightRAG's keyword split is a design, evaluated only by LLM win rates in its paper. Temporal: MRAG/TempRAGEval, TimelyRAG and TKGQA programs (e.g., [2404.01720](https://arxiv.org/abs/2404.01720)) support explicit constraint parsing; TKGQA methods parse to logical forms. Decomposition for KG multi-hop: IRCoT-style loops (BM25-based) and SubQRAG; none evaluated against a no-LLM graph-expansion retriever. RAG vs GraphRAG (Han et al., [2502.11371](https://arxiv.org/abs/2502.11371)): RAG better on single-hop detail, GraphRAG on multi-hop; complementary [PP, abstract via search snippet].

### Q4: Evaluation pitfalls
- GraphRAG LLM-judge evaluation: position/length bias, unrelated questions; gains much more moderate under unbiased evaluation (Zeng et al., [2506.06331](https://arxiv.org/abs/2506.06331)) [PP]. Win rate differences >30% from ordering alone (search snippet from [2502.11371]-related work; verify before citing).
- Weak baselines: BM25/Contriever baselines inflate gains; evaluate against the actual production embedder + reranker.
- Contamination: Wikipedia/MS MARCO-era sets leak into LLM (Yoon et al.); use held-out private/synthetic corpora.
- Benchmarks are English; averaging hides per-type harm (AmbigNQ -2.4 vs HotpotQA +1.7).
- Cost is rarely reported: Query2doc >2000 ms; RAG-Fusion paper reports no latency.

## Recommendation [inferred]
**v1 options (query-time, free to vary):**
1. Temporal constraint parsing -> date filter for step 3/4 (regex/dateparser first, optional LLM; deterministic fallback). Highest fit: graph has dated facts; as-of and conflicting-version question types depend on it. Keep "as-of" in tool args so the calling agent can supply dates without LLM inside retrieval.
2. Query keyword/entity extraction for step 1 (LLM optional; default is no LLM). Report entity-link recall with/without.
3. Cross-lingual variant: bilingual query fusion (original + translation) through RRF; do not replace the original (DELTA evidence). Alternatively rely on bge-m3 and benchmark first.
4. Multi-query + RRF (N=3-4), opt-in. Maps onto existing RRF.
**v1 option, index-time:** HyPE/doc2query-style chunk questions as an extra vector column, opt-in, cost recorded as index LLM calls. Test on definitions/formulas and numbers: likely weaker there [I].
**Later:** decomposition/IRCoT (leave to the calling agent; ship it as a documented agent pattern, not inside retrieval); confidence-gated router (needs a signal such as top-score margin or entity-link confidence); conversational rewriting (agent's job, same reason); trained rewriters.
**Not offered / experimental only:** HyDE and Query2doc as defaults. They address a BM25/unsupervised-dense gap your hybrid + modern embedders already narrow, and the LLM cannot know private figures. Provide as a clearly-labelled experimental flag only if the benchmark owner wants the ablation. Step-back: skip (no retrieval-specific evidence; hurts specific lookups [I]).
**Benchmark design:** matrix = strategy x question type (8 types in the brief) x embedder; baseline = no-LLM pipeline with best embedder (+ reranker if present); columns = recall@k/MRR on evidence chunk IDs (not LLM judge), entity-link recall, as-of correctness, extra LLM calls, p50/p95 latency, tokens, index LLM calls; paired bootstrap/significance; report per-type deltas and worst-case harm; blind/position-randomised LLM judge only for final answers, with human spot-check; include held-out (not web-seen) docs and Vietnamese-original queries, plus translated-query control.

## Gaps and caveats
- Many figures are abstract-level; HyDE and Jagerman PDFs were unreadable via fetcher, so their tables were not read. Verify before quoting.
- No direct HyDE/Query2doc results with bge-m3, multilingual-e5, Qwen3-Embedding; no Vietnamese QE ablations; no conversational-rewriting or doc2query (classic) coverage; no isolated LightRAG keyword ablation.
- Several 2026 arXiv IDs (2607.29402, 2609.05637, 2609.11572) came from search/fetch summaries; HyPE metadata is inconsistent (IEEE Access 2025 volume vs arXiv July 2026 submission). Venue claims unconfirmed on publisher pages.
- Leads: reasoning-intensive retrieval (TEMPO, ReasonIR), reranker-side time handling, query-time agentic search (Search-R1 family).

## Sources
1. Gao et al. 2023, HyDE, ACL — https://arxiv.org/abs/2212.10496
2. Wang et al. 2023, Query2doc, EMNLP — https://arxiv.org/abs/2303.07678
3. Jagerman et al. 2023, Query Expansion by Prompting LLMs — https://arxiv.org/abs/2305.03653
4. Zhang et al. 2024, MuGI — https://arxiv.org/abs/2401.06311
5. Li et al. 2023/24, QE for strong cross-encoders — https://arxiv.org/abs/2311.09175
6. Abe et al. 2025, LLM-based QE fails (SIGIR short) — https://arxiv.org/abs/2505.12694
7. Yoon et al. 2025, Knowledge leakage (ACL Findings) — https://arxiv.org/abs/2504.14175
8. Shanian et al. 2026, Better Together (EMNLP Industry) — https://arxiv.org/abs/2609.05637
9. Vake et al. 2025, HyPE (IEEE Access) — https://arxiv.org/abs/2607.29402
10. Li et al. 2025-26, QE survey — https://arxiv.org/abs/2509.07794
11. Rackauckas 2024, RAG-Fusion — https://arxiv.org/abs/2402.03367
12. Zheng et al. 2024, Step-back (ICLR) — https://arxiv.org/abs/2310.06117
13. Trivedi et al. 2023, IRCoT (ACL) — https://arxiv.org/abs/2212.10509
14. Ma et al. 2023, Rewrite-Retrieve-Read (EMNLP) — https://arxiv.org/abs/2305.14283
15. Jiang et al. 2024, Adaptive-RAG (NAACL) — https://arxiv.org/abs/2403.14403
16. Guo et al. 2024, LightRAG — https://arxiv.org/abs/2410.05779
17. Zhang et al., MRAG / TempRAGEval — https://arxiv.org/abs/2412.15540
18. TimelyRAG — https://arxiv.org/abs/2609.11572 ; ChronoQA — https://arxiv.org/abs/2508.12282
19. Park et al. 2026, DELTA (ACL Findings) — https://arxiv.org/abs/2601.02956
20. Zeng et al. 2025, unbiased GraphRAG evaluation — https://arxiv.org/abs/2506.06331
21. Han et al. 2025, RAG vs GraphRAG — https://arxiv.org/abs/2502.11371
22. DeepRetrieval — https://arxiv.org/abs/2503.00223
23. Vietnamese legal IR — https://arxiv.org/abs/2409.13699
24. RMIT LiveRAG (G-RAG, hypothetical answer + grid ANOVA) — https://arxiv.org/abs/2506.14516

## Method
Queries: ~12 web searches (QE strong retrievers, HyPE, temporal RAG, rewriting benchmarks, QE failure, HyDE multilingual, Jagerman, GraphRAG decomposition/keywords, Adaptive-RAG, TKGQA, Vietnamese, GraphRAG eval bias, DeepRetrieval/multilingual) and ~20 abstract/HTML fetches. Tools: WebSearch, WebFetch only.
