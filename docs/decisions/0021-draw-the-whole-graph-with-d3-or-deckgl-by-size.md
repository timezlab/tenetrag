# Draw the whole graph in full with D3 below 5,000 nodes and deck.gl from 5,000, and refuse without WebGL2

**Status:** accepted
**Date:** 2026-10-11
**Deciders:** Liam Lee (UI brainstorm, 2026-10-07; recorded in the
[app brief](../product/app-brief.md))

## Context
The whole-graph canvas of the [app brief](../product/app-brief.md)
must open a 100k-node graph in under 2 seconds and stay at 30 FPS or more
while zooming and panning on a reference laptop. Other requirements:
- 2D is the main view and 3D an advanced one.
- Nodes of one community sit together, coloured by community or by type.
- A graph that has not been clustered is still drawn in full.

A throwaway renderer prototype measured the options on a server CPU with
software rendering:
- **D3 with SVG, every node drawn.** At 2,000 nodes it zooms at 32 FPS.
  At 4,999 nodes it zooms at 20 FPS and drags a node at 15 FPS. Panning
  stays at 60 FPS.
- **A D3 bubble overview.** Communities open level by level, and never
  more than 3,000 circles and 4,000 lines are drawn. It ran at 60 FPS at
  100k nodes, but it needs a separate open-and-close logic per level.
- **deck.gl 9.4.0 (MIT), every node drawn.** Each layer is one instanced
  draw call, and the canvas redraws only on interaction. At 100k nodes it
  drew in 1–3 seconds even on CPU renderers. Real-GPU numbers are not
  measured yet.

Chrome 139 and later and Edge 144 and later no longer fall back to
software WebGL when there is no GPU. They do so only if IT sets the
temporary `EnableUnsafeSwiftShader` policy (checked 2026-10-07,
[Edge policy](https://learn.microsoft.com/en-us/deployedge/microsoft-edge-browser-policies/enableunsafeswiftshader)).
On a virtual desktop without a GPU, WebGL does not run at all.

Laying out 100k nodes in the browser cannot finish in 2 seconds, and
nothing runs Node on the server
([ADR 0020](0020-ship-the-app-as-fastapi-with-a-nextjs-static-export.md)).

## Decision
1. **Renderer by size, and every node is always drawn.**
   - **Below 5,000 nodes:** D3 with SVG. It draws community hulls when
     communities exist. Nodes can be dragged for the current view, and
     nothing is saved.
   - **From 5,000 nodes:** deck.gl on WebGL2. 2D uses
     `OrthographicView`. Nodes come from binary typed arrays, not JSON.
     Only light layers change with zoom:
     - community circles per level;
     - summed links between communities when far, real edges when near;
     - community labels when far, node labels when near, with overlaps
       removed.
   - The threshold is one named constant, `WEBGL_MIN_NODES` (5,000).
     Before each release, D3 at 4,999 nodes must zoom and pan at 30 FPS
     or more on the reference laptop. Otherwise the constant is lowered
     to a size that passes.
2. **3D,** at any size, uses deck.gl `OrbitView` on the same x and y.
   z is lifted per community level, so each community is a ball inside
   its parent's ball. 3D needs communities. Without them the 3D button
   is off and says why.
3. **No WebGL2 refuses, and nothing is drawn in part.** A graph of
   5,000 nodes or more without WebGL2 shows a notice: this browser has
   no GPU access, so the graph cannot be drawn. The notice names the
   Chrome and Edge change as the reason. A WebGL context lost while
   drawing is recreated once. If that fails, the same notice appears.
   - Only the whole-graph canvas refuses. The question, trace and
     benchmark canvases do not use WebGL. They work on any machine.
4. **Positions are computed in Python and stored.**
   - **Module.** A `layout` module outside the engine computes the
     positions. It imports protocols and `config` only.
   - **Storage.** It writes `layout_positions` through
     `GraphStore.put_positions`, keyed by the clustering run id. With no
     communities, the key is the index run id.
   - **With communities:** nested circles per level (a port of d3's
     `packSiblings`), with a small force between top-level communities.
     No force runs on the nodes themselves.
   - **Without communities:** a force layout over the whole graph. The
     library is chosen in the M6 spec. It sits behind an adapter in
     `layout` and meets the six conditions of
     [ADR 0009](0009-reuse-permissive-libraries-behind-adapters.md),
     which now also allows reuse in `layout`. It lives in the
     `communities` extra.
   - **When it runs.** `serving` runs it after `apply` whenever the
     `communities` extra is installed. For an index built without that
     extra, `client.graph.compute_layout()` runs it.
   - **Re-index.** Existing nodes keep their place, and only new nodes
     are placed.
   - **No stored positions.** A graph below 5,000 nodes is laid out in
     a web worker.
5. **D3 stays** for the question canvas and the benchmark map, which are
   small and need sharp text.

## Alternatives considered
- **The D3 bubble overview as the main 2D view for large graphs.**
  Replaced by deck.gl drawing every node. deck.gl gives one drawing path
  with or without communities, keeps every node visible, and removes the
  per-level open-and-close logic.
- **deck.gl at every size.** Rejected:
  - small graphs would need a GPU for no gain;
  - SVG text is sharper than deck.gl's font atlas.
- **Without WebGL2, fall back to the bubble overview (option A).**
  Rejected by the author: it keeps a second drawing mode alive only for
  machines without a GPU.
- **Without WebGL2, search or pick a community, then draw that part
  with D3 (option B).** The author chose it first, then replaced it
  with refusal: a partial view of a large graph is not the whole-graph
  canvas.
- **Without WebGL2, tell users to ask IT for
  `EnableUnsafeSwiftShader` (option C).** Rejected:
  - the policy is temporary;
  - software WebGL ran at about 1 FPS at 100k nodes.
- **vis-network** for 2D. Rejected:
  - community regions still have to be drawn by hand;
  - it fits React poorly;
  - it had the slowest first draw of the libraries tried.
- **3d-force-graph** for 3D. Rejected:
  - it creates one three.js object per node and link, about 4,900 draw
    calls at 2,000 nodes;
  - it redraws continuously.
- **Layout in the browser for every size.** Rejected: 100k nodes cannot
  open in 2 seconds.

## Consequences

**Better:**
- Every node is always on screen, and the same code path serves graphs
  with and without communities.
- 2D and 3D share layers, positions, picking and the inspector.
- The browser does no layout work for large graphs, so opening is a
  download and one draw.

**Worse:**
- One canvas has two renderers to maintain and test.
- Staff on a virtual desktop without a GPU cannot see a large graph at
  all. Such desktops are common in regulated organizations.
- deck.gl labels come from a font atlas and are less sharp than SVG.
- A binary payload format to define and version.
- The layout adds time to every `apply` that has the `communities`
  extra. The force library for unclustered graphs is not chosen yet.
- The 30 FPS target on a real GPU is not measured yet.

**Must now be true:**
- `WEBGL_MIN_NODES` is the only place the threshold appears.
- A Playwright test runs Chromium with `--disable-3d-apis` on a graph of
  5,000 nodes or more. It expects the GPU notice and no other console
  error.
- `tenetrag.layout` imports only `tenetrag.protocols` and
  `tenetrag.config`, and `tenetrag.engine` never imports it. The
  import-linter layers enforce both.
- `layout_positions` rows carry the run id they were computed for, and
  the canvas never mixes positions from two run ids.

## Revisit if
- The reference laptop misses 30 FPS with deck.gl at 100k nodes.
- Most of an adopter's users turn out to lack GPU access.
- Chrome or Edge restores a software WebGL fallback, or WebGPU changes
  the renderer choice.
