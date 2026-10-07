# Quality gates (specs/001-sdk-foundation, research R2 to R6).
# `make check` runs the five local gates in order and stops at the first failure.

.PHONY: check format-check lint types imports test integration dev-up dev-down prod-up prod-down

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
integration:
	uv run pytest -m docker

# The local stack (docs/guides/local-stack.md). Compose reads deploy/.env.
# Data stays in named volumes; add -v to `down` to delete it.
DEV_STACK = docker compose -f deploy/compose.yaml -f deploy/compose.dev.yaml
PROD_STACK = docker compose -f deploy/compose.yaml -f deploy/compose.prod.yaml

dev-up:
	$(DEV_STACK) up -d --wait

dev-down:
	$(DEV_STACK) down

prod-up:
	$(PROD_STACK) up -d --wait

prod-down:
	$(PROD_STACK) down
