# Enterprise knowledge practice: products, glossaries, semantic layers and logs

> **Snapshot, 2026-10-04 — not maintained.** Web lane on vendor docs, standards and templates; partial coverage. The maintained,
> re-verified summary is in [domain-schemas.md](../reference/domain-schemas.md); where they differ, the maintained doc
> wins. Local paths were removed before publishing.
>
> **Errata and later resolutions:**
> - Viva Topics retirement on 2025-02-22 confirmed; AI-generated topic pages became
>   "no longer available" rather than literally deleted.
> - Open Semantic Interchange is now Apache Ossie (Apache-2.0, incubating), confirmed on
>   ossie.apache.org; the old GitHub organization shows no public repositories.

## r4 Enterprise practice for `enterprise-docs` (2026-10-04)

Labels: [primary] read on owning source this session (via WebFetch, which summarises pages, so quotes are the tool's extraction); [secondary] search snippet or third-party; [inferred] my reasoning.
Coverage is partial. Section 7 lists what was not verified.

### 1. Summary
- Every product I could read models people, documents/content, projects, meetings/events and organisations as first-class types. None publishes a "Policy", "Procedure" or "Metric" type. Those are domain-pack territory, so our `Policy`/`Procedure` are not validated by any vendor list. [primary/secondary, section 3.1]
- Atlassian Teamwork Graph is the clearest published list. Collaboration: Calendar event, Comment, Conversation, Design, Document, Message, Space, Video. Work: Project, Work item. Org: Customer organization, Deal. Code objects are also listed. [primary]
- Viva Topics (topics for Project, Event, Organization, Location, Product, Creative work, Field of study) was retired 2025-02-22. AI-generated topic pages were deleted, and user-published ones became plain SharePoint pages. This is the strongest "topic hub" cautionary tale found. [primary + secondary]
- Glossary term fields converge on: name, definition, acronym, synonym/alias, related term, parent/category, owner(s), expert/steward, status (draft/published/expired in Purview; Verified/Draft/Deprecated in Atlan), resources, custom attributes. SKOS adds definition, scopeNote, example, changeNote, historyNote, altLabel, broader/narrower/related. [primary]
- Metric definitions converge on: name, label, description, type, expression, filter, time dimension and grain, plus numerator and denominator for ratios. dbt has five metric types: simple, cumulative, derived, ratio, conversion. [primary]
- The OSI standard (now "Apache Ossie", Apache-2.0 incubating) has no owner, lifecycle, certification or effective-date fields. Its metric is name, expression, description, datatype, ai_context (instructions, synonyms, examples) and custom_extensions. No standard I read versions metric definitions over time. A graph that stores definitions as dated claims therefore fills a real gap. [primary]
- Decision logs and RAID logs are field-rich but share a small core: id, type, description, owner, status, date raised, due or review date, plus decision-specific rationale, options and superseded-by. This supports `Decision`/`ActionItem` as types, with Risk/Issue/Assumption/Dependency as one claim type with a `kind` enum. [secondary + inferred]
- Campaign briefs share objective, audience, messaging, channel, budget, KPI and timeline. Only the sources' wording is industry-neutral. Campaign is a generic type, and the offer is industry-specific content. [secondary + inferred]
- Practitioner/academic modelling uses a directed SUPERSEDES edge between versions and puts time on edges or facts. Dense graphs need caps on hops, node types and per-entity results. [secondary]

### 2. Sources table
| # | Source | Hook | Date |
|---|---|---|---|
| 1 | [dbt metrics overview](https://docs.getdbt.com/docs/build/metrics-overview) | metric types and fields | read 2026-10 |
| 2 | [OSI / Apache Ossie repo](https://github.com/open-semantic-interchange/OSI) | renamed, Apache-2.0 | 2026-10 |
| 3 | [Ossie core spec](https://raw.githubusercontent.com/open-semantic-interchange/OSI/main/core-spec/spec.md) | metric/dataset/field fields; version 0.2.0.dev0 | 2026-10 |
| 4 | [Databricks metric view YAML](https://docs.databricks.com/aws/en/metric-views/data-modeling/) | source, filter, fields, measures, joins | 2026-10 |
| 5 | [Databricks business semantics](https://docs.databricks.com/aws/en/business-semantics) | metric views, domains, pages, certification | 2026-10 |
| 6 | [Snowflake semantic view DDL](https://docs.snowflake.com/en/user-guide/views-semantic/sql) | TABLES/FACTS/DIMENSIONS/METRICS | 2026-10 |
| 7 | [Purview glossary terms](https://learn.microsoft.com/en-us/purview/unified-catalog-glossary-terms-create-manage) | term fields and lifecycle | 2026-09 |
| 8 | [Atlan glossary bulk upload](https://docs.atlan.com/product/capabilities/governance/glossary/how-tos/bulk-upload-terms-in-the-glossary) | CSV columns | 2026-10 |
| 9 | [W3C SKOS Reference](https://www.w3.org/TR/skos-reference/) | note and label properties | 2009 |
| 10 | [Atlassian object types](https://developer.atlassian.com/platform/teamwork-graph/object-types/) | object-type list | 2026-10 |
| 11 | [Atlassian search result (object-type overview)](https://developer.atlassian.com/platform/teamwork-graph/object-types/overview) | category list (page itself 404 on fetch) | 2025-07 |
| 12 | [Zep entity types blog](https://www.getzep.com/blog/entity-types-structured-agent-memory/) | three default types | 2025-05 |
| 13 | [Viva Topics retirement](https://learn.microsoft.com/en-us/microsoft-365/topics/changes-coming-to-topics) | retired 2025-02-22 | 2026-04 |
| 14 | [Glean knowledge graph docs](https://docs.glean.com/security/knowledge-graph) | content/people/activity (snippet only) | n/d |
| 15 | [Viva Topics types, third-party](https://m365admin.handsontek.net/microsoft-viva-custom-topic-types-for-viva-topics/) | type list (snippet only) | n/d |
| 16 | [CocoIndex meeting-notes graph](https://cocoindex.io/blogs/meeting-notes-graph/) | Meeting/Person/Task model | 2026 |
| 17 | [arXiv 2604.14220](https://arxiv.org/pdf/2604.14220) | SUPERSEDES edges in enterprise-document KG (preprint, 2026-04) | 2026-04 |
| 18 | [RAID search results](https://quire.io/guide/raid-log/) | RAID fields (snippet) | n/d |
| 19 | [Decision log search results](https://elium.com/templates/decision-log) | decision fields (snippet) | n/d |
| 20 | [Campaign brief search results](https://smartsheet.com/sites/default/files/2025-01/IC-Integrated-Marketing-Campaign-Brief-Template-12312_PDF.pdf) | brief sections (snippet) | 2025-01 |
| 21 | [SBVR vocabulary entry structure, BRCommunity](https://brcommunity.com/articles.php?id=b288) | entry parts (snippet) | n/d |

### 3. Findings

#### 3.1 Enterprise knowledge graph products (Q1)
- Atlassian lists object types as "Calendar event, Comment, Conversation, Design, Document, Message, Space, Video; Branch, Build, Commit, Deployment, Pull request, Repository, Software service; Project, Work item; Customer organization, Deal". Only a subset is indexed for Rovo Search and Chat: Build, Deployment, Software service and the Test types are not. [primary: 10; secondary: 11]
- Atlassian says object types are "standardized categories that unify and relate objects from different products". Connectors map external items onto them, for example Asana tasks to Work item. Document types are generic. [primary: 10]
- Glean describes its graph as three pillars, Content (documents, messages, tickets), People (identity, roles, teams) and Activity (edits, comments, clicks). The docs publish no finer type list. [secondary: 14]
- Viva Topics types were Project, Event, Organization, Location, Product, Creative work and Field of study, with 150+ finer types and custom topic types planned. A topic page held a description, people, and related sites, files and pages. [secondary: 15]
- Viva Topics was retired 2025-02-22. AI-generated topic pages were removed. Published topic pages became ordinary SharePoint pages. [primary: 13]
- Zep's default types: the May 2025 blog lists three: User, Preference and Procedure ("a multi-step instruction for agent behavior"). A search summary listed six (User, Assistant, Preference, Location, Event, Object). The Graphiti custom-types page defines no defaults. These conflict and are unresolved. Both lists are agent-memory oriented, not enterprise-document oriented. [primary: 12; secondary]
- A Neo4j-style meeting graph (CocoIndex tutorial, not Neo4j-owned) uses Meeting (date, notes), Person and Task. Edges are ATTENDED (`is_organizer`), DECIDED (Meeting to Task) and ASSIGNED_TO. Person names are deduplicated by embedding plus LLM confirmation. [primary: 16] Note that it treats decisions and actions as one Task type.
- Not read: Notion, Google Workspace, Slack, Writer, Microsoft Graph's own resource list, and any Neo4j-owned post. See section 7.

#### 3.2 Business glossaries (Q2)
- Purview term fields:
  - Name, definition (description limit 10,000 characters in the UI), owners, parent term, acronyms, resources and custom attributes. Bulk CSV adds experts.
  - Relationships are synonyms and related terms, which can span governance domains. A term can also link to data products, assets, columns and critical data elements.
  - Lifecycle is Draft, then Published, then Expired. Stewards edit only in Draft. Duplicate names are allowed with a warning. [primary: 7]
- Atlan CSV columns: Name, Type (term or category), Description, Business name (alias), Categories, User owners, Group owners, Certification (Verified, Draft or Deprecated), Certification message, Tags. [primary: 8]
- Atlan's docs separately mention Synonyms, Antonyms and Translated terms. [secondary, search snippet]
- SKOS: seven note properties (note, definition, scopeNote, example, changeNote, historyNote, editorialNote). Labels are prefLabel (one per language), altLabel and hiddenLabel. Relations are broader, narrower and related. [primary: 9]
- SBVR vocabulary entries consist of primary representation, definition, source, examples and notes, and synonyms. [secondary: 21]
- Collibra: the Glossary domain type holds the asset types Business Term, Acronym and KPI. The attribute list was not retrievable. [secondary]
- Unity Catalog now has Glossary (preview, June 2026 per a third-party summary) and "Pages" for authoritative concept definitions. Glossary field-level docs were not retrievable. [primary: 5; secondary]
- No glossary product I read stores a term's definition as a dated, multi-version value. They hold one current definition plus status. Definition history is an audit-log feature at most. [inferred from 7 and 8; not verified for Collibra or Alation]

#### 3.3 Metric definitions (Q3)
- dbt: required `name` and `type`. Optional `description`, `label`, `filter` and `config` (meta, group, tags, enabled). Ratio needs `numerator` and `denominator`. Derived needs `expr` and `input_metrics`. Cumulative has `window`, `grain_to_date` and `period_agg`. Simple has `agg`, `expr` and `agg_time_dimension`. Conversion has entity, base and conversion metrics. [primary: 1]
- Databricks metric view YAML: `version`, `source`, `filter`, `fields` (dimensions), `measures` (name and expr), `joins`. Window measures, display_name, synonyms, format and materialization also exist. Metric views are Unity Catalog securable objects. [primary: 4, 5]
- Snowflake semantic view clauses: TABLES (with synonyms and comments), RELATIONSHIPS, FACTS, DIMENSIONS, METRICS (including NON ADDITIVE BY). It also has AI_VERIFIED_QUERIES (question, timestamp, verifier, SQL). Verification is the only trust or lifecycle signal I saw. [primary: 6]
- OSI/Ossie: metric fields are as in the summary. The spec itself states no owner, lifecycle or certification fields. It is at version 0.2.0.dev0. [primary: 3]
- Not read: Cube, LookML. Version, effective date and owner are absent from every metric spec I read. [primary]
- Recommendation [inferred]:
  - Model `Metric` as an entity (identity key: normalised name plus domain). Model each formula as a `MetricDefinition` claim, linked to `Metric`, holding `expression_verbatim` (source text, untranslated), `metric_kind` enum (simple, ratio, derived, cumulative, conversion), `numerator_text`, `denominator_text`, `filter_text`, `grain`, `time_dimension_text`, `unit`, `valid_from`, `valid_to` and `status` enum. Evidence and source come from the engine.
  - Do not parse formulas into an AST at extraction time. The numerator, denominator and filter are optional text attributes that follow the dbt vocabulary and help later export.
  - Two conflicting definitions then become two claims with separate time and source. This matches the "return every version" requirement. This avoids both a version-per-entity design and overwriting.
  - A `Definition` claim for glossary terms (non-metric) can reuse the same shape through a single `Definition` claim type. Metric would be a subtype or `kind` of a `Term`/`Concept` anchor.

#### 3.4 Decisions, actions, risks (Q4)
- RAID templates: type (Risk/Assumption/Issue/Dependency), id, description and impact, probability (1-5), impact (1-5), score, owner, response (Avoid/Reduce/Transfer/Accept), action, status (Open/Mitigating/Monitoring/Closed/Deferred), date raised, due or review date. A risk may become an issue and an assumption may be validated. [secondary: 18]
- Decision logs: title, id, date, decision maker or body, category, status (proposed/approved/superseded/reversed), impact, context, options considered, decision and rationale, owner and timeline, expected outcome, review date. [secondary: 19]
- Not read: RACI and OKR field lists, meeting-minute templates.
- Graph worthiness [inferred]:
  - Types: `Decision` and `ActionItem` (already drafted), plus one `Risk` claim type with `kind` enum (risk, assumption, issue, dependency).
  - Attributes: probability, impact, score, response, category, review date, expected outcome and rationale (verbatim text).
  - RACI is a role enum on an owner relation, not its own type.
  - OKR is a Project or goal with KPI-target attributes, not a new type. Not verified.

#### 3.5 Campaigns (Q5)
- Brief contents are objective (SMART goals), target audience, messaging/USP, channels and tactics, budget, KPIs (MQL, SQL, CPA), timeline and milestones, assets. [secondary: 20 and search summary]
- Campaign is a generic marketing construct. Segment, channel, offer and KPI vocabulary is industry-specific, so keep them as attributes and enums in the pack or a domain-specific pack. [inferred]

#### 3.6 Modelling advice (Q6)
- Versioning: a directed SUPERSEDES edge from newer to older document or clause, with timestamp and version as node attributes. Temporal graphs give relationships validity periods so a new fact supersedes without deleting history. [secondary: 17 (preprint, snippet and shallow read)]
- Cascading amendments across versions make multi-hop retrieval hard. [secondary: 17]
- Ownership: Purview, Atlan and Atlassian all treat owner as a person or group reference with a role, not a free-text string. Atlan separates user and group owners. [primary: 7, 8]
- Hubs: dense enterprise graphs where common entities connect thousands of records produce noisy context. Mitigations are hop limits, relationship allow-lists, node-type constraints, time filters, minimum evidence and per-entity caps. [secondary, search summary; no primary read]
- Duplicates (case, abbreviations, language) remain unresolved by string-match merging in GraphRAG engines. [secondary]
- What went wrong in practice: Viva Topics, a Topic-centred AI graph, was retired and its AI-only topic pages deleted. [primary: 13] The reason is not stated in the doc and the failure cause is not established.

### 4. Proposed `enterprise-docs` changes
1. Add `MetricDefinition` claim (or `Definition` claim with a `subject_kind` enum) under a `Metric` entity or a `Concept` of kind metric. Why: no glossary or semantic-layer spec versions definitions over time (3.2, 3.3). Source: 1, 3, 7.
2. Add `Metric` as a `Concept` subtype/enum value (`metric`, `business_term`, `kpi`) rather than a new top-level type. Why: Collibra separates Business Term, Acronym and KPI, but the differences are enum-worthy. Source: Collibra snippet [secondary].
3. Claim attributes: `expression_verbatim`, `metric_kind` (simple, ratio, derived, cumulative, conversion), `numerator_text`, `denominator_text`, `filter_text`, `grain`, `time_dimension_text`, `unit`, `status`. Why: dbt vocabulary. Source: 1.
4. `status` enum on definitions and Policy/Procedure: draft, published, deprecated/expired. Why: Purview and Atlan lifecycles. Source: 7, 8. Do not add "certification" as a separate field in v1. Keep it as one `status` value (verified/certified), because the graph records what documents say.
5. Terms: add acronym and synonym as attributes (`acronym`, `alias`) on the entity and a `RELATED_TO` or `BROADER_THAN` relation only if needed. Why: Purview, Atlan and SKOS all treat them as first-class. Source: 7, 8, 9. Prefer attributes over new relation types.
6. Add one `Risk` claim type with `kind` enum (risk, assumption, issue, dependency), owner, status, due, `severity_text`. Why: RAID shares the same core fields. Source: 18 [secondary].
7. `Decision`: add `supersedes_decision` as an existing `SUPERSEDES` relation reuse; attributes decision_date, rationale_verbatim, options_text, decided_by. Why: decision-log templates. Source: 19 [secondary].
8. `ActionItem`: keep. Add `status` enum (open, in_progress, done, blocked, cancelled) [inferred]. Keep it a claim rather than an entity. The CocoIndex model treats it as Task with ASSIGNED_TO. Source: 16.
9. `Policy` and `Procedure`: keep, but add `version_label`, `effective_from` and `effective_to` as attributes, and reuse `SUPERSEDES` between versions. Why: SUPERSEDES edge in enterprise-document graphs. Source: 17 [secondary, shallow]. No vendor list publishes Policy or Procedure, so these rest on the user's own domain need [inferred].
10. Ownership: model as relation `OWNER_OF` with a `role` enum (owner, steward, expert, approver, contributor, responsible, accountable). Why: Purview owner/expert and the RACI roles. Source: 7 [primary]; RACI [inferred].
11. Add `Campaign` as a generic type (or an enum value on `Project`) with attributes objective, period, budget_text, channel (enum), segment_text, offer_text and `KpiTarget` as claim with metric, target_value and period. Prefer an enum on `Project` unless campaigns need their own relations. Source: 20 [secondary].
12. Do not add Topic. Use `Concept` only for defined business terms. Why: Viva Topics retirement and hub-noise advice (3.6). Source: 13.
13. Add `Team`, `committee`, `department` as is. Atlassian's "Space" and "Customer organization" suggest organisation categories such as `customer`, `partner`; consider adding to `OrgCategory`. Source: 10.

### 5. Competency questions
These are drawn from product capabilities and templates, so they are [inferred] phrasing of what the products support, not verbatim user queries.
1. What is the current definition and formula of metric X, and what was it on date D?
2. Do two documents define metric X differently? Which is newer, and which source says what?
3. Which documents define or mention business term X, and what are its synonyms and acronym?
4. Who owns policy or procedure X, and who approved it?
5. Which version of policy X applies on date D, and what superseded it?
6. Which procedures implement policy X?
7. What decisions were made in meetings about project X, by whom, and are they still in force?
8. What action items from meeting X are open, who owns them, and what is overdue?
9. What risks and dependencies are open for project X and who owns them?
10. What was the objective, segment, channel, budget and offer of campaign X, and what KPI targets applied?
11. Which systems does procedure X use?
12. Which requirements apply to department Y?

### 6. Licenses
- W3C SKOS: W3C document licence, copyright 2009 MIT/ERCIM/Keio, with liability and trademark conditions. Reusing the property names is routine, but copying text needs checking. [primary: 9; licence detail not read in full]
- OSI / Apache Ossie: Apache-2.0, incubating. [primary: 2]
- OMG SBVR: licence not checked. Do not copy text. Reusing concept names is likely fine but unverified.
- DAMA-DMBOK: not checked. Copyrighted book. Do not copy definitions.
- Vendor field lists (Purview, Atlan, dbt, Databricks, Snowflake, Atlassian): documentation. I used field names as facts only and did not check licences. Do not copy text.
- dbt MetricFlow code is Apache-2.0 [inferred from knowledge, not read this session].

### 7. Gaps
- Not read: Glean (beyond a snippet), Notion, Google Workspace, Slack, Writer, Microsoft Graph resource types, any Neo4j-owned blog, Cube, LookML, DAMA-DMBOK, SBVR text itself, Collibra attribute list, Alation, Unity Catalog glossary fields.
- Atlassian `object-types/overview` page 404 on fetch (path may have moved). The list came from the object-types page and search results.
- Zep defaults conflict (3 vs 6).
- RAID, decision, campaign, RACI, OKR and meeting-minutes findings are from search snippets of template vendors, not owning standards. OKR and RACI were not covered.
- arXiv 2604.14220 is a preprint and the fetch returned little schema detail.
- Hub-noise and "what went wrong" evidence is thin. No practitioner postmortem was found beyond Viva Topics retirement (cause unstated).
- Industry-genericity of "campaign" is [inferred].
