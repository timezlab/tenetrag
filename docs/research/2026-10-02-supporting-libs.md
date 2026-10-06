# Supporting libraries for a permissive GraphRAG SDK (as of 2026-10-02)

> **Snapshot, 2026-10-02 — not maintained.** Round 2 web research lane on
> supporting libraries: community detection, embeddings, rerankers, Vietnamese
> text processing and document parsers. The maintained, re-verified summary is
> in [supporting-libraries.md](../reference/supporting-libraries.md); where
> they differ, the maintained doc wins.
>
> **Errata and later resolutions:**
> - multilingual-e5-large-instruct is MIT, verified on its model card (the
>   report says "from memory, unverified").
> - Marker was re-checked: code Apache-2.0, model weights modified OpenRAIL-M,
>   as the table says. It is not GPL.
> - graspologic-native maintenance: the GitHub repo was last pushed
>   2026-06-14.

Method: PyPI JSON pages, HF model cards, GitHub, Databricks docs fetched this session. The fetch tool summarizes pages with a small model, so release dates are often missing or unreliable. Those cells say "n/v" (not verified). Licenses come from PyPI metadata or repo pages unless marked. Vietnamese = VN.

## Executive summary
- Hierarchical communities, permissive, light: NetworkX 3.5+ `leiden_partitions` (BSD-3, but "backend-only"). Otherwise graspologic-native (MIT, Rust, hierarchical Leiden, numpy+scipy only). Avoid leidenalg/igraph (GPL) and graspologic itself (heavy, stale, numpy<2 pin).
- Embeddings: Databricks FMAPI hosts only one multilingual embedding model, Qwen3-Embedding-0.6B (Public Preview, 2026-03). Others hosted are English-only. bge-m3 is the best-documented VN-capable open model. Avoid jina v3 (CC BY-NC).
- Postgres has no VN text-search config. Use `simple` + `unaccent` + `pg_trgm`, and optionally pre-segment text. ParadeDB pg_search is AGPL and absent from Lakebase's extension list.
- Parsing: Docling (MIT) is the main safe choice. PyMuPDF is AGPL (excluded). MinerU is no longer AGPL, but its new license has extra terms.

## 1. Community detection / graph algorithms
| name | version/date | license | maintained? | VN | notes | source |
|---|---|---|---|---|---|---|
| graspologic | 3.4.4 (GitHub release dated Sep 8, year not shown; likely 2024) | MIT | Stale: 3.4.4 still latest on PyPI (inference: ~2 yrs). Python `<3.13,>=3.9` | n/a | Deps: numpy<2, scipy<2, scikit-learn, gensim, hyppo, POT, statsmodels, umap-learn, matplotlib, seaborn, networkx<4, graspologic-native. Heavy. The numpy<2 pin and Python<3.13 conflict with modern runtimes | [PyPI](https://pypi.org/pypi/graspologic/json), [releases](https://github.com/graspologic-org/graspologic/releases) |
| graspologic-native | 1.3.1 (date n/v) | MIT | Likely (same org; unverified) | n/a | Rust (PyO3) hierarchical Leiden. Needs numpy>=1.24, scipy>=1.10, Python>=3.9. The kernel MS GraphRAG uses | [PyPI](https://pypi.org/pypi/graspologic-native/json) |
| leidenalg | 0.12.0 | GPL-3.0-or-later | Yes | n/a | Needs igraph>=1.0. **GPL risk** | [PyPI](https://pypi.org/pypi/leidenalg/json) |
| python-igraph / igraph | 1.0.0 | GPL ("GNU General Public License"; version not stated) | Yes | n/a | **GPL risk** | [PyPI](https://pypi.org/pypi/igraph/json) |
| networkx | 3.7 | BSD-3-Clause | Yes | n/a | 3.5 added Leiden "as a backend-only algorithm" (PR #7743). `leiden_partitions` yields a dendrogram, `leiden_communities` returns the best partition. Louvain, label propagation and PageRank are built in. "Backend-only" (needs a backend such as nx-parallel/graphblas; I could not confirm whether pure-Python fallback exists) | [PyPI](https://pypi.org/pypi/networkx/json), [3.5 notes](https://networkx.org/documentation/stable/release/release_3.5.html), [docs](https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.community.leiden.leiden_partitions.html) |
| cdlib | 0.4.1 (2026-07-25) | BSD-2-Clause | Yes | n/a | Core deps include python-igraph (GPL, transitive). Many deps. **Transitive GPL risk** | [PyPI](https://pypi.org/pypi/cdlib/json) |
| rustworkx | 0.18.1 | Apache-2.0 | Yes | n/a | Fast graph lib, no Leiden in the sources I read (unverified). Has PageRank | [PyPI](https://pypi.org/pypi/rustworkx/json) |
| scikit-network | 0.33.5 | BSD | Yes (n/v) | n/a | Louvain/Leiden and PageRank on scipy.sparse, with a light dependency set. Leiden is from memory, unverified this session | [PyPI](https://pypi.org/pypi/scikit-network/json) |
| GraphFrames | 0.11.0 (2026-04, via search snippet) | Apache-2.0 | Yes | n/a | Spark 3.5/4.0. Algorithms: PageRank, connected and strongly connected components, label propagation, triangle count, shortest paths, k-core, power iteration clustering, MIS. **No Leiden** seen. Maven coordinates changed to `io.graphframes` in 0.10 | [GitHub](https://github.com/graphframes/graphframes), [search summary](https://www.puppygraph.com/blog/graph-frames) |

Recommendation: default to graspologic-native for hierarchical Leiden (MIT, a few MB, MS-GraphRAG parity). Use networkx Leiden as a pure-permissive fallback once its backend requirement is confirmed. Use GraphFrames LPA/connected components for Delta-scale work; it has no Leiden, so hierarchy would need a custom implementation. Make igraph/leidenalg an opt-in extra that is documented as GPL, or exclude it.

## 2. Personalized PageRank / sparse math
| name | version | license | maintained? | notes | source |
|---|---|---|---|---|---|
| scipy.sparse | 1.18.1 | BSD-3 (bundles GCC runtime exception libs) | Yes | Power iteration with `csr_matrix @ vector` | [PyPI](https://pypi.org/pypi/scipy/json) |
| networkx `pagerank(personalization=)` | 3.7 | BSD-3 | Yes | Pure-Python/scipy-based. Dict conversion overhead | [PyPI](https://pypi.org/pypi/networkx/json) |
| fast-pagerank | 1.0.0 (2023-07-02) | MIT | Inactive since 2023 | Small scipy wrapper; claims faster than networkx. Trivial to inline | [PyPI](https://pypi.org/pypi/fast-pagerank/json) |

Performance (estimate / inference, not benchmarked here): a sparse-matrix power iteration costs O(iterations x nnz). For 10^4-10^6 edges with ~20-50 iterations that is milliseconds to about a second in scipy, and a few seconds in networkx at 10^6 edges (mostly conversion). Run a local benchmark before committing.
Recommendation: write about 30 lines of scipy.sparse PPR in the SDK (no extra dependency) and keep networkx only for offline use. Load the adjacency matrix once per index version and cache it. Because the graph lives in plain tables, build the CSR matrix from an edge-table scan.

## 3. Embeddings
| name | version/date | license | hosted/maintained | VN evidence | notes | source |
|---|---|---|---|---|---|---|
| Databricks FMAPI: `databricks-qwen3-embedding-0-6b` | 2026-03-17, Public Preview | Qwen3 Apache-2.0 | Databricks-hosted | 100+ languages, VN not named | Only multilingual model on FMAPI. 32K ctx, 1024-d with MRL down to 32 | [blog](https://www.databricks.com/blog/sota-embedding-model-agentic-workflows-now-public-preview) |
| Databricks FMAPI `databricks-gte-large-en`, `databricks-bge-large-en` | current | n/v | Hosted | English only, not multilingual | 1024-d; gte 8192 ctx, bge 512 | [docs](https://docs.databricks.com/aws/en/machine-learning/foundation-models/supported-models) |
| BAAI bge-m3 | n/v | MIT | Self-host | VN-MTEB avg 64.90, retrieval 39.84 | Dense+sparse+multi-vector, 8192 ctx, ~568M params. Note: MIRACL has no VN split (from memory, unverified) | [HF](https://huggingface.co/BAAI/bge-m3), [paper](https://arxiv.org/html/2507.21500v1) |
| multilingual-e5-large-instruct | n/v | MIT (from memory, unverified) | Self-host | VN-MTEB avg 67.99, retrieval 40.88 (best of the models in the paper's table); non-instruct large 63.87 / 37.65 | 512 ctx | [paper](https://arxiv.org/html/2507.21500v1) |
| Qwen3-Embedding 0.6B/4B/8B | 2025-06 | Apache-2.0 | Self-host / Databricks (0.6B) | No VN-specific numbers found. MMTEB mean 64.33 / 69.45 / 70.58 | 32K ctx | [HF](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B) |
| jina-embeddings-v3 | n/v | **CC BY-NC 4.0** | API/self-host | Multilingual, VN not verified | Non-commercial. **License risk** | [jina](https://jina.ai/models/jina-embeddings-v3/) |
| AITeamVN/Vietnamese_Embedding | n/v | Apache-2.0 | Community | Fine-tuned from bge-m3. Legal Zalo 2021 MRR@10 0.8181 (self-reported). VN-MTEB avg 63.34 / retrieval 34.18, below base bge-m3 | 2048 max length | [HF](https://huggingface.co/AITeamVN/Vietnamese_Embedding) |
| Cohere embed-multilingual-v3 | n/v | Proprietary API | Yes | VN listed among 100+ languages (weak source) | No VN benchmark found | [docs](https://docs.cohere.com/docs/cohere-embed) |
| OpenAI text-embedding-3 | n/v | Proprietary API | Yes | No VN-specific benchmark found; not in VN-MTEB | Reported MIRACL gains only | n/a |
| dangvantuan/vietnamese-embedding, bkai-foundation-models | not checked | not checked | | | Budget cut | n/a |

VN-MTEB caveat: the data is machine-translated (Aya-23-35B), so it is a weak proxy for native Vietnamese enterprise documents.

Recommendation: the SDK must make the embedding model pluggable and record model name and dimension in the index. Default to `databricks-qwen3-embedding-0-6b` on Databricks (Preview, so state this in the docs) and bge-m3 or multilingual-e5-large-instruct locally. Evaluate on a private Vietnamese golden set before choosing.

## 4. Rerankers
| name | license | VN evidence | notes | source |
|---|---|---|---|---|
| bge-reranker-v2-m3 | Apache-2.0 | None on the card (multilingual, built on bge-m3) | Self-host, about 568M params | [HF](https://huggingface.co/BAAI/bge-reranker-v2-m3) |
| Qwen3-Reranker 0.6B/4B/8B | Apache-2.0 | 100+ languages; MMTEB-R 66.36 / 72.74 / 72.94 | 32K ctx, instruction-aware | [HF](https://huggingface.co/Qwen/Qwen3-Reranker-0.6B) |
| jina-reranker-v2-base-multilingual | **CC BY-NC 4.0** | n/v | Non-commercial. **License risk** | [jina](https://jina.ai/models/jina-reranker-v2-base-multilingual/) |
| Cohere rerank-v3.5 (multilingual) | Proprietary API | Trained on 23 languages including VN (secondary source) | Not on FMAPI | [Azure catalog](https://ai.azure.com/catalog/models/Cohere-rerank-v3.5) |

Recommendation: make rerankers optional and off by default. Offer an LLM-as-reranker through the serving endpoint as a no-dependency path. Pair bge-reranker-v2-m3 or Qwen3-Reranker-0.6B as extras (both Apache-2.0).

## 5. Vietnamese text processing
| name | version/date | license | maintained? | notes | source |
|---|---|---|---|---|---|
| underthesea | 9.5.0 (about 2026-04) | Apache-2.0 | Yes | Core deps light (click, tqdm, requests, joblib, PyYAML, underthesea_core, huggingface-hub). torch/transformers are extras | [PyPI](https://pypi.org/pypi/underthesea/json) |
| pyvi | 0.1.1 (2021-06-30) | MIT | Abandoned | Needs scikit-learn and sklearn-crfsuite | [PyPI](https://pypi.org/pypi/pyvi/json) |
| VnCoreNLP | 1.2 jar (27 MB + 115 MB models) | **GPL-3.0-or-later** (LICENSE.md) | Low activity (46 commits) | Needs Java 1.8+. **License risk** | [GitHub](https://github.com/vncorenlp/VnCoreNLP), [LICENSE](https://raw.githubusercontent.com/vncorenlp/VnCoreNLP/master/LICENSE.md) |
| Postgres FTS | n/a | PostgreSQL license | n/a | No VN dictionary or stemmer config (my knowledge; the search did not contradict it). Use `simple` + `unaccent` | [unaccent docs](https://access.crunchydata.com/documentation/postgresql15/15.1/unaccent.html) |
| Lakebase extensions | n/a | n/a | n/a | pgvector 0.8.0-0.8.1, pg_trgm, unaccent (PG 16/17/18). Not seen: pg_search, pg_bigm | [docs](https://docs.databricks.com/aws/en/oltp/projects/extensions) |
| ParadeDB pg_search | 0.21.x | **AGPL-3.0** | Yes | BM25 over Tantivy; ICU tokenizer. Optional only, never bundled | [pigsty](https://pigsty.io/ext/fts/pg_search) |
| Databricks AI Search full-text | Beta | n/a | n/a | BM25. Tokenizer "splits at word boundaries, removes punctuation, lowercases". VN not documented. Storage-optimized endpoints only | [docs](https://docs.databricks.com/aws/en/ai-search/ai-search) |
| Unicode normalization | stdlib `unicodedata` | PSF | Yes | NFC at ingestion fixes composed/decomposed forms. Tone-mark placement (hòa vs hoà) is a separate step needing a small mapping table (own code; no vetted library found; inference) | n/a |

NER / LLM extraction in VN (single-source): a recent paper reports few-shot prompting improves LLMs on Vietnamese NER but stays below supervised encoder fine-tuning ([arXiv 2608.29890, En-ViMedNER, biomedical](https://arxiv.org/pdf/2608.29890); I read only the search snippet, so treat as unverified). VLSP 2021 supervised best F1 about 81.9. No evidence found on LLM relation or entity extraction quality for general VN enterprise text.

Recommendation: for lexical search, store an NFC, lowercased, accent-stripped column alongside the original (syllable-level tokens, since Vietnamese is whitespace-delimited by syllable). Add pg_trgm for entity-name fuzzy match, and keep bigram/phrase handling optional. Use underthesea only as an optional extra for word segmentation (Apache-2.0). Never relay VnCoreNLP.

## 6. Document parsing
| name | version/date | license | VN support | structure | notes | source |
|---|---|---|---|---|---|---|
| Docling | 2.132.0 (date n/v) | MIT | OCR via RapidOCR (PP-OCR v6 `vi`), EasyOCR (`vi` in latin model), Tesseract (`vie`, separate install) | Layout, reading order, tables (TableFormer); PDF/DOCX/PPTX/XLSX/MD | Model weight licenses not verified (check each: layout, TableFormer, OCR) | [PyPI](https://pypi.org/pypi/docling/json), [OCR docs](https://docling-project.github.io/docling/concepts/OCR_native/) |
| MinerU | 4.0.10 (2025-12-15 per PyPI page; contradicts a 3.1.0 = 2026-04 claim, so dates unreliable) | "MinerU Open Source License": Apache-2.0 plus extra terms: commercial license if MAU >100M or revenue >$20M/month; mandatory attribution for online services; auto-termination | Not verified | Layout, tables, formulas | Moved off AGPL (secondary source). Not Apache: **license risk** | [PyPI](https://pypi.org/pypi/mineru/json), [LICENSE](https://github.com/opendatalab/MinerU/blob/master/LICENSE.md) |
| Marker | 2.0.0 | Code Apache-2.0 (PyPI); model weights modified AI Pubs Open RAIL-M, free only below $5M funding/revenue | Not verified | Layout, tables, formulas | Needs PyTorch. Single-source, and contradicts the "GPL" expectation, so re-check the repo. **Weights license risk** | [PyPI](https://pypi.org/pypi/marker-pdf/json) |
| Unstructured | 0.27.10 (n/v) | Apache-2.0 | OCR via tesseract | Partitioning | Heavy deps (spacy, pandas, unstructured-inference). Version looks odd and is unverified | [PyPI](https://pypi.org/pypi/unstructured/json) |
| PyMuPDF | 1.28.2 | **AGPL-3.0 or Artifex commercial** | n/a | Fast text/tables | **Exclude, even as an extra** | [PyPI](https://pypi.org/pypi/pymupdf/json) |
| pypdf | 6.19.0 (date unreliable) | BSD-3-Clause | Text layer only | No layout | Pure Python | [PyPI](https://pypi.org/pypi/pypdf/json) |
| pdfplumber | 0.11.10 (2026-06-15) | MIT | Text layer only | Tables from native PDFs | Built on pdfminer.six | [PyPI](https://pypi.org/pypi/pdfplumber/json) |
| python-docx | 1.2.0 (2025-06-16) | MIT | Unicode native | Paragraphs, tables | | [PyPI](https://pypi.org/pypi/python-docx/json) |
| python-pptx | 1.0.2 (2024-08-07) | MIT | Unicode native | Slides, tables | Slow cadence | [PyPI](https://pypi.org/pypi/python-pptx/json) |
| openpyxl | 3.1.5 (2024-06-28) | MIT | Unicode native | Sheets | Slow cadence | [PyPI](https://pypi.org/pypi/openpyxl/json) |
| Databricks `ai_parse_document` | GA (per current doc page) | Managed service | Docs warn about non-Latin scripts (JP/KR); VN not stated. Earlier snippets said "tuned for English" | Layout elements, tables, figures; PDF, images, DOC(X), PPT(X) (no XLSX); max 500 pages / 100 MB; regional | Not usable locally or in non-Databricks runs | [docs](https://docs.databricks.com/aws/en/sql/language-manual/functions/ai_parse_document) |

Recommendation: core extras are python-docx, python-pptx, openpyxl, pypdf and pdfplumber (all permissive). Offer Docling as an optional `[layout]` extra for layout and table structure, after checking model-weight licenses. Offer `ai_parse_document` as a Databricks-only parser behind a protocol, tested on a VN sample. Do not depend on PyMuPDF, VnCoreNLP, leidenalg, igraph, jina models or MinerU/Marker without legal review.

## License risk list
1. **GPL**: leidenalg 0.12.0 (GPL-3.0+), python-igraph 1.0.0 (GPL), VnCoreNLP (GPL-3.0+). cdlib pulls igraph transitively.
2. **AGPL**: PyMuPDF; ParadeDB pg_search.
3. **Non-commercial**: jina-embeddings-v3 and jina-reranker-v2 (CC BY-NC 4.0).
4. **Custom or restricted**: MinerU Open Source License (revenue/MAU thresholds plus attribution); Marker model weights (modified Open RAIL-M, $5M cap).
5. **Unverified**: Docling model weight licenses (TableFormer, layout, OCR models); multilingual-e5 license (MIT from memory); graspologic-native maintenance.
6. **Platform dependency**: Databricks Qwen3 embedding endpoint is Public Preview; AI Search full-text is Beta.

gaps: Release dates for most PyPI items were not obtainable through the fetch tool. No direct Vietnamese benchmark for Qwen3-Embedding, OpenAI, Cohere, Jina or any reranker. dangvantuan/vietnamese-embedding and bkai models were not checked. NetworkX Leiden "backend-only" behaviour is unclear. Docling model licenses, pg_bigm and a tone-mark library were not covered. PPR timings were not measured.
leads: a Vietnamese golden-set evaluation of embeddings and rerankers, a legal review of the Docling model weights, and a local PPR benchmark.
