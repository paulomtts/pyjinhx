# ADR 0004: Graph engine reconciles on DOM mutation, not on a resync call

**Status:** Accepted, 2026-10-12. Unreleased.

## Context

The `PJXGraph*` builtins port the graph kit from Nori, a pan/zoom canvas of
node cards joined by edges. Two things made that kit hard to reuse. It read a
global `d3`, so every app had to load d3 itself, at a version the kit agreed
with. And it learned about server updates only when told: after every swap the
app had to call `resyncNodes`, and follow a "one `react=` key" rule so that a
swap never replaced more than the kit expected.

In pyjinhx the graph parts are plain `BaseComponent`s, and htmx may swap any of
them: the whole node layer, one node out-of-band, one edge, or a fragment
streamed over SSE. The engine cannot know which of those happened, or when.

## Decision: reconcile on mutation

Each mounted stage watches its `.pjx-graph__viewport` with a
`MutationObserver` (`childList`, `subtree`, and the `data-x`, `data-y`,
`data-from`, `data-to`, `data-port`, `data-state` and `data-label`
attributes). However many records a swap makes, they schedule one
`reconcile()` in the next animation frame. Changes inside the edge planes are
the engine's own drawing and are ignored, so a redraw does not schedule the
next one.

`reconcile()` is idempotent. It places every node whose `data-x`/`data-y`
differ from the pair it was last placed with, keyed by element identity, so a
swapped-in element is always placed and a kept, unmoved one is left alone. Then
it redraws every edge. Pointer and click listeners are delegated to the canvas,
so there is nothing to bind on a new node or unbind from a removed one.

The viewport is observed, not the node layer, because the viewport is the one
part no update shape replaces. Replacing the node layer is just another
mutation inside it.

A swap that lands while a node or a wire is being dragged marks the stage
dirty instead of moving things under the pointer. Releasing the drag ends the
gesture and runs one reconcile.

A second observer on the document mounts any stage root that appears and stops
any that leaves, so a swapped stage root boots on its own and, with a
`storage_key`, restores its pan/zoom view from storage instead of refitting.

## Decision: one child element per edge

`PJXGraphEdges` renders one hidden `span[data-pjx-graph-edge]` per edge, with
`data-edge-id`, `data-from`, `data-to`, `data-port`, `data-state` and
`data-label`. One edge can then be swapped out-of-band like any element, and
every edge change, added, removed or edited, is a mutation the observer sees.

Every reconcile redraws all edges rather than tracking which pairs changed.
Measured at about 15 ms for 200 edges between 50 nodes, before node lookups
were indexed once per redraw, the cost did not justify per-pair bookkeeping.

## Decision: persist the position base

When the user drops a node, the engine stores `{x, y, base}`, where `base` is
the node's server `data-x`/`data-y` at drag time, in localStorage under
`pjx-graph:<storage_key>`. The drop holds as long as the server keeps sending
that base. Once the server sends a different position, the server wins and the
stored drop is deleted. The base is persisted, not kept in memory, so the rule
holds after a full page load. With an empty `storage_key` nothing is stored. A
drop holds on the page until the server moves that node and is gone on reload.

## Decision: bundle a pinned d3 subset

`scripts/vendor_d3_zoom.py` vendors d3-selection 3.0.0, d3-zoom 3.0.0 and their
dependencies (d3-dispatch, d3-drag, d3-interpolate, d3-color, d3-transition,
d3-timer, d3-ease), with their ISC licence header, into
`pjx_graph/src/d3.vendor.js` (51,799 bytes, under a 60 KB target). A component
has exactly one `js_path`, so `scripts/build_pjx_graph_js.py` concatenates that
file with `pjx_graph/src/engine.js` into the committed `pjx_graph.js`, and a
test fails if the committed file is stale. The app loads nothing, and the
engine neither reads nor writes a global `d3`.

## Rejected: a `resync()` call after each swap

The Nori way: the app calls the engine after every swap that touched the
graph. Every app has to learn when to call it, a missed call fails silently
with stale positions or edges, and out-of-band and SSE swaps have no natural
place to make the call.

## Rejected: observing the node layer

Watching `.pjx-graph__nodes` directly would be narrower, but the most common
update shape replaces that element, which would leave the observer attached to
a detached node and blind to everything after.

## Rejected: edges as one JSON attribute or `<script>` blob

A single blob is simpler to render, but one edge could no longer be swapped on
its own, and every change would mean diffing the whole blob to find what moved.

## Rejected: keeping the position base in memory

Without the base on disk, the rule cannot be applied after a reload. The
engine would either let a stale drop win over a newer server position, or
throw away a drop that is still valid.

## Rejected: requiring the app to load d3

Two copies or two versions of d3 on one page clash, and every app pays an
extra setup step for a dependency it never uses directly.

## Consequences

- Apps never call the engine after a swap. Any htmx swap shape works,
  including out-of-band swaps and SSE.
- A swap during a drag shows on release, not immediately.
- Every reconcile redraws every edge.
- The engine never sends positions to the server. Apps that persist them
  listen for `pjx:graph:move`.
- The graph's JS asset is about 93 KB unminified.
- Upgrading d3 means rerunning `scripts/vendor_d3_zoom.py` and then
  `scripts/build_pjx_graph_js.py`.

## Related

- [Graph](../guide/graph.md) — the components, events and JavaScript API.
- [Updating the graph](../guide/graph.md#updating-the-graph) — the update
  shapes this reconcile model supports.
- [Positions and persistence](../guide/graph.md#positions-and-persistence) —
  the app-facing statement of the position rule.
- [Builtin conventions](../guide/builtin-conventions.md) — the contract every
  builtin follows.
- [ADR 0003](0003-builtin-css-ordering.md) — the CSS ordering the graph's
  stylesheet relies on.
