<!--
Sync Impact Report
- Version change: 1.0.0 → 1.1.0 (MINOR: two named exceptions expand the
  guidance of principles II and IX; no principle is removed or redefined)
- Modified principles:
  II. Fail Closed on Identity: adds the accepted environment reads of the
  official OpenAI and Databricks SDKs (ADR 0018)
  IX. Dated Facts and Vetted Dependencies: the ADR 0009 conditions allow
  narrow exceptions granted by an ADR (ADR 0017 psycopg, ADR 0018)
- Added sections: none. Removed sections: none
- Templates: plan, spec and tasks templates need no edit (✅); AGENTS.md
  version and identity rule updated (✅)
- Deferred: none

Previous report (1.0.0):
- Version change: template (unversioned) → 1.0.0 (first ratification)
- Principles: the five template slots are replaced by nine principles:
  I. No Adopter Data in Git (NON-NEGOTIABLE); II. Fail Closed on Identity;
  III. The Engine Depends Only on Protocols; IV. Provenance and Fidelity;
  V. Time and Versions Are Data; VI. Entity Identity Is Declared and Tested;
  VII. Reproducible Indexes, Comparable Backends; VIII. Measured, Opt-in Quality;
  IX. Dated Facts and Vetted Dependencies
- Added sections: Technology and Scope Constraints; Development Workflow and
  Quality Gates; Governance
- Removed sections: none
- Templates and guidance:
  ✅ .specify/templates/plan-template.md: its Constitution Check derives gates
     from this file; no edit needed
  ✅ .specify/templates/spec-template.md: no conflict
  ⚠ .specify/templates/tasks-template.md: says tests are optional; the
     Development Workflow section below overrides it. Left unedited because
     Spec Kit upgrades manage the template.
  ✅ .agents/skills/speckit-*/SKILL.md: generic, no agent-specific names to fix
  ✅ AGENTS.md: key rules and docs map point to this file
- Deferred: the exact gate commands (formatter, linter, type-checker, pytest)
  arrive in M0 and are listed in AGENTS.md, not here.
-->

# TenetRAG Constitution

TenetRAG is a Python SDK for GraphRAG: it indexes documents into a
domain-defined graph of dated, evidence-backed facts and serves graph-guided
retrieval to user-built agents. These principles bind every spec, plan, task
and change. The decisions behind them are in `docs/decisions/` (ADRs).

## Core Principles

### I. No Adopter Data in Git (NON-NEGOTIABLE)

- Anything specific to an adopting organization (its name, use case,
  documents, prompts, golden sets, examples) MUST live only in
  `docs/private/`, which is gitignored.
- Public code, fixtures, tests, examples and docs MUST be synthetic or come
  from public sources.
- Every commit MUST be preceded by a `git status` check for adopter
  material.

Rationale: the SDK is open source and its first adopter's material is
confidential. A leak in git history cannot be taken back.

### II. Fail Closed on Identity

- Credentials MUST be explicit objects passed by the caller. A missing
  requested credential MUST raise `AuthError`.
- The SDK MUST NOT fall back to another identity: no ambient environment,
  runtime or service-principal fallback.
- A runtime × identity × backend combination that cannot work MUST fail at
  configuration or preflight, with the reason, before any query.
- Real credentials MUST NOT appear in source, config, examples, logs or
  fixtures.
- Exception (ADR 0018): once the caller has named a source, the official
  OpenAI and Databricks SDKs may read their own environment variables
  (`OPENAI_ORG_ID`, `OPENAI_PROJECT_ID`, `OPENAI_CUSTOM_HEADERS`,
  `DATABRICKS_*`). The SDK passes everything it knows explicitly, and
  warns when it sees such variables set. With no source named, nothing is
  read.

Rationale: a silent fallback can read data under the wrong user
([ADR 0003](../../docs/decisions/0003-caller-supplied-credentials.md)).

### III. The Engine Depends Only on Protocols

- `engine` MUST import only the protocols module, `config` and `packs`. It
  MUST NOT import `storage`, `llm`, `auth`, `databricks-sdk`, `pyspark` or
  any backend driver.
- `serving` is the only module that wires implementations to protocols.
- The engine owns normalization, fusion, ranking, PageRank, entity and
  event resolution and supersession ordering, so backends stay thin.
- Importing the base package MUST NOT require any optional extra.

Rationale: one engine runs unchanged on Postgres, Neo4j and Delta, and its
tests run on fakes (ADRs 0001, 0008, 0014; `ARCHITECTURE.md`).

### IV. Provenance and Fidelity

- Every entity, relation, event and fact MUST link to its chunks and
  documents and record the pack and version that produced it.
- Every extracted item MUST carry a verbatim quote that code checks against
  its chunk. An item that fails a check is dropped with a counted reason,
  never silently.
- Source text MUST NOT be translated. Figures stay verbatim with their time
  and source. Text is normalized only where no meaning is lost (Unicode
  NFC, tone-mark placement), and diacritics are kept.
- LLM output is untrusted input: it is validated against a schema at the
  boundary, and the model's own confidence is never used.

Rationale: answers must be citable and checkable down to the sentence
(ADR 0012; SDK brief principles 3 and 5).

### V. Time and Versions Are Data

- Valid time MUST come from the text, or from the document's stated
  effective dates. The document date and the ingest time are kept apart.
- Every version MUST be kept. Supersession is computed from stated dates,
  never by deleting rows, and statuses are recomputed when a document is
  edited or deleted.
- Retrieval MUST be able to return every version with the current one
  flagged, and the version in force on a given date.

Rationale: questions about policies and figures are questions about time,
and engines that hide or reorder versions give wrong answers (ADR 0013).

### VI. Entity Identity Is Declared and Tested

- A name alone MUST NOT identify an entity. Each entity type declares its
  scope, keys, vetoes and name rule in its pack, and resolution follows
  them.
- Identity values MUST carry checked quotes. A missing value is never a
  different value.
- Every shipped pack MUST ship identity cases. CI requires zero wrong
  merges, and every key and veto has a case that goes wrong without it.

Rationale: a wrong merge corrupts facts and spreads through traversal,
while a wrong split stays recoverable through `same_as`
([ADR 0016](../../docs/decisions/0016-identify-entities-by-scope-keys-and-vetoes.md)).

### VII. Reproducible Indexes, Comparable Backends

- Ids MUST be deterministic hashes, so a replay writes the same ids.
- Every parameter is classified index-time or query-time. Every index-time
  setting MUST enter a stage hash, so a change is detected and re-indexing
  stays targeted (ADR 0005).
- Each document's write is atomic, an index has one writer at a time, and
  the run record counts drops, merges, blocked candidates, LLM calls and
  tokens.
- Every backend MUST pass the same contract suite, which first runs on the
  in-memory reference store. The suite asserts behaviour and candidate
  sets, never backend-specific scores.

Rationale: users compare backends and re-run indexes, so results must not
depend on timing or on the store (ADRs 0008, 0012, 0014, 0015).

### VIII. Measured, Opt-in Quality

- The default query path makes no LLM call. Query strategies, the router,
  community reports and multi-step retrieval are opt-in, and each is a
  benchmark variant reported per question type (ADRs 0010, 0011).
- A claimed quality gain MUST cite a benchmark result. Numbers in design
  docs are starting values to tune on the synthetic corpus.
- Prefer the simplest design that works: no speculative layers, and no
  store or model call inside a loop over unbounded data.

Rationale: GraphRAG claims often fail against a tuned hybrid baseline, so
only measured gains earn a place on the default path.

### IX. Dated Facts and Vetted Dependencies

- Platform behaviour (Databricks, Neo4j) is relied on only after reading
  its dated reference doc. Preview and Beta items MUST be re-verified
  against the linked source.
- A third-party library outside the engine sits behind an adapter and
  meets the six conditions of ADR 0009, including a permissive license,
  unless an ADR grants a narrow, named exception. The exceptions are
  psycopg and psycopg-pool under LGPL (ADR 0017), and the environment
  reads of principle II (ADR 0018).
- Before a dependency is added: its exact name is verified, its version is
  checked on OSV (including `MAL-` advisories), its install scripts are
  read, and no version published in the last 24 hours is used. The
  lockfile is committed. The network is never piped into a shell.
- Text under a non-permissive license, such as the Neo4j documentation
  (CC BY-NC-SA), MUST NOT be copied into the repository: link to it.

Rationale: platforms change fast, and supply-chain attacks target fresh
releases and mistyped package names.

## Technology and Scope Constraints

- Python 3.11 or later. One package, `tenetrag`, with optional extras.
  Apache-2.0 with a NOTICE file.
- Graph stores: Postgres (local, managed, Lakebase), Neo4j (2026.09 or
  later) and Delta. Vector stores: pgvector, the Neo4j vector index and
  Databricks AI Search.
- Documents in Vietnamese and English. Public docs are written in English.
- Protocols are synchronous and batched, and graph expansion is one `hop`
  per store call (ADR 0014).
- Agents get engine methods and tools, never a raw SQL or Cypher tool.
  Queries are parameterized on every backend.

## Development Workflow and Quality Gates

- **Specs.** A feature of three or more tasks, or more than two days of
  work, goes through Spec Kit in `specs/NNN-<name>/`. Smaller changes are
  made directly. Each plan's Constitution Check lists the principles it
  touches and how it meets them.
- **Decisions and docs.** Each decision is an ADR in `docs/decisions/`,
  append-only: a new ADR supersedes an old one. Docs change in the same
  change as the code, and `ARCHITECTURE.md` changes with module boundaries.
- **Gates.** The formatter, linter, type-checker and pytest are set up in
  M0, and their exact commands are listed in `AGENTS.md`. They run before
  any change is called done. A suppression comment names its reason.
- **Tests.** A behaviour change ships with tests, and a bug fix ships with
  a regression test that fails before the fix. Engine unit tests run on the
  in-memory reference store with fake models, with no network. This
  overrides the "tests are optional" note in the Spec Kit tasks template.
- **Commits.** Small and topical, each after the Principle I check.

## Governance

- This constitution takes precedence over other practice documents.
  `AGENTS.md` and `.agents/rules/` are working summaries of it. When they
  conflict, the constitution wins and the summary is corrected.
- An amendment is a change to this file that updates the Sync Impact
  Report and carries its effects into the Spec Kit templates and
  `AGENTS.md`. Adding, removing or redefining a principle also needs an
  ADR.
- Versioning is semantic. MAJOR removes or redefines a principle. MINOR
  adds a principle or section, or materially expands guidance. PATCH
  clarifies wording.
- Reviews check compliance. A plan that breaks a principle records the
  reason in its Complexity Tracking table, and an ADR that contradicts a
  principle amends the constitution first.

**Version**: 1.1.0 | **Ratified**: 2026-10-06 | **Last Amended**: 2026-10-06
