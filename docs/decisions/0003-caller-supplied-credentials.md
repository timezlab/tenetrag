# Require caller-supplied credentials and never fall back to another identity

**Status:** accepted; refined by
[ADR 0018](0018-name-credential-sources-in-the-profile.md) (2026-10-06):
the profile may name a credential's source, and the official SDKs' own
environment reads are accepted with a warning.
**Date:** 2026-10-02
**Deciders:** Liam Lee (brainstorm session, 2026-10-02)

## Context
Agents call the SDK from a local machine, notebooks, jobs, Databricks Apps and
Model Serving, under PAT, OAuth M2M/U2M, OBO or the runtime identity. What
each identity can reach depends on the runtime: Model Serving OBO cannot reach
Lakebase or Volumes, and Apps OBO needs one Postgres role per user. Databricks
helpers fail open. AppKit's `asUser(req)` falls back to the app's service
principal when the token is missing, and `get_user_workspace_client()` falls
back to the SP "without raising". A fallback like that silently bypasses
row-level security
([databricks-platform.md](../reference/databricks-platform.md)). Content
authorization is out of scope for v1, so the SDK must at least never widen
the identity the caller asked for.

## Decision
Credentials are explicit objects the caller passes in: PAT, OAuth M2M, OAuth
U2M, OBO token or Databricks runtime, or a `WorkspaceClient` the caller built.
They are set per client and can be overridden per request. The SDK does no
ambient credential discovery. A preflight check runs the runtime × identity ×
backend matrix. A combination known not to work, or a missing requested
credential, raises `AuthError` naming the reason before any query runs. On an auth failure the SDK never
retries with a different identity. The one allowed retry is re-minting a
Lakebase token for the same identity after expiry.

## Alternatives considered
- **Ambient auth (`WorkspaceClient()` default chain)** — rejected: the
  identity that ends up running depends on environment variables and config
  files, which is exactly the silent widening we must prevent.
- **Fall back to the app or service principal when no user token is
  present** — rejected: queries succeed as the wrong identity and RLS is
  ignored.
- **SDK-managed authorization (document ACLs, RLS policies)** — deferred out
  of v1. Provenance keeps it possible later without re-indexing.

## Consequences

**Better:**
- The identity behind every query is the one the caller named.
- Impossible configurations fail at startup with a reason, not mid-query.
- Behaviour is the same across runtimes and testable without a workspace,
  using fake credential providers.

**Worse:**
- More setup for callers: even notebook users pass a credential, for example
  `Credentials.runtime()` (constructor names are set in the M0 spec).
- The capability matrix has to track Databricks Preview features as they
  change.
- Apps OBO on Lakebase is limited by the 500 Postgres roles per branch.

**Must now be true:**
- Every backend and model client takes a `Credentials` object. No code path
  builds `WorkspaceClient()` without explicit credentials.
- A missing OBO token raises `AuthError`; it is never replaced by a default.
- No call to fallback helpers such as `get_user_workspace_client()` or
  AppKit `asUser`.
- Requests in OBO mode never use a pool opened under another identity.

## Revisit if
Databricks provides a fail-closed per-request identity primitive across
Apps and Model Serving, or v2 takes on content authorization.
