# Implementation Plan: Domain packs and the synthetic corpus (M1, part 1)

**Branch**: none (solo work on `main`) | **Date**: 2026-10-12 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/002-packs-and-corpus/spec.md`

## Summary

Feature 002 gives every later M1 feature its inputs and test oracles:
1. `tenetrag.packs`, a pure module that loads a pack and its ancestors,
   merges them, checks the result, compiles flat structured-output
   schemas, checks coverage against competency questions, and gives a
   stamp and the hashes that enter the stage hashes;
2. the shipped `core` and `enterprise-docs` packs, as package data;
3. a `pack` field in the profile, and stage hashes that include the
   pack;
4. 77 identity cases in the packs' vocabulary: the 60 design cases of
   ADR 0016, recovered from the session record, and 17 added for
   coverage and for ADR 0023;
5. a synthetic bilingual corpus of about 40 documents with planted
   answers, the running example D1 to D5, and a golden set, rebuilt by a
   deterministic generator.

Technical approach, from [research.md](research.md):
- **No new dependency:** pydantic, PyYAML and the standard library.
- **Layers:** `packs` is a sibling of `config`. The safe YAML loader moves
  to a private bottom-layer module, `tenetrag._yaml`, shared by both.
- **Stacking:** depth-first linear order, each file a delta that may only
  add; every other change fails with a rule id that names both packs.
- **Compile:** one fixed 52-property shape, where types grow enums, not
  keys. A prototype passed M0's `check_schema` under the Databricks
  profile.
- **Hashes:** content, index (no retrieval hints, no glossary), glossary
  and per-file hashes, in M0's canonical JSON form.
- **Corpus:** sentences written in a fact table; the generator renders,
  checks quotes and types, derives version statuses, and writes golden
  questions.

## Technical Context

**Language/Version**: Python 3.11–3.14 (CI matrix 3.11 and 3.14), as in M0

**Primary Dependencies**:
- base: pydantic 2.13 and PyYAML 6.0.3, both locked by M0;
- standard library: `json`, `hashlib`, `unicodedata`, `re`,
  `importlib.resources`, `logging`;
- no extra is used by `packs`, and none is added.

**Storage**: none. Packs and cases are YAML package data; the corpus is files under `tests/fixtures/corpus/`

**Testing**:
- pytest, network blocked, as in M0;
- broken test packs, one per rule id, under `tests/fixtures/packs/`;
- a golden test that pins each shipped pack version's file hash;
- the corpus check regenerates into a temporary directory and compares
  bytes.

**Target Platform**: anywhere the base install runs; no service, no model, no store

**Project Type**: library (one more pure module of the Python SDK), plus test fixtures

**Performance Goals**:
- loading, checking and compiling `[enterprise-docs, finance]` under
  1 s (SC-006);
- one corpus generation under 30 s (SC-010);
- the unit suite stays under M0's 60 s budget.

**Constraints**:
- `packs` imports no optional package and no other `tenetrag` module
  than `protocols` and `_yaml`, enforced by import-linter.
- Loading never builds objects from YAML and never runs pack content.
- Compiled schemas and generated files are byte-identical on every run
  and every CI Python.
- No adopter data: every name and identifier is fictional, except the
  codes of public legal documents (FR-041).

**Scale/Scope**:
- About 10 new source modules, 2 shipped packs, 3 case files, about
  40 documents and 5 user stories.
- Estimate: about 6 working days (spec Assumptions).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | How 002 meets it | Pre | Post |
|---|---|---|---|
| I. No adopter data in git | The packs, the cases and the corpus are synthetic. The recovered design data uses fictional companies and the reserved `.example` email domain. Adopter glossaries stay in private user packs, and a shipped pack with a glossary fails a test. `git status` is checked before each commit | ✅ | ✅ |
| II. Fail closed on identity | Not engaged for credentials: no credential is read. In the same spirit, `stage_hashes` takes the pack hash as a required keyword, so no caller can leave the pack out | n/a | n/a |
| III. Engine depends only on protocols | `packs` is pure: standard library, pydantic, PyYAML, `protocols` and `_yaml`. The layers contract places it beside `config`, and a forbidden contract keeps it off the optional SDKs (research R1) | ✅ | ✅ |
| IV. Provenance and fidelity | Every expected item in the corpus has a quote that the generator checks against its document's text. Pack text and corpus text are NFC, and figures stay verbatim in Vietnamese formats. The compiled schema asks for a quote on every item and every attribute | ✅ | ✅ |
| V. Time and versions | The corpus plants versions, supersession and deletions, and states the statuses a correct engine derives. A hand-written test pins the running example's statuses, including r1 current again after D2 is deleted | ✅ | ✅ |
| VI. Entity identity | Each shipped pack ships identity cases. The checker requires a merge and an apart case for every type with identity fields, and a case for every key and veto (FR-031). The 60 design cases keep their ids. Zero wrong merges is enforced when the engine runs them in feature 004 | ✅ | ✅ |
| VII. Reproducible indexes | The pack's index hash enters the `extract` and `resolve` stage hashes. Retrieval hints enter none, and the glossary has its own hash. Shipped pack versions are pinned by file hash, and golden tests pin the new stage hashes (research R7, R8) | ✅ | ✅ |
| VIII. Measured, opt-in quality | No quality claim. Simplest design: one fixed schema shape instead of per-stack shapes, sentences written by hand instead of a text generator, no new dependency | ✅ | ✅ |
| IX. Dated facts, vetted dependencies | No new dependency. The structured-output limits come from the dated Databricks reference through M0's capability profile. The prototype was run on 2026-10-12 | ✅ | ✅ |
| Workflow: tests ship with behaviour | Each contract lists the tests that pin it. Every rule id has a broken test pack (SC-003) | ✅ | ✅ |
| Workflow: decisions are ADRs | No new ADR: the pack format, stacking, identity cases and hashes are already decided (ADRs 0005, 0013, 0016 and domain-packs.md). The choices here are implementation choices, recorded in research.md | ✅ | ✅ |
| Workflow: docs with code | ARCHITECTURE.md, domain-packs.md, v1-packs.md, test-corpora.md, the engine brief's testing section and the AGENTS.md status change with the code (FR-043). The drafts of `core` and `enterprise-docs` are removed so the shipped files are the only copy | ✅ | ✅ |

**Gate result:** pass, before and after the design. No principle needs
an exception, and Complexity Tracking is empty. The design adds four
small spec edits (research R13), which narrow wording and change no
requirement's intent.

## Project Structure

### Documentation (this feature)

```text
specs/002-packs-and-corpus/
├── spec.md
├── plan.md              # this file
├── research.md          # Phase 0
├── research/identity-design-cases.json   # recovered design data (snapshot)
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/           # Phase 1: packs, config, identity-cases, corpus
├── checklists/requirements.md
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
pyproject.toml                 # layers: "config | packs", "protocols | _retry | _yaml"; packs forbidden contract
Makefile                       # + corpus target, which regenerates the corpus
src/tenetrag/
├── _yaml.py                   # safe loader with duplicate keys, parse, problem text (moved from config)
├── config/
│   ├── loading.py             # uses _yaml; resolves a relative pack path
│   ├── profile.py             # + pack field
│   └── hashing.py             # stage_hashes(profile, *, pack_hash)
└── packs/
    ├── __init__.py            # load_pack, shipped_packs, compile_schema, check_coverage, types
    ├── format.py              # pydantic models of one pack file (data-model §2)
    ├── loading.py             # resolve references, read files, linear order, phases
    ├── stacking.py            # apply deltas, origins, stack.* rules
    ├── checks.py              # references, identity lint, text lint, glossary
    ├── stack.py               # PackStack and its frozen parts (data-model §3)
    ├── problems.py            # PackProblem, the ConfigError text
    ├── hashing.py             # content, index, glossary and file hashes
    ├── compile.py             # compile_schema, CompiledSchema
    ├── coverage.py            # check_coverage, CoverageReport
    ├── cases.py               # identity case models, load_cases, check_cases
    └── shipped/
        ├── core.yaml
        ├── core.cases.yaml
        ├── enterprise-docs.yaml
        └── enterprise-docs.cases.yaml
tests/
├── unit/
│   ├── test_yaml.py
│   ├── config/                # + pack field, stage hashes with pack_hash, new golden values
│   └── packs/
│       ├── test_format.py  test_stacking.py  test_checks.py
│       ├── test_hashing.py  test_shipped.py  test_compile.py
│       ├── test_coverage.py  test_cases.py
│       └── test_corpus.py     # quotes, fit, golden coverage, running example, regeneration
├── fixtures/
│   ├── packs/                 # valid and broken test packs, one per rule id
│   ├── identity/finance.cases.yaml
│   └── corpus/
│       ├── facts/             # the fact table (input, hand-edited)
│       └── generated/         # docs/*.md, documents.jsonl, graph.json, golden.jsonl (output, committed)
└── support/corpus/            # the generator: python -m tests.support.corpus [--check]
docs/product/packs/finance.yaml   # stays a draft until M4; core.yaml and enterprise-docs.yaml removed
```

**Structure decision:** the pack logic is one subpackage of small
modules split by job: reading a file, stacking, checking, hashing,
compiling, coverage and cases. Each has its own test file, and
`stack.py` holds the one read-only shape the others produce or read.
The corpus generator is test support, since only tests and contributors
run it. Its output is committed so that a test can run without
regenerating.

## Complexity Tracking

No violations.
