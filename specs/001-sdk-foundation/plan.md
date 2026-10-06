# Implementation Plan: SDK foundation (M0)

**Branch**: none (solo work on `main`) | **Date**: 2026-10-06 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-sdk-foundation/spec.md`

## Summary

M0 creates the `tenetrag` package and the five things every later
milestone needs:
1. repository gates that run the same way locally and in CI;
2. a validated profile whose fields are each index-time or query-time,
   with per-stage hashes;
3. explicit credentials that fail closed, which the profile can name by
   source;
4. chat and embedding models behind the `ChatModel` and `EmbeddingModel`
   protocols, for Databricks, OpenAI-compatible servers and fakes;
5. Neo4j and Postgres connection wrappers with health checks, retry of
   whole units and per-identity pools.

Technical approach, from [research.md](research.md):
- **Tooling:** uv, ruff, mypy, pytest and import-linter.
- **Models:** thin classes over the `openai` SDK.
- **Databricks auth:** the Databricks SDK for its OAuth, CLI-profile and
  runtime flows. Its own reads of `DATABRICKS_*` variables are accepted
  under ADR 0018.
- **Postgres:** psycopg and psycopg-pool, under the license exception of
  ADR 0017.
- **Neo4j:** the official driver, with telemetry off.

## Technical Context

**Language/Version**: Python 3.11–3.14 (CI matrix 3.11 and 3.14; 3.15 joins after its 2026-10-09 release)

**Primary Dependencies**:
- base: pydantic 2.13, PyYAML 6.0.3, jsonschema 4.26;
- extras: `openai` (openai 3.24), `databricks` (openai, databricks-sdk
  0.146), `neo4j` (neo4j ≥ 6.3.1), `postgres` (psycopg[binary] 3.3,
  psycopg-pool 3.3).

**Storage**: Neo4j 2026.09+ (Community, Enterprise, Aura) and Postgres 16+ with `vector` and `pg_trgm`. Connections only; no schema in M0

**Testing**:
- pytest 9.1, with network blocked by pytest-socket for unit tests;
- `httpx2.MockTransport` for model HTTP;
- testcontainers for Docker integration tests;
- live tests that are opt-in through named variables.

**Target Platform**: Linux and macOS for development; Linux in CI, Databricks runtimes and servers

**Project Type**: library (Python SDK, one package with optional extras)

**Performance Goals**: unit suite under 60 s on a CI runner (SC-002); fresh clone to green gates in 10 minutes or less (SC-001)

**Constraints**:
- No network in unit tests.
- A bare `import tenetrag` loads no optional package.
- No secret in any repr, log or error.
- Every dependency passes the gate: OSV, age over 24 hours, enforced by
  `exclude-newer`.

**Scale/Scope**:
- About 15 source modules and 5 user stories.
- Estimate: about 6.5 working days.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | How M0 meets it | Pre | Post |
|---|---|---|---|
| I. No adopter data in git | All fixtures and profiles are synthetic, and the Ollama and Databricks examples use public model names. `git status` is checked before each commit | ✅ | ✅ |
| II. Fail closed on identity | Credentials are explicit or named in the profile. A missing one raises `MissingCredentialError`, and a mismatch is rejected at creation. Refresh stays on the same identity. There is no `ModelServingUserCredentials` and no fallback helper. The OpenAI and Databricks SDKs' own environment reads are the narrow exception of ADR 0018, with a warning (constitution 1.1.0) | ⚠ needed ADR 0018 | ✅ after amendment |
| III. Engine depends only on protocols | No engine yet. The errors live in `tenetrag.protocols.errors`, so the M1 engine can import them (research R14). Import contracts are enforced from day one (R5). The base import loads no extra | ✅ | ✅ |
| IV. Provenance and fidelity | Not engaged: no extraction yet. Model output is validated against a schema at the boundary, and nothing is truncated silently | ✅ | ✅ |
| V. Time and versions | Not engaged in M0 | n/a | n/a |
| VI. Entity identity | Not engaged in M0 | n/a | n/a |
| VII. Reproducible indexes | Every field has a phase, and stage hashes come from index-time fields only, in one module, with golden tests (ADR 0005). Ids and runs start in M1 | ✅ | ✅ |
| VIII. Measured, opt-in quality | No quality claims. Simplest design: thin SDK wrappers, one small retry module, no speculative layers. The capability profile never switches strategy at run time | ✅ | ✅ |
| IX. Dated facts, vetted dependencies | Versions are dated and checked on OSV (research table), and the lock is committed with `exclude-newer = "24 hours"`. psycopg is LGPL, and the SDKs read the environment, which breaks two of ADR 0009's six conditions. ADRs 0017 and 0018 record narrow exceptions (constitution 1.1.0) | ⚠ needed ADRs 0017, 0018 | ✅ after amendment |
| Workflow: tests ship with behaviour | Each contract lists the tests that pin it. Bug fixes get a failing test first | ✅ | ✅ |
| Workflow: decisions are ADRs | ADR 0017 (psycopg exception), ADR 0018 (credential sources in the profile, accepted SDK environment reads), ADR 0019 (repository gates) | ✅ | ✅ |
| Workflow: docs with code | `ARCHITECTURE.md`, `AGENTS.md` Commands and `README.md` change in the same change set as the code (FR-030) | ✅ | ✅ |

**Gate result:** two principles needed exceptions, and the governance
rule says an ADR that contradicts a principle amends the constitution
first. ADRs 0017 and 0018 and constitution 1.1.0 were written with this
plan, so the gate passes. Both exceptions are listed under Complexity
Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/001-sdk-foundation/
├── spec.md
├── plan.md              # this file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/           # Phase 1: config, auth, llm, storage
├── checklists/requirements.md
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
pyproject.toml                 # package, extras, ruff, mypy, pytest, import-linter, [tool.uv]
uv.lock
Makefile                       # check = format, lint, types, imports, unit
LICENSE                        # Apache-2.0
NOTICE
.github/workflows/ci.yml       # gates + integration, Python 3.11 and 3.14
src/tenetrag/
├── __init__.py                # __version__, re-exported errors; nothing optional
├── py.typed
├── _retry.py                  # RetryPolicy, classify verdicts (research R10)
├── protocols/
│   ├── __init__.py
│   ├── errors.py              # data-model §1
│   └── models.py              # ChatModel, EmbeddingModel, Message, ChatResult, Usage
├── config/
│   ├── __init__.py            # load_profile, profile_from_yaml, profile_from_dict, Profile
│   ├── phases.py              # Phase, Stage, markers, field_phases
│   ├── profile.py             # Profile and section models
│   ├── sources.py             # CredentialSource union
│   ├── loading.py             # safe YAML with duplicate-key check
│   └── hashing.py             # stage_hashes: the one module of ADR 0005
├── auth/
│   ├── __init__.py            # Credentials, Credential, Secret, AccessToken, resolve_credential
│   ├── credentials.py
│   ├── resolve.py             # targets, accepted kinds, env warnings
│   └── databricks.py          # Databricks SDK adapters, imported lazily
├── llm/
│   ├── __init__.py            # factories, classes, CapabilityProfile
│   ├── capabilities.py        # shipped profiles, lookup, overrides
│   ├── structured.py          # strategies, schema checks, validation, re-ask
│   ├── openai_compatible.py   # OpenAI SDK adapter (chat, embeddings)
│   ├── databricks.py          # base_url and profile defaults over openai_compatible
│   └── fake.py                # FakeChatModel, FakeEmbeddingModel
└── storage/
    ├── __init__.py            # open_connection, HealthReport
    ├── neo4j.py
    └── postgres.py
tests/
├── conftest.py                # markers, socket blocking, planted-secret fixtures
├── unit/
│   ├── test_base_import.py
│   ├── test_errors.py
│   ├── test_secrets_never_leak.py
│   ├── test_retry.py
│   ├── config/  auth/  llm/  storage/
└── integration/               # marked docker
    ├── neo4j/  postgres/
└── live/                      # marked live, opt-in
```

**Structure decision:** a single library with a `src/` layout, one
subpackage per module of `ARCHITECTURE.md` that M0 needs, and tests
split by need (unit, Docker, live). `_retry.py` is a private stdlib-only
helper shared by `llm` and `storage`. It holds one piece of knowledge,
the retry policy, used in two places, and `ARCHITECTURE.md` lists it.

## Complexity Tracking

| Violation | Why needed | Simpler alternative rejected because |
|---|---|---|
| psycopg and psycopg-pool are LGPL-3.0 (principle IX, ADR 0009 condition 1) | The pool natively gives a check before use, a maximum age, and a token minted per connection (Lakebase), and M1 needs COPY | pg8000 (BSD-3) means owning a thread-safe pool, slower writes and unverified-TLS defaults; author's decision 2026-10-06 (ADR 0017) |
| The OpenAI SDK reads `OPENAI_ORG_ID`, `OPENAI_PROJECT_ID` and `OPENAI_CUSTOM_HEADERS`; the Databricks SDK fills unset settings from `DATABRICKS_*` (principles II and IX, ADR 0009 condition 3) | It reuses the official clients' OAuth, CLI-profile, runtime and request code instead of maintaining our own | An own HTTP client and own Databricks auth (about 300 lines) would close both gaps, but the author judged a warning enough (ADR 0018) |
