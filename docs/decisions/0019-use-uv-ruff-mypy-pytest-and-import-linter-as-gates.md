# Use uv, ruff, mypy, pytest and import-linter as the repository gates

**Status:** accepted
**Date:** 2026-10-06
**Deciders:** Liam Lee (M0 planning session, 2026-10-06)

## Context
The constitution requires a formatter, a linter, a type checker and tests
before any change is called done. M0 sets them up
([spec 001](../../specs/001-sdk-foundation/spec.md), FR-001 to FR-006).
Two more requirements apply:
- The import rules of `ARCHITECTURE.md` must be checked by a tool.
- The dependency gate requires that no version younger than 24 hours is
  used, and that the lockfile is committed.

Versions, licenses and OSV results were checked on 2026-10-06
([research](../../specs/001-sdk-foundation/research.md#versions-and-the-dependency-gate)).

## Decision

| Need | Tool | Notes |
|---|---|---|
| Environments, lock, running | uv 0.12 | `uv.lock` committed; `[tool.uv] exclude-newer = "24 hours"`; CI uses `uv sync --locked` |
| Build backend | hatchling | pure Python, `src/` layout |
| Format and lint | ruff 0.16 | `ruff format`, plus `ruff check` with `E F W I B UP S SIM RUF ANN PT TID BLE N` |
| Types | mypy 2.4 | `strict = true`, `pydantic.mypy` plugin |
| Tests | pytest 9.1 | pytest-socket blocks the network in unit tests; testcontainers runs the Docker tests (dev only); markers `docker` and `live` |
| Import rules | import-linter 2.15 | contracts in `pyproject.toml`, one per rule of `ARCHITECTURE.md` |
| CI | GitHub Actions | actions pinned by full commit SHA; Python 3.11 and 3.14 |

`make check` runs format check, lint, types, imports and unit tests in
that order. `AGENTS.md` lists the exact commands.

## Alternatives considered
- **basedpyright.** It is a strong checker, but it brings Node through
  `nodejs-wheel-binaries`. The `pyright` wrapper downloads Node at run
  time.
- **ty.** Still beta (0.0.84).
- **Poetry or pip-tools.** uv covers locking, environments and running in
  one tool, and its `exclude-newer` enforces the 24-hour rule.
- **`uv_build`.** It is stable, but it is tied to uv's 0.x versions.
  hatchling is less coupled.
- **pre-commit hooks.** Not needed for one developer. `make check` and CI
  run the same gates.

## Consequences

**Better:**
- One command reproduces CI locally.
- The 24-hour rule is enforced by the resolver, not by memory.
- Import rules fail the build instead of waiting for review.

**Worse:**
- mypy strict is slower than pyright on large code bases. That is not an
  issue at M0's size.
- import-linter contracts must be updated with every new module, the
  engine's in M1 first.

**Must now be true:**
- `AGENTS.md` lists the commands in its Commands section.
- The CI workflow pins each action by SHA.
- `uv.lock` changes only through `uv lock`, which respects
  `exclude-newer`.

## Revisit if
- ty reaches a stable release, or mypy becomes a bottleneck.
- uv's resolution or lock format changes incompatibly.
