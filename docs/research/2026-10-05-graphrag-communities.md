# Microsoft GraphRAG communities in source — research report

> **Snapshot, 2026-10-05 — not maintained.** Code lane: microsoft/graphrag
> tag v3.2.0 (commit 769542f) read in a shallow clone, with v2.7.0 fetched
> for comparison. Nothing from GraphRAG was executed. A separate demo ran
> graspologic-native 1.3.1 `hierarchical_leiden` on a toy graph. The
> maintained summary is in
> [graphrag-engines.md](../reference/graphrag-engines.md#microsoft-graphrag-communities);
> where they differ, the maintained doc wins. Local paths were removed
> before publishing.

Paths are relative to `packages/graphrag/graphrag/`. Labels: [source] read
at the cited lines · [inferred] deduced from the code.

## 1. Graph input to clustering
- The clustering input is the relationships table only
  (`index/workflows/create_communities.py:32,86`). Nodes are the source and
  target titles found in edges [source]. Entities with no relationship never
  get a community [inferred].
- Edge weight is the LLM `relationship_strength`, parsed as a float, with
  1.0 when parsing fails (`index/operations/extract_graph/graph_extractor.py:158-163`).
  Duplicate pairs across chunks are summed (`weight=("weight","sum")`,
  `index/workflows/extract_graph.py:126`). The weight is not a count [source].
- The graph is undirected: `index/operations/cluster_graph.py:60-67` puts
  the lesser name first, then `drop_duplicates(keep="last")`. A reversed
  pair keeps the last row's weight; it is not summed [source].
- Descriptions are summarized by an LLM only when an item has 2 or more
  descriptions (`summarize_descriptions/description_summary_extractor.py:63-68`).
  Defaults are `max_length` 500 and `max_input_tokens` 4000
  (`config/defaults.py:316-323`). Clustering ignores descriptions [source].

## 2. Clustering
- The call is `graspologic_native.hierarchical_leiden`
  (`graphs/hierarchical_leiden.py:11-26`) with resolution 1.0, randomness
  0.001, modularity and 1 iteration. v3 no longer imports graspologic
  [source].

| Setting | Default | Where |
|---|---|---|
| `max_cluster_size` | 10 | `config/defaults.py:71` |
| `use_lcc` | True | `config/defaults.py:72` |
| `seed` | 0xDEADBEEF | `config/defaults.py:73` |

- With `use_lcc`, `stable_lcc` keeps only edges with both endpoints in the
  largest connected component (`graphs/stable_lcc.py:51-58`). Nodes outside
  it get no community. It also upper-cases and strips names [source].
- Level 0 is the coarsest. Dynamic selection starts at level 0 as the root
  (`query/context_builder/dynamic_community_selection.py:70-71`) [source;
  direction partly inferred].
- Parent is `partition.parent_cluster`, or -1 at the root
  (`cluster_graph.py:95-97`). Children come from grouping on parent
  (`create_communities.py:166-178`) [source].
- graspologic-native splits any cluster whose size reaches
  `max_cluster_size` into a subnetwork and runs Leiden on it again, until
  no cluster exceeds the cap (function docstring) [source].

## 3. Communities table
- Columns (`data_model/schemas.py:92-105`): id, human_readable_id,
  community, level, parent, children, title, entity_ids, relationship_ids,
  text_unit_ids, period, size [source].
- A relationship belongs to a community only when both endpoints are in
  the same community at that level (`create_communities.py:113-127`).
  `text_unit_ids` come from those relationships (lines 131-134) [source].

## 4. Community reports
- Levels run finest first (`summarize_communities/utils.py:11-17`);
  communities in a level run concurrently [source].
- Context (`summarize_communities/graph_context/sort_context.py:57-126`):
  edges sorted by combined endpoint degree, descending; their nodes and
  claims are added in that order until `max_input_length`. Sections:
  Entities, Claims, Relationships [source].
- Quirk: edge details are aggregated per node with `agg("first")`
  (`graph_context/context_builder.py:101-115`), so each node carries at most
  one edge as source and one as target. The same line is in v2.7.0
  [source].
- Substituting sub-community reports for an oversized context
  (`build_mixed_context.py`) looks unreachable: `summarize_communities.py:63-73`
  builds every level's context while the report list is still empty, and
  reports are generated afterwards (lines 75-98). Oversized contexts are
  trimmed. v2.7.0 has the same structure [inferred, strong].
- Output (`community_reports_extractor.py:32-41`): title, summary,
  findings[{summary, explanation}], rating (float), rating_explanation; the
  table adds `full_content` and `full_content_json` [source].
- Defaults: `max_length` 2000, `max_input_length` 8000
  (`config/defaults.py:82-83`). The prompt asks for an impact severity
  rating from 0 to 10 (`prompts/index/community_report.py:17`) [source].
- The Fast pipeline uses a text-based report variant built from text units
  (`workflows/create_community_reports_text.py`, `workflows/factory.py:64-73`)
  [source].

## 5. Global search
- Default `community_level` 2 is set only in the CLI
  (`cli/main.py:404-405`); the API has none (`api/query.py:68`) [source].
- Report selection (`query/indexer_adapters.py:87-101`): keep levels ≤ N,
  then give each entity the report of its deepest community at or below N
  [source].
- Batching (`query/context_builder/community_context.py:100-186`): reports
  shuffled with seed 86, packed under `max_context_tokens` 12000, ordered
  with an occurrence weight (normalized text-unit count). One map call per
  batch [source].
- The factory passes `use_community_summary: False` and
  `include_community_rank: True` (`query/factory.py` ~162-170), so the map
  step reads `full_content` [source].
- Map output: `{"points":[{"description","score"}]}`, integer score 0–100
  (`global_search/search.py:276-304`,
  `prompts/query/global_search_map_system_prompt.py:21`); `map_max_length`
  1000 [source].
- Reduce (`search.py:333-380`): drops points with score ≤ 0, sorts by score,
  fills `data_max_tokens` 12000, writes with `reduce_max_length` 2000.
  With no points and general knowledge off (factory default), it returns a
  canned no-data answer [source].
- Dynamic selection exists and is off by default
  (`cli/main.py:412-414`). It rates level-0 reports from 0 to 5
  (`rate_prompt.py`), keeps those at or above the threshold, queues their
  children, and drops the parent unless `keep_parent`. With nothing
  relevant, it rates the next level, up to `max_level`
  (`dynamic_community_selection.py:73-176`). Defaults: threshold 1,
  max_level 2, keep_parent False, num_repeats 1, use_summary False
  (`config/defaults.py:204-208`) [source].

## 6. Local search
- `query/structured_search/local_search/mixed_context.py:224-290` counts
  how many of the top-k matched entities each community contains, sorts by
  (matches, rank) and fills its share with full-content reports.
  `community_prop` 0.15 and `text_unit_prop` 0.5 of a 12000-token budget
  (`config/defaults.py:265-266`) [source].

## 7. DRIFT
- The primer uses a random report's `full_content` as a template for a
  hypothetical answer (HyDE) and embeds it (`drift_search/primer.py:71-100`).
  It takes the top `drift_k_followups` (20) reports by cosine similarity
  (`drift_context.py:204-229`), runs over `primer_folds` (5) folds and
  returns an intermediate answer and follow-up queries. Local search then
  runs for `n_depth` (3) rounds with community share 0.1 and text-unit
  share 0.9 (`config/defaults.py:99-106`) [source].

## 8. Incremental update
- Only the delta runs: the standard workflows execute against a delta table
  provider (`index/run/run_pipeline.py:61-85`). Delta community ids are
  offset by the old maximum plus one and appended
  (`index/update/communities.py:44-84`); reports are appended the same way
  (`:87-149`) [source].
- Old communities are never re-clustered, so the hierarchy is not merged
  across old and new data [inferred].
- No delete path was found in `cli/main.py` or `api/index.py` [source,
  negative result].

## 9. Cost signals
- One LLM call per community per level (`summarize_communities.py:75-98`);
  failures return None and are dropped [source].
- No setting skips levels or caps the report count; the levers are
  `max_cluster_size`, `use_lcc` and the query-time `community_level`
  [inferred].

## Differs from common descriptions
- Edge weight is the summed LLM strength, not a co-occurrence count (the
  Fast pipeline uses PMI or counts).
- Global search maps over full report content, not short summaries.
- Sub-community report substitution appears dead.
- Each node's context carries one edge per direction, not all edges.
- Dynamic selection exists but is off; it rates 0–5 from level 0.
- Under the default `use_lcc`, nodes outside the largest component get no
  community.
- Updates add communities for the delta only.

## Gaps
- `workflows/update_entities_relationships.py` and DRIFT follow-up parsing
  were not read past the cited lines.
- Nothing from GraphRAG was run, so the dead-substitution claim rests on
  reading the loop order.
