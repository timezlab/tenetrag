# Fact-check: Lakebase, OBO and Apps user authorization

> **Snapshot, 2026-10-02 — not maintained.** Round 1 adversarial fact-check of
> four load-bearing claims from the platform lanes. Recovered from the session
> transcript. The maintained, re-verified summary is in
> [databricks-platform.md](../reference/databricks-platform.md); where they
> differ, the maintained doc wins.
>
> **Errata:** none found.

All four claims hold up on the mechanism, but two of them need changes before they drive the architecture. Claim 2 has fail-open and scale caveats. Claim 4 is not GA. Azure pages and the npm-mirrored AppKit doc were read as raw text. AWS and GCP pages were read through a summarizer. Wayback is blocked here, so I could not diff old page revisions.

## claim 1: Lakebase has no Apache AGE but has pgvector with HNSW
verdict: CONFIRMED. The AGE absence is inferred from the official list; no page says "unsupported".
confidence: high
evidence:
- The full table has no `age`. The `vector` row reads "Vector data type and ivfflat and hnsw access methods", version 0.8.0 on PG16/17 and 0.8.6 on PG18. [Azure](https://learn.microsoft.com/en-us/azure/databricks/oltp/projects/extensions) (2026-09-30). The [AWS](https://docs.databricks.com/aws/en/oltp/projects/extensions) and [GCP](https://docs.databricks.com/gcp/en/oltp/projects/extensions) tables match.
- The [compatibility page](https://docs.databricks.com/aws/en/oltp/projects/compatibility) (2026-09) says "Any functionality that requires superuser privileges ... is not allowed". The [Lakebase release notes](https://docs.databricks.com/aws/en/release-notes/lakebase/) never mention AGE.
- disconfirming query "CREATE EXTENSION age Lakebase" and "Lakebase Apache AGE not supported" → no Lakebase hits and no contrary evidence.
nuance:
- GCP page: "As of June 15, Lakebase is available in Beta on GCP". The year is not shown, and AWS and Azure are unlabeled.
- `lakebase_vector` (IVF with RaBitQ) is an alternative to HNSW. Lakebase Search went GA 2026-09-18 and cannot be turned off once enabled.
- Graph-adjacent extensions only: `pg_graphql` (GraphQL), `pgrouting` and `ltree`.
- I could not fetch a Lakebase Provisioned extension list (404). Provisioned instances are being auto-upgraded to Autoscaling.

## claim 2: OBO to Lakebase via Apps user authorization (`postgres` scope, per-user role, RLS)
verdict: CONFIRMED, with design-changing caveats
confidence: high on the mechanism, medium on the limits
evidence:
- The AppKit doc (appkit-ui 0.45.0, v0 docs) says: "Enable user authorization with the postgres scope". It says user token and identity come from `x-forwarded-access-token` and `x-forwarded-email`. It says "current_user reflects user identity". It also says "Do not grant `databricks_superuser` to OBO users — superusers bypass RLS." [source](https://cdn.jsdelivr.net/npm/@databricks/appkit-ui@0.45.0/docs/plugins/lakebase.md)
- `postgres` is in the supported scopes. [Apps auth](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/databricks-apps/auth) (2026-09-28).
- `\du` shows "databricks_superuser | Create role, Create DB, Cannot login, Bypass RLS". [roles page](https://learn.microsoft.com/en-us/azure/databricks/oltp/projects/postgres-roles) (2026-09-11).
- disconfirming query "Lakebase role limits and OAuth pooler" → the caveats below.
nuance:
1. **Fail-open traps.** The default service-principal pool "bypasses RLS as table owner". `asUser(req)` in dev mode falls back to the service-principal pool when no token exists. Agent `get_user_workspace_client()` falls back to the service principal "without raising". The SDK must fail closed.
2. **Role cap.** [Limits](https://docs.databricks.com/aws/en/oltp/projects/limitations) lists "Maximum number of Postgres roles per branch | 500", so one role per user caps out near 500 users per branch. Roles can be created programmatically (`databricks_create_role()`, SDK/REST `create_role`), but that needs CREATE ROLE and an OAuth session. Group roles let members log in with their own token, but then `current_user` is the group, so per-user RLS is lost. Renaming a user breaks grants.
3. **Pooling.** The built-in PgBouncer does not support OAuth. Per-user pools connect directly (default max 3, idle 30 s, tokens last 1 h).
4. **Scope breadth.** The `postgres` scope appears broad: the [scopes page](https://docs.databricks.com/api/workspace/api/scopes) lists project, branch and role API operations (summarizer-read). The agents-on-Apps page's OBO resource list omits Lakebase, which is a docs inconsistency.

## claim 3: Model Serving OBO does not support Lakebase or UC Volumes
verdict: CONFIRMED. UC Volumes is named explicitly; Lakebase is excluded by omission from a closed list.
confidence: high
evidence:
- "agents with OBO authentication can only access the Databricks resources listed in the following table. Resources not listed here, such as Unity Catalog Volumes (file upload/download), are not supported". The table has AI Search, serving endpoint, SQL warehouse, UC connections, UC tables/functions, Genie and MCP. Lakebase is absent. [Azure](https://learn.microsoft.com/en-us/azure/databricks/generative-ai/agent-framework/agent-authentication-model-serving) (ms.date 2026-09-21). The [AWS copy](https://docs.databricks.com/aws/en/agents/custom-agents/model-serving/agent-authentication-model-serving) is identical.
- Lakebase appears only under automatic passthrough ("Lakebase | `databricks_superuser` | 3.3.2 or above"). That path runs as "a service principal" created per model version, so the identity is shared. No Lakebase-specific sentence names the identity, so that part is inferred. The agent-memory page is silent on it.
- disconfirming query "ModelServingUserCredentials Lakebase" → nothing.
nuance:
- OBO here is Public Preview, "disabled by default and must be enabled by a workspace admin".
- The page now says "For new use cases, Databricks recommends deploying agents on Databricks Apps".

## claim 4: Release status of Apps user authorization (Oct 2026)
verdict: UNVERIFIABLE as GA. The best reading is still Public Preview.
confidence: medium that it is officially Preview; high that no GA announcement exists
evidence:
- Preview was announced 2025-03-26 in the [release notes](https://docs.databricks.com/aws/en/release-notes/product/2025/march). I checked each monthly release-notes page from Oct 2025 to Sep 2026 and found no GA entry.
- The Apps auth page (2026-09-28) has no Preview admonition. A missing label is not a GA announcement.
- [Agents-on-Apps auth](https://learn.microsoft.com/en-us/azure/databricks/agents/custom-agents/agent-authentication) (2026-09-11): "User authorization is in Public Preview. Your workspace admin must enable it before you can use user authorization."
- A [community blog](https://community.databricks.com/t5/technical-blog/databricks-apps-for-platform-admins-part-1-backend-architecture/ba-p/152208) (2026-03-30) says "Public Preview (as of March 25, 2026)".
- [What's coming](https://learn.microsoft.com/en-us/azure/databricks/release-notes/whats-coming) (updated 2026-10-01): "In late September 2026, user authorization for Databricks Apps will be automatically enabled for workspaces with the compliance security profile enabled." This is still future tense. The 2026-09-18 release note covers only Apps itself, not user authorization.
- disconfirming query "user authorization generally available" → none. One search snapshot of an older revision said "early June 2026", which is unverified but implies the date slipped.
nuance: Treat it as Preview for risk planning. Compliance-profile workspaces may not have it until the auto-enable lands. The 2025 enablement was a workspace Previews toggle; the current Apps page describes a scope allowlist (default "All APIs") instead. Ask the account team for written GA status.
