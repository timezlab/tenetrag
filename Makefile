# Quality gates (specs/001-sdk-foundation, research R2 to R6).
# `make check` runs the five local gates in order and stops at the first failure.

.PHONY: check format-check lint types imports test integration

# Keep the gates in order even under `make -j`.
.NOTPARALLEL:

check: format-check lint types imports test

format-check:
	uv run ruff format --check .

lint:
	uv run ruff check .

types:
	uv run mypy

imports:
	uv run lint-imports

# Unit tests run with the network blocked (pytest addopts).
test:
	uv run pytest -m "not docker and not live"

# Needs a Docker daemon; skipped with a reason when there is none.
# Exit 5 (no test collected) is allowed until T055 adds the first docker test.
integration:
	uv run pytest -m docker || test $$? -eq 5
