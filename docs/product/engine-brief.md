# Core engine — design brief (2026-10-05)

Status: reviewed by the author on 2026-10-05. It answers open question 1
of the [SDK platform brief](sdk-platform-brief.md): the core engine
design and the exact store-protocol methods. The author took the
recommended option of every question E1–E14 except E10, where they chose
the plan estimate only. On E8 they added the glossary and the
known-entity hints. The answers are recorded at the end.
On 2026-10-06 the author settled entity identity
([ADR 0016](../decisions/0016-identify-entities-by-scope-keys-and-vetoes.md)):
entities are identified by scope, keys and vetoes, not by name. The data
model, the card, extraction, validation, resolution, versions, retrieval
output, the store protocol, configuration and tests follow it.
Nothing is built yet, and every number in this brief is a starting value
to tune on the synthetic corpus.

Settled inputs, designed in here:
- the per-document consistency floor and the run record
  ([ADR 0008](../decisions/0008-build-databricks-and-open-branches-in-parallel.md));
- `one_at_a_time` supersession with conflict flags, `where` endpoint
  constraints and `TEXT_IN` links
  ([domain-packs.md](domain-packs.md#how-the-pack-is-used));
- opt-in query strategies and `retrieve_multi_step()`
  ([ADR 0010](../decisions/0010-offer-query-strategies-as-opt-in-benchmarked-options.md));
- the two community layers
  ([ADR 0011](../decisions/0011-cluster-by-default-and-make-community-reports-opt-in.md));
- diacritics kept, numbers normalized by the model and checked by code
  (brief principle 5).

Evidence: the 13 inputs in
[graphrag-research.md](../reference/graphrag-research.md#inputs-for-the-engine-brief-inferred)
and the engine comparison in
[graphrag-engines.md](../reference/graphrag-engines.md).

**Goal** — The engine turns parsed documents into a graph of entities,
events, relations and facts. Every item carries a checked verbatim quote,
and every dated version is kept. `retrieve()` answers with ranked chunks
plus the facts they support, and makes no LLM call by default. The engine
reaches storage and models only through protocols, so the same code runs
on Postgres, Neo4j and Delta.

## Running example

A synthetic corpus of a fictional company, Công ty CP Alpha. The
sections below refer to it.

| Doc | Content | Dates stated in the text |
|---|---|---|
| D1, "Quy chế công tác phí", version 1 (vi, DOCX) | "Mức phụ cấp lưu trú là 2.000.000 VND/ngày." Owner: Phòng Tài chính. | issued 2025-01-10, effective 2025-02-01 |
| D2, "Quy chế công tác phí", version 2 (vi, PDF) | "Mức phụ cấp lưu trú là 2.500.000 VND/ngày." "Quy chế này thay thế phiên bản 1." | issued 2026-01-05, effective 2026-01-15 |
| D3, minutes of the Risk Committee (vi, DOCX) | Chunk 1: date, chair, attendees. Chunk 3: the committee approves version 2; Nguyễn Văn An updates the expense system by 2026-01-10. | meeting 2025-12-20 |
| D4, "KPI handbook 2025" (en, PDF) | "Churn rate = customers lost in the period ÷ customers at the start of the period." | issued 2025-03-01 |
| D5, "Quy chế công tác phí", version 1, of Công ty CP Beta (vi, DOCX) | "Mức phụ cấp lưu trú là 800.000 VND/ngày." Owner: Beta's Phòng Tài chính. | issued 2026-03-01, effective 2026-03-15 |

The letterheads name the issuers: Công ty CP Alpha for D1–D4, and
Công ty CP Beta for D5. D5 is the identity test: its policy, its unit and
its limit must stay apart from Alpha's, although every name is the same
(§2.6).

Questions:
- **Q-a** "Phụ cấp lưu trú theo quy chế công tác phí vào tháng 3/2025 là
  bao nhiêu?" Expected: 2.000.000 VND/ngày from D1, with D2's
  2.500.000 VND/ngày as the later version.
- **Q-b** "Ai thông qua quy chế công tác phí phiên bản 2, khi nào?"
  Expected: a Decision made in the 2025-12-20 meeting by the Risk
  Committee, from D3.
- **Q-c** "How is churn rate calculated?" Expected: the Definition from D4.

The graph after indexing (excerpt):

```
(Policy v2) ──SUPERSEDES──► (Policy v1) ◄──OWNER_OF── (Organization Phòng Tài chính)
    ▲    ▲ source                ▲ source
    │  [Requirement r2]       [Requirement r1]
    │   "2.500.000 VND/ngày"   "2.000.000 VND/ngày"
    │   from 2026-01-15        from 2025-02-01, closed 2026-01-15
    │   current                superseded
    │        └──── metric ──► (Metric phụ cấp lưu trú) ◄── metric ───┘
    │ about
(Decision d1) ──made_in──► (Meeting m1, 2025-12-20)
    └──decided_by──► (Organization Ủy ban Rủi ro)

( ) node: entity or event    [ ] fact    every item also links to its chunk and quote
```

## 1. Data model

### Kinds and identity

| Kind | Graph shape | Identity | One row per | Example |
|---|---|---|---|---|
| Document | node | source path relative to the index root | file | D1 |
| Chunk | node, `PART_OF` its document | document and position | span of the document text | D1, chunk 3 |
| Entity | node, typed by the pack | type, scope, keys and vetoes from the pack; resolved (§2.6) | thing in the world | Policy v1 |
| Event | node, typed by the pack, roles to entities and events | type and pack `identity` (§2.7, E2) | happening | Meeting m1 |
| Relation | typed edge, entity → entity | none: one row per statement per chunk (E1) | source chunk | `OWNER_OF` Phòng Tài chính → Policy v1 |
| Fact | node, typed by the pack, roles to entities and events | none: one row per statement per chunk | source chunk | Requirement r1 |
| Mention | `MENTIONED_IN`, entity → chunk | entity and chunk | chunk | "Quy chế công tác phí" in D1, chunk 1 |
| Evidence | columns on relation and fact rows; `SUPPORTED_BY` rows for events | item and chunk | chunk | the quote of r1 |

Relations and facts carry their evidence on the row: `doc_id`,
`chunk_id`, `quote`, `quote_start`, `quote_end`. Events have many evidence
rows, because several chunks and documents can describe one happening.

Why one row per chunk for relations and facts:
- Deleting a document removes rows by `doc_id`. No reference counts.
- Each row keeps its own quote, time and status.
- Agreeing sources stay visible as separate rows. Retrieval groups them.

### Engine-owned fields

The fields listed in [domain-packs.md](domain-packs.md#pack-format) stay.
This brief adds:
- `version_key` and `closed_at`, for versions (§3);
- `valid_source`: `text`, or `document` when the time is inherited from
  the document card (§3.1);
- `quote_match`: `exact` or `fuzzy` (§2.5);
- `observed_at_source`: `caller`, `card` or `ingest` (§2.2);
- `scope_path`, `scope_source` and `label` on entities (§2.6);
- `issuer` on documents (§2.2), which fact version keys can name (§3.2);
- `name_norm`, `alias_norm`, `text_norm`: matching columns (§7);
- `run_id` on every row.

`confidence` is 1.0 for an exact quote match and 0.7 for a fuzzy one. The
LLM's own confidence is not used.

### Logical tables

This is the layout on Postgres and Delta. The Neo4j mapping follows.

| Table | Columns | Notes |
|---|---|---|
| `documents` | doc_id, source_uri, content_hash, pipeline_hash, title, code, version_label, doc_date, effective_from, effective_to, language, issuer_id, issuer_source, subject_type, subject_id, observed_at_source, run_id | written last in a document's unit |
| `chunks` | chunk_id, doc_id, ordinal, start, end, text, text_norm, heading_path, page_start, page_end, chunk_hash, tokens, language | `text` is the document's NFC text from `start` to `end` |
| `entities` | entity_id, type, name, name_norm, label, scope_path, scope_source, attributes (JSON), identity (JSON of normalized key values), degree | canonical record; `scope_path` lists entity ids from the outermost scope in, and its last id is the direct scope |
| `aliases` | entity_id, alias, alias_norm, language, origin (`surface`, `former_name`, `translation`, `glossary`, `reviewer`) | exact-match index on `alias_norm` |
| `attribute_sources` | entity_id, attribute, value, value_norm, doc_id, chunk_id, quote, quote_start, quote_end, observed_at | one row per value per source; `entities.attributes` shows the newest value by `observed_at` |
| `identity_blocks` | entity_id, candidate_id, attribute (`scope` or a veto), value, candidate_value, quote, candidate_quote, doc_id, chunk_id, run_id | a candidate that resolution kept apart (§2.6) |
| `mentions` | entity_id, chunk_id, doc_id, surface, start, end | surface form verbatim in the chunk |
| `relations` | relation_id, type, subject_id, object_id, attributes, valid_from, valid_to, valid_precision, valid_source, observed_at, recorded_at, status, closed_at, version_key, doc_id, chunk_id, quote, quote_start, quote_end, quote_match, confidence, pack, pack_version, run_id | |
| `events` | event_id, type, attributes, identity, valid_from, valid_to, valid_precision, pack, pack_version, run_id | |
| `event_evidence` | event_id, doc_id, chunk_id, quote, quote_start, quote_end, quote_match, observed_at | an event left without evidence is deleted |
| `facts` | as `relations`, without subject_id and object_id | |
| `roles` | owner_id, owner_kind (`event`, `fact`), role, target_id, target_kind (`entity`, `event`), doc_id, chunk_id | one row per source, so deletes stay row-local |
| `text_in` | entity_id, doc_id, attribute | derived (§2.9) |
| `same_as` | entity_a, entity_b, score, origin (`embedding`, `llm_unsure`, `ambiguous_alias`, `ambiguous_key`, `ambiguous_version`, `same_name`), status (`candidate`, `confirmed`, `rejected`) | a traversable link, not a merge |
| `resolution_decisions` | pair_key, verdict, method, model, run_id | caches LLM verdicts; a reviewer verdict wins |
| `extraction_cache` | cache_key, payload (JSON), created_at | validated extraction per chunk (§2.5) |
| `runs` | run_id, status, started_at, finished_at, stage hashes, prompt versions, pack stamp, stats (JSON) | drops, counts, LLM calls and tokens live in `stats` |
| `communities`, `community_members`, `community_reports` | §8 | M5 |

Postgres keeps one schema per index. Neo4j Community has one user
database, so every node carries `index_id`, and uniqueness constraints are
composite: `index_id` plus the key.

Neo4j mapping:
- **Nodes:** `Document`, `Chunk`, `Entity` plus the pack type as a second
  label, `Event` plus its type, `Fact` plus its type, `Alias`,
  `AttributeSource`, `IdentityBlock`, `Run`, `ExtractionCache`,
  `Community`.
- **Edges:** `PART_OF`; `MENTIONED_IN {surface}`; typed relation edges
  that carry the row's columns, so two sources give two parallel edges;
  `ROLE {name, doc_id, chunk_id}`; `SUPPORTED_BY {quote, …}` from events
  and facts to chunks; `ALIAS_OF`; `TEXT_IN`; `SAME_AS`; `IN_COMMUNITY`.
- A fact also keeps its evidence columns as node properties, since it has
  exactly one source.

### Ids and hashes

Every id is a deterministic SHA-256 hash. Nothing uses `uuid4`, so a
replay after a crash writes the same ids.

| Id | Hash of |
|---|---|
| `doc_id` | normalized source path relative to the index root |
| `content_hash` | the file's bytes |
| `chunk_hash` | the chunk's NFC text |
| `chunk_id` | doc_id, ordinal, chunk_hash |
| `entity_id` | type, direct scope, and the first key value the creating mention has, else its normalized name; stable after. When that hash already belongs to another entity, such as a same-named entity that a veto keeps apart, a counter is added until the hash is free. Plan order makes the result repeatable. |
| `event_id` | type and the identity values at creation |
| `relation_id`, `fact_id` | chunk_id, type, resolved endpoint or role ids, normalized attributes, valid time |
| `version_key` | type, plus the resolved ids and values the pack names (§3.2) |
| `cache_key` | chunk_hash, the context header text, the glossary entries sent with the chunk, the extraction stage hash (prompt version, model, merged pack hash without the glossary) |

Moving or renaming a file is a delete plus an add. The extraction cache
makes the add cheap when the context header is unchanged.

The known-entity hints of §2.4 are left out of `cache_key` on purpose.
They depend on the graph, so including them would re-extract unchanged
chunks after every run and break brief success criterion 2.

## 2. Index pipeline

```
scan(path) → plan ──► apply(plan)
                        │ take the writer lease, open a run record
                        ├─ deleted documents: cascade and recompute versions (§2.12)
                        └─ new and changed documents, pipelined:
   parse → NFC → document card → chunk → embed chunks
     → resolve the card's issuer and subject
     → per chunk: cache hit, or glossary entries + known-entity hints → extract (1 LLM call)
       → validate → cache
     → resolve entities and events (store lookups + run overlay; LLM confirms the fuzzy residue)
     → versions and supersession → TEXT_IN → entity vectors
     → write the document as one atomic unit
   after all documents: degrees → clustering (communities extra) → reports (opt-in)
   close the run record, release the lease
```

Parsing, extraction and embedding run concurrently, up to
`max_concurrency` model calls. Resolution and writes run one document at
a time in plan order, so a later document resolves against an earlier
one. The engine keeps an in-memory overlay of the entities and events
written in the current run, so a backend that batches writes (Delta) needs
no read-your-writes.

### 2.1 Parse and normalize
- Parsers come from `ingest`
  ([ADR 0009](../decisions/0009-reuse-permissive-libraries-behind-adapters.md))
  and return text plus structure: pages, headings, tables.
- The engine stores the NFC form of the parsed text, and offsets refer to
  it. Tone-mark placement and casefolding apply only to the `_norm`
  columns (§7).
- Each chunk gets a language tag (`vi`, `en` or `mixed`) from a heuristic
  on Vietnamese letters. No dependency.

### 2.2 Document card (E5)
Fields: title, code, version_label, doc_date (the issue date),
effective_from, effective_to, language, kind, issuer and subject_type.
- `issuer` is the organization named in the letterhead or signature
  block.
- `subject_type` is the pack entity type the document itself is, such as
  `Policy` for D1, or none for minutes.

Each field is taken from the first source that has it:
1. caller metadata, as a dict per document or a sidecar file;
2. the LLM card: one call per document over its first two pages, each
   field with a verbatim quote checked like any quote;
3. profile patterns, such as a regex for document codes;
4. file metadata, for the title only. File dates are never used as
   document dates.

`observed_at` falls back to the ingest date. The card feeds the
extraction context header, `observed_at`, the inherited valid time
(§3.1) and `document_link` matching (§2.9). This answers the
`document_link` part of open question 4 in
[domain-packs.md](domain-packs.md#open-questions).

The issuer and the subject resolve before any chunk
([ADR 0016](../decisions/0016-identify-entities-by-scope-keys-and-vetoes.md)):
1. **Issuer.** The issuer comes from caller metadata (a name or an
   entity id), else the card, else the profile's `default_issuer`, and
   `issuer_source` records which. It resolves as an `Organization` by the
   rules of §2.6. Entities whose pack scope inherits from the document
   take it as their scope when the text names none. Facts take it as
   their `issuer` (§3.2).
2. **Subject.** When `subject_type` is set, the card's title, code,
   version_label, issue date and issuer describe the document's own
   entity. It resolves next and enters every chunk's prompt as hint `K0`
   (§2.4). In D2, "Quy chế này" then attaches to Policy v2.

### 2.3 Chunk (E7)
- semchunk inside our wrapper: target 500 tokens, maximum 800, no
  overlap.
- A chunk never crosses a top-level heading. A table stays whole when it
  fits. Otherwise it splits by rows, and the header row goes into each
  piece's context header, not into its text, so `text[start:end] ==
  chunk` still holds.
- Each chunk keeps its heading path, such as "Chương II > Điều 5".
- Tokens are counted with `EmbeddingModel.count_tokens` when the model
  offers it. Otherwise characters ÷ 3 serves as a conservative estimate
  [inferred: check on the synthetic corpus].
- The embedding input is the context header plus the chunk text:
  "Quy chế công tác phí · Chương II > Điều 5", a blank line, then the
  text. The stored text stays verbatim. The recipe is part of the
  embedding stage hash.

### 2.4 Extract (E6)
- One LLM call per chunk returns entities, relations, events and facts
  together. Entities carry local ids (`e1`, `e2`) that the other items
  point to. A pointer to a missing id drops the item.
- Prompt layout: the static part first (instructions, compiled pack,
  examples), then the context header (card fields, heading path, document
  date for resolving relative dates), then the glossary entries and
  known-entity hints below, then the chunk. The static prefix lets
  provider prompt caching cut cost.
- **Glossary** (proposed by the author on 2026-10-05). A user pack can
  list naming rules for the organization's own names and acronyms:

  ```yaml
  glossary:
    - name: Công ty CP Alpha
      type: Organization
      aliases: [Alpha, ALP]
      note: The parent company only, never its subsidiaries.
    - name: phụ cấp lưu trú
      type: Metric
      aliases: [PCLT]
  ```

  - The prompt gets only the entries whose name or an alias occurs in the
    chunk after normalization, so a glossary of hundreds of terms adds a
    few lines per chunk.
  - Extraction still returns the surface form exactly as written
    (`PCLT`). The glossary name becomes the canonical name, and the
    surface form an alias. The model never expands an acronym into the
    quote.
  - Resolution uses the glossary in step 1 of §2.6, and branch A of
    retrieval looks up glossary aliases too, so an agent asking about
    `PCLT` finds `phụ cấp lưu trú`.
  - A glossary change marks for re-index only the documents whose text
    contains an added, changed or removed name or alias. Their other
    chunks still hit the cache.
  - Shipped packs carry no glossary. An adopter's terms stay in its
    private user pack.
- **Known-entity hints** (proposed by the author on 2026-10-05). Before
  extraction, the engine finds existing entities the chunk may mention and
  lists up to 15 of them in the prompt, each with a local key (`K1`), type,
  name and aliases:
  - entities whose alias occurs in the chunk, by exact n-gram lookup (the
    branch A method of §4.1);
  - entities whose name vector is close to the chunk vector (top 10,
    cosine ≥ 0.6, a starting value that the M1 trial measures).

  Each hint shows its label (§2.6), so two same-named entities look
  different in the prompt. Key `K0` is reserved for the document's
  subject (§2.2), and the card's issuer is always listed.

  An extracted entity may answer `ref: K1`, meaning "this mention is that
  known entity". Code checks every `ref` before trusting it:
  - the surface form occurs in the chunk;
  - the type equals the hinted entity's type;
  - the hinted entity passes the scope and veto filter of §2.6;
  - the digit guard of §2.6 passes.

  A failed check drops the `ref`, and the entity goes through normal
  resolution.

  Two rules keep runs reproducible and edits cheap:
  - Hints come only from rows written before the current run started.
    Documents extracted in parallel therefore see the same graph, whatever
    their timing. Duplicates within one run are left to resolution.
  - Hints are not part of `cache_key` (§1). A cached extraction is reused
    as it is, and a `ref` to an entity that no longer exists falls back to
    normal resolution. A full rebuild can therefore differ slightly from a
    graph built up over many runs.

  Hints help most in incremental runs. On a first run the graph is empty,
  so only the glossary helps, and resolution does the rest. Hints add
  about 300–450 input tokens per chunk, outside the cached prefix.
- Each item gives its type, attributes (verbatim text and typed value),
  valid time with precision when the text states one, and a verbatim
  quote.
- **Entities follow the pack's identity fields**
  ([ADR 0016](../decisions/0016-identify-entities-by-scope-keys-and-vetoes.md)).
  The prompt section for each entity type is compiled from the pack. It
  says what the type is, what its scope means (the issuer, the employer,
  the owner), which attributes identify it, which relations corroborate a
  name, and which attributes only describe it. Each entity returns:
  - `surface`: the words exactly as written;
  - `is_name`: `false` for a phrase that only refers to a name, such as
    "Quy chế này", "phiên bản 1" or "Công ty";
  - `name`: the full name in the text's language, never translated, which
    for a non-name phrase is the name it refers to;
  - `translation`: the name in the graph language, only when it differs;
  - `scope`: a local id or hint key, only when the text says whose thing it
    is. Otherwise it stays empty and §2.6 fills it, so the model never
    guesses;
  - `former_names`: earlier names the text states ("trước đây là …"), each
    with its quote;
  - `attributes`: each one as `{value, quote}`, only when the text states
    it.

  ```json
  {"id": "e2", "type": "Policy", "surface": "phiên bản 1", "is_name": false,
   "name": "Quy chế công tác phí",
   "attributes": {"version_label": {"value": "1", "quote": "phiên bản 1"}}}
  ```

  The translation becomes an alias with origin `translation`, and former
  names become aliases with origin `former_name`.
- One pass by default. When the compiled schema prompt passes a token
  threshold, extraction splits into passes by type group (domain-packs
  step 1). The M1 trial run sets the threshold and answers open questions
  2 and 3 in [domain-packs.md](domain-packs.md#open-questions).
- Temperature 0. Parse failures follow the `llm` layer's
  structured-output strategy.

### 2.5 Validate
The domain-packs drop reasons apply, plus these checks:
- **Quote.** The quote must occur in the chunk after NFC and whitespace
  collapse. The stored quote is the chunk's own text at the offsets found.
  If that fails, a match that ignores diacritics and punctuation is tried.
  On success the item is kept with `quote_match: fuzzy`. Otherwise it is
  dropped as `QUOTE_NOT_IN_CHUNK`.
- **Surface form.** An entity's surface form must occur in the chunk under
  the same rule.
- **Value.** `BAD_VALUE` when a typed value does not match the digits in
  its quote after unit words are applied (nghìn, triệu, tỷ, thousand,
  million, billion).
- **Entity attributes.** Each `{value, quote}` needs its quote in the
  chunk, or in the context header for card values. Dates must equal a
  date written in the quote. Codes, tax IDs, LEIs, ISINs, employee IDs and
  emails must equal their quote under the attribute's comparator (§2.6).
  A value that fails is removed and counted as `BAD_VALUE`, and the entity
  stays. A missing veto value never blocks a merge, so a misread date
  costs at most a split, never a wrong merge. The demo planted a contract
  end date of 2026-12-30 against "gia hạn đến 31/12/2026", and this check
  removed it.
- **Names.** A `name` found neither in the chunk nor in its context
  header is kept only as a fuzzy-match hint, as a translation is.
- **Non-names.** The surface of a mention with `is_name: false` never
  becomes an alias. The mention resolves through its `ref`, or through
  its `name` and keys like any other. Without a `ref`, and with a `name`
  that fails the check above, it is dropped as `NOT_A_NAME`, so no entity
  is ever named "quy chế này".
- **Time.** A date outside 1900 to 30 years after today is removed from
  the item and counted. The item stays.

Counts per type and reason go into the run record, with up to five
examples per reason. The cache stores the validated output before
resolution, so resolution can run again without an LLM call.

### 2.6 Resolve entities (E8)
Names are labels, not identity
([ADR 0016](../decisions/0016-identify-entities-by-scope-keys-and-vetoes.md)).
Each entity type in the pack declares:
- `scope`: whose thing it is;
- `identity`: keys, with the scope in front;
- `vetoes`: attributes that block a merge when they differ;
- `names`: how the name counts.

The format is in [domain-packs.md](domain-packs.md#identity-fields). The
draft packs give:

| Type | Scope | Keys | Vetoes | Name rule |
|---|---|---|---|---|
| Organization, company categories | none | registration_id · lei (finance) | registration_id, established_on, lei | key; a short name with no legal form, such as `Alpha`, never merges by name and goes to step 4 |
| Organization, unit categories | the parent organization, as a path | registration_id (a branch's 13-digit code) | registration_id, established_on | key within the parent |
| Person | employer | [scope, employee_id] · email | employee_id | evidence: needs a shared unit or title |
| Policy, Procedure | issuer | [scope, code] · [scope, title, version_label] · [scope, title, issued_on] | code, version_label, issued_on | versioned |
| Work | issuer | [scope, code]; the code alone when it names its issuer (`39/2016/TT-NHNN`) | code, issued_on | key within the issuer |
| Project | owner | [scope, code] | code | key within the owner |
| System | owner | none | none | key within the owner |
| Product | provider | none | none | key within the provider |
| Place | parent place | none | none | key within the parent |
| Instrument | none | isin · [exchange, ticker] while listed | isin | none |
| Metric, Concept | none | none | none | key: the term is the node, and each source's meaning is a `Definition` fact |

For Policy, Procedure and Work, `title` in a key is the entity's name.

**Scope.**
- Sources, in order:
  1. the text: the extraction's `scope`, or for a person, the
     organization of the unit they are a `MEMBER_OF` in the same chunk;
  2. caller metadata;
  3. the card's issuer (§2.2);
  4. the profile's `default_issuer`;
  5. otherwise unknown.

  Sources 2–4 apply only to types whose pack scope inherits from the
  document. `enterprise-docs` turns that on for internal documents.
  `core` leaves it off, since a news article's publisher is not the
  employer of every person it names. `scope_source` records the source.
- A scope is a path, such as Công ty CP Alpha › Chi nhánh Hà Nội. Two
  scopes conflict when neither path is a prefix of the other. A path from
  the text must match exactly. A path inherited from the document is
  coarse for an organization unit: "somewhere in Alpha" matches a unit
  under any Alpha branch.
- With an unknown scope, candidates of every scope stay. The mention
  merges only when exactly one candidate passes, and the run record
  counts these merges.
- An `Organization` takes a scope only when its category is a unit
  category: core's `unit`, plus enterprise-docs' department, team,
  committee, business unit and branch. With no category, a name that
  starts with a legal form from `resolution.legal_forms` is a company. Any
  other name is a unit when the text names its parent, and has an unknown
  scope otherwise. It never inherits the document's issuer, so
  "Ngân hàng Nhà nước" is never placed inside Alpha.
- A code that names its issuer, by `resolution.self_scoped_codes`,
  gives its mention no inherited scope, and its key skips the scope check
  (step 2). "Thông tư 39/2016/TT-NHNN" cited by Alpha and by Beta is one
  Work.

**Order.** Within one type, the first step that decides wins:
0. **Filter.** Drop candidates whose scope conflicts, and candidates with
   a veto attribute known on both sides with different values under its
   comparator. A missing value is not a different one. Each dropped
   candidate that shares the mention's name or a key value becomes an
   `identity_blocks` row with the attribute, both values and both quotes.
   Every later step sees only the candidates left, except the global keys
   of step 2.
1. **Glossary and checked hints.** A surface form that matches a glossary
   name or alias of the same type resolves to the entity with that
   glossary name, created on first mention with the glossary aliases. A
   match with another type is not applied and is counted in the run
   record, since a product can share a name with a company. A `ref` that
   passed the checks of §2.4 attaches to its hinted entity. Neither needs
   an LLM confirmation, since the glossary is the user's own rule and the
   extraction call already judged the `ref` in context. A glossary entity
   or hinted entity removed by the filter is not applied and is counted.
2. **Keys,** in pack order, on values under each attribute's comparator.
   Key values come only from the text, never from a translation. One hit
   merges. Two or more hits give a new entity with `same_as` links
   (`ambiguous_key`) to each.
   - A key made only of `unique: global` attributes (tax ID, LEI, ISIN,
     email), or a self-scoped code, is checked against every candidate
     that passed the vetoes, whatever its scope. The value alone proves
     identity. An email that names Trần Thị Bình of Alpha in a Beta
     document still finds her, although the inherited scope says Beta.
   - On a merge, the entity keeps its own scope. The mention's inherited
     scope is dropped and recorded in the run record.
3. **Name rule,** on the normalized name, former names, and aliases with
   origin `surface`, `former_name`, `glossary` or `reviewer`. Translated
   names never count here.
   - `key`: one hit merges. Two or more give a new entity with `same_as`
     (`ambiguous_alias`).
   - `evidence`: the mention merges with the one candidate that shares a
     unit (`MEMBER_OF`) or a title (`HOLDS_POSITION`) stated in the same
     chunk. A candidate with no unit or title known on either side goes to
     step 4 with its profile. When every candidate's unit and title
     differ, the mention becomes a new entity with `same_as`
     (`same_name`). A Nguyễn Văn An named as head of Phòng Tài chính
     merges with the one already known in that unit. A Chuyên viên of
     Phòng Công nghệ thông tin with the same name becomes a second person.
   - `versioned`: one hit merges. When several versions hit and the
     mention states no code, version or issue date, it resolves to the
     version in force on the citing document's date: the newest whose
     `version_start` (effective_from, else issued_on) is on or before that
     date. Otherwise the mention becomes a new entity with `same_as`
     (`ambiguous_version`). A notice dated 2025-06-20 that cites
     "quy chế công tác phí" with no version resolves to version 1, and
     one dated 2026-03-02 resolves to version 2.
   - `none`: skipped.
4. **Fuzzy candidates:** name trigram similarity ≥ 0.5 from the graph
   store, or name-vector cosine ≥ 0.85 from the vector store, top 5.
   - A digit guard rejects a pair whose names differ in a digit (`QC-05`
     and `QC-06`, `Q3` and `Q4`).
   - Company names are compared without their legal form, since
     "Công ty CP" is shared boilerplate.
   - A listwise LLM call confirms the rest. It sees the mention (surface,
     name, attributes with quotes, scope label, one quote) and its
     candidates (label, key attributes, aliases, one quote each). It
     answers with one candidate, `none` or `unsure`. Calls are batched per
     document, with at most `resolution.confirm_batch` (50) candidate
     pairs per call, so a long document makes several calls.
   - A chosen candidate merges, and the surface form becomes an alias.
     `unsure` gives a new entity with `same_as` (`llm_unsure`). `none`
     gives a new entity.
5. Otherwise a new entity.

**Within a document,** the card's issuer resolves first, then the subject
(`K0`), then each chunk's entities in reference order: a mention's scope
target and unit resolve before the mention.

In D5:
- Beta's policy: the filter removes Alpha's versions 1 and 2 on scope
  and records two blocks. No candidate is left, so a new Policy is
  created, labelled "Quy chế công tác phí · v1 (Công ty CP Beta)".
- Beta's "Phòng Tài chính": the category is department and the scope is
  inherited from Beta, so Alpha's unit is blocked and a new one is made.
- Beta's limit gets issuer Beta, so it never joins the version group of
  Alpha's limits (§3.2).

Notes:
- **Labels.** An entity's `label` is its name, plus "· v2" for a
  versioned type, plus the names on its scope path in parentheses:
  "Phòng Tài chính (Công ty CP Beta)". Hints, retrieval output and agent
  tools show it.
- **Attribute values.** Each value goes to `attribute_sources` with its
  quote, document and `observed_at`. `entities.attributes` shows the
  newest, so a policy whose end date was extended shows the new date and
  keeps both sources.
- **Run record.** It counts unknown-scope merges, blocks per attribute,
  ambiguous keys and names, and LLM verdicts.
- Cross-language pairs, such as `Phòng Tài chính` and
  `Finance Department`, reach step 4 through the name vector, since
  trigrams cannot match them.
- Verdicts are cached in `resolution_decisions`. The key is the mention's
  type, direct scope, normalized name and key values, plus the candidate
  id, so a verdict for Alpha's unit never applies to Beta's. A re-run
  repeats no call. A reviewer verdict overrides a cached one.
- The cost per document depends on its new entities, never on the graph
  size: every lookup is an indexed store query.
- Merges are reversible. Mentions keep their surface forms and the cache
  keeps the raw extraction, so splitting an entity re-resolves its
  mentions from the cache.
- Merging two entities that already exist is a reviewer action and comes
  after v1. Resolution only attaches new extractions.

### 2.7 Resolve events (E2)
1. **Within a document,** two events of the same type merge when their
   times are equal or one is missing, and no role has two disjoint,
   non-empty sets of targets. In D3, the meeting in chunk 1 (date, chair,
   attendees) and the `made_in` meeting in chunk 3 (date only) become one
   Meeting. Two decisions of the same day about different policies stay
   apart, because their `about` targets differ.
2. **Across documents,** events merge only on a full match of the type's
   `identity`, a pack field that now applies to events. A type without
   `identity` never merges across documents.

There is no fuzzy or LLM event resolution in v1. Proposed identities for
the shipped event types:

| Type | `identity` |
|---|---|
| `Event` (core) | `[time, title]` |
| `Meeting` | `[time, title]`, `[time, chair]` |
| `Decision` | `[time, about, decided_by]` |
| `Acquisition` | `[time, buyer, target]` |
| `RatingAction` | `[time, rater, rated, scope]` |
| `CorporateAction` | `[time, issuer, kind]` |

An acquisition announced in March and completed in June gives two events,
because the times differ. Linking deal stages waits for a user who needs
it.

### 2.8 Versions and supersession
Computed in the engine (§3). The pipeline loads the version groups a
document touches, computes statuses, and passes status changes for other
documents' rows with the write.

Governed documents are one entity per version, linked by `SUPERSEDES`.
A mention with no version resolves to the version in force on the citing
date (§2.6, step 3).

### 2.9 TEXT_IN
- Writing a document compares its card code and title with the link
  attributes of entities whose type sets `document_link`.
- Writing an entity compares its link attributes with document codes and
  titles.
- An exact match after normalization adds a `text_in` row, with two more
  conditions: the entity's scope must not conflict with the document's
  issuer, and when both state a `version_label`, the labels must be equal.
  Policy v1 then links to D1 only, and Beta's policy never links to
  Alpha's files.
- Deleting either side removes the row.

### 2.10 Write
One `write_documents` call takes a batch, and each document in it is
atomic (§6). Inside a document's unit:
1. delete the previous version's rows: chunks, mentions, relations, facts,
   roles, event evidence, attribute sources, identity blocks;
2. insert the new rows, and upsert entities, aliases and events;
3. apply status changes to other documents' rows (§3);
4. delete orphans: entities with no mention, role or relation, and events
   with no evidence;
5. write the document row last. On Delta it doubles as the commit marker.

A large document is still one unit. Its rows are never split across
transactions, since a half-written document would break the
per-document floor.

**Vectors.** When the graph store also writes the vectors (§6.3), they go
inside the document's unit. Otherwise the engine upserts the document's
vectors first, writes the graph, then deletes the previous version's
vectors. A crash in between leaves extra vectors whose chunk ids are not
in the graph. Retrieval drops them, and the next run overwrites them.

### 2.11 After all documents
- Recompute `degree` for the entities the run touched: the number of
  distinct neighbour entities reached through relation and role rows. The
  hub penalty reads it. Counting rows would make an entity look like a
  hub just because one statement repeats across many chunks.
- Cluster, and write reports when they are on (§8).
- Close the run record as `completed`, `completed_with_errors`,
  `interrupted` or `failed`.

### 2.12 Edit and delete
- An edit writes the new version (§2.10). Unchanged chunks hit the cache.
- A delete reads the document's version keys first, computes the statuses
  of the remaining rows, then calls `delete_documents`, atomic per
  document. Orphans go as in §2.10.
- Facts that the deleted document superseded become current again,
  because statuses are recomputed. Graphiti's `remove_episode` misses this
  ([pitfalls](../reference/graphrag-engines.md#pitfalls-to-avoid)).

### 2.13 Cost (E10, decided)
- The plan estimates LLM calls and tokens per stage: the document card
  (one per document), extraction (passes × chunks not in the cache, with
  the hint tokens of §2.4), resolution (one listwise call per 50
  candidate pairs, for documents with fuzzy candidates or unconfirmed
  person names), chunk questions and reports when they are on. Money appears only when the profile gives model prices.
- The estimate is the only control (author, 2026-10-05). A run never stops
  on its own for cost. Progress and the run record show actual calls and
  tokens beside the estimate, and the caller can interrupt a run; the
  documents already written stay, and `apply` resumes.
- Nothing picks chunks by centrality to save cost, because unique
  decisions sit in the least central chunks (KET-RAG pitfall).
- Expected cost: about 1.1 LLM calls per chunk, counting the card and the
  confirmations. HippoRAG 2 uses about 2.

## 3. Time and versions

### 3.1 Time fields
- `valid_from`, `valid_to`, `valid_precision` (day, month, year) come
  from the text only. The model resolves relative dates ("từ quý sau")
  against the document date in the context header.
- An item with no stated time inherits the card's `effective_from` and
  `effective_to` when the document states them, with
  `valid_source: document`. It never inherits the issue date or a file
  date. In the example, r1 gets 2025-02-01 from D1.
- `observed_at` is the card's doc_date, else the ingest date.
- `recorded_at` is the write time.

### 3.2 Version groups (E3)
Two mechanisms put rows into version groups:
- **Relations** with `cardinality: one_at_a_time` (settled on
  2026-10-04): the group is the type plus the listed endpoints.
- **Facts** with `version_key`, a new pack field. It names the roles and
  attributes that make two facts statements of the same thing:

  | Fact type | `version_key` |
  |---|---|
  | `Definition` | `[issuer, term, scope]` |
  | `ReportedFigure` | `[metric, subject, period, basis]`; `finance` adds `segment`, `consolidation`, `period_kind` |
  | `Requirement` | `[issuer, metric, applies_to, condition]` |
  | `ActionItem`, `Statement` | none |

  A fact type without `version_key` has no versions, so each of its facts
  is current.
- **`issuer`** is engine-owned
  ([ADR 0016](../decisions/0016-identify-entities-by-scope-keys-and-vetoes.md)).
  It is the scope of the entity in the fact's `source` role when there is
  one, else the document's issuer (§2.2). A version key that names it
  never puts two organizations' statements in one group.
  `ReportedFigure` needs no issuer, since its `subject` already says whose
  figure it is, and two sources reporting one company's figure should
  meet in one group.

Inside a group:
- Rows order by `valid_from`, falling back to `observed_at`.
- Rows with equal normalized content are one version backed by several
  sources.
- The newest version is `current`. Older versions are `superseded`, and
  `closed_at` is set to the next version's start when they state no end.
- Two different contents with the same start are both `conflicting`, and
  the run record lists them.
- Nothing is deleted. Statuses are stored as of today and recomputed for
  every group a write or delete touches.

In the example, r1 and r2 share the version key (Requirement, issuer
Công ty CP Alpha, metric "phụ cấp lưu trú", no `applies_to`, no
`condition`). r2 starts later, so r1 is `superseded` with `closed_at`
2026-01-15. D5's limit has issuer Công ty CP Beta, so it starts its own
group and r2 stays current.

### 3.3 As-of and ranges (E9)
- `as_of=D`: an item applies at D when its valid interval contains D,
  with `closed_at` as the end when no end is stated. An item with no valid
  time applies when `observed_at ≤ D`.
- In each version group, the version current at D is the newest one that
  applies at D. The store pre-filters out items that start after D, and
  the engine picks the versions, because supersession ordering lives in
  the engine.
- `as_of` returns only the versions current at D unless
  `all_versions=True`, which adds the others with their flags.
- `during=(start, end)` returns items whose interval overlaps the range.
- With no time argument, every version comes back, grouped by version key,
  with the newest flagged.
- Chunks are never filtered by date: a 2026 document can answer a
  question about 2025.

For Q-a with `as_of=2025-03-15`: r1 applies (2025-02-01, closed
2026-01-15), and r2 starts later. The result holds r1 as current at D.

## 4. Retrieval

### 4.1 `retrieve()`

```
query (+ strategies: variants, time filter, entity hints; all off by default)
 ├─ A. entity linking: alias n-grams (exact) · entity vectors · fuzzy names for hints
 └─ B. hybrid chunks: vector top 20 + full text top 20 → RRF → entities they mention
        ▼
 seeds: A ∪ B, top 10, hub-penalized
        ▼
 expand ≤ 2 hops: relations, events and facts, filtered by type, time and status;
                  ≤ 20 neighbours and ≤ 50 items per entity per hop
        ▼
 candidate chunks = evidence chunks of the subgraph ∪ B's chunks
        ▼
 rank: RRF(cosine to the query, full-text rank, graph score) → optional reranker → top_k
        ▼
 items ranked by their best evidence chunk; versions grouped; output
```

1. **Strategies** ([ADR 0010](../decisions/0010-offer-query-strategies-as-opt-in-benchmarked-options.md)).
   Each enabled strategy returns query variants, a time filter or entity
   hints. The original query always runs. Each variant runs branches A
   and B, and their lists fuse through RRF. Without the temporal
   strategy, `as_of` comes from the caller, usually the agent's tool call.
2. **Branch A, no LLM.**
   - Every word n-gram of the normalized query, up to ten words, is
     looked up exactly in `aliases`. This catches multi-syllable
     Vietnamese names such as `phụ cấp lưu trú`. Vietnamese words are
     syllables, so a name such as "Ngân hàng Thương mại Cổ phần Alpha"
     takes seven, and six was too short.
   - Entity-vector search with the query vector: k = 10, cosine ≥ 0.75.
   - Fuzzy name search only for entity hints from a strategy. A whole
     query is too noisy for it.
3. **Branch B.** Vector search over chunks (top 20) and full-text search
   over `text_norm` (top 20), fused by RRF with k = 60. Entities mentioned
   in those chunks become seeds. An entity's score is the sum of its
   chunks' RRF scores ÷ log₂(2 + its mentions in the whole index), which
   damps hubs.
4. **Seeds.** The union of A and B, scores normalized per branch, top 10.
   An entity-type filter applies here when the caller gives one.
5. **Expansion.** One `hop` call per hop (E14). It follows relations to
   neighbour entities, events and facts through roles, and `same_as`
   links at half weight. Filters: item types, the time pre-filter,
   statuses.
   - Per entity per hop: at most 20 neighbours and 50 items, in store
     order (support, then `observed_at` descending, then id).
   - A reached item scores its source entity's score × 0.5 per extra hop
     ÷ log₂(2 + that entity's degree). Types listed in the pack's
     `hub_penalty` get the penalty even as seeds.
   - Hop 2 starts from the 20 best entities reached in hop 1.
6. **Candidate chunks:** the evidence chunks of the reached items, plus
   branch B's chunks. A seed's mention chunks are not added, since a hub
   has too many.
7. **Ranking.** Three ranked lists over the candidates: the exact cosine
   of each chunk vector to the query (vectors fetched by id), branch B's
   full-text rank, and the graph score (the sum of the scores of items
   whose evidence is the chunk). RRF with k = 60 fuses them. An optional
   reranker reorders the top 30. The first `top_k` (8) are returned.
8. **Items.** Each reached item ranks by RRF of its best evidence chunk's
   cosine and its graph score. The top `max_items` (30) are returned
   (E11). Each one carries its quote, so an item whose chunk is outside
   the top 8 is still evidence. It is flagged
   `in_returned_chunks: false`.
9. **Versions.** Items are grouped by version key. With `as_of`, the
   version current at D is marked; otherwise the newest.
10. **Router** (M4, off by default). `rules` sends the query to branch B
    alone when branch A finds no entity scoring ≥ 0.8 and no time filter
    applies. `confidence` runs branch B first, and adds the graph path
    only when B's top scores sit close together.

Q-a: the n-grams `phụ cấp lưu trú` and `quy chế công tác phí` link the
Metric and both Policy versions. Branch B finds the sentence in D1 and D2.
Hop 1 reaches r1 and r2 through the `metric` and `source` roles, and
`SUPERSEDES` between the versions. With `as_of=2025-03-15`, r1 comes first
with its quote from D1.

### 4.2 Output

`RetrievalResult` holds:
- `chunks`: chunk id, document id, title and date, text, offsets, pages,
  heading path, score, and the lists that found it (`vector`, `text`,
  `graph`);
- `entities`: id, type, name, label, scope (id and label), key
  attributes, aliases, `same_as` links, score, seed flag and how it was
  linked. Two same-named entities differ by label;
- `items`: relations, events and facts, each with id, kind, type, subject
  and object or roles, attributes (verbatim and typed), valid time,
  `observed_at`, status, the newest or current-at-D flag, version key,
  evidence (chunk id, document id, quote, offsets), `in_returned_chunks`
  and score;
- `stamp`: pack name, version and hash; index run id and stage hashes;
- `trace`: time per stage, candidate counts, strategies run, the router's
  choice, LLM calls and tokens. The benchmark reads it.

### 4.3 Other retrieval methods
- **`answer(query, …)`** runs `retrieve()`, then one LLM call. The
  context lists chunks with ids, and items with their validity rendered as
  `[valid 2025-02-01 → 2026-01-15, superseded]`, as post-graph-rag does.
  The answer cites chunk ids. It returns the answer, the citations and the
  retrieval result.
- **`retrieve_multi_step(query, max_steps=3)`** (M5). Step 1 runs
  `retrieve()`. An LLM then reads the question, the earlier sub-queries
  and a compact view of the results (top items with quotes, chunk
  snippets), and returns either `done` or the next sub-query with an
  optional `as_of` and type filter. Results fuse across steps by RRF. The
  trace lists every step and its LLM calls.
- **`retrieve_global(query, level, budget)`** (M5, opt-in): the
  map-reduce over community reports of
  [ADR 0011](../decisions/0011-cluster-by-default-and-make-community-reports-opt-in.md).

## 5. Methods for agents (E12)

Engine methods. `as_tools()` and the MCP server expose them in M3, with
type arguments as pack-generated enums.

| Tool | Returns |
|---|---|
| `retrieve(query, as_of?, during?, types?, top_k?)` | the `RetrievalResult` of §4.2 |
| `describe_schema(detail, name?)` | the merged pack summary ([domain-packs.md](domain-packs.md#how-the-pack-is-used)) |
| `find_entities(name, type?)` | candidates with id, type, name, label, scope, aliases and mention count; "quy chế công tác phí" returns Alpha's two versions and Beta's version 1, each labelled |
| `get_entity(id, as_of?, item_types?, page?)` | the entity, its label and scope, its aliases, its attributes with their sources, its `same_as` links, and its relations, events and facts with evidence, versions grouped: "everything about X" |
| `get_neighbors(id, relation_types?, as_of?)` | neighbour entities and the relations between them |
| `get_sources(ids)` | chunks with text, document title, date and offsets, for item or chunk ids |

No tool runs raw Cypher or SQL. The `describe_schema` summary has a
default budget of 4,000 tokens, which settles the other part of open
question 4 in [domain-packs.md](domain-packs.md#open-questions).

## 6. Protocols

Rules for every protocol:
- **Synchronous methods (E13).** The engine runs model calls and the two
  retrieval branches in a bounded thread pool. `serving` can add async
  wrappers later. The MCP server calls the engine from worker threads.
- **Batched.** Every read takes a list of ids or keys. No store call sits
  inside a loop over unbounded data.
- **Engine operations, not query languages**
  ([ADR 0008](../decisions/0008-build-databricks-and-open-branches-in-parallel.md)).
  Expansion is one `hop` per call, and the engine composes hops (E14).
- **Plain records.** Records are frozen dataclasses, since the protocols
  module imports only the standard library.
- **Capabilities, checked at config load.** A pairing that cannot work
  raises `ConfigError` before any query.
- **Prompts arrive resolved.** `serving` resolves prompts from the
  registry ([ADR 0004](../decisions/0004-sdk-owned-versioning.md)) and
  passes `ResolvedPrompt(name, version, text)` to the engine, which never
  talks to MLflow.

### 6.1 `GraphStore`

```python
class GraphStore(Protocol):
    # Setup, writer lease, runs
    def ensure_schema(self, schema: StoreSchema) -> None: ...
        # tables, indexes, constraints; on Neo4j also per-type DDL for the pack's relation types
    def acquire_writer(self, owner: str, ttl_s: int) -> WriterLease: ...
        # raises WriterBusyError while another writer holds the index
    def begin_run(self, run: RunRecord) -> None: ...
    def finish_run(self, run_id: str, status: RunStatus, stats: RunStats) -> None: ...
    def get_runs(self, limit: int) -> list[RunRecord]: ...

    # Change detection and caches
    def document_states(self) -> dict[str, DocumentState]: ...
        # doc_id -> content_hash, pipeline_hash, run_id
    def get_cached_extractions(self, keys: Sequence[str]) -> dict[str, bytes]: ...
    def put_cached_extractions(self, entries: Mapping[str, bytes]) -> None: ...
    def get_resolution_decisions(self, pair_keys: Sequence[str]) -> dict[str, Verdict]: ...
    def put_resolution_decisions(self, decisions: Sequence[Verdict]) -> None: ...

    # Resolution and linking
    def find_by_identity(self, keys: Sequence[IdentityKey]) -> list[EntityRecord]: ...
        # each key carries a scope id, or ANY_SCOPE for an unknown scope or a self-scoped code
    def find_events(self, keys: Sequence[IdentityKey]) -> list[EventRecord]: ...
    def match_names(self, names_norm: Sequence[str], types: Sequence[str] | None,
                    exclude_run: str | None = None) -> list[NameMatch]: ...    # exact
        # exclude_run hides rows written by the current run, for the hints of §2.4
        # matches carry scope and alias origin; the engine filters scope, vetoes and origins
    def search_names(self, text_norm: str, types: Sequence[str] | None,
                     limit: int, min_similarity: float) -> list[NameMatch]: ...  # fuzzy
    def match_document_links(self, keys: Sequence[DocumentLinkKey]) -> list[TextInLink]: ...

    # Versions
    def get_version_groups(self, version_keys: Sequence[str]) -> list[ItemRecord]: ...
    def get_document_version_keys(self, doc_ids: Sequence[str]) -> dict[str, list[str]]: ...

    # Writes: each document is atomic
    def write_documents(self, writes: Sequence[DocumentWrite]) -> None: ...
    def delete_documents(self, deletes: Sequence[DocumentDelete]) -> None: ...
    def refresh_degrees(self, entity_ids: Sequence[str]) -> None: ...

    # Retrieval reads
    def entities_in_chunks(self, chunk_ids: Sequence[str]) -> list[Mention]: ...
    def hop(self, entity_ids: Sequence[str], spec: HopSpec) -> HopResult: ...
    def get_entities(self, entity_ids: Sequence[str]) -> list[EntityRecord]: ...
    def get_items(self, item_ids: Sequence[str]) -> list[ItemRecord]: ...
        # with roles and evidence
    def get_chunks(self, chunk_ids: Sequence[str]) -> list[ChunkRecord]: ...
    def get_documents(self, doc_ids: Sequence[str]) -> list[DocumentRecord]: ...

    # Communities (M5)
    def cluster_edges(self) -> Iterator[WeightedEdge]: ...
    def replace_communities(self, run_id: str, communities: Sequence[Community]) -> None: ...
    def get_communities(self, level: int | None) -> list[Community]: ...
    def write_reports(self, reports: Sequence[CommunityReport]) -> None: ...
    def delete_reports(self, community_ids: Sequence[str]) -> None: ...
    def get_reports(self, level: int) -> list[CommunityReport]: ...
```

Main records:

| Record | Fields |
|---|---|
| `DocumentWrite` | document, chunks, entities, aliases, attribute_sources, identity_blocks, mentions, relations, events, event_evidence, facts, roles, text_in, same_as, status_changes, vectors (only when the graph store writes them), run_id |
| `DocumentDelete` | doc_id, status_changes, run_id |
| `StatusChange` | item_id, status, closed_at |
| `IdentityKey` | type, scope id or `ANY_SCOPE`, key names, normalized values |
| `EntityRecord` | entity_id, type, name, label, scope_path, scope_source, attributes, identity, aliases with origins, degree |
| `NameMatch` | entity_id, type, scope_path, matched alias, alias origin, score |
| `HopSpec` | relation_types, item_types, statuses, starts_before (as-of pre-filter), overlaps (range), include_same_as, neighbour_limit, item_limit |
| `HopResult` | edges (from, to, via kind, via type, item ids, support, degree of `to`) and items (item id, kind, type, entity id, role, chunk id) |
| `ItemRecord` | item id, kind, type, subject and object or roles, attributes, time fields, status, closed_at, version_key, evidence list, pack, pack_version |

### 6.2 `VectorStore`

Chunk full-text search sits here, not in `GraphStore`, because it lives
with the vectors on every pairing: Postgres full text beside pgvector,
the Neo4j full-text index beside its vector index, AI Search hybrid beside
its vectors.

```python
Collection = Literal["chunks", "entities", "chunk_questions"]

class VectorStore(Protocol):
    capabilities: VectorCapabilities
        # text_search, fused_hybrid_only (AI Search), eventual_sync, max_dimensions
    def ensure_collections(self, spec: VectorSpec) -> None: ...
        # embedding model id and dimensions per collection
    def upsert(self, collection: Collection, records: Sequence[VectorRecord]) -> None: ...
    def delete(self, collection: Collection, ids: Sequence[str]) -> None: ...
    def delete_documents(self, collection: Collection, doc_ids: Sequence[str]) -> None: ...
    def search(self, collection: Collection, vectors: Sequence[Sequence[float]], k: int,
               where: VectorFilter | None) -> list[list[Hit]]: ...
        # batched: one call for every chunk of a document (hints) or every query variant
    def search_text(self, collection: Collection, text_norm: str, k: int,
                    where: VectorFilter | None) -> list[Hit]: ...
    def get_vectors(self, collection: Collection, ids: Sequence[str]) -> dict[str, list[float]]: ...
```

- `VectorRecord`: id, vector, doc_id, type, language, run_id, text_norm
  (for full text). `VectorFilter` can exclude a run, for the hints of
  §2.4.
- Entity vectors embed "type: name (alias; alias; …)". They are
  re-embedded when an alias is added.
- AI Search fuses ANN and BM25 itself, so branch B gets one fused list
  there instead of two.

### 6.3 Which store writes the vectors

`serving` decides when it composes the stores:

| Pairing | Vectors written by | Atomic with the graph |
|---|---|---|
| Postgres graph + pgvector in the same database | the graph store, inside the document's transaction | yes |
| Neo4j graph + Neo4j vector index | the graph store, inside the document's transaction | yes |
| Delta graph + AI Search | the graph store, as columns of the Delta tables that the Delta Sync index reads | no; the SDK reports or waits for sync lag |
| Any other pairing, such as Neo4j graph + pgvector | the vector store, before the graph write (§2.10) | no; extra vectors are harmless |

### 6.4 Model protocols

```python
class ChatModel(Protocol):
    model_id: str
    def generate(self, messages: Sequence[Message], *, schema: Mapping | None = None,
                 max_output_tokens: int | None = None,
                 temperature: float = 0.0) -> ChatResult: ...
        # ChatResult: text, data (parsed JSON or None), usage (input, cached input, output tokens)

class EmbeddingModel(Protocol):
    model_id: str
    dimensions: int
    max_input_tokens: int
    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...
    def embed_queries(self, texts: Sequence[str]) -> list[list[float]]: ...
        # separate calls, so models with query and passage prefixes work
    def count_tokens(self, text: str) -> int | None: ...

class Reranker(Protocol):  # optional, `rerank` extra
    def rerank(self, query: str, texts: Sequence[str]) -> list[float]: ...
```

The structured-output strategy stays in the `llm` layer. The engine still
validates `data` against the compiled schema, since it is LLM output.

### 6.5 Backend notes

| Operation | Postgres | Neo4j | Delta |
|---|---|---|---|
| `hop` | `LATERAL … LIMIT` per entity | `CALL (e) { … LIMIT }` per entity | in-process cache, refreshed on table version change |
| `match_names` | B-tree on `alias_norm` | range index on `Alias.alias_norm` | dictionary in the cache |
| `search_names` | `pg_trgm` similarity | Lucene fuzzy query on a full-text index of names | trigram index in the cache |
| `search_text` | `simple` full text on `text_norm` | full-text index with `standard-no-stop-words` on `text_norm` | AI Search hybrid (fused) |
| document unit | one transaction | one transaction | batch plus `run_id` marker (open question 2 spike) |
| writer lease | advisory lock | lease node | lease row with a conditional update (spike) |

Fuzzy scores differ between `pg_trgm` and Lucene, so the contract suite
asserts candidate sets, never scores
([ADR 0008](../decisions/0008-build-databricks-and-open-branches-in-parallel.md)).

## 7. Text and language

- **`norm(text)`:** NFC, then the tone-mark placement table (`hoà` →
  `hòa`), then casefold, then whitespace collapse. Diacritics and `đ` are
  kept, so `lãi`, `lại` and `lai` stay distinct. It fills `name_norm`,
  `alias_norm` and `text_norm`, and normalizes query n-grams. The original
  text is never overwritten.
- **Full text** indexes `text_norm` with no stemming and no stop words.
  The tokens are syllables, not words. The golden set measures whether a
  segmenter would help
  ([supporting-libraries.md](../reference/supporting-libraries.md#vietnamese-text-processing)).
- **Graph language:** the profile's `language`, default `en`, sets the
  language of canonical names. Every surface form stays an alias.
- **Cross-language:** name vectors propose pairs, the LLM confirms or
  leaves a `same_as` candidate (§2.6). The bilingual query variant is an
  opt-in strategy.
- **Queries without diacritics:** "phu cap luu tru" does not match
  `phụ cấp lưu trú` exactly. The calling agent or the opt-in diacritic
  restoration strategy adds them back. Vector search still matches
  loosely.

## 8. Communities (M5)

[ADR 0011](../decisions/0011-cluster-by-default-and-make-community-reports-opt-in.md)
left these details to this brief:
- **Clustering graph.** Entities are the nodes. The weight between two
  entities is the number of relation rows between them plus the number of
  events and facts in which both hold roles. Every status counts, since a
  past owner is still related to the topic. Confirmed `same_as` links
  count, candidates do not.
- **Algorithm.** Hierarchical Leiden from graspologic-native with a fixed
  seed and `max_cluster_size` 10, Microsoft's default and the setting
  behind ADR 0011's cost figures. Every level is kept. The cap is an
  index-time parameter, but changing it calls no LLM; it only rewrites
  reports.
- **Warm start.** Each run starts from the previous run's level-0
  membership (`starting_communities`). New entities start unassigned.
  `communities.warm_start: false` gives a cold run that does not depend on
  history.
- **Matching across runs.** Per level, a new community takes the id of
  the previous community with the highest member Jaccard, when that value
  is at least 0.5 and the choice is mutual. Otherwise it gets a new id.
- **Report rewrites,** when reports are on: the members changed, or a hash
  over the community's internal items changed (relation, fact and event
  ids with their statuses).
- **Report fields:** title, summary and findings. Each finding cites item
  ids, and through them chunks. There is no importance rating, since
  global search scores points per query. Reports use the profile's
  `language`.
- **Storage:** `communities` (community_id, level, parent_id, size,
  member_hash, content_hash, run_id), `community_members` (community_id,
  entity_id) and `community_reports` (community_id, title, summary,
  findings, model, prompt version, content_hash, run_id). On Neo4j:
  `Community` nodes with `IN_COMMUNITY` and `CHILD_OF` edges.

## 9. Configuration added

Index-time parameters
([ADR 0005](../decisions/0005-index-time-vs-query-time-parameters.md)):

| Parameter | Default | Stage |
|---|---|---|
| `chunking.target_tokens`, `max_tokens`, `overlap` | 500, 800, 0 | chunk |
| `embedding.context_header` | on | embed |
| `document_card.llm` | on | extract |
| `document_card.patterns` | none | extract |
| `extraction.passes` | `auto` | extract |
| `extraction.hints`, `hint_limit`, `hint_cosine_min` | on, 15, 0.6 (measured in M1) | extract |
| `glossary` (user pack) | none | extract, per chunk |
| `default_issuer` (profile) | none | card, resolve |
| `resolution.llm_confirm` | on | resolve |
| `resolution.trigram_min`, `name_cosine_min`, `candidates` | 0.5, 0.85, 5 | resolve |
| `resolution.confirm_batch` | 50 candidate pairs per call | resolve |
| `resolution.legal_forms` | Vietnamese and English legal forms, such as "Công ty CP", "Công ty TNHH", "Ngân hàng TMCP", "Tập đoàn", "JSC", "Ltd" | resolve |
| `resolution.self_scoped_codes` | Vietnamese legal-document suffixes that name the issuer, such as `/QH15`, `/NĐ-CP`, `-NHNN`, `-BTC`, `-TTg` | resolve |
| `language` (graph language) | `en` | extract |
| `communities.max_cluster_size`, `warm_start` | 10, on | cluster |
| `reports.enabled`, `model`, `prompt` | off | reports |
| `chunk_questions` (HyPE) | off | extract |

The hint settings enter the extraction stage hash like any prompt change,
while the hinted entities themselves stay out of `cache_key` (§1). The
glossary is part of the user pack and works per chunk through
`cache_key`. `default_issuer`, the legal forms and the self-scoped codes
change which entities merge, so they enter the resolution stage hash.
`max_concurrency` (8) changes no graph content, so
ADR 0005 classes it with the query-time parameters, and it enters no
hash.

Query-time parameters:

| Parameter | Default |
|---|---|
| `retrieval.top_k`, `max_items` | 8, 30 |
| `retrieval.seed_limit` | 10 |
| `retrieval.hops`, `neighbour_limit`, `item_limit` | 2, 20, 50 |
| `retrieval.branch_k` (vector and full text) | 20 |
| `retrieval.entity_cosine_min` | 0.75 |
| `retrieval.rrf_k` | 60 |
| `retrieval.same_as_weight`, `hop_decay` | 0.5, 0.5 |
| `retrieval.reranker`, `rerank_top` | none, 30 |
| `retrieval.step4` | `provenance` (M5 adds `ppr`, `propagation`) |
| `strategies`, `router` | none, off |
| `answer.model`, `answer.prompt` | from the profile |
| `global.level`, `global.token_budget` | M5 |

## 10. Testing

- Engine unit tests run on an in-memory reference `GraphStore` and
  `VectorStore` kept in `tests/`, with fake models. The contract suite
  also runs on the reference store, so it pins the expected behaviour
  before any backend exists.
- The running example becomes a synthetic fixture with golden results for
  Q-a, Q-b and Q-c. Deleting D2 must make r1 current again.
- The synthetic corpus plants duplicate names (acronyms, both languages,
  short forms) to measure the precision of `ref` hints and of LLM
  confirmations, and the duplicates left after each stage.
- **Identity**
  ([ADR 0016](../decisions/0016-identify-entities-by-scope-keys-and-vetoes.md)):
  - The 60 synthetic cases of the
    [identity suite](../research/2026-10-05-entity-identity-criteria.md#9-the-suite)
    become engine unit tests: 30 pairs that must stay apart and 30 that
    must merge. The snapshot has 57; three were added on 2026-10-06 for
    the global keys and the company registration veto. CI requires zero
    wrong merges.
  - Each shipped pack's identity cases run in CI under the same rule
    ([domain-packs.md](domain-packs.md#identity-fields)).
  - Indexing D5 must leave Beta's policy, unit and limit apart from
    Alpha's, and r2 current.
  - The M1 labelled sample reports wrong merges and wrong splits
    separately, with merges weighted higher.
- Contract-suite cases added by this brief, beyond the list in ADR 0008:
  - replaying `write_documents` changes no counts;
  - per-document atomicity after a run killed mid-way;
  - orphan cleanup after edit and delete;
  - status changes applied in the same unit as the write;
  - `hop` caps per entity;
  - exact alias match after tone-mark normalization;
  - `exclude_run` hides the current run's rows from name and vector
    lookups;
  - `find_by_identity` with a scope and with `ANY_SCOPE`;
  - attribute sources and identity blocks deleted with their document;
  - `text_in` added and removed;
  - extraction-cache round trip;
  - writer lease exclusion;
  - the as-of pre-filter;
  - recovery from a crash between the vector write and the graph write.

## 11. Milestones

| Part | Milestone |
|---|---|
| Data model, ids, pipeline, document card, glossary and known-entity hints, extraction, validation, entity resolution by scope, keys and vetoes with its identity tests, event resolution, versions, `TEXT_IN`, edit and delete, run record, cost estimate | M1 |
| `retrieve()` with branches A and B, provenance step 4, `answer()`, the engine methods of §5 | M1 |
| `GraphStore` and `VectorStore` on Postgres and Neo4j, reference store, contract suite | M1 |
| Delta and AI Search backends, Lakebase | M2 |
| Tools and MCP over the §5 methods | M3 |
| Query strategies, chunk questions, router | M4 |
| `retrieve_multi_step()`, PPR and score propagation for step 4, the subgraph vector query, communities, reports, `retrieve_global()` | M5 |
| Reviewer merge and split of entities | after v1 |

## 12. What changed elsewhere

Done on 2026-10-05, after the author's review:
- [domain-packs.md](domain-packs.md) and the draft packs: `identity` on
  events, `version_key` on facts, a `glossary` section for user packs,
  the new engine-owned fields.
- [ARCHITECTURE.md](../../ARCHITECTURE.md): the `Reranker` protocol, and
  full-text search under `VectorStore`.
- ADRs for the decisions behind E1
  ([0012](../decisions/0012-store-relations-and-facts-as-one-row-per-chunk.md)),
  E2–E3 ([0013](../decisions/0013-resolve-events-by-identity-and-version-facts-in-the-engine.md)),
  E13–E14 ([0014](../decisions/0014-use-synchronous-protocols-with-one-hop-per-store-call.md))
  and the vector write path
  ([0015](../decisions/0015-write-vectors-with-the-graph-when-one-store-holds-both.md)).

Done on 2026-10-06, after the author settled entity identity
([ADR 0016](../decisions/0016-identify-entities-by-scope-keys-and-vetoes.md)):
- [domain-packs.md](domain-packs.md#identity-fields) and the draft packs:
  `scope`, `vetoes`, `names`, `corroborate`, `version_start`, `compare`,
  `unique`, identity lint and identity cases; `issuer` in fact version
  keys.
- [v1-packs.md](v1-packs.md): the identity of each default type.
- [graphrag-engines.md](../reference/graphrag-engines.md) and
  [graphrag-research.md](../reference/graphrag-research.md): how engines,
  matchers and papers handle identity.
- The seven rules found by the engine-flow demo are in this brief: the
  subject hint `K0` and `is_name` (§2.2, §2.4), scope and veto conflicts
  blocking every step (§2.6), `TEXT_IN` on `version_label` (§2.9),
  translations never matching by name (§2.6), the next free hash on an id
  collision (§1), ten-word n-grams (§4.1) and the hint threshold measured
  in M1 (§2.4). So are the three large-document rules: confirmation
  batches of at most 50 pairs (§2.6), one unit per document (§2.10) and
  degree by distinct neighbours (§2.11).

## Decisions on the open questions

Decided by the author on 2026-10-05. Each item keeps the options that
were offered and names the chosen one. For every question except E10,
the choice was the agent's recommendation.

1. **E1 — Relation rows.** (A) One row per statement per chunk; two
   sources give two parallel edges on Neo4j. (B) One row per relation with
   a list of evidence. Chosen: A. Deletes stay row-local on every
   backend, and each row keeps its own quote, time and status. B needs
   evidence lists or reified edges on Neo4j.
2. **E2 — Events.** (A) No event resolution; each extraction is its own
   node. (B) Merge within a document by time and compatible roles, and
   across documents by pack `identity`. (C) B plus fuzzy and LLM event
   matching. Chosen: B. With A, the decision in chunk 3 of D3
   points to a different meeting node from the one in chunk 1.
3. **E3 — Fact versions.** (A) Add `version_key` to fact types, so the
   newest fact per group is flagged. (B) No fact versions: only
   `one_at_a_time` relations supersede. Chosen: A. Without it, the
   two allowance limits in D1 and D2 are both "current".
4. **E4 — What is embedded.** (A) Chunks only. (B) Chunks and entity
   names. (C) Chunks, entities and fact quotes. Chosen: B. Entity
   vectors serve linking and cross-language resolution. C repeats the AWS
   toolkit's storage-cost problem, and facts are reached through the
   graph.
5. **E5 — Document card.** (A) Rules and file metadata only. (B) Caller
   metadata, then one LLM call per document, then rules. (C) Caller
   metadata only. Chosen: B. Versions order by document dates, so a
   wrong date gives a wrong "newest", and file dates are unreliable.
6. **E6 — Extraction calls.** (A) One call per chunk for every kind.
   (B) Two calls: entities, then the rest restricted to them. (C) Several
   chunks per call, labelled by chunk id. Chosen: A, with B and C
   as benchmark variants. A costs about half of B, and C risks wrong chunk
   citations.
7. **E7 — Chunking.** (A) One size, about 500 tokens, no overlap,
   structure-aware, heading path in the context header. (B) Two levels:
   small chunks for retrieval, larger sections for extraction. (C) Fixed
   size with overlap. Chosen: A, with 300, 800 and 1,200 tokens as
   benchmark variants. B doubles the provenance work, and overlap
   extracts the same fact twice.
8. **E8 — Entity resolution.** (A) No LLM: fuzzy matches become
   `same_as` candidates only. (B) An LLM confirms fuzzy candidates within
   and across languages; `same` merges, `unsure` links. (C) B, but never
   merge across languages, only link. The first recommendation was B. It
   keeps the graph clean for about one batched call per document. C leaves
   `Phòng Tài chính` and `Finance Department` as two nodes.
   On 2026-10-05 the author proposed two steps before extraction: a
   glossary of naming rules in the user pack, and existing entities from
   the graph passed to the extraction prompt. Both are now in §2.4 and
   step 1 of §2.6. They remove most duplicates upstream, and B handles
   the rest: the first run, documents of the same run, and mentions the
   model does not link. Chosen: B with the glossary and hints.
   On 2026-10-06
   ([ADR 0016](../decisions/0016-identify-entities-by-scope-keys-and-vetoes.md))
   the name and key stages became the scope, key, veto and name-rule
   steps of §2.6. B's LLM confirmation stays, now listwise and within the
   scope.
9. **E9 — As-of for items with no stated time.** (A) Apply when the
   document is dated on or before D. (B) Always apply, flagged. (C) Never
   apply. Chosen: A, after inheriting the document's stated
   effective dates (§3.1).
10. **E10 — Budget.** (A) Estimate in the plan only. (B) Estimate plus a
    default stop at 1.5 times the estimated LLM calls. (C) The user must
    set an absolute cap. Chosen: A (§2.13). The agent had recommended B.
11. **E11 — Items beyond the returned chunks.** (A) Only items whose
    evidence is in the top-k chunks. (B) A separate item budget, each
    item with its quote and an `in_returned_chunks` flag. (C) Every item
    reached. Chosen: B. A drops facts that "everything about X"
    questions need, and C floods the context.
12. **E12 — Agent tools.** (A) `retrieve` and `describe_schema` only.
    (B) Plus `find_entities`, `get_entity`, `get_neighbors` and
    `get_sources`. (C) B plus a raw query tool. Chosen: B. Agents
    iterate through graph tools (RAGSearch), and a raw query tool is a
    security and parity risk.
13. **E13 — Sync or async.** (A) Synchronous API and protocols, with a
    bounded thread pool inside. (B) Async first, with sync wrappers.
    (C) Both everywhere. Chosen: A. Notebooks already run an event
    loop, so sync wrappers over async code break there, and C doubles the
    work of a solo developer.
14. **E14 — Expansion in the store.** (A) One `hop` per call; the engine
    composes hops. (B) One `expand` call runs every hop in the backend.
    Chosen: A. It adds one round trip per hop, a few milliseconds,
    and keeps the backends thin and comparable.
