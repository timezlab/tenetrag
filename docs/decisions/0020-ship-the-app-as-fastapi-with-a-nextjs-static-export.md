# Ship the app as FastAPI with a Next.js static export, hosted as a Databricks App or locally

**Status:** accepted
**Date:** 2026-10-11
**Deciders:** Liam Lee (UI brainstorm, 2026-10-06 and 2026-10-07; recorded
in the [app brief](../product/app-brief.md))

## Context
The [platform brief](../product/sdk-platform-brief.md) keeps a full-scope
app in v1: folder browser, plan review, apply, graph view, chat,
retrieval inspector and benchmark runs. The
[app brief](../product/app-brief.md) adds four canvases (whole graph,
question, live index trace, benchmark) that need custom drawing: React
Flow, D3 and deck.gl. The trace canvas is needed in M1, five milestones
before the app, as a single offline file from `tenetrag trace <doc>
--html`.

Constraints that bound the choice:
- The SDK is Python, and users install it with `pip`. Asking them for
  Node at run time would add a second toolchain to every install.
- The app must run as a Databricks App under the viewer's OBO token and
  also on a laptop or a team server outside Databricks.
- Identity fails closed
  ([ADR 0003](0003-caller-supplied-credentials.md)), and the profile
  names credential sources, never secrets
  ([ADR 0018](0018-name-credential-sources-in-the-profile.md)).
- Third-party libraries are permissive, pinned and confined
  ([ADR 0009](0009-reuse-permissive-libraries-behind-adapters.md)).
- One developer maintains everything.

## Decision
1. **Server.** `tenetrag.app` is a FastAPI server in the `app` extra.
   `/api/*` is a thin JSON layer over the public API of `tenetrag` and
   `tenetrag.serving`. The server also serves a Next.js app built with
   `output: 'export'` and `trailingSlash: true`. The wheel carries the
   built files, so nothing runs Node at run time.
2. **Frontend.** `frontend/` is an npm workspace with four parts:
   - `packages/api-types`: TypeScript types generated from the Pydantic
     models;
   - `packages/trace-canvas`: the trace canvas, depending only on React
     and React Flow;
   - `apps/trace-html` (M1): built by Vite and vite-plugin-singlefile
     into one `trace.html` template. The CLI puts the trace JSON into a
     `<script type="application/json">` tag, with `<` escaped as
     `\u003c`;
   - `apps/web` (M6): the Next.js app, which imports the same canvas.
3. **Routes with ids.** Each such route has one static placeholder page,
   `_`. A `StaticFiles` subclass serves `…/<id>/` from `…/_/`, including
   `index.txt`. It rewrites only segments that match `[0-9a-f]+` and
   returns 404 for anything else.
4. **Layers.** The layers are `cli → app → serving`. `cli` uses stdlib
   argparse. `tenetrag app` imports `tenetrag.app.server` only when that
   command runs.
5. **Two hosting modes.**
   - **Databricks App.** The viewer's OBO token comes from
     `x-forwarded-access-token` on every request. A missing token
     returns 401 (`AuthError`) and never falls back to the app's
     service principal. The service principal is used only for a store
     the profile names it for.
   - **Local, `tenetrag app --profile <file>`.** One account logs in
     through ADR 0018's `basic` source (`user` + `password_env`). There
     is no default password, and the server refuses to start when the
     variable is unset. Passwords are compared with
     `hmac.compare_digest`, and login attempts are rate-limited. The
     server binds to `127.0.0.1`. Any other address needs
     `--tls-cert`/`--tls-key` or `--behind-proxy`. Sessions live on the
     server. The cookie is `HttpOnly` and `SameSite=Strict`, and every
     POST passes a same-origin check.
6. **Identity per store.** This is how ADR 0003 applies in the app. The
   profile sets each store's identity: the viewer's OBO token, or a
   named credential. A store in OBO mode never uses a pool opened under
   another identity. Neo4j cannot take an OBO token, so it always uses a
   named credential, and every viewer shares that one read identity. The
   page shows which identity reads each store.
7. **How ADR 0009 applies.**
   - **FastAPI.** ADR 0009 now also allows reuse in `app`. FastAPI, and
     the ASGI server that runs it, are `app`'s framework. The `app`
     module is their adapter boundary: no other module imports them,
     and `app` reaches the SDK only through the public API. All six
     conditions hold.
   - **npm packages.** They meet the same conditions in npm terms:
     - a permissive licence, checked in CI;
     - a committed lockfile;
     - installs with `npm ci --ignore-scripts`;
     - a 24-hour wait before a new version is used, matching uv;
     - no telemetry, so every build sets `NEXT_TELEMETRY_DISABLED=1`
       (Next.js enables telemetry by default; checked in its source on
       2026-10-11);
     - they ship only as built static files.
8. **Writes.** The canvases are read-only. The app writes only to log a
   user in, to apply a reviewed plan, and to start a benchmark run.

## Alternatives considered
- **Streamlit or Dash, with the canvas as a custom component.** Rejected
  for three reasons:
  - the canvas is still JavaScript;
  - Streamlit reruns the script on every interaction, which loses the
    zoom state;
  - `trace --html` could not reuse the component.
- **A full Node/TypeScript app,** in the style of Databricks AppKit.
  Rejected: it means two servers beside a Python SDK.
- **Next.js in server mode.** Rejected: it needs Node at run time beside
  Python. Login, sessions and OBO live in FastAPI, so the frontend needs
  no server of its own.
- **No app, using Neo4j Browser and notebooks instead.** Rejected:
  - Neo4j Browser does not reach the Lakebase, Postgres or Delta
    branches;
  - the author kept the app's full scope on 2026-10-04.
- **One frontend project instead of a workspace.** Rejected by the
  author:
  - `trace-canvas` could import Next.js by accident;
  - M1 could not build the trace canvas before `apps/web` exists.
- **`trace --html` made by packing the Next export into one file.**
  Rejected: Next.js loads chunks through its own runtime, so packing is
  unsupported and breaks on upgrades.
- **`tenetrag trace --serve` instead of one file.** Rejected: sharing a
  trace would need a running process.
- **A default password on first start,** as Grafana does. Rejected: it
  is a sample credential left enabled, so the server refuses to start
  instead.

## Consequences

**Better:**
- One codebase serves both hosting modes, and `pip install
  'tenetrag[app]'` is enough to run it.
- The trace canvas is written once and used in two places: the offline
  file in M1 and the app in M6.
- Login, sessions and OBO live in one Python module, `app.security`,
  where the fail-closed rules of ADR 0003 are tested.

**Worse:**
- A second language and two build tools (Vite and Next.js) for one
  maintainer. CI needs Node from M1.
- A static export has no server rendering and no rewrites. The
  placeholder rewrite is our code to maintain.
- Next.js export pages use inline scripts, so a strict CSP is not solved
  yet. The M6 spec settles it.
- With Neo4j, viewers of a Databricks App share one read identity. They
  are not separated per user.
- A wheel built from source without the frontend has no canvases.
  `tenetrag trace --html` then fails and prints the build command.

**Must now be true:**
- Only modules under `tenetrag.app` import `fastapi` or the ASGI
  server. An import-linter contract enforces this once `app` exists.
- `tenetrag.app` imports no `tenetrag` module except `serving`'s public
  API and the names `tenetrag` re-exports.
- `tests/app` asserts three things:
  - a request without `x-forwarded-access-token` gets 401 in Databricks
    App mode, and no store call runs;
  - `tenetrag app` exits non-zero when the password variable is unset;
  - `tenetrag app` exits non-zero on a non-local address without TLS or
    `--behind-proxy`.
- The static rewrite returns 404 for any id segment that does not match
  `[0-9a-f]+`.
- `HEAD /` returns 200 even when `src/tenetrag/app/static/` is empty.
- `src/tenetrag/cli/assets/trace.html` and `src/tenetrag/app/static/`
  are gitignored. CI builds both before `uv build`.
- Every frontend build runs `npm ci --ignore-scripts` with
  `NEXT_TELEMETRY_DISABLED=1`. `frontend/package-lock.json` is
  committed.
- `packages/api-types/types.gen.ts` matches the Pydantic models, and CI
  fails on drift.

## Revisit if
- Databricks ships a fail-closed, per-request identity primitive for
  Python apps that would replace our OBO handling.
- Next.js drops or breaks `output: 'export'`, or a needed feature
  requires server rendering.
- An adopter needs separate per-user read identities on Neo4j.
