# Tech debt

Known gaps and quirks that were left for later on purpose. One entry per
item. Remove an entry in the change that fixes it.

## No test calls one model client from many threads

- **Where:** `src/tenetrag/llm/openai_compatible.py:67`, `:155`, and
  `src/tenetrag/llm/databricks.py`.
- **Symptom:** FR-024 asks for model clients that are safe to share
  across threads. That rests on the shared `openai` client and on the
  token source, whose refresh is tested across threads
  (`test_refresh_happens_once_across_threads`). No test runs `generate()`
  or `embed_documents()` concurrently.
- **Why deferred:** M0 has no caller that shares a model across threads.
- **Trigger to fix:** M1, when the engine's bounded thread pool
  (ADR 0014) first shares a model.
- **Created:** 2026-10-07

## The live Databricks smoke test has not run

- **Where:** `tests/live/test_databricks_live.py`, and the shipped
  profiles at `src/tenetrag/llm/capabilities.py:131-135`.
- **Symptom:** the 1024-dimension profile of
  `databricks-qwen3-embedding-0-6b` and the sampling rules of
  `databricks-claude-sonnet-5` are checked against docs and mocked HTTP
  only.
- **Why deferred:** the test needs the author's workspace and a
  `databricks auth login` profile. CI holds no secrets.
- **Trigger to fix:** before M1 indexes with Databricks models. Run
  `TENETRAG_LIVE_DATABRICKS_PROFILE=<profile> uv run pytest -m live -q`.
- **Created:** 2026-10-07

## A rejection while the Postgres pool grows ends as unavailable

- **Where:** `src/tenetrag/storage/postgres.py:125-139`.
- **Symptom:** a password or token rejected when the pool opens a new
  connection in its background worker is logged by psycopg-pool as a
  warning. The waiting unit then ends with `PoolTimeout`, which maps to
  `StoreUnavailableError`, not `CredentialRejectedError` (FR-028). A
  rejection at opening is reported correctly.
- **Why deferred:** psycopg-pool only logs its workers' errors, so the
  real cause needs a hook into the pool's connect step
  ([research R12](../specs/001-sdk-foundation/research.md), As built).
- **Trigger to fix:** when Lakebase tokens expire under load in M1, or
  when a user reports a misleading "unavailable".
- **Created:** 2026-10-07
