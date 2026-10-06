# Cluster the graph by default; make community reports and global search opt-in

**Status:** accepted
**Date:** 2026-10-05
**Deciders:** Liam Lee (session 2026-10-05)

## Context
Brief open question 13 asked whether v1 builds communities always, as an
option that is off by default, or not at all. Microsoft GraphRAG v3.2.0
was read in source on 2026-10-05
([graphrag-engines.md](../reference/graphrag-engines.md#microsoft-graphrag-communities)):
- It clusters the relationship graph with hierarchical Leiden
  (graspologic-native). It then writes one LLM report per community per
  level. Global search maps over every report at a chosen level and
  reduces the scored points into an answer.
- Updates cluster only the new documents and append their communities.
  Old communities are never re-clustered, and there is no delete path.
- With its default largest-component cut, nodes outside the largest
  connected component get no community. Edges between communities appear
  in no report.

Evidence
([graphrag-research.md](../reference/graphrag-research.md)):
- The measured community win is global summarization: 64.40 vs 51.30 on
  GraphRAG-Bench, at 40–50× the prompt tokens. On single-fact questions,
  plain RAG matches or beats graph methods.
- Our target questions are entity-centric and temporal. The first
  realistic golden set had no global question when it was approved.

Cost, measured on 2026-10-05 on synthetic graphs with planted communities
(one run per size, one machine): graspologic-native Leiden took 0.22 s for
about 100,000 edges. The hierarchical variant with a cluster cap of 10
took 0.42 s and produced 5,305 communities across levels. Microsoft's
design would make about 5,305 report calls for that graph. Clustering is
cheap; reports are not. Real graphs have a different structure, so their
community counts can differ widely.

## Decision
1. **Communities have two layers.** Clustering groups entities and calls
   no LLM. Community reports and global search build on the clusters and
   call an LLM.
2. **Clustering is on by default.**
   - At the end of each index run, the whole graph is re-clustered with
     hierarchical Leiden and a fixed seed.
   - Every connected component is kept. There is no largest-component
     cut. Entities with no relation have no community.
   - Membership per level is stored with the run record and replaced as a
     whole each run, under the consistency floor
     ([ADR 0008](0008-build-databricks-and-open-branches-in-parallel.md)).
3. **Clustering is best-effort side work.**
   - It needs the `communities` extra, which wraps graspologic-native
     behind an adapter outside the engine
     ([ADR 0009](0009-reuse-permissive-libraries-behind-adapters.md)).
     The `app` extra includes it.
   - Without the extra, the run skips clustering and the plan says so.
   - A clustering error is recorded in the run record and marks the
     previous membership as stale. The documents of the run still commit.
4. **Community reports and global search are off by default.** When a
   profile turns them on:
   - The plan shows how many reports will be written and their estimated
     cost before anything runs.
   - A run rewrites only the reports whose community changed: its members
     changed, or a relation, fact or evidence link inside it changed.
     Communities are matched across runs by their members, not by id.
     Reports of communities that no longer exist are deleted.
   - Each report links to its member entities and relations, and through
     them to chunks. A global answer cites those chunks. A report is a
     derived summary and never counts as evidence on its own.
   - Global search is a separate method, `retrieve_global()`, because it
     runs a map-reduce of LLM calls. `retrieve()` stays one step with no
     LLM by default
     ([ADR 0010](0010-offer-query-strategies-as-opt-in-benchmarked-options.md)).
   - The report prompt and report model are index-time parameters.
     Global-search settings, such as the level and the token budget, are
     query-time parameters
     ([ADR 0005](0005-index-time-vs-query-time-parameters.md)).
   - Turning reports on without the `communities` extra raises
     `ConfigError`.
5. **Both layers ship in M5.** The golden set gains a global question
   type. `retrieve_global()` is a benchmark variant that is compared with
   the baselines on that type and reports its LLM calls and tokens.
6. **The engine brief sets the details:**
   - the cluster-size cap and the levels that are kept;
   - the rule that matches communities across runs;
   - whether to warm-start from the previous membership (graspologic-native
     takes `starting_communities`);
   - the report prompt and fields;
   - the clustering protocol and the storage shape on each backend.

## Alternatives considered
- **Always build reports (option A, Microsoft's default).** Rejected: a
  full build costs about one LLM call per community per level, and the
  measured gain covers only global summaries. Our questions are
  entity-centric and temporal.
- **No communities in v1 (option C).** Rejected: global questions would
  have no answer path, and the app would lose its topic map, while
  clustering costs under a second per 100,000 edges.
- **Both layers off by default (option B as first proposed on
  2026-10-04).** Rejected: clustering is cheap, calls no LLM, and gives
  the app a topic map without any setting.
- **Cluster only the new documents and append, as Microsoft does.**
  Rejected: an entity can sit in an old and a new community, the
  hierarchy never merges, and deletes leave stale communities.
- **Keep only the largest connected component (Microsoft's default).**
  Rejected: entities in smaller components would get no community.
- **graspologic-native as a base dependency.** Rejected: ADR 0009 keeps
  third-party libraries behind optional extras, and clustering alone is
  side work, so skipping it is safe.

## Consequences

**Better:**
- Users who opt in get an answer path for global questions, and the plan
  shows the cost first.
- The app can colour the graph by community at no LLM cost.
- Edits and deletes rewrite only the reports they affect.

**Worse:**
- Every backend stores community membership, and report tables when
  reports are on. The contract suite must cover them.
- Re-clustering reads every edge on every run. On Delta, that is a full
  scan into the indexing process. Timing was measured only on synthetic
  graphs.
- Leiden can move entities between communities after a small edit, so a
  run can rewrite more reports than the edit suggests.
- Edges between communities appear in no report.
- Reports are LLM summaries and can merge or drop figures and dates.

**Must now be true:**
- No retrieval default reads community reports.
- Reports are written only when the profile enables them and the plan
  has shown their count and cost.
- Every report links to its member entities and relations, and every
  global answer cites chunks.
- Deleting a document re-clusters and removes or rewrites the reports it
  touched.
- The golden set has global questions before `retrieve_global()` is
  benchmarked.

## Revisit if
- `retrieve_global()` beats the baselines on the global questions of a
  real golden set at an acceptable token cost, and adopters ask for it.
  Reports could then become a default in some profiles.
- Re-clustering the largest real graph takes longer than the rest of an
  incremental run.
- networkx's Leiden is confirmed to work without a backend, which would
  allow clustering without the extra.
