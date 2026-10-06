# Version prompts and index runs in the SDK through MLflow Prompt Registry

**Status:** accepted
**Date:** 2026-10-02
**Deciders:** Liam Lee (brainstorm session, 2026-10-02)

## Context
Extraction and answer prompts change graph contents and answers, so a
benchmark result or an index is reproducible only if it records which prompt
versions produced it. Agents call the SDK directly without the app, and
benchmarks run from notebooks, so versioning cannot live only in the UI.
MLflow Prompt Registry offers versioned prompts with aliases such as
`@production`, both in Unity Catalog (Beta on Databricks) and on a local
MLflow server.

## Decision
The SDK owns versioning and builds it on MLflow's existing features rather
than a versioning system of its own. Prompts resolve from MLflow Prompt
Registry by name and alias, on Databricks UC or a local MLflow server, and
inline prompts in the profile serve as the fallback when no registry is
configured. Every index
run records the resolved prompt versions, the configuration hash and the
pipeline version. Benchmark runs log the same data to MLflow. The app is a
UI over this SDK mechanism and keeps no versioning of its own.

## Alternatives considered
- **Versioning in the app** — rejected: agents and notebooks would bypass
  it, and benchmarks would not be reproducible outside the UI.
- **Our own prompt version tables in the graph store** — rejected: this
  duplicates a Databricks feature users already govern, and loses the
  registry UI and aliases.
- **No prompt versioning, git only** — rejected: a deployed agent could not
  switch prompts by alias without a release.

## Consequences

**Better:**
- Any index or benchmark run can be traced to exact prompt versions.
- Promoting a prompt is an alias move in MLflow, not a code release.
- Works offline with inline prompts or a local MLflow server.

**Worse:**
- MLflow becomes a dependency of the versioning path; the Databricks registry
  is Beta and may change.
- Two prompt sources (registry and inline) need clear precedence and logging
  of which one was used.

**Must now be true:**
- Prompts are loaded only through the SDK's prompt resolver, never read
  directly from files inside the engine.
- Every index run writes prompt versions, configuration hash and pipeline
  version alongside its `run_id`.
- An alias that cannot be resolved raises `ConfigError` instead of silently
  using the inline prompt, unless the profile marks inline as the source.

## Revisit if
MLflow Prompt Registry on Databricks is withdrawn or changes incompatibly
before GA, or users need versioned artifacts the registry cannot hold, such
as entity-type schemas.
