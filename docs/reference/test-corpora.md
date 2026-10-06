# Test corpora — candidates, licenses and fit

**Verified:** 2026-10-04 from dataset pages, papers and license texts where
marked [primary]. Search summaries are marked [secondary], and our
judgment [inferred]. Before using any set, re-read its license page.
Raw report (snapshot, not maintained): kept in `docs/private/research/`
because it names an adopter context.

## Why this page exists

An adopter's internal documents stay inside its environment. They never
reach a developer laptop or this repository. Development and the
benchmark still need documents that resemble them:
- internal policies and procedures that get new versions;
- meeting minutes with decisions and action items;
- product and campaign documents;
- documents with historical figures and metric formulas;
- Vietnamese and English, sometimes mixed in one document;
- PDF, DOCX, PPTX, XLSX and Markdown.

The question types to cover are listed in the
[brief](../product/sdk-platform-brief.md): single-fact lookup, everything
about an entity, decisions in meetings, definitions and formulas,
historical figures, as-of-date questions over versioned documents,
conflicting versions, and cross-lingual questions.

No public dataset matches all of this. The plan combines a synthetic
corpus, public proxy corpora and, later, the real corpus in place.

## Plan

| Tier | What | Where it lives | Purpose |
|---|---|---|---|
| 1 | Synthetic bilingual corpus from our own generator, 30–60 documents, with planted ground truth | public repo (`tests/fixtures/`) | Unit tests, pack trials, as-of and conflict tests, delete tests, CI |
| 2 | Public proxy corpora, closest first (tables below) | downloaded locally by a script, never committed unless the license allows it | M1 end-to-end runs, the benchmark, per-type breakdown |
| 3 | The adopter's real corpus | the adopter's workspace only | The quality gate. The same benchmark harness runs as a job there and exports only aggregate metrics per question type |

**Tier 1 generator** [inferred]. A script writes documents from a fact
table it controls:
- policy versions with effective dates and supersession;
- meetings with decisions and action items;
- conflicting definitions of the same metric from two sources;
- figures with periods;
- a Vietnamese–English mix.

It renders the documents to MD, DOCX, PPTX, XLSX and PDF, and writes one
golden JSON file per question type. The golden answers come from the
fact table, so they are exact. One known risk: LLM-written questions
overlap the text more than human questions do. Mix in hand-written
questions.

## English proxies

| Corpus | Size | License; may it go in the repo? | QA | Dates or versions | Exercises | Fit (1–5) |
|---|---|---|---|---|---|---|
| [EnterpriseRAG-Bench](https://github.com/onyx-dot-app/EnterpriseRAG-Bench) (arXiv 2605.05253) | ~500k synthetic company documents across chat, email, tickets, docs and wikis; 500 questions in 10 categories plus 100 metadata-dependent | MIT [primary]; small subsets yes | yes | conflicting information and near-duplicates; versions not verified | multi-document, conflicts, absent information | 4 |
| [Python PEPs](https://peps.python.org/pep-0012/) | several hundred | public domain or CC0 [primary]; yes | no, generate from headers | `Status`, `Replaces`, `Superseded-By`, dates | version chains, supersession, as-of status | 4 |
| [Apache board minutes](https://www.apache.org/foundation/records/minutes/) | monthly, 1999–2026 [primary] | Apache-2.0 per the records page [secondary]; confirm before committing | no | dated meetings | decisions, action items, officers, projects | 4 |
| [FOMC statements and minutes](https://www.federalreserve.gov/disclaimer.htm) | many | mostly public domain [primary]; check per page | no | dated decisions over time | decisions per meeting, figures with period | 4 |
| [WixQA](https://huggingface.co/datasets/Wix/WixQA) | 6,221 articles; 200 expert and 200 simulated QA pairs | MIT [primary]; yes | yes | no | product documentation lookup, how-to | 3 |
| [MultiHop-RAG](https://huggingface.co/datasets/yixuantt/MultiHopRAG) | 609 documents, 2,556 queries | ODC-BY [primary]; yes, with attribution | yes, typed (inference, comparison, temporal, null) | dated news | per-type benchmark plumbing | 3 |
| [IETF RFCs](https://trustee.ietf.org/documents/trust-legal-provisions/tlp-5/) | ~9,000 | RFCs after 2015-03-25 may be copied whole but not modified [primary]; download at test time | no | `Obsoletes`, `Updates` | supersession, definitions | 3 |
| SEC EDGAR filings | many | redistribution terms not verified | no; generate from XBRL facts | multi-year | finance pack: ownership, figures, securities | 4 |

**Local use only (non-commercial licenses):**

| Corpus | License | Exercises |
|---|---|---|
| [FinanceBench](https://huggingface.co/datasets/PatronusAI/financebench) | CC BY-NC 4.0 [primary] | figures with period and source, from PDF filings |
| [MeetingBank](https://huggingface.co/datasets/huuuyeah/meetingbank) | CC BY-NC-SA 4.0 [primary] | real minutes and agendas; decisions per meeting |
| [CRAG](https://github.com/facebookresearch/CRAG) | CC BY-NC 4.0 [primary] | questions whose answers change over time |

## Vietnamese proxies

| Corpus | Size | License; may it go in the repo? | QA | Dates or versions | Fit (1–5) |
|---|---|---|---|---|---|
| Legal normative documents from the official database ([vbpl.vn](https://vbpl.vn)) | large | excluded from copyright by IP Law Article 15 [secondary: legal summaries; statute text not read]; site terms not verified | no | amendments, replacements, effective dates (relation fields on the site not verified) | 4 |
| [Zalo Legal Text Retrieval](https://huggingface.co/datasets/GreenNode/zalo-ai-legal-text-retrieval-vn) (MTEB mirror) | 60,701 documents, 788 queries | MIT on the mirror [primary]; original challenge terms not verified | yes | no | 3 |
| Public disclosures of listed companies: AGM minutes and resolutions, annual reports, many in both Vietnamese and English | many years | not verified; download locally only | no | yearly | 4 |
| ViNumQA (VLSP 2025) | over 4,000 numeric finance QA triples | not verified [secondary] | yes | report periods | 3 |
| [VN-MTEB](https://arxiv.org/abs/2507.21500) | 41 machine-translated datasets | per dataset | qrels | no | 2 (embedding choice only) |

For cross-lingual tests, machine-translate a subset of a tier-1 or tier-2
corpus and label it as machine-translated.

## Not verified
- Licenses of ELITR, QMSum, AMI, DocFinQA, TAT-DQA, ConvFinQA, FRAMES,
  TimeQA, ALQAC, VLSP, ViNumQA, ECB accounts and EnronQA.
- SEC redistribution terms; vbpl.vn terms and relation metadata.
- Not checked at all: EnterpriseBench, ConcurrentQA, Loong, DocBench,
  benchmark-qed AutoQ, RAGAS test-set generation, UIT-ViQuAD 2.0.
- The 10 category names and file formats of EnterpriseRAG-Bench.
- Whether the EnterpriseRAG-Bench generator can plant versions and as-of
  facts.
