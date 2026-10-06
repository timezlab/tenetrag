# Offer query strategies as opt-in, benchmarked retrieval options

**Status:** accepted
**Date:** 2026-10-04
**Deciders:** Liam Lee (session 2026-10-04)

## Context
The retrieval flow from
[ADR 0006](0006-rename-to-tenetrag-and-run-beyond-databricks.md) has no LLM
by default. Entity linking and hybrid chunk search seed the graph,
expansion follows it, and provenance leads to chunks. The calling agent
iterates. The author wants query strategies, such as HyDE, that users can
switch on to improve search, and that the benchmark can measure.

Research on 2026-10-04
([graphrag-research.md](../reference/graphrag-research.md#query-strategies)):
- HyDE and Query2doc gains are large over BM25 and small over strong dense
  retrievers. Query2doc reports +3 to +15 points over BM25 and +0.4 to +1.9
  over distilled dense retrievers.
- The gains depend on the LLM already knowing the answer. When it does not,
  they shrink, and dense retrieval can drop. A private corpus is the worst
  case.
- Multi-query with fusion helped on a hard enterprise set and hurt on
  ambiguous questions.
- Parsing a time constraint out of the query into a filter suits question
  types that need dates.
- Generating questions per chunk at index time (HyPE) adds no query
  latency.
- No study covers Vietnamese, and few test modern multilingual embedders.

## Decision
1. **A query-strategy stage runs before retrieval entry.** Each strategy
   takes the query and returns one or more of: query variants, filters
   (such as a date range), or extra vectors. Results fuse through the
   existing RRF. The original query is always kept.
2. **All strategies are off by default.** The no-LLM pipeline stays the
   default and the baseline. Each strategy is a profile parameter.
   Query-side strategies are query-time. Chunk-question generation is
   index-time
   ([ADR 0005](0005-index-time-vs-query-time-parameters.md)).
3. **All strategies the author named ship in v1, off by default,** except
   conversational rewriting, which stays with the calling agent. The engine
   brief fixes the exact list and prompts.

   | Strategy | Kind | LLM | Status |
   |---|---|---|---|
   | Temporal constraint parsing into a date filter | query-time | rules first, LLM optional | v1 |
   | Keyword and entity extraction for entity linking | query-time | none by default, LLM optional | v1 |
   | Bilingual query variant fused with the original | query-time | translation call or none | v1 |
   | Diacritic restoration for a Vietnamese query typed without diacritics, added next to the original | query-time | 1 call | v1; added on 2026-10-04 because matching keeps diacritics |
   | Multi-query with RRF (3–4 variants) | query-time | 1 call | v1 |
   | Questions per chunk as extra vectors (HyPE) | index-time | per chunk at index | v1 |
   | HyDE, Query2doc | query-time | 1 call | v1; docs warn that gains shrink on private corpora and with strong embedders |
   | Confidence-gated routing | query-time | some queries | v1, as a mode of the optional router ([ADR 0006](0006-rename-to-tenetrag-and-run-beyond-databricks.md)) |
   | Decomposition, IRCoT | multi-step | per hop | v1, as a separate method `retrieve_multi_step()`; `retrieve()` stays one step |
   | Conversational rewriting | query-time | 1 call | not in the SDK: the calling agent owns the chat history and rewrites the query |

4. **Every strategy is a benchmark variant.** It is compared with the
   no-LLM baseline that uses the production embedder and, if configured,
   the reranker. Reports are broken down by question type and embedder.
   Columns:
   - recall@k and MRR on evidence chunk ids;
   - entity-link recall;
   - as-of correctness;
   - extra LLM calls;
   - p50 and p95 latency;
   - tokens;
   - index-time LLM calls.

   Each report shows the worst per-type loss beside the average gain.
5. **LLM strategies use the `ChatModel` protocol with explicit
   credentials.** Their prompts resolve through the prompt resolver
   ([ADR 0004](0004-sdk-owned-versioning.md)). A translated query is added
   next to the original, never in place of it.

## Alternatives considered
- **HyDE on by default.** Rejected: its gain shrinks with modern dense
  retrievers. It also depends on the LLM knowing facts that a private
  corpus holds and the LLM has never seen.
- **Leave all query rewriting to the agent.** Rejected: the author wants
  built-in options. Temporal parsing and entity extraction depend on our
  graph's dates and types, which the agent does not know.
- **Conversational rewriting in the SDK,** through
  `retrieve(query, history=...)`. Rejected by the author: the agent holds
  the conversation and can send a self-contained query.
- **Decomposition as a mode of `retrieve()`.** Rejected: one call would then
  hide several LLM calls and hops. A separate method keeps `retrieve()`
  predictable.
- **Ship the strategies without benchmark variants.** Rejected: averages
  hide per-type harm. A strategy that helps multi-hop questions can hurt
  simple lookups.

## Consequences

**Better:**
- Users switch on a strategy and see its effect per question type on their
  own golden set.
- Temporal parsing turns the graph's dates into filters.

**Worse:**
- Each strategy adds prompts, tests and benchmark cost.
- LLM strategies add latency. Query2doc reports over 2 seconds per query.
- A strategy switched on blindly can lower quality on simple or ambiguous
  questions.

**Must now be true:**
- Every strategy is off unless the profile enables it.
- No strategy replaces the original query.
- Each strategy has a benchmark variant and a per-question-type report.
- Retrieval metrics count the LLM calls and tokens a strategy adds.
- Chunk-question generation is declared index-time, so switching it on
  marks documents for re-index.

## Revisit if
- A strategy beats the baseline on every question type of a real golden
  set. It could then become a default.
- Evidence for Vietnamese or for modern multilingual embedders changes the
  picture.
