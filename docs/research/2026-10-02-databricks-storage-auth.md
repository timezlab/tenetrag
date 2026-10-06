# Databricks storage and auth facts for a GraphRAG SDK

> **Snapshot, 2026-10-02 — not maintained.** Round 1 web research lane on
> Lakebase, identity and OBO, Volumes and workspace files, Delta and synced
> tables, regions and compliance (about 60 searches and fetches). The
> maintained, re-verified summary is in
> [databricks-platform.md](../reference/databricks-platform.md); where they
> differ, the maintained doc wins. Adopter-specific lines were removed before
> publishing.
>
> **Errata and later resolutions:**
> - Apps user authorization status, open in sections 4.2 and 9, was settled as
>   Public Preview by
>   [2026-10-02-factcheck-lakebase-obo.md](2026-10-02-factcheck-lakebase-obo.md).
> - The LightRAG Postgres question in section 10 was answered in
>   [2026-10-02-core-engines-source.md](2026-10-02-core-engines-source.md):
>   `PGGraphStorage` needs AGE; `PGTableGraphStorage` (added 2026-06-22) uses
>   plain tables.

Research date: 2026-10-02. Lane: web research (read-only; nothing installed).
Audience: dispatching agent deciding load-bearing architecture choices for a Python GraphRAG SDK that runs on Databricks (pluggable engines: Microsoft GraphRAG, LightRAG, LlamaIndex PropertyGraphIndex, others). First adopter: an internal team; cloud unknown.

Labels (per brief): [primary] official doc or release note; [secondary] blog, forum or third party; [inferred] my reasoning; [unverified] could not confirm.
Dates are the page's "last updated" / ms.date where visible, otherwise the date I read it.

---

## 0. Executive summary: five findings most likely to change the architecture

1. **No Apache AGE and no native graph store.** Lakebase (Postgres 16/17/18) extension lists contain pgvector (ivfflat and HNSW), pg_trgm, unaccent, ltree, pgrouting, PostGIS, pg_graphql (a GraphQL API, not a graph database), but not AGE (also absent: pg_search, pgvectorscale, pg_cron). No roadmap or forum statement about AGE found. [primary for the list; absence-based; roadmap [unverified]]. The graph therefore has to live as relational node and edge tables, traversed with `WITH RECURSIVE` (Postgres in Lakebase; Databricks SQL rCTE is GA), pgRouting for path-finding [inferred], GraphFrames on classic clusters only, or an external graph DB (Neo4j). Any engine storage backend that depends on AGE will not run on Lakebase [inferred; the LightRAG Postgres graph backend is believed to use AGE, to be verified in the engine-comparison lane].
2. **OBO to Lakebase works only through Databricks Apps.** Apps user authorization (scope `postgres`, header `x-forwarded-access-token`) lets AppKit open a per-user Postgres pool where `current_user` is the end user, so Postgres RLS works; each user needs a pre-created Postgres role, and `databricks_superuser` bypasses RLS. Model Serving OBO (Public Preview) does not list Lakebase; Model Serving passthrough to Lakebase runs as a system service principal and needs the deployer to hold `databricks_superuser` (shared identity, no per-user enforcement). Apps user authorization is labeled Public Preview on one Databricks page and an Oct-2025 community thread, but unlabeled on the 2026-09-28 auth page: treat as Preview until confirmed.
3. **Lakebase connections are token-bound.** The Postgres password is a workspace OAuth token that lives 1 hour (ttl 300-3600 s), minted with `w.postgres.generate_database_credential(endpoint=...)`. Connection pools must mint a fresh token for every new connection. Roles map from Databricks identities via `databricks_create_role(name, 'USER'|'SERVICE_PRINCIPAL'|'GROUP')`. Native password roles are off by default for new projects (since 2026-05-21).
4. **Cloud choice is a region and compliance question.** Azure `southeastasia` (GA 2026-03-02) and AWS `ap-southeast-1` (Singapore) both host Lakebase; GCP has only us-east4, us-central1, europe-west3. PCI-DSS and HITRUST: Azure all Lakebase regions (2026-08-10); AWS us-east-1 first, then all AWS Lakebase regions (September 2026 release note, cross-checked against the AWS data-protection page); both require a workspace with the compliance security profile. Private Link needs an extra port-5432 "performance-intensive services" endpoint for external Postgres clients.
5. **Files are poor graph stores; Delta plus Lakebase is the natural pair.** UC Volumes: no direct-append or random writes, sparse files unsupported, 5 GB UI upload limit. Workspace files: 500 MB cap, executors cannot write, access expires after 36 h (interactive) / 30 days (jobs). GraphFrames runs only on classic DBR ML clusters. Delta to Lakebase is first-class (synced tables, ARRAY<FLOAT> can map to `vector(n)`); Lakebase to Delta exists as Lakebase Change Data Feed (Public Preview).

---

## 1. Lakebase product facts (Q1)

### 1.1 Names, variants, lifecycle
- "Lakebase" is Databricks' managed Postgres. The current product is the Autoscaling platform: project -> branches -> computes (endpoints), databases, roles; scale-to-zero, instant branching/restore, high availability, read replicas. [primary] https://learn.microsoft.com/en-us/azure/databricks/oltp/projects/manage-projects (2026-09-11)
- "Lakebase Provisioned" (database instances, API namespace `w.database`) is the legacy variant: no new Provisioned databases after 2026-03-12 [primary] https://learn.microsoft.com/en-us/azure/databricks/dev-tools/databricks-apps/lakebase (2026-09-11); the instances page (2026-09-25) states instances were upgraded to the Autoscaling platform in July 2026 [primary, read in an earlier pass: https://learn.microsoft.com/en-us/azure/databricks/oltp/instances/]. New work should target the Autoscaling API (`w.postgres`).
- Timeline (Azure release notes, https://learn.microsoft.com/en-us/azure/databricks/release-notes/lakebase/, updated 2026-10-01) [primary]:
  - 2026-02-04 Azure Beta; 2026-03-02 Azure GA (11 new regions incl. southeastasia) and high availability; 2026-03-04 GA with compliance security profile.
  - 2026-05-12 Lakebase CDF Public Preview; 2026-05-20 CMK in all AWS+Azure regions, compute up to 64 CU; 2026-05-21 native password auth disabled by default for new projects.
  - 2026-06-16 Lakebase Search Beta; 2026-06-18 Postgres 18; 2026-07-14 SOC 2 Type 2.
  - 2026-08-10 PCI-DSS + HITRUST; 2026-08-14 Postgres APIs GA (REST, CLI, Python/Java/Go SDKs); 2026-08-18 eastasia and three other regions; 2026-08-24 minors 16.15 / 17.11 / 18.6; 2026-08-31 SLA (99.99% zone-redundant HA, 99.9% single compute); 2026-09-03 japaneast.
  - 2026-09-18 Lakebase Search GA; 2026-09-30 extension version bumps; 2026-10-01 LTAP Direct Writes GA.
  - Beta: snapshots API (2026-09-15), backup schedule API (2026-09-22), system-table telemetry (2026-09-23).

### 1.2 Postgres versions
- Postgres 16, 17 (default), 18. Select 18 at project creation. [primary] https://learn.microsoft.com/en-us/azure/databricks/oltp/projects/manage-projects (2026-09-11); Postgres 18 added 2026-06-18 [primary] release notes above.
- PG19 is not offered, so PG19 SQL/PGQ (property-graph queries) is not available in Lakebase [inferred from the version list; see 6].

### 1.3 Regions (region = workspace region; cannot be changed)
- Azure (19) [primary, 2026-09-11, https://learn.microsoft.com/en-us/azure/databricks/oltp/projects/manage-projects]: eastus, eastus2, centralus, northcentralus, southcentralus, westus, westus2, canadacentral, brazilsouth, northeurope, uksouth, westeurope, francecentral, germanywestcentral, australiaeast, centralindia, **southeastasia**, eastasia, japaneast. `southeastasia` GA 2026-03-02; `eastasia` 2026-08-18; `japaneast` 2026-09-03.
- AWS (12) [primary, 2026-09-11, https://docs.databricks.com/aws/en/oltp/projects/manage-projects]: us-east-1, us-east-2, us-west-2, ca-central-1, sa-east-1, eu-central-1, eu-west-1, eu-west-2, ap-south-1, **ap-southeast-1 (Singapore)**, ap-southeast-2, ap-northeast-1 (Tokyo, added 2026-06).
- GCP (3) [primary, 2026-09-11, https://docs.databricks.com/gcp/en/oltp/projects/manage-projects]: us-east4, us-central1, europe-west3.

### 1.4 Extensions (confirm / refute list)
Sources: https://learn.microsoft.com/en-us/azure/databricks/oltp/projects/extensions (2026-09-30), https://docs.databricks.com/aws/en/oltp/projects/extensions, release notes (2026-09-30 bump).

| Extension | Status | Notes |
|---|---|---|
| Apache AGE | **absent** [primary, absence-based] | No official statement or roadmap found [unverified] |
| pgvector | present, ivfflat + HNSW | 0.8.x; `vector`, `halfvec` types; max 16,000 dims in synced-table type override |
| pg_trgm | present | |
| unaccent | present | |
| ltree | present | |
| pgrouting | present | shortest-path functions over edge tables [inferred usefulness] |
| PostGIS family | present | 3.3.10 (PG16), 3.5.7 (PG17), 3.6.4 (PG18) as of 2026-09-30 |
| pg_graphql | present | GraphQL API, not a graph store |
| hstore, hll (2.21), databricks_auth | present | `databricks_auth` provides `databricks_create_role` and synced-table manager helpers |
| lakebase_vector / lakebase_text / lakebase_tokenizer | present, GA 2026-09-18 (tokenizer 2026-09-28) | `lakebase_ann` ANN index (pgvector-compatible, 1B+ vectors per index claimed), `lakebase_bm25` BM25 index; needs "Lakebase Search" enabled in project settings (enablement is irreversible per the earlier-read lakebase-search page, https://learn.microsoft.com/en-us/azure/databricks/oltp/projects/lakebase-search, 2026-09-23) |
| pg_search, pgvectorscale, pg_cron | absent [primary, absence-based] | |

### 1.5 Sizing and platform limits [primary, https://learn.microsoft.com/en-us/azure/databricks/oltp/projects/manage-projects, 2026-09-11]
- Compute 0.5 to 112 CU (autoscaling up to 64 CU; 1 CU = 2 GB RAM). New project default for the production branch: 8-16 CU autoscaling, scale-to-zero 24 h, HA disabled; project compute defaults for new computes 2-4 CU.
- Scale to zero: 60 s to 7 days. HA: 1-3 secondaries across zones; read replicas up to 6 per branch; 20 concurrently active computes (default branch exempt).
- 500 branches/project; 500 roles and 500 databases per branch; 1000 projects/workspace; 10 manual snapshots; history window 2-30 days (default 7); storage quota per branch adjustable on request.
- Up to 1,000 concurrent connections; each synced table uses up to 16 [primary, https://learn.microsoft.com/en-us/azure/databricks/oltp/projects/sync-tables, 2026-10-01].
- Not supported: Postgres superuser, native logical replication ("not yet available"), tablespaces, direct access to Postgres logs [primary, https://docs.databricks.com/aws/en/oltp/projects/compatibility, 2026-09-11].
- UI-created roles get `databricks_superuser`; the project creator automatically gets a role and owns `databricks_postgres` [primary, manage-projects].

### 1.6 Compliance, encryption, networking
- SOC 2 Type 2 (2026-07-14). PCI-DSS and HITRUST for workspaces with the compliance security profile: Azure all Lakebase regions (2026-08-10); AWS limited to us-east-1 at 2026-08-10, then extended to all AWS Lakebase regions (September 2026) [primary, cross-verified: https://docs.databricks.com/aws/en/release-notes/lakebase/ and https://docs.databricks.com/aws/en/oltp/projects/data-protection]. HIPAA, C5, TISAX also; Azure adds ISMAP, IRAP (australiaeast only), UK Cyber Essentials Plus (uksouth, ukwest) [primary, https://learn.microsoft.com/en-us/azure/databricks/oltp/projects/data-protection, ms.date 2026-07-15]. The pages point to per-region "Regional support for features" tables on the PCI-DSS / HITRUST pages, which I did not read [unverified for southeastasia and ap-southeast-1 specifically].
- Customer-managed keys: all AWS and Azure Lakebase regions, new projects only (2026-05-20) [primary].
- Private Link [primary, https://learn.microsoft.com/en-us/azure/databricks/oltp/projects/private-link, 2026-09-11]: inbound Private Link (443) is required; Service Direct "performance-intensive services" Private Link (port 5432, host `*.database.<region>.azuredatabricks.net`) is additionally required for Postgres clients outside the workspace that use a regional connection string. Not needed for in-workspace Apps, Feature Store connectors, in-product UI, or Data-API-only access.
- Lakebase CDF fails when destination storage is private-endpoint-only [primary, https://learn.microsoft.com/en-us/azure/databricks/oltp/projects/lakebase-cdf, updated 2026-09-30; from earlier read].

---

## 2. Lakebase identity and access (Q2)

### 2.1 Mechanisms
- **OAuth token as password** (default). Mint with the SDK; token valid up to 1 hour; use `sslmode=require`; token is workspace-scoped. Connections: 24 h idle timeout, 3-day maximum life (from the earlier read of https://learn.microsoft.com/en-us/azure/databricks/oltp/projects/authentication, 2026-09-11) [primary, not re-verified this pass].
- **Native Postgres password roles**: disabled by default for new projects since 2026-05-21; enable in project settings. Needed for PgBouncer-style pooling per the earlier read of the auth docs [primary, not re-verified].
- **Role mapping**: Postgres role must exist for the Databricks identity. `CREATE EXTENSION IF NOT EXISTS databricks_auth; SELECT databricks_create_role('<identity>', 'USER'|'SERVICE_PRINCIPAL'|'GROUP');` Roles can also be created via the Lakebase UI/REST API (2026-03-12). [primary, https://docs.databricks.com/aws/en/oltp/projects/postgres-roles]
- **Token scoping**: `claims` is an optional list of `{permission_set: READ_ONLY|PERMISSION_SET_UNSPECIFIED, resources: [{table_name: "<catalog.schema.table>"}]}`; "the returned token will be scoped to UC tables with the specified permissions". `ttl` 300-3600 s; `expire_time` between 5 min and 1 h ahead. [primary, https://docs.databricks.com/api/postgres/v1/generate-database-credential.md, undated]. How Postgres enforces the claims in practice [unverified].

### 2.2 SDK method names [primary unless noted]
- `w.postgres.generate_database_credential(endpoint="projects/<p>/branches/<b>/endpoints/<e>", claims=None, expire_time=None, ttl=None)` returns `.token`, `.expire_time` (SDK docs https://databricks-sdk-py.readthedocs.io/en/latest/workspace/postgres/postgres.html; databricks-sdk-py v0.145.0 released 2026-10-01 per CHANGELOG).
- `w.postgres.create_project / get_project / list_projects / update_project / delete_project(purge=True) / undelete_project`; branch, endpoint, database and role methods; `create_synced_table / get_synced_table / delete_synced_table`; CDF and Data API methods exist (names not captured). APIs GA since 2026-08-14.
- Legacy Provisioned: `w.database.generate_database_credential(...)` with `instance_names` (SDK >= 0.61.0) [secondary, search snippet only]; exact signature [unverified].

```python
from databricks.sdk import WorkspaceClient
w = WorkspaceClient()
credential = w.postgres.generate_database_credential(
    endpoint="projects/my-project/branches/production/endpoints/my-compute")
# credential.token is the Postgres password; connect with sslmode=require
```

Pool pattern (token minted for every new connection) [primary, https://learn.microsoft.com/en-us/azure/databricks/oltp/projects/external-apps-connect]:

```python
class OAuthConnection(psycopg.Connection):
    @classmethod
    def connect(cls, conninfo="", **kwargs):
        credential = client.postgres.generate_database_credential(endpoint=endpoint_name)
        kwargs["password"] = credential.token
        return super().connect(conninfo, **kwargs)
```

### 2.3 How each runtime gets credentials
| Runtime | Identity | How credentials arrive | Status |
|---|---|---|---|
| Databricks App, app authorization | Auto-created service principal | Env `DATABRICKS_CLIENT_ID/SECRET` (SDK unified auth); adding a Lakebase resource ("Can connect and create") creates a Postgres role named after the SP client ID with CONNECT + CREATE; env `PGHOST, PGDATABASE, PGPORT, PGSSLMODE, PGUSER, PGAPPNAME`; resource key `postgres`. App mints its own 1 h token. [primary, https://learn.microsoft.com/en-us/azure/databricks/dev-tools/databricks-apps/lakebase] | documented |
| Databricks App, user authorization (OBO) | End user | Scope `postgres`; forwarded token in `x-forwarded-access-token` (+ `x-forwarded-email`); AppKit `asUser(req)` builds a per-user pool authenticated with the user's identity; `current_user` is the user; per-user role must pre-exist; per-user pools idle-close after 30 s. [primary, https://developers.databricks.com/docs/appkit/v0/plugins/lakebase.md] Forwarded token is scoped to the app's workspace [primary, https://docs.databricks.com/aws/en/dev-tools/databricks-apps/auth, 2026-09-28]. | Preview status conflicting |
| Model Serving, automatic passthrough | Per-model-version system service principal | Declare `DatabricksLakebase(...)` in `resources` at `log_model`; MLflow >= 3.3.2; the endpoint creator must hold `databricks_superuser`. [primary, https://learn.microsoft.com/en-us/azure/databricks/generative-ai/agent-framework/agent-authentication-model-serving, 2026-09-21] | documented |
| Model Serving, OBO | End user | **Lakebase is not in the OBO supported-resource list** (AI Search index, serving endpoint, SQL warehouse, UC connections, UC tables and functions via Statement Execution, Genie, MCP). [primary, same page] | Public Preview |
| Model Serving, manual | Your SP | OAuth client id/secret from Databricks secrets as env vars; then mint Postgres token. [primary, same page] | documented |
| Serverless notebook / Job | Notebook user, or the job's run-as identity/SP | `WorkspaceClient()` picks `runtime` / `runtime-oauth` credentials from the environment, then call `generate_database_credential`; the identity needs a Postgres role. [inferred from SDK auth types + docs; the notebook doc I found covers legacy instances: https://docs.databricks.com/aws/en/oltp/query/notebook] | inferred |
| External client (outside Databricks) | PAT or OAuth M2M SP | SDK mints token; connect to regional host; Private Link 5432 endpoint if the workspace uses Private Link. [primary, external-apps-connect + private-link pages] | documented |

### 2.4 Can an OBO token authenticate as the user?
- In Apps: yes, via AppKit: it extracts the forwarded token and identity and "initializes a dedicated pool for that user with OAuth credentials"; `current_user` reflects the user. [primary, AppKit docs]. Using the raw forwarded token as a Postgres password outside AppKit is [inferred] (consistent with "OAuth token as password" plus the `postgres` scope) but not shown in the docs I read.
- In Model Serving: no (see table).
- PAT/OAuth M2M: authenticates as the PAT owner / SP; same token-as-password mechanism.

### 2.5 Row-level security
- Native Postgres RLS works; AppKit example: `CREATE POLICY user_orders ON app.orders FOR ALL TO PUBLIC USING (owner = current_user);` Superusers, including members of `databricks_superuser`, bypass RLS. [primary, AppKit docs]
- Synced tables are owned by `databricks_writer_<dbid>`, so owner-only commands such as configuring RLS cannot be run on them directly [primary, sync-tables page]. [inferred design consequence]: put per-user ACL/RLS on SDK-owned native tables (or views over them), not on synced tables.
- Project-level permissions (CAN CREATE / CAN USE / CAN MANAGE) govern platform actions; database access is separate Postgres roles and grants [primary, manage-projects].
- `GROUP` role semantics (membership, inheritance) not captured [unverified].

---

## 3. Delta <-> Lakebase movement (Q3)

### 3.1 Delta -> Lakebase: synced tables [primary, https://learn.microsoft.com/en-us/azure/databricks/oltp/projects/sync-tables, 2026-10-01]
- Sources: managed and external Delta, managed and external Iceberg, views and materialized views.
- Modes: Snapshot (full copy each run; 10x more efficient if >10% of rows change); Triggered (scheduled or on-demand incremental; costly if run more often than every 5 minutes); Continuous (seconds of latency, minimum 15-second intervals, highest cost). Triggered and Continuous need change data feed on the source (write-time CDF or Automatic CDF, which also covers Iceberg).
- Throughput guidance: about 150 rows/s per CU for Continuous/Triggered, up to 2,000 rows/s per CU for Snapshot.
- Limits: up to 16 connections per synced table; 20 synced tables per source table; recommended not to exceed 1 TB per table that needs refreshes; names `[A-Za-z0-9_]+`; additive schema changes only for Triggered/Continuous; definition cannot be changed in place; duplicate primary keys fail the sync unless a timeseries key is set; rows with NULL primary-key columns are excluded; UC schema name becomes the Postgres schema.
- Types: ARRAY/MAP/STRUCT become JSONB; GEOGRAPHY, GEOMETRY, VARIANT, OBJECT unsupported. `type_overrides` can map `ARRAY<FLOAT|DOUBLE>` to `vector(n)` or `halfvec(n)` (n = 1-16,000) and STRING to `varchar(n)`, but the extension must be installed before the synced table is created (`CREATE EXTENSION IF NOT EXISTS lakebase_vector CASCADE;` or `vector`).
- Postgres side: read-only by recommendation (reads, create/alter/drop index, drop table); owned by `databricks_writer_<dbid>`; the creator gets SELECT/DELETE/TRUNCATE plus schema USAGE/CREATE; a `databricks_superuser` can read and write.
- LTAP Direct Writes (GA 2026-10-01): opt-in per synced table, speeds initial load and (for Snapshot) every refresh by writing straight to the storage layer; PG 16/17/18; cannot be added later.
- Creation API: `w.postgres.create_synced_table(synced_table=SyncedTable(spec=SyncedTableSyncedTableSpec(source_table_full_name=..., branch="projects/<p>/branches/<b>", primary_key_columns=[...], scheduling_policy=...SNAPSHOT, postgres_database=..., create_database_objects_if_missing=True)), synced_table_id="<catalog>.<schema>.<table>").wait()`. A Lakeflow Jobs task type "Database Table Sync pipeline" can trigger or schedule syncs.

### 3.2 Lakebase -> Delta [primary]
- Lakebase Change Data Feed (Public Preview since 2026-05-12): WAL-based row-level changes written to Unity Catalog managed Delta tables (`lb_<table>_history` naming, `wal2delta`, `REPLICA IDENTITY FULL` required, per the earlier read of https://learn.microsoft.com/en-us/azure/databricks/oltp/projects/lakebase-cdf, updated 2026-09-30). Fails with private-endpoint-only destination storage.
- A "Register database in Unity Catalog" feature exists (link on the sync-tables page); I did not read it [unverified].
- Native Postgres logical replication is not available [primary].

---

## 4. Auth surfaces (Q4)

### 4.1 SDK unified auth [primary, https://learn.microsoft.com/en-us/azure/databricks/dev-tools/auth/unified-auth (2026-09-11) and databricks-sdk-py `credentials_provider.py`]
Registered `auth_type` values: `pat`, `basic`, `runtime`, `runtime-oauth`, `oauth-m2m`, `external-browser`, `databricks-cli`, `azure-client-secret`, `azure-cli`, `google-credentials`, `google-id`, `env-oidc`, `file-oidc`, `github-oidc`, `github-oidc-azure`, `azure-devops-oidc`, `metadata-service`, `model-serving`. Docs list "Azure managed identity" but I saw no matching registered `auth_type` [unverified naming].
Mapping to the SDK's three required modes:
- PAT: `pat` (`DATABRICKS_TOKEN`).
- OAuth M2M: `oauth-m2m` (`DATABRICKS_CLIENT_ID`, `DATABRICKS_CLIENT_SECRET`).
- OBO: Apps forwarded token or Model Serving `ModelServingUserCredentials()` credential strategy. Apps docs show passing the forwarded token as a bearer to the SQL connector (`sql.connect(..., access_token=user_token)`) [primary]; building a `WorkspaceClient` from it with `token=` is [inferred].

### 4.2 Apps OBO [primary, https://docs.databricks.com/aws/en/dev-tools/databricks-apps/auth, 2026-09-28]
- Header `x-forwarded-access-token`; identity headers `X-Forwarded-Email`, `-User`, `-Preferred-Username` (https://learn.microsoft.com/en-us/azure/databricks/dev-tools/databricks-apps/http-headers).
- Scopes declared per app (`user_api_scopes` in app config): ai-functions, ai-gateway, apps, files, genie, model-serving, **postgres**, sql, vector-search (docs also show `ai-search` after the 2026-06-01 rename), sql:restricted-query, catalog.*:read, workspace.workspace; defaults `iam.access-control:read`, `iam.current-user:read` (https://docs.databricks.com/api/workspace/api/scopes).
- Admin setting: Settings > Development > Apps > "Restrict OAuth scopes for apps to selected values".
- Token is scoped to the app's workspace; never log tokens. No lifetime/refresh statement found [unverified].
- Status: no Preview badge on the auth page (2026-09-28); the agents-on-Apps page says Public Preview; an Oct-2025 community thread says "in public preview" with no GA date [secondary, https://community.databricks.com/t5/administration-architecture/databricks-apps-on-behalf-of-user-authorization-general/m-p/134678]. Treat as Preview [unverified].

### 4.3 Model Serving OBO [primary, https://learn.microsoft.com/en-us/azure/databricks/generative-ai/agent-framework/agent-authentication-model-serving, 2026-09-21]
- Public Preview; MLflow >= 2.22.1; disabled by default, workspace admin must enable.
- Code: `user_client = WorkspaceClient(credentials_strategy=ModelServingUserCredentials())` (from `databricks_ai_bridge`); initialize inside `predict`/`predict_stream`, not `__init__`; declare scopes with `AuthPolicy(system_auth_policy=SystemAuthPolicy(resources=[...]), user_auth_policy=UserAuthPolicy(api_scopes=["model-serving","ai-search"]))`.
- Databricks recommends Apps for new agents.

### 4.4 Which downstream services accept OBO
| Service | Apps (user authorization) | Model Serving OBO |
|---|---|---|
| Vector Search / AI Search | scope `vector-search` (renamed AI Search 2026-06-01) | yes (`VectorSearchClient` with `CredentialStrategy.MODEL_SERVING_USER_CREDENTIALS`) |
| SQL warehouses | `sql`, `sql:restricted-query` | yes |
| UC tables / functions | via `sql` and `catalog.*:read` | tables only via SQL Statement Execution; functions via SQL warehouse (serverless Spark with OBO not supported) |
| Genie | `genie` | yes |
| Model Serving endpoints | `model-serving` | yes |
| Files / UC Volumes | `files` | **no** (explicitly unsupported) |
| Lakebase | `postgres` | **no** (not listed) |
| AI Functions / AI Gateway | `ai-functions`, `ai-gateway` | not listed |

[primary for both columns; the scope list is from the scopes API page and the OBO list from the Model Serving page.]

---

## 5. UC Volumes and Workspace files (Q5)

### 5.1 UC Volumes [primary, https://learn.microsoft.com/en-us/azure/databricks/volumes/volume-files, 2026-09-30]
- Path `/Volumes/<catalog>/<schema>/<volume>/...`; POSIX/FUSE-style paths, plus Spark, pandas, SQL (`read_files`, `LIST`), `dbutils.fs`, `%sh`, Databricks CLI (`dbfs:/Volumes/...`), SDK `WorkspaceClient.files`, REST Files API (`/api/2.0/fs/files/...`), SQL connectors (`PUT INTO`, `GET`, `REMOVE`).
- Intended use: non-tabular data and workload support files (ingest files, text/image/audio, artifacts, libraries, init scripts, build artifacts); tabular data belongs in UC tables.
- Limits: files up to the underlying cloud storage maximum, but UI upload is capped at 5 GB (use the SDK above that). Direct-append and non-sequential (random) writes are not supported (zip, Excel): write to local disk, then copy. Sparse files unsupported. Other docs state the Files API limit as 5 GiB; unit wording differs between pages [unverified exact limit].
- Compute access: classic UC clusters (dedicated and standard) get POSIX and Spark access; serverless notebooks/jobs use the same paths (DataFrame checkpoints in volumes are not supported on serverless, and need DBR 18.1+); SQL warehouses via SQL (`read_files`, `LIST`); Apps can attach a Volume as a resource (https://learn.microsoft.com/en-us/azure/databricks/dev-tools/databricks-apps/uc-volumes; whether `/Volumes` is FUSE-mounted inside the app container [unverified]); Model Serving OBO cannot touch Volumes [primary]; Model Serving automatic passthrough does not list Volumes [primary absence].
- Performance numbers: none published in the pages read [unverified].

### 5.2 Workspace files [primary, https://learn.microsoft.com/en-us/azure/databricks/files/workspace, 2026-09-11]
- Intended for notebooks, code modules, config (YAML), small data files, libraries, logs.
- File size limit 500 MB. Executors cannot write. Access to `/Workspace` expires after 36 h on interactive compute and 30 days for jobs. Git-sourced jobs cannot write to the current directory or via relative paths. On serverless the working directory is not guaranteed (use absolute paths). Workspace files cannot be accessed from UDFs on standard access mode DBR <= 14.2.
- Recommendation [inferred]: configs and code only; never graph data.

---

## 6. Graph capability in 2026 (Q6)

- **Native graph store or query feature: none found.** Absence-based; no Databricks graph query language or graph DB in docs read. [inferred]
- **Recursive CTEs: GA.** DBSQL 2025.20 (2025-07-03) Public Preview, DBSQL 2025.25 (August 2025) "Recursive common table expressions (rCTEs) are generally available", DBSQL 2025.35 (2025-10-30) adds `LIMIT ALL`. [primary, https://docs.databricks.com/aws/en/sql/release-notes/2025]. Reference page (updated 2026-09-11) shows no Preview badge; applies to DBSQL and DBR 17.0+; `MAX RECURSION LEVEL` default 100 (error `RECURSION_LEVEL_LIMIT_EXCEEDED`); result capped at 1,000,000 rows unless `LIMIT`/`LIMIT ALL`; must be `UNION ALL`; no correlated references in the step; not for UPDATE/DELETE/MERGE. [primary, https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-qry-select-cte]. A search-result snippet still said "Public Preview"; it is stale. Cycle guard pattern from the docs:

```sql
WITH RECURSIVE search_graph(f,t,label,path,cycle) AS (
  SELECT *, array(struct(g.f,g.t)), false FROM graph g
  UNION ALL
  SELECT g.*, path || array(struct(g.f,g.t)), array_contains(path, struct(g.f,g.t))
  FROM graph g, search_graph sg WHERE g.f = sg.t AND NOT cycle)
SELECT path FROM search_graph;
```
- Postgres `WITH RECURSIVE` on Lakebase is standard Postgres [inferred]; add `pgrouting` for shortest paths [inferred].
- **GraphFrames**: ships with classic Databricks Runtime ML; not usable on serverless or Databricks Connect (https://learn.microsoft.com/en-us/azure/databricks/integrations/graphframes/ and https://learn.microsoft.com/en-us/azure/databricks/dev-tools/databricks-connect/python/limitations) [primary for classic-only; serverless exclusion inferred]. `graphframes-py` on PyPI has 2026 releases (https://pypi.org/project/graphframes-py/) [secondary].
- **Neo4j / partners**: Neo4j Connector for Apache Spark 6.0 (https://neo4j.com/docs/spark/current/) and a Neo4j-Databricks connector announcement (https://neo4j.com/blog/news/neo4j-databricks-connector/) [secondary]; Databricks' own blog (2025-04) "Building, Improving, and Deploying Knowledge Graph RAG Systems on Databricks" uses Neo4j + Delta (https://databricks.com/blog/building-improving-and-deploying-knowledge-graph-rag-systems-databricks) [secondary: search snippet only].
- **Genie Ontology** (announced at Data + AI Summit, June 2026): a context graph for Genie, not a user-facing graph store. [secondary, https://www.storagenewsletter.com/2026/06/26/data-ai-summit-2026-all-news and https://atlan.com/know/ai-agent/databricks/genie-ontology/]
- **PostgreSQL 19 SQL/PGQ**: beta feature of upstream PG19 [secondary, https://thebuild.com/blog/sqlpgq-in-postgresql-19-graph-queries-without-the-graph-database/, https://victoriametrics.com/blog/postgres-19/]; Lakebase offers PG 16-18 only, no statement about PG19 adoption [unverified].
- **Vector Search rename**: now "Databricks AI Search" (2026-06-01); SDK and class names keep `VectorSearch` [secondary, https://community.databricks.com/t5/mvp-articles/databricks-ai-search/td-p/161008].

---

## 7. Implications for the SDK design [inferred, not research findings]
1. Storage tiers: Delta (system of record: chunks, entities, relationships, community reports, embeddings) -> synced tables -> Lakebase (serving: relational node/edge tables, pgvector/lakebase_vector, BM25/tsvector, recursive-CTE traversal). Volumes only for engine artifacts (parquet, GraphML/JSON), written via local disk then copy.
2. Engine adapters must not assume AGE; engines whose Postgres backend needs AGE need an alternate (relational) graph store implementation.
3. Auth: accept a `WorkspaceClient` or unified-auth config; for Lakebase always mint tokens per new connection; per-user pools for OBO (Apps only); in Model Serving expect a shared identity, so do authorization in the SDK layer or host the query service in Apps.
4. Per-user filtering: RLS on SDK-owned native tables (not synced tables); keep end users out of `databricks_superuser`.
5. Treat Apps user authorization and Model Serving OBO as Preview for production planning; Lakebase CDF is Preview.

---

## 8. Verification log (conflicts and corrections)
- Recursive CTE status: a search snippet said Public Preview; the DBSQL 2025 release notes say GA at 2025.25 and the CTE doc has no Preview badge -> GA. (Search-summary claimed October for 2025.25, fetch said August; month not load-bearing.)
- AWS PCI-DSS/HITRUST: Azure release note (2026-08-10) says AWS limited to us-east-1; AWS release notes and AWS data-protection page say all AWS Lakebase regions as of September 2026 -> use the later statement. A search snippet saying Lakebase supports only HIPAA/C5/TISAX/None is stale (March 2026).
- Apps user authorization status: unresolved (see 4.2).
- Earlier fetch summaries were partial at times; I re-fetched primary pages for cross-checks (Lakebase overview, authentication, Model Serving OBO, GraphFrames).

## 9. Gaps (could not verify)
- Any AGE roadmap or forum statement (absence-based finding).
- Practical enforcement semantics of the `claims` parameter; `GROUP` role semantics; Lakebase cold-start latency after scale-to-zero.
- Apps forwarded-token lifetime/refresh; raw forwarded token as Postgres password outside AppKit.
- Whether `/Volumes` is FUSE-mounted inside Apps containers; Volume performance numbers; 5 GB vs 5 GiB wording.
- GraphFrames-on-serverless exclusion (inferred); PG19 SQL/PGQ adoption by Lakebase.
- Azure managed identity `auth_type` name in the SDK; legacy `w.database.generate_database_credential` signature.
- Apps user-authorization Preview/GA status; per-region PCI-DSS/HITRUST tables for southeastasia and ap-southeast-1; "Register database in Unity Catalog" details.

## 10. Leads (outside this lane)
- Engine lane: does LightRAG's Postgres graph backend require Apache AGE; what do Microsoft GraphRAG (parquet + LanceDB) and LlamaIndex PropertyGraphIndex need from storage?
- Vector Search / AI Search as an alternative embedding store (index sync from Delta, OBO scope `vector-search`).
- Local data-residency rules are out of scope here.

## Sources (numbered, dated)
1. Lakebase landing page, Azure: https://learn.microsoft.com/azure/databricks/oltp/ (2026-09-29/30)
2. Lakebase Provisioned page: https://learn.microsoft.com/en-us/azure/databricks/oltp/instances/ (2026-09-25)
3. Extensions (Azure): https://learn.microsoft.com/en-us/azure/databricks/oltp/projects/extensions (2026-09-30); AWS: https://docs.databricks.com/aws/en/oltp/projects/extensions
4. Compatibility: https://docs.databricks.com/aws/en/oltp/projects/compatibility (2026-09-11)
5. Limitations: https://docs.databricks.com/aws/en/oltp/projects/limitations (2026-09-11)
6. Manage projects: Azure https://learn.microsoft.com/en-us/azure/databricks/oltp/projects/manage-projects, AWS https://docs.databricks.com/aws/en/oltp/projects/manage-projects, GCP https://docs.databricks.com/gcp/en/oltp/projects/manage-projects (all 2026-09-11)
7. Lakebase release notes: Azure https://learn.microsoft.com/en-us/azure/databricks/release-notes/lakebase/ (updated 2026-10-01); AWS https://docs.databricks.com/aws/en/release-notes/lakebase/ (read 2026-10-02)
8. Data protection: Azure https://learn.microsoft.com/en-us/azure/databricks/oltp/projects/data-protection (ms.date 2026-07-15, updated 2026-09-11); AWS https://docs.databricks.com/aws/en/oltp/projects/data-protection
9. Private Link for Lakebase: https://learn.microsoft.com/en-us/azure/databricks/oltp/projects/private-link (2026-09-11)
10. Lakebase authentication: https://learn.microsoft.com/en-us/azure/databricks/oltp/projects/authentication (2026-09-11); roles https://docs.databricks.com/aws/en/oltp/projects/postgres-roles; API usage https://docs.databricks.com/aws/en/oltp/projects/api-usage; external apps https://learn.microsoft.com/en-us/azure/databricks/oltp/projects/external-apps-connect
11. REST schema: https://docs.databricks.com/api/postgres/v1/generate-database-credential.md (undated)
12. SDK docs: https://databricks-sdk-py.readthedocs.io/en/latest/workspace/postgres/postgres.html; databricks-sdk-py CHANGELOG (v0.145.0, 2026-10-01) and `credentials_provider.py` on GitHub
13. Apps: Lakebase resource https://learn.microsoft.com/en-us/azure/databricks/dev-tools/databricks-apps/lakebase (2026-09-11); auth https://docs.databricks.com/aws/en/dev-tools/databricks-apps/auth (2026-09-28); headers https://learn.microsoft.com/en-us/azure/databricks/dev-tools/databricks-apps/http-headers; UC volumes https://learn.microsoft.com/en-us/azure/databricks/dev-tools/databricks-apps/uc-volumes; scopes https://docs.databricks.com/api/workspace/api/scopes
14. AppKit Lakebase plugin: https://developers.databricks.com/docs/appkit/v0/plugins/lakebase.md (read 2026-10-02)
15. Model Serving agent authentication: https://learn.microsoft.com/en-us/azure/databricks/generative-ai/agent-framework/agent-authentication-model-serving (2026-09-21)
16. Unified auth: https://learn.microsoft.com/en-us/azure/databricks/dev-tools/auth/unified-auth (2026-09-11)
17. Synced tables: https://learn.microsoft.com/en-us/azure/databricks/oltp/projects/sync-tables (2026-10-01); Lakebase CDF https://learn.microsoft.com/en-us/azure/databricks/oltp/projects/lakebase-cdf (2026-06-11, updated 2026-09-30); Lakebase Search https://learn.microsoft.com/en-us/azure/databricks/oltp/projects/lakebase-search (2026-09-23)
18. UC Volumes: https://learn.microsoft.com/en-us/azure/databricks/volumes/volume-files (2026-09-30); Workspace files https://learn.microsoft.com/en-us/azure/databricks/files/workspace (2026-09-11); serverless limitations https://learn.microsoft.com/en-us/azure/databricks/compute/serverless/limitations (2026-09-29)
19. Recursive CTE: https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-qry-select-cte (2026-09-11); DBSQL 2025 release notes https://docs.databricks.com/aws/en/sql/release-notes/2025
20. GraphFrames: https://learn.microsoft.com/en-us/azure/databricks/integrations/graphframes/; Databricks Connect limitations https://learn.microsoft.com/en-us/azure/databricks/dev-tools/databricks-connect/python/limitations; PyPI https://pypi.org/project/graphframes-py/; https://graphframes.io/
21. Neo4j: https://neo4j.com/blog/news/neo4j-databricks-connector/; https://neo4j.com/docs/spark/current/; Databricks blog https://databricks.com/blog/building-improving-and-deploying-knowledge-graph-rag-systems-databricks (2025-04, snippet only)
22. Genie Ontology: https://www.storagenewsletter.com/2026/06/26/data-ai-summit-2026-all-news (2026-06-26); https://atlan.com/know/ai-agent/databricks/genie-ontology/
23. PG19 SQL/PGQ: https://thebuild.com/blog/sqlpgq-in-postgresql-19-graph-queries-without-the-graph-database/; https://victoriametrics.com/blog/postgres-19/
24. AI Search rename: https://community.databricks.com/t5/mvp-articles/databricks-ai-search/td-p/161008
25. Community thread on Apps OBO status: https://community.databricks.com/t5/administration-architecture/databricks-apps-on-behalf-of-user-authorization-general/m-p/134678 (2025-10-12/13)

## Method
About 60 web searches/fetches across docs.databricks.com (AWS/GCP), learn.microsoft.com (Azure), release notes, SDK docs/source, vendor blogs. Disconfirming queries run for: AGE availability/roadmap, rCTE status, PCI-DSS regional scope, Apps OBO status, Lakebase in Model Serving OBO. Fetched pages are treated as data; some fetch summaries came from a small model and were re-fetched or cross-checked where load-bearing.
