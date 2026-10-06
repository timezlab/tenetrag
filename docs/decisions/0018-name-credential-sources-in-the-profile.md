# Name credential sources in the profile, and accept the official SDKs' own environment reads

**Status:** accepted
**Date:** 2026-10-06
**Deciders:** Liam Lee (M0 spec and planning session, 2026-10-06)

## Context
[ADR 0003](0003-caller-supplied-credentials.md) makes credentials explicit
objects that the caller passes in, with no ambient discovery. Reviewing
the M0 spec, the author raised two points:
- TenetRAG must run as well self-hosted as on Databricks.
- A CLI, an MCP server or a job should start from a profile file alone,
  without code that builds credentials.

On a laptop, the common Databricks login is `databricks auth login`,
which stores a named profile.

Planning then read the source of the clients we build on
([research R9 and R11](../../specs/001-sdk-foundation/research.md)):
- **`openai` 3.24.0.** An explicit `api_key` and `base_url` stop the
  reads of `OPENAI_API_KEY` and `OPENAI_BASE_URL`. No argument stops the
  reads of `OPENAI_ORG_ID`, `OPENAI_PROJECT_ID` and
  `OPENAI_CUSTOM_HEADERS`, and the last one can add any header.
- **`databricks-sdk` 0.146.0.** `Config` fills every attribute the caller
  left unset from `DATABRICKS_*`, `ARM_*` and `GOOGLE_CREDENTIALS`, before
  it reads a named profile, and nothing turns this off. An explicit
  `auth_type` keeps the auth family fixed.

These reads break ADR 0009's condition 3 (no ambient credentials) and the
letter of ADR 0003. Closing them would mean our own HTTP client and our
own Databricks OAuth, CLI-profile and runtime code, about 300 lines.

## Decision
1. **The profile may name a credential's source, never its value.** Each
   connection and model can carry a `credential` entry:
   - `none`;
   - `api_key` (with `env`);
   - `basic` (with `user` and `password_env`);
   - `pat` (with `token_env`);
   - `oauth_m2m` (with `client_id` and `client_secret_env`);
   - `oauth_u2m`;
   - `cli_profile` (with `name`);
   - `runtime`.

   A credential passed in code overrides the profile. A named source that
   is missing, empty or expired raises `AuthError` naming the source. With
   no source named, nothing is read. `obo`, `token_provider` and
   `workspace_client` exist only in code.
2. **The official SDKs' own environment reads are accepted.**
   - The OpenAI SDK may read `OPENAI_ORG_ID`, `OPENAI_PROJECT_ID`,
     `OPENAI_CUSTOM_HEADERS` and `OPENAI_LOG`.
   - The Databricks SDK may fill unset settings from its variables, once
     the caller has named a Databricks source that delegates to it
     (`oauth_m2m`, `oauth_u2m`, `cli_profile`, `runtime`,
     `workspace_client`).
   - TenetRAG passes everything it knows explicitly, including
     `auth_type`.
   - When it sees any of these variables set, it logs one warning per
     process naming them, never their values.
3. **Fail-closed rules that stay:**
   - With no source named, TenetRAG raises `MissingCredentialError` even
     when these variables are set.
   - `pat` and `obo` are plain bearer tokens that do not go through the
     Databricks SDK.
   - `ModelServingUserCredentials` is never used, since it falls back to
     the default chain outside Model Serving.
   - Refresh stays on the same identity.

## Alternatives considered
- **Credentials only in code** (ADR 0003 as written). Rejected: a CLI, an
  MCP server or a job would need wrapper code just to build credentials.
- **Our own HTTP client and Databricks auth, to close every read.**
  Rejected by the author: about 300 lines to maintain, for variables
  users can leave unset.
- **Block the reads with undocumented tricks**, such as passing `""` for
  every unused Databricks attribute plus a custom credentials strategy.
  Rejected: it relies on internal behaviour that could change in any
  weekly release.

## Consequences

**Better:**
- A self-hosted or Databricks setup starts from one profile file.
- `databricks auth login` profiles work directly.
- The official clients' OAuth refresh, CLI integration and request code
  are reused, not rewritten.

**Worse:**
- If a user names a CLI profile while `DATABRICKS_TOKEN` or
  `DATABRICKS_HOST` is also set, the Databricks SDK may use them or
  reject the mix. The warning is the only guard.
- `OPENAI_CUSTOM_HEADERS` can add headers to model requests.
- A profile copied to another machine uses whatever that machine's named
  variables hold.

**Must now be true:**
- Constitution principles II and IX name this exception (constitution
  1.1.0).
- The M0 spec's FR-016 and FR-017 and Story 3 describe it.
- Tests show that no credential is read without a named source, and that
  the warnings name the variables and not their values.

## Revisit if
- An adopter needs a hard guarantee against these reads, for example
  under a security review.
- The OpenAI SDK gains a switch to stop reading its environment, or the
  Databricks SDK gains a no-environment mode.
