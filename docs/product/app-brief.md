# App UI — design brief (2026-10-07)

Status: draft. It is the "separate brief" for the `app` component of
the [SDK platform brief](sdk-platform-brief.md), written from a
brainstorm whose five design sections the author approved one by one on
2026-10-06 and 2026-10-07. Its settled decisions are recorded in
[ADR 0020](../decisions/0020-ship-the-app-as-fastapi-with-a-nextjs-static-export.md)
(app stack and hosting),
[ADR 0021](../decisions/0021-draw-the-whole-graph-with-d3-or-deckgl-by-size.md)
(whole-graph renderers and positions) and
[ADR 0022](../decisions/0022-record-a-live-index-trace-outside-the-document-unit.md)
(live index trace), all 2026-10-11.

It also adds four things the engine and the SDK must provide before the
app exists: a live index trace per document and `retrieve(...,
explain=True)` in M1, per-question benchmark results in M4, and a
read-only graph browse API with precomputed node positions in M6.

**Goal** — A developer can see how each document became part of the
graph and why a question got its answer, and an end user can check the
evidence behind any node or answer, in a web app over the public SDK API
that runs as a Databricks App or locally.

## Users & pain

- **Developers** checking extraction and entity merges. Today the only
  record of an index run is `runs.stats`: counts per drop reason with at
  most five examples for the whole run. Which chunk produced which item,
  what was dropped where, and why two mentions merged or stayed apart is
  not visible anywhere.
- **End users** who must see the evidence before they trust an answer:
  from a node or a cited answer back to the quote, the chunk and the
  document.
- **Benchmark readers** comparing many runs at once: which index and
  which query-time variant wins, at what cost, and which questions fail.

Operators watching large runs are not a target: the run record, Lakeflow
Jobs or an external orchestrator already cover them.

## Constraints

Discovered (repo):
- `app` may use the public `serving` API only
  ([ARCHITECTURE.md](../../ARCHITECTURE.md)). The engine depends only on
  protocols, so anything new it records goes through a protocol.
- Every document is one atomic unit, and the run record marks a run
  complete ([ADR 0008](../decisions/0008-build-databricks-and-open-branches-in-parallel.md),
  [engine brief §2.10](engine-brief.md#210-write)).
- Credentials are explicit and fail closed; the profile names a source,
  never a secret ([ADR 0003](../decisions/0003-caller-supplied-credentials.md),
  [ADR 0018](../decisions/0018-name-credential-sources-in-the-profile.md)).
- Every id is a SHA-256 hex hash ([engine brief §1](engine-brief.md#ids-and-hashes)).
- `RetrievalResult` already has a `trace` field for retrieval timing and
  counts ([engine brief §4.2](engine-brief.md#42-output)). The index trace
  here is a different thing, kept per document.
- Third-party libraries must be permissive and pinned
  ([ADR 0009](../decisions/0009-reuse-permissive-libraries-behind-adapters.md));
  uv waits 24 hours before installing a new version
  ([ADR 0019](../decisions/0019-use-uv-ruff-mypy-pytest-and-import-linter-as-gates.md)).
- Databricks Apps pass the viewer's OBO token in
  `x-forwarded-access-token`, and Lakebase allows at most 500 Postgres
  roles per branch ([databricks-platform.md](../reference/databricks-platform.md#identity-and-obo)).
- Chrome 139 and later and Edge 144 and later no longer fall back to
  software WebGL (SwiftShader) when there is no GPU, unless IT sets the
  temporary `EnableUnsafeSwiftShader` policy (checked 2026-10-07:
  [Edge policy](https://learn.microsoft.com/en-us/deployedge/microsoft-edge-browser-policies/enableunsafeswiftshader),
  [blink-dev intent to remove](https://groups.google.com/a/chromium.org/g/blink-dev/c/yhFguWS_3pM/m/oLrB5up_BwAJ)).
  On such a machine WebGL does not run at all.

Supplied (author):
- v1 is for viewing: no notes, no "report wrong" button, no saved boards,
  no graph edits.
- Four canvases, 2D first with 3D as an advanced view, and the 2D
  renderer split by graph size (below).
- One app with two hosting modes: a Databricks App, and a local command
  with a login.
- The index trace is live while a document indexes.
- A graph without communities is still drawn in full.
- Without WebGL2, a graph of 5,000 nodes or more is refused, not drawn
  in part.
- The UI speaks English and Vietnamese. UI details are tuned during
  implementation.

Assumed (to confirm in this review):
- Only the whole-graph canvas refuses without WebGL2. The question,
  trace and benchmark canvases are small, do not use WebGL, and work on
  any machine.
- "Dragging" in the success signal means panning the view.
- 3D needs communities: without them there is nothing to lift into
  nested balls, so the 3D button is off and says why.
- Positions are computed after `apply` whenever the `communities` extra
  is installed (the `app` extra includes it).

## Chosen approach

### 1. Scope

| Canvas | Route | What it is for | Drawn with |
|---|---|---|---|
| Whole graph | `/graph/` | Go from a node to its attributes, its chunk and its document; see communities | D3 (SVG) below 5,000 nodes, deck.gl (WebGL2) from 5,000; deck.gl for 3D |
| Question | `/ask/` | The subgraph behind one question, why each part is there, and what the limits cut | D3 |
| Index trace | `/trace/<doc_id>/` and `tenetrag trace <doc> --html` | Each pipeline step of one document with its inputs and outputs, live while it runs | React Flow |
| Benchmark | `/benchmark/` | Many runs at once: a config tree, and a quality–cost map with a Pareto frontier | React Flow (tree), D3 (map) |

The platform brief's other app screens stay in scope: the folder
browser, plan review, apply, chat over `answer()`, and benchmark runs.
This brief settles how they are hosted and how they connect to the
canvases, not their layout:
- an answer in the chat opens the question canvas;
- a document in a plan opens its trace;
- the benchmark canvas is the "benchmark runs" screen;
- the question canvas is the platform brief's retrieval inspector: it
  shows every entity, item and chunk `retrieve()` returned.

The canvases are read-only. The app writes only through the actions the
platform brief already lists: apply a reviewed plan and start a
benchmark run, plus login.

### 2. Architecture

**Packages and builds.**

```
frontend/                          npm workspace, source only (lockfile committed)
├── packages/
│   ├── api-types/                 M1 · types.gen.ts generated from the Pydantic models; CI fails on drift
│   └── trace-canvas/              M1 · React + React Flow; depends only on react and @xyflow/react
├── apps/
│   ├── trace-html/                M1 · Vite + vite-plugin-singlefile → dist/trace.html (one file)
│   └── web/                       M6 · Next.js, output: 'export', trailingSlash: true
│       ├── src/app/               routes: graph/ · ask/ · trace/[docId]/ · benchmark/ · sources/ · plan/
│       ├── src/canvases/          graph/ · ask/ · benchmark/ (trace comes from the package)
│       └── tests/                 Playwright
        │  CI builds the frontend before the wheel and copies it into package data
        ▼
src/tenetrag/
├── cli/                           M1 · `tenetrag` command, stdlib argparse
│   ├── trace.py                   `tenetrag trace <doc> --html`
│   └── assets/trace.html          gitignored; copied from apps/trace-html/dist
├── app/                           M6 · `app` extra
│   ├── server.py                  FastAPI; static files mounted last
│   ├── security.py                OBO, basic login, sessions, same-origin check
│   ├── static.py                  `_` placeholder rewrite; JSON 404 under /api
│   ├── schemas.py                 view models (for example the inspector's node view)
│   ├── api/                       graph.py · ask.py · trace.py · benchmark.py · sources.py
│   └── static/                    gitignored; copied from apps/web/out
└── serving/ …
deploy/databricks-app/             app.yaml and bundle for the Databricks App mode
```

- **Layers:** `cli → app → serving`. `tenetrag app` lives in `cli` and
  imports `app.server` only when that command runs; without the `app`
  extra it says what to install. `tenetrag trace --html` never imports
  FastAPI.
- **One name per feature** across the route, the API module and the
  canvas: `graph`, `ask`, `trace`, `benchmark`, `sources`.
- **No shared UI package yet.** Cards, chips and colour tokens stay in
  `trace-canvas` until `apps/web` needs them in M6.
- **Nothing needs Node at run time.** The wheel carries the built files.
  Built from source without the frontend, `tenetrag trace --html` fails
  with the build command instead of writing an empty page.
- **Libraries,** all permissive (versions checked 2026-10-07): React
  Flow (`@xyflow/react` 12.12.0, MIT), vite-plugin-singlefile 2.3.3
  (MIT), D3 7.9.0 (ISC), deck.gl 9.4.0 (MIT), Next.js 16 (MIT), FastAPI
  (MIT).
- **ADR 0009's adapter rule.** FastAPI and its server are the `app`
  module's framework, and `app` is their adapter boundary: no other
  module imports them, and all six conditions hold (ADR 0020). The
  force-layout library sits behind an adapter in `layout` and meets all
  six (ADR 0021).

**Routes.** Pages with an id use one static placeholder page, `_`:
`generateStaticParams` returns `_`, and a `StaticFiles` subclass serves `…/<id>/` (including
`index.txt`) from `…/_/`. The page reads the id from the URL. Every id
is hex (SHA-256, or an MLflow run id), so the rewrite touches only
segments matching `[0-9a-f]+` and returns 404 for anything else; a path
cannot reach another file.

| Route | Page |
|---|---|
| `/` | Home: the index, the last apply, entries to the four canvases |
| `/graph/`, `/graph/node/<entity_id>/`, `/graph/community/<id>/` | Whole graph, optionally opened at a node or a community |
| `/ask/` | Question canvas with the chat beside it; the benchmark opens it with `?q=…&run=<run_id>` |
| `/trace/<doc_id>/` | Index trace of one document |
| `/benchmark/`, `/benchmark/run/<run_id>/` | Config tree and map tab, optionally with a run selected |
| `/sources/`, `/plan/` | Folder browser, plan review and apply |

`/api/*` is a thin JSON layer over public SDK functions. In development,
`next dev` proxies `/api/*` to a local FastAPI on the synthetic corpus;
a static export has no rewrites, so the proxy exists only there.

**Hosting modes.**

| | Databricks App | Local: `tenetrag app --profile p.yaml` |
|---|---|---|
| Viewer | OBO token in `x-forwarded-access-token` on every request | One account, logged in through ADR 0018's `basic` source (`user` + `password_env`) |
| Identity for stores and models | The viewer's OBO token by default (Lakebase gives each user a Postgres role). The app's service principal only when the profile says so | The profile's named credential sources |
| Missing credential | 401 and `AuthError`; never the app's service principal | Refuses to start when the password variable is unset; no default password |
| Address | Managed by Apps | `127.0.0.1`. Any other address needs `--tls-cert`/`--tls-key` or `--behind-proxy` |
| Session | Managed by Apps | Server-side session, cookie `HttpOnly` and `SameSite=Strict`; every POST passes a same-origin check |
| Health | `HEAD /` returns 200, even before the frontend is built | same |

The profile sets each store's identity: the viewer's OBO token, or a
named credential. A store in OBO mode never uses a pool opened under
another identity
([ADR 0003](../decisions/0003-caller-supplied-credentials.md)). Neo4j
cannot take an OBO token, so it always uses a named credential and every
viewer shares one read identity. That is explicit configuration, not a
fallback, and the page shows which identity reads each store. The
ADR 0020 records this per-store reading of ADR 0003.

### 3. Data the engine and SDK add

| Addition | Where | Milestone | Used by |
|---|---|---|---|
| Live index trace per document | `TraceSink` protocol; tables `trace_events` and `trace_status`; `client.get_trace()` | M1 | Trace canvas, `trace --html` |
| `retrieve(..., explain=True)` | new `explain` field on `RetrievalResult` | M1 | Question and benchmark canvases |
| Per-question benchmark results | inside each MLflow run, plus config tags | M4 | Benchmark canvas |
| Read-only graph browse API | `client.graph`, plus `get_attribute_sources` and `iter_graph` on `GraphStore` | M6 | Whole-graph canvas |
| Node positions | `layout` module; table `layout_positions` with `put_positions` and `get_positions` | M6; nesting needs M5's communities | Whole-graph canvas (2D and 3D) |

What already exists and is reused: `runs.stats`, `identity_blocks`,
`mentions`, `same_as`, `resolution_decisions`, and the extraction cache
of validated output before resolution.

**3.1 Live index trace (M1).**
- **Protocol.** The engine emits trace events through a new `TraceSink`
  protocol that the graph store implements, so the engine still depends
  only on protocols. Its operations: start a document's trace, append a
  batch of events, finish it with a status, read the events after a
  sequence number, mark stale running traces interrupted, and delete a
  document's trace.
- **Write cadence.** Each step appends one batch when it finishes. A long
  step (extraction) also appends progress about every 2 seconds, such as
  "37/120 chunks". No store call runs per item.
- **Tables.** `trace_events` (doc_id, run_id, seq, step, payload) and
  `trace_status` (doc_id, run_id, status, started_at, finished_at,
  error), with status `running`, `done`, `failed` or `interrupted`.
- **Outside the document unit.** Trace events are written before and
  outside the document's atomic write. A document that fails still has a
  trace, and the trace shows the failing step.
- **Lifecycle.** Only the latest run per document is kept. When a
  document starts indexing again, its old trace is replaced at once, so
  the run in progress is always the one shown. A document delete
  removes its trace right after `delete_documents`; a crash in between
  leaves a trace with no document, which the app shows as deleted. When
  a run takes the writer lease, it marks traces left `running` by a dead
  process as `interrupted`.
- **Content.** Every step records its counts, time, LLM calls and
  tokens. Inputs and outputs that live in other tables are referenced by
  id: chunks, entities, items, identity blocks.
  - **Extraction and drops** are referenced through the chunk's
    extraction-cache entry (`cache_key`, and whether it was a hit). The
    cache payload gains the chunk's dropped items with their reason codes
    and offending text, so a cache hit shows the same drops as the run
    that filled it.
  - **Resolution decisions** are stored nowhere else, so the trace copies
    them: each mention's target, method, and the candidates with the
    attribute that kept each apart.

  ```json
  {"step": "validate", "chunk": "7e1…", "cache_key": "a90…", "cache_hit": false,
   "kept": 6, "dropped": 1}
  {"step": "resolve", "chunk": "7e1…", "mention": "Nguyễn Văn An",
   "decision": "new", "method": "key_lookup",
   "candidates": [{"entity": "41c…", "label": "Nguyễn Văn An (Công ty CP Beta)",
                   "kept_apart_by": "scope", "quote": "…"}]}
  ```
- **Always on.** The trace never changes the graph, so it is not part of
  any stage hash. Its size stays well below the document's chunk text,
  since only resolution decisions are copied. Raw prompts and LLM
  replies are not stored.
- **API.** `client.get_trace(doc, after=None)` takes a source path or a
  `doc_id` (the `doc_id` is the hash of the path) and returns the status
  and the events after `after`. An entity or cache entry the trace
  references that no longer exists is shown as "no longer exists".
- **Live view.** While the status is `running`, the app polls
  `/api/trace/<doc_id>?after=<seq>` every second. Server-sent events can
  replace polling once the Apps proxy is shown to keep a stream open.

**3.2 `explain=True` (M1).** Off by default. When on, `RetrievalResult`
gains `explain`:
- for each seed: how it was linked (alias n-gram, entity vector with its
  score, or through a chunk), its score and rank, and whether it was kept
  or cut;
- for each reached entity and item: the hop, the entity it came from and
  the relation it came through;
- for each limit the engine applies in
  [engine brief §4.1](engine-brief.md#41-retrieve) (top 10 seeds, the
  20 best hop-1 entities that start hop 2, `top_k`, `max_items`): what
  it cut, with scores, at most 50 entries per limit plus the total;
- for the per-entity caps that the store applies inside `hop` (20
  neighbours and 50 items, in store order): each entity whose result
  reached a cap, marked "capped". The store does not return what it
  left out, and `explain` adds no store call to find it.

The rest of the result is identical with `explain` on or off.
`answer(..., explain=True)` passes the flag to the `retrieve()` it runs,
so the question canvas explains the exact retrieval behind the answer.

**3.3 Per-question benchmark results (M4).**
- Each MLflow run carries tags: golden set and its version, every
  index-time stage hash (chunk, embed, extract, resolve, cluster,
  reports), and the query-time parameters. The config tree is built
  from these tags alone.
- Each run also stores one result per question: question type, retrieved
  chunks, right or wrong, failure category and latency.
- "Open in question canvas" re-runs `explain` with the run's
  configuration. When the run's index was deleted, the button is
  disabled and says so.

**3.4 Graph browse API (M6).** `client.graph` offers: entity,
neighbours, chunk, document, name search, communities and positions.
Most of it wraps existing protocol reads (`get_entities`, `hop`,
`get_chunks`, `get_documents`, `search_names`, `get_communities`).
`GraphStore` gains:
- `get_attribute_sources`, to go from an attribute to its quote and
  chunk;
- `iter_graph`, which streams every node (id, kind, type, label) and
  every edge (endpoints, kind, type) in batches, as `cluster_edges`
  does. The layout and the whole-graph payload read it;
- `put_positions` and `get_positions`, for the layout below.

**3.5 Node positions (M6).**
- Computed in pure Python, since nothing runs Node at run time, by a
  `layout` module outside the engine. `layout` imports protocols and
  `config` only, and sits in the layer of `ingest` and `benchmark`
  under `serving`.
- `serving` runs it after `apply` whenever the `communities` extra is
  installed (assumed above). For an index built without it, such as by
  a job without the extra, `client.graph.compute_layout()` computes the
  positions.
- **With communities:** nested circles per level, a port of d3's
  `packSiblings`, with a small force between top-level communities. 3D
  keeps the same x and y and lifts z per community level, so each
  community is a ball inside its parent's ball. No force runs on the
  100k nodes themselves.
- **Without communities:** a force layout over the whole graph (library
  still to choose, see open questions).
- Keyed by the run id of the clustering run, or of the index run when
  there are no communities. On re-index, existing nodes keep their place
  and only new nodes are placed. A full re-layout happens when
  communities change a lot; the M6 spec sets the threshold.
- Communities hold entities. Events and facts sit beside the entities
  that hold roles in them; the M6 spec fixes the rule.
- Graphs of 5,000 nodes or more travel to the browser as binary typed
  arrays (positions, community per level, colour codes, edge endpoints),
  a few MB at 100k nodes, not as JSON. The M6 spec fixes the format.

### 4. The canvases

**Shared.**
- The inspector sits on the right; on a phone it becomes a bottom sheet.
- Colour tokens for light and dark themes.
- Search and the inspector work from the keyboard.
- v1 targets laptop screens; phones can view but are not a target.
- Source text is never translated.
- UI strings in English and Vietnamese, kept in separate files, picked
  from the browser language, with a switch.
- Every canvas has four states: loading, empty, error with a retry
  button, and stale data.

**Whole graph** (`/graph/`).
- **Renderer by size, every node always drawn:**
  - **Below 5,000 nodes:** D3 with SVG, with community hulls when
    communities exist. Labels are sharp and nodes can be dragged for the
    current view; nothing is saved.
  - **From 5,000 nodes:** deck.gl `OrthographicView` on WebGL2. Nodes are
    one instanced layer from typed arrays. Only light layers change with
    zoom (level of detail):
    - community circles per level, shown when they are big enough on
      screen;
    - summed links between communities when far, real edges when near;
    - community labels when far, node labels when near, placed by circle
      size and node spacing, with overlaps removed by
      `CollisionFilterExtension` (to re-verify in the M6 spec);
    - Vietnamese text through `TextLayer` with `characterSet: "auto"`.
  - The 5,000 threshold is a named constant.
- **No WebGL2 at 5,000 nodes or more:** the canvas shows "This browser
  has no GPU access (no WebGL2), so graphs of 5,000 nodes or more cannot
  be drawn", with the reason: Chrome 139+ and Edge 144+ no longer draw
  WebGL on the CPU. Nothing is drawn in part. A WebGL context lost while
  drawing is recreated once; if that fails, the same notice appears.
- **Colour** by community (top level by default, with a level picker),
  by kind (entity, event, fact) or by pack type. Eight colours, assigned
  greedily so that neighbouring communities differ. Without communities,
  colour by community is off with a "not clustered" note.
- **Search** in the browser over the loaded labels, ignoring diacritics,
  ranked prefix, then word start, then infix.
- **Node to quote in three clicks:**
  1. Click a node. The inspector shows its label with scope ("Phòng Tài
     chính (Công ty CP Beta)"), each attribute with its sources, and its
     items with validity, such as `[2025-02-01 → 2026-01-15,
     superseded]`.
  2. Click a quote. The chunk opens with the quote highlighted, under the
     document's header (title, date, version).
  3. Click "Open document".
- **3D (advanced),** deck.gl `OrbitView` on the same x and y with z
  lifted per community level. Lit spheres; moving particles are off by
  default because they force continuous redraws. Nodes cannot be dragged
  in 3D.

**Question** (`/ask/`).
- A question box with an optional `as_of` date. The `answer()` reply
  with citations sits beside the canvas.
- **Laid out in hop columns, not by force:** seeds in column 1, hop 1 in
  column 2, hop 2 in column 3, and chunks on the right by rank. The
  canvas explains a path, and a path reads left to right; a force layout
  would mix the hops.
- Facts and events are small nodes between entities. Versions stack, and
  the one valid on the question's date is marked ✓.
- A "cut" layer, hidden by default, shows each cut candidate dimmed with
  a dashed border and its reason, such as "below the top 10 seeds". An
  entity whose hop reached a store cap carries a "capped at 20
  neighbours" badge.
- Clicking a citation in the answer highlights its chunk and the items
  that rest on it.

**Index trace** (`/trace/<doc_id>/` and `trace --html`).
- Header: document name, run, status, parser, pipeline hash.
- One React Flow column of cards per step: parse with the document card,
  chunk and embed, extract, validate, resolve, write. Each card shows
  counts, time, LLM calls and tokens; opened, it lists its entries in a
  virtual scroll.
- Selecting a chunk lights its path through every step.
- A dropped item shows its reason code and offending text. A resolution
  decision shows its candidates and the attribute that kept each apart.
- Text search inside the trace.
- **Live:** finished steps show full cards, the running step a progress
  bar, later steps are dimmed, and a failed step has a red border with
  the error.
- The `--html` file is the same canvas with links to the app replaced by
  ids, since there is no server. Exported while the document is still
  running, it is a snapshot marked "running".

**Benchmark** (`/benchmark/`).
- **Main tab: config tree** golden set → index (index-time hashes) →
  variant (query-time parameters). Cards switch to a compact form below
  zoom 0.55. Chips highlight runs, indexes collapse, and the inspector
  lists failure categories and the wrong questions.
- **Second tab: quality–cost map** with the Pareto frontier.
- The baseline of a variant is the hybrid run with the same chunk and
  embedding hashes.
- With several golden sets, a picker at the top shows one tree at a
  time.
- The thresholds of the quality rule come from the benchmark
  configuration, never from code.
- Clicking a wrong question opens the question canvas with that run's
  configuration.

### 5. Errors

The API always returns a generic JSON error with a request id; details
go to the server log only. SDK exceptions map to:

| Exception | HTTP |
|---|---|
| `AuthError` | 401 |
| `CredentialMismatchError` (a configuration mistake) | 500, with "check the configuration" |
| a failed same-origin check | 403 |
| an id the store does not return | 404 |
| `WriterBusyError` on apply | 409 |
| `LLMError` | 502 |
| `StorageError` | 503 |
| `ConfigError` | 500, with "check the configuration" |

Edge states:
- **No communities yet:** the whole graph is drawn in full with the
  renderer for its size, at force-layout positions.
- **Positions older than the graph:** the previous positions are used,
  new nodes sit next to a neighbour, and a line says "layout updating".
  With no positions at all, a graph below 5,000 nodes is laid out in a
  web worker. A larger one shows "computing layout" while a run computes
  it, or else how to compute it (`client.graph.compute_layout()`).
- **No WebGL2, 5,000 nodes or more:** the refusal above.
- **Document without a trace:** only documents indexed before the
  feature. The page says why and how to re-index.
- **Trace status** `failed` or `interrupted` is shown as such, with the
  last step reached.

### 6. Security

- **OBO fails closed:** a missing token is a 401, never the app's
  service principal.
- **Local login:** no default password; the server refuses to start
  without the password variable. Passwords are compared with
  `hmac.compare_digest`, and login attempts are rate-limited (for
  example 5 per minute per IP). It binds to `127.0.0.1`; any other
  address needs TLS or `--behind-proxy`.
- **Sessions and writes:** server-side sessions, cookie `HttpOnly` and
  `SameSite=Strict`, a same-origin check on every POST. The only writes
  are login, apply and starting a benchmark run.
- **Untrusted text:** document text, quotes, dropped text and LLM output
  are always rendered as plain text; no `dangerouslySetInnerHTML`. The
  JSON in `trace.html` sits in `<script type="application/json">` with
  `<` escaped as `\u003c`.
- **Strict CSP** header; how it handles the inline scripts of a Next
  static export is settled in the M6 spec.
- **Traces hold document text,** so they have the same access as the
  graph. `trace --html` warns that the file must be protected like the
  source document.
- **Ids in paths** are rewritten only when they are hex.
- **npm supply chain:** lockfile committed, `npm ci --ignore-scripts`, a
  24-hour cooldown on new versions like uv's, and a CI check that blocks
  non-permissive licences.

### 7. Testing

- **Engine (M1),** on the reference store with fake models:
  - the trace of D3 in the running example, with a planted Nguyễn Văn An
    at Công ty CP Beta and one planted bad quote, records "kept apart by
    scope" for that candidate and exactly one `QUOTE_NOT_IN_CHUNK` drop;
  - the trace is written step by step, can be read part way with
    `after`, becomes `interrupted` when the lease is taken over, and is
    deleted with its document;
  - `explain=True` returns the same result as `explain=False` and makes
    no extra store call.
- **Python (`tests/cli`, `tests/app`):**
  - a missing OBO token gives 401 with no identity fallback;
  - local mode refuses to start without the password variable, and
    refuses a non-local address without TLS or `--behind-proxy`;
  - the rewrite rejects non-hex ids;
  - `trace --html` escapes `</script>` inside the trace.
- **Web:**
  - vitest for the pure functions: search ranking, greedy colouring,
    label placement, the Pareto frontier, the quality rule;
  - Playwright on the real build with FastAPI and synthetic data: the
    three-click path, the no-WebGL path (`--disable-3d-apis`) shows the
    refusal and no other console error, no horizontal scroll at 390 px,
    both themes, every string in English and Vietnamese;
  - `types.gen.ts` matches the Pydantic models.
- **Performance:** CI checks 100k nodes with a loose budget to catch
  regressions. The real targets are measured on a reference laptop
  before each release.
- **Fixtures** are synthetic only (the Alpha and Beta corpus), never
  adopter data.

Evidence so far, from a throwaway renderer prototype outside the repo,
measured on a server CPU with software rendering (no usable GPU):
- D3 drawing every node: 2,000 nodes zoom at 32 FPS and drag a node at
  29 FPS; 4,999 nodes zoom at 20 FPS and drag a node at 15 FPS; panning
  stays at 60 FPS. Software SVG is slower than a laptop, so these are
  lower bounds.
- deck.gl at 100k nodes on CPU renderers: first draw 2.9 s in 2D and
  1.1 s in 3D, 4–8 FPS while panning (llvmpipe). The script work is
  about 250 ms; the rest is rasterising. Real-GPU numbers are not
  measured yet.

## Milestones

| | Adds | Depends on |
|---|---|---|
| M1 | `TraceSink`, `trace_events`, `trace_status`, `client.get_trace()`, drops in the extraction cache; `retrieve(..., explain=True)` and `answer(..., explain=True)`; the `cli` module with `tenetrag trace <doc> --html`; `frontend/` with `api-types`, `trace-canvas` and `trace-html`; Node in CI | engine brief |
| M4 | MLflow config tags and per-question results | M1 |
| M5 | Hierarchical communities, which nesting and colour by community need | M4 |
| M6 | `tenetrag.app` (FastAPI + Next export), `tenetrag app`, the Databricks App bundle, `client.graph` with `compute_layout()`, `get_attribute_sources`, `iter_graph`, `put_positions`, `get_positions`, the `layout` module and `layout_positions`, the four canvases | this brief, M5, stable API |

## Alternatives considered

- **Dagster as the trace UI.** It draws a DAG of assets, not one document's
  content through each step, and offers no custom views. One partition
  per document strains its UI at 10k–100k documents, and it needs its own
  webserver, daemon and Postgres. It fits only as an optional external
  orchestrator around `apply()`.
- **MLflow Tracing as the trace view.** A span tree with inputs and
  outputs, but no chunk-lineage view, and its limits at 100k documents
  are unmeasured.
- **A Python UI framework** (Streamlit or Dash) with the canvas as a
  custom component: the canvas is still JavaScript, Streamlit's reruns
  lose zoom state, and `trace --html` could not reuse the component.
- **A full Node/TypeScript app:** two servers beside a Python SDK.
- **No app** (Neo4j Browser and notebooks): Neo4j Browser does not reach
  the Lakebase, Postgres or Delta branches, and the platform brief keeps
  the app's full scope.
- **One frontend project** instead of a workspace: `trace-canvas` could
  import Next by accident, and M1 could not build it without `apps/web`.
- **`trace --html` from the Next export packed into one file:** Next
  loads chunks through its own runtime, so packing is unsupported and
  breaks on upgrades. **`trace --serve`** instead of one file: needs a
  running process to share a trace.
- **vis-network** for 2D: community regions still drawn by hand, a poor
  fit with React, and the slowest first draw of the libraries tried.
- **3d-force-graph** for 3D: one three.js object per node and link
  (about 4,900 draw calls at 2,000 nodes) and continuous redraws; deck.gl
  draws each layer in one call and redraws only on interaction.
- **D3 bubble overview** for large graphs (open communities level by
  level, never more than 3,000 circles): replaced by deck.gl drawing
  every node, one path with or without communities.
- **Without WebGL2: the bubble overview, or a partial D3 drawing of a
  searched node or picked community.** The author chose to refuse
  instead of keeping a second drawing mode.
- **Search first** when there are no communities: the author wants the
  full graph.
- **Force layout for the question canvas:** it mixes the hops a reader
  needs to follow.
- **Whole-graph layout in the browser:** 100k nodes cannot open in
  2 seconds that way. Small graphs without stored positions still use a
  web worker.
- **Trace written atomically with the document:** cannot be watched
  live, and a failed document would have no trace.
- **Server-sent events now:** whether the Apps proxy keeps a stream open
  is unverified; polling works everywhere.
- **Free benchmark board:** conflicts with "no saved boards".
- **Two runs side by side in the question canvas:** comparison belongs
  to the benchmark canvas.
- **tldraw** (licence) and **Excalidraw** (free drawing, not a fixed
  pipeline) for the trace canvas.

## Out of scope (v1)

- Notes, "report wrong", saved boards.
- Editing the graph; reviewer merge and split stay after v1
  ([engine brief §11](engine-brief.md#11-milestones)).
- Comparing two runs in the question canvas.
- Content authorization; platform permissions apply.
- Storing raw LLM prompts and replies with the graph.
- Drawing part of a large graph without WebGL2.
- Dragging nodes in 3D.
- More than one account in local mode.
- Server-sent events.

## Compatibility

- `retrieve()` without `explain` returns exactly what the engine brief
  defines; `explain` is an added field.
- Trace writes never touch the graph tables, the document's atomic unit
  or any stage hash.
- Importing `tenetrag` needs none of the `app` dependencies, and `cli`
  uses only the standard library until a command needs more.
- The engine still imports only protocols, `config` and `packs`.

## What changes elsewhere (after review)

- [sdk-platform-brief.md](sdk-platform-brief.md):
  - the `app` row: two hosting modes, the four canvases, the question
    canvas as the retrieval inspector, a link to this brief;
  - the scope line: "so does the app UI" points here;
  - packaging: the wheel carries the built frontend; a `cli` entry point;
    the `communities` extra also carries the layout's force library;
  - milestones: M1 gains the trace, `explain` and `trace --html`; M4 the
    per-question results; M6 depends on this brief;
  - success criterion 8: add the canvases, the trace and local hosting.
- [engine-brief.md](engine-brief.md):
  - §1: the `trace_events`, `trace_status` and `layout_positions` tables;
  - §2: trace events per step, outside the document unit, interrupted
    traces on lease takeover, and the trace delete after
    `delete_documents`;
  - §2.5: the extraction-cache payload keeps the chunk's drops;
  - §4.2 and §4.3: the `explain` field, and `answer(..., explain=True)`;
  - §6: the `TraceSink` protocol, `get_attribute_sources`, `iter_graph`,
    `put_positions` and `get_positions`;
  - §10 and §11: the tests and milestones above.
- [ARCHITECTURE.md](../../ARCHITECTURE.md): the `cli` and `layout`
  modules, the `cli → app → serving` layers, `app` described by this
  brief, and a "local app" row under where things run.
- [docs/index.md](../index.md): this brief (added with the draft).

## Success criteria

1. From a node in the whole-graph canvas, a user reaches the quote in
   its chunk and the document in at most three clicks (Playwright).
2. On the reference laptop, a 100k-node graph opens in under 2 seconds
   and stays at 30 FPS or more while zooming and panning, in 2D and 3D,
   checked before each release. CI runs the same check with a loose
   budget.
3. On the reference laptop, D3 at 4,999 nodes zooms and pans at 30 FPS
   or more; otherwise the 5,000 threshold is lowered to what passes.
4. `tenetrag trace <doc> --html` on the synthetic corpus writes one HTML
   file that opens with no server and shows every step with its inputs
   and outputs, including the planted scope block and the planted bad
   quote (M1).
5. While a document indexes on Postgres or Neo4j, the trace canvas
   shows each finished step and the running step's progress within 5
   seconds of it happening; the M2 spec sets Delta's bound. A
   failed document's trace shows the failing step; a killed run's trace
   shows `interrupted` once the next run takes the lease.
6. `retrieve(..., explain=True)` returns the same result as without it
   and makes no extra store call; the question canvas shows why each
   seed, entity and item is there, and what each limit cut.
7. The benchmark canvas builds its config tree from MLflow tags alone,
   and a wrong question opens in the question canvas with its run's
   configuration.
8. Without WebGL2, a graph of 5,000 nodes or more shows the GPU notice
   and no other console error, and the other three canvases still work.
9. A missing OBO token gives 401 with no service-principal fallback;
   local mode refuses to start without the password variable, or on a
   non-local address without TLS or `--behind-proxy`.

## Open questions

1. **Force-layout library in Python** for 100k nodes without
   communities: permissive licence, a few minutes on a laptop CPU,
   repeatable with a seed. None checked yet. Research before the M6
   spec.
2. **The reference laptop:** which machine, and its real-GPU numbers for
   deck.gl at 100k nodes. The author measures with the prototype.
3. **D3 node drag near the threshold** (15 FPS at 4,999 nodes on the test
   machine). Recommended: redraw only the dragged node's lines and hull,
   not all of them. Not confirmed by the author; settle in the M6 spec.
4. **Raw prompts and replies** as an opt-in to MLflow Tracing:
   undecided, does not block v1. The author decides before M4.
5. **CSP with Next's inline scripts** in a static export: M6 spec.
6. **npm cooldown mechanism** equivalent to uv's 24 hours: M1 spec,
   since Node enters CI there.
7. **How the wheel build runs the frontend build** (a hatch build hook
   or a CI step before `uv build`): M1 spec.
8. **MLflow storage format** for per-question results: M4 spec.
9. **Trace progress on Delta:** a progress write every 2 seconds per
   document makes many small commits. The M2 spec decides whether the
   Delta store buffers progress.
10. **Server-sent events on the Apps proxy:** a spike before replacing
    polling; does not block v1.

## Handoff

- **M1 spec** (`speckit-specify`): the live index trace, `explain`, the
  `cli` module and `trace --html`, with the `frontend/` workspace. The
  engine parts land in the M1 engine spec or a spec of their own.
- **ADRs 0020–0022** record the settled decisions: the app stack
  (FastAPI with a Next.js static export shipped in the wheel, two
  hosting modes, the per-store reading of ADR 0003 and ADR 0009 extended
  to `app`); the 2D renderer split by size with the WebGL2 refusal; the
  live index trace outside the document unit.
- **M4 and M6 specs** take their parts of this brief when those
  milestones start.
