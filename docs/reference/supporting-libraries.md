# Supporting libraries — licenses and Vietnamese support

**Verified:** 2026-10-02 from PyPI metadata, GitHub repo pages and model
cards. Release dates were often unavailable and are omitted. These are
**candidates**, not chosen dependencies. Before adding any of them, run the
dependency gate in `.agents/rules/common/security.md`: exact name, OSV.dev,
install scripts, no release from the last 24 h. The SDK is permissively
licensed, so a GPL or AGPL runtime dependency, even an optional one, needs an
explicit decision. Databricks-side facts (Lakebase extensions, hosted models,
`ai_parse_document`) are in
[databricks-platform.md](databricks-platform.md).
Raw lane reports (snapshots, not maintained):
[supporting libraries](../research/2026-10-02-supporting-libs.md),
[library reuse audit](../research/2026-10-04-library-reuse.md) (2026-10-04).
Reuse rule: [ADR 0009](../decisions/0009-reuse-permissive-libraries-behind-adapters.md).

## Reuse audit (2026-10-04)

LlamaIndex was read in source at tag v0.14.25 (2026-09-21), and PyPI
metadata on 2026-10-04. Nothing was installed or run. Labels: [source] read
in code, [pypi] package metadata, [inferred].

**`llama-index-core` 0.14.25** — MIT, Python ≥ 3.10, Pydantic ≥ 2.8.

| Finding | Where | Effect on us |
|---|---|---|
| 25 required dependencies, including nltk, SQLAlchemy, networkx, numpy, Pillow, tiktoken, aiohttp | [pypi] | Heavy for an extra; never in the base package |
| `import llama_index.core` imports SQLAlchemy and Pillow eagerly | `__init__.py` [source] | Slow, heavy import |
| `Settings.llm` and `Settings.embed_model` default to OpenAI and read `OPENAI_API_KEY`; many components fall back to `Settings.llm` | `settings.py`, `llms/utils.py`, `embeddings/utils.py` [source] | Breaks fail-closed credentials unless every model is passed explicitly |
| The Databricks LLM class falls through to `OPENAI_API_KEY` when its own variables are unset | `llama-index-llms-databricks` `base.py` [source] | A cross-identity fallback; do not use |
| No telemetry; NLTK and tiktoken data ship inside the wheel | wheel listing [source] | No network on the default path |
| Splitters recover offsets with `str.find` after stripping; ids are `uuid4` unless `id_func` is set; tokens counted with the gpt-3.5 encoding | `node_parser/interface.py`, `node_utils.py`, `text/sentence.py` [source] | Usable only with our offset check, ids, tokenizer and an exact pin |
| `IngestionPipeline` hashes text plus metadata, keeps its own docstore | `ingestion/pipeline.py`, `schema.py` [source] | Conflicts with our two-level hashing and run model |
| Property-graph extractors emit triples with no dates, evidence or facts | `property_graph/transformations/schema_llm.py` [source] | Bypasses our pack compiler; prompt reference only |
| HyDE ~25 lines, RRF ~25 lines (fuses on a node hash), `StepDecomposeQueryTransform` "doesn't work yet" | `query_transform/base.py`, `retrievers/fusion_retriever.py` [source] | Write our own, with attribution |
| `SentenceTransformerRerank` sets `trust_remote_code=True` by default | `postprocessor/sbert_rerank.py` [source] | Use `CrossEncoder` directly |
| 20 core releases in 12 months, small breaking changes in patch versions | changelog [pypi] | Pin exactly if used |

**Lighter libraries for single steps:**

| Library | Version | License | Dependencies | Notes |
|---|---|---|---|---|
| semchunk | 4.1.1 | MIT | tqdm | `offsets=True` returns spans with `chunk == text[start:end]` by construction [source]. Best fit for provenance |
| chonkie | 1.7.0 | MIT | heavier | Chunks carry start and end indexes; exactness not verified |
| langchain-text-splitters | 1.1.3 | MIT | langchain-core | Offsets found with `find`, like LlamaIndex |
| markitdown | 0.1.8 | MIT | per-format extras | Converts to Markdown, so offsets refer to the converted text, which must become the stored text |
| docling | 2.133.0 | MIT (code) | torch | Two layout-model cards show Apache-2.0 and CDLA-Permissive-2.0; other models unchecked. Prefetch models with `artifacts_path` |
| unstructured | 0.27.10 | Apache-2.0 | spaCy, numba; Python ≥ 3.11 | Too heavy |
| bm25s | 0.3.12 | MIT | numpy | English stopwords and a `\w\w+` tokenizer by default; pass `stopwords=None` |
| rank-bm25 | 0.2.2 | Apache-2.0 | numpy | Unmaintained since 2022 |
| sentence-transformers | 6.1.0 | Apache-2.0 | torch | `CrossEncoder` for reranking |
| haystack-ai | 3.3.0 | Apache-2.0 | posthog | Telemetry on by default, from the opt-out notice on `main` [inferred] |

## License risk list

| Risk | Packages |
|---|---|
| GPL | `leidenalg` (GPL-3.0+), `python-igraph` (GPL), VnCoreNLP (GPL-3.0+); `cdlib` pulls in igraph |
| AGPL | PyMuPDF (AGPL-3.0 or commercial), ParadeDB `pg_search` (also not offered on Lakebase) |
| Non-commercial | `jina-embeddings-v3`, `jina-reranker-v2-base-multilingual` (CC BY-NC 4.0) |
| Custom terms | MinerU (Apache-2.0 base, plus a commercial license above usage thresholds and mandatory attribution); Marker model weights (modified OpenRAIL-M, free below $5M funding or revenue; code is Apache-2.0) |
| No license file | KGGen (`pyproject.toml` says MIT; GitHub reports none) |
| Unverified | Docling model-weight licenses |

## Community detection and graph algorithms

| Library | Version | License | Notes |
|---|---|---|---|
| graspologic-native | 1.3.1 | MIT | Rust hierarchical Leiden, the kernel MS GraphRAG uses; needs only numpy and scipy |
| graspologic | 3.4.4 | MIT | Heavy dependency tree (gensim, POT, umap-learn, matplotlib…) with `numpy<2`; appears unmaintained |
| networkx | 3.7 | BSD-3-Clause | Louvain, label propagation, PageRank with personalization; Leiden since 3.5 but documented as backend-only (pure-Python fallback not confirmed) |
| leidenalg, python-igraph | 0.12.0, 1.0.0 | GPL | Avoid |
| cdlib | 0.4.1 | BSD-2-Clause | Depends on python-igraph |
| rustworkx | 0.18.1 | Apache-2.0 | No Leiden found |
| GraphFrames | 0.11.x | Apache-2.0 | Spark: PageRank, connected components, label propagation, shortest paths; no Leiden. Useful for batch clustering over Delta |

**Recommendation:**
- Use graspologic-native for communities, behind the `communities` extra
  ([ADR 0011](../decisions/0011-cluster-by-default-and-make-community-reports-opt-in.md)).
- Use networkx Leiden as a fallback once its backend requirement is
  confirmed.
- On Delta, GraphFrames connected components can cluster entity-resolution
  candidates.

## Personalized PageRank

- scipy (BSD-3-Clause) power iteration over a CSR matrix built from the edge
  table is about 30 lines. That needs no new dependency.
- NodeRAG's `utils/PPR.py` (MIT) is a port target. `fast-pagerank` (MIT) is
  inactive.
- Expected cost is O(iterations × edges). For 10⁴–10⁶ edges that is
  milliseconds to about a second in scipy. This is an **estimate**, not
  measured, so benchmark it before committing. Cache the matrix per index
  version.

## Multilingual embeddings

| Model | License | Vietnamese evidence | Notes |
|---|---|---|---|
| `databricks-qwen3-embedding-0-6b` (FMAPI) | Apache-2.0 weights | 100+ languages; no Vietnamese-specific score found | The only multilingual embedding hosted by Databricks (Public Preview); 32K context, 1024-d with Matryoshka |
| multilingual-e5-large-instruct | MIT | VN-MTEB average 67.99, retrieval 40.88: best in the VN-MTEB table | Self-host |
| BAAI bge-m3 | MIT | VN-MTEB average 64.90, retrieval 39.84 | Dense + sparse + multi-vector; 8192 context; the dense baseline in MaGiX |
| AITeamVN/Vietnamese_Embedding | Apache-2.0 | Fine-tuned from bge-m3; VN-MTEB below its base | Self-reported legal-domain gains |
| Qwen3-Embedding 4B / 8B | Apache-2.0 | MMTEB mean 69.45 / 70.58; no Vietnamese breakdown | Self-host |
| Cohere embed-multilingual-v3, OpenAI text-embedding-3 | Proprietary | No Vietnamese benchmark found | API |
| jina-embeddings-v3 | CC BY-NC 4.0 | — | Excluded |

VN-MTEB ([arXiv 2507.21500](https://arxiv.org/abs/2507.21500)) is
machine-translated, so it is a weak proxy for native enterprise Vietnamese.
Record the embedding model and dimension with the index, and choose the model
from our own golden set.

## Rerankers

| Model | License | Notes |
|---|---|---|
| bge-reranker-v2-m3 | Apache-2.0 | Multilingual, built on bge-m3; no Vietnamese score on the card |
| Qwen3-Reranker 0.6B / 4B / 8B | Apache-2.0 | MMTEB-R 66.36 / 72.74 / 72.94; instruction-aware |
| Cohere rerank-v3.5 | Proprietary | Vietnamese listed among training languages (secondary source) |
| jina-reranker-v2-base-multilingual | CC BY-NC 4.0 | Excluded |

**Recommendation:** make rerankers optional and off by default. An LLM
reranker through the serving endpoint is the no-dependency path.

## Vietnamese text processing

| Tool | License | Notes |
|---|---|---|
| Python `unicodedata` | PSF | NFC at ingest. Tone-mark placement (`hòa` vs `hoà`) needs a small mapping table of our own; no vetted library found |
| underthesea 9.5.0 | Apache-2.0 | Word segmentation and NER; light core dependencies, torch only as an extra |
| pyvi 0.1.1 | MIT | Abandoned since 2021 |
| VnCoreNLP 1.2 | GPL-3.0+ | Java; avoid |
| Postgres full-text | PostgreSQL | No Vietnamese dictionary or stemmer. Use the `simple` config on the engine's normalized column, plus `pg_trgm` for fuzzy names. `unaccent` is available on Lakebase but not used (decision below) |
| AI Search full-text (Beta) | Databricks | BM25; the tokenizer splits on word boundaries and lowercases. Vietnamese behaviour undocumented |

Vietnamese words span several space-separated syllables, so a `simple`
tokenizer indexes syllables, not words. Phrase queries and trigram matching
recover much of this, but measure it on the golden set before adding a
segmenter [inferred]. Keep an NFC, lowercased, tone-mark-normalized column
beside the original text for matching, and never overwrite the original.

**Diacritics are kept** (author, 2026-10-04). Stripping them merges
different words: in the first test corpus, `lãi` (interest) appears 1,548
times and `lại` (again) 653 times, and both would become `lai`. The same
goes for names such as Lai and Lại. A query typed without diacritics gets
them back from a model: the calling agent, or the opt-in diacritic
restoration strategy
([ADR 0010](../decisions/0010-offer-query-strategies-as-opt-in-benchmarked-options.md)).
Not verified: whether `pg_trgm` and the `simple` parser treat Vietnamese
letters as word characters under the database's ctype (a `C` ctype may
not), including on Lakebase. The contract suite must test it.

## Document parsing

| Library | License | Vietnamese | Structure | Notes |
|---|---|---|---|---|
| python-docx, python-pptx, openpyxl | MIT | Unicode native | Paragraphs, slides, sheets, tables | Slow release cadence |
| pypdf | BSD-3-Clause | Text layer only | None | Pure Python |
| pdfplumber | MIT | Text layer only | Tables in born-digital PDFs | Built on pdfminer.six |
| Docling 2.x | MIT (code) | OCR via RapidOCR, EasyOCR or Tesseract `vie` | Layout, reading order, tables; PDF, DOCX, PPTX, XLSX | Check model-weight licenses before shipping it as an extra |
| Unstructured | Apache-2.0 | OCR via Tesseract | Partitioning | Heavy dependencies |
| Marker | Apache-2.0 code; restricted weights | Not verified | Layout, tables | Weights not free for larger companies |
| MinerU | Custom | Not verified | Layout, tables, formulas | Custom license terms |
| PyMuPDF | AGPL-3.0 | — | — | Excluded, even as an extra |
| `ai_parse_document` | Databricks service | "Non-optimal" for non-Latin scripts; Vietnamese not stated | Typed elements, bounding boxes; no XLSX | Databricks only; see [databricks-platform.md](databricks-platform.md#document-parsing) |

**Recommendation:**
- The base parsers are the MIT/BSD set in the first three rows.
- Docling becomes an optional layout extra once its weights are checked.
- `ai_parse_document` is a Databricks-only parser behind the parser
  protocol, tested on Vietnamese samples.
