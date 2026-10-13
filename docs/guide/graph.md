# Graph

The graph builtins render a pan/zoom node graph: draggable node cards joined by edges, with zoom
controls and a side panel. Everything ships with the components, including the small d3 subset the
engine uses, so the app supplies no script or stylesheet. The engine is headless. It draws, pans,
zooms, drags and selects, then reports what the user did as `pjx:graph:*` events. What happens next
(creating an edge, opening the panel, saving a position) is up to the app.

## Quick start

```python
from fastapi import FastAPI

from pyjinhx import setup
from pyjinhx.builtins import (
    PJXGraph,
    PJXGraphControls,
    PJXGraphEdges,
    PJXGraphNode,
    PJXGraphNodes,
    PJXGraphSidePanel,
)

app = FastAPI()
setup(app)


def flow_graph() -> PJXGraph:
    nodes = [
        PJXGraphNode(
            id="node-a", node_id="a", x=40, y=60, title="Fetch", out_ports=("next",)
        ),
        PJXGraphNode(
            id="node-b", node_id="b", x=320, y=60, title="Store", in_port=True
        ),
    ]
    return PJXGraph(
        id="flow",
        storage_key="flow",
        nodes=PJXGraphNodes(
            id="flow-nodes",
            nodes_html=PJXGraphNodes.join(node.render() for node in nodes),
        ),
        edges=PJXGraphEdges(
            id="flow-edges",
            edges=[{"id": "a-b", "from": "a", "to": "b", "port": "next"}],
        ),
        controls=PJXGraphControls(),
        panel=PJXGraphSidePanel(id="flow-panel"),
    )


@app.get("/flow")
def flow():
    return flow_graph()
```

There is no script call. The engine mounts every `[data-pjx-graph]` stage when the page loads, when a
stage is inserted later (by an htmx swap or plain DOM code), and on `htmx:load`. A stage removed
from the document is unmounted. Once a stage is mounted, and has drawn its edges (after the first fit, or the restore of a stored view),
its root gets `data-pjx-graph-ready`.

The canvas spans the width of its container and is at least `--pjx-graph-min-height` (24rem) tall.
For a taller stage, raise that token or give `.pjx-graph__canvas` a height. A stage that is hidden
when it mounts has no size to frame its nodes against. Press **Fit** (or call `fit()`) once it shows.

Give the stage, both layers and the panel stable ids. The update shapes below target them.

## Components

Every component also takes `id`, `class_name` and `extra_attrs`, as described in
[Builtin conventions](builtin-conventions.md#the-contract). The tables below list the other props.
Text props are escaped. `Slot` props and the panel's `content` render raw HTML.

### PJXGraph

The stage: canvas, viewport, edge plane, and the slots for the layers, the controls and the panel.

| Prop | Type | Default | Notes |
|---|---|---|---|
| `nodes` | `Slot` | required | The node layer. It must contain a `PJXGraphNodes`: the engine needs its `.pjx-graph__nodes`. |
| `edges` | `Slot` | `""` | The edge layer, normally a `PJXGraphEdges`. |
| `controls` | `Slot` | `""` | Normally a `PJXGraphControls`. Floats over the canvas. |
| `panel` | `Slot` | `""` | Normally a `PJXGraphSidePanel`. Renders as a sibling after the canvas, outside it, so clicks in the panel never pan, drag or select. |
| `storage_key` | `str` | `""` | Names the browser record for the view and dropped positions. `""` means nothing persists. See *Positions and persistence* below. |
| `scale_min` | `float` | `0.2` | Smallest zoom. Must be finite and greater than 0. |
| `scale_max` | `float` | `2.0` | Largest zoom. Must be finite and greater than 0. |
| `aria_label` | `str` | `"Graph"` | The root's `aria-label`. The root has `role="group"`. |

`PJXGraph(id="g", nodes=layer, scale_min=3, scale_max=1)` raises a `pydantic.ValidationError`
(a `ValueError`): `scale_min` must not exceed `scale_max`.

### PJXGraphNodes

The node layer: one container that holds the node markup.

| Prop | Type | Default | Notes |
|---|---|---|---|
| `nodes_html` | `Slot` | `""` | Rendered node markup, raw. |

`PJXGraphNodes.join(parts) -> Markup` concatenates already-rendered node markup in order without
escaping it. Pass it the strings `PJXGraphNode(...).render()` returns. The layer root renders even
when it is empty, so it is always there as a swap target.

### PJXGraphNode

One node card, absolutely positioned at `(x, y)` in world pixels.

| Prop | Type | Default | Notes |
|---|---|---|---|
| `node_id` | `str` | required | Non-empty. The id that edges, selection and events use (`data-node-id`). |
| `x` | `float` | required | Finite. Written to `data-x`. |
| `y` | `float` | required | Finite. Written to `data-y`. |
| `node_type` | `str` | `""` | Written to `data-node-type`, for the app's CSS and JS. |
| `title` | `str` | required | The card's title. |
| `eyebrow` | `str` | `""` | A small line above the title. Omitted when empty. |
| `summary` | `str` or `None` | `None` | `None` omits the summary `<p>`. `""` renders an empty one. |
| `color` | `str` | `""` | Sets `--pjx-graph-node-color` (the left border and the icon). Must not contain `;`. |
| `icon` | `Slot` | `""` | Raw HTML shown before the body. |
| `in_port` | `bool` | `False` | Renders the in-port handle on the left edge. |
| `out_ports` | `tuple[str, ...]` | `()` | One out-port handle per key, spread down the right edge. Keys must be non-empty and unique. |

`node_id` is required: the node needs it to be selected, joined by edges, or named in an event.
A non-finite `x`/`y` (`nan`, `inf`), an empty `node_id`, an empty or repeated `out_ports` key, a
`color` that contains `;`, or a `node_id`, `node_type`, `color` or `out_ports` key that contains a
double quote (`"`) raises a validation error.

### PJXGraphEdges

The edge layer: one hidden `<span data-pjx-graph-edge>` per edge. The engine reads the spans and
draws the visible edges in the SVG edge plane. Nothing in this layer is visible itself.

| Prop | Type | Default | Notes |
|---|---|---|---|
| `edges` | `list[dict[str, str]]` | `[]` | One dict per edge. Keys are below. |

| Key | Required | Notes |
|---|---|---|
| `id` | yes | Non-empty and unique in the layer. Written to `data-edge-id`. |
| `from` | yes | Non-empty. The source `node_id`. |
| `to` | yes | Non-empty. The target `node_id`. |
| `port` | no | The source's out-port key. With no matching port, the edge leaves from the middle of the source's right edge. |
| `state` | no | A single class token. The drawn edge gets `pjx-graph__edge--<state>`. A state with whitespace in it gets no class. |
| `label` | no | Text drawn along the edge. Always shown as text, never markup. |

An edge dict raises a validation error when `id`, `from` or `to` is missing or empty, when it has a
key outside the six above, when its `id` repeats another edge's, or when `id`, `from`, `to`, `port`
or `state` contains a double quote (`"`). An edge whose `from` or `to` node is missing, or hidden with
`display: none`, is not an error. It is skipped silently and drawn at the next reconcile after both ends show. If you reveal a node
by changing its class or style rather than by a swap, call `drawEdges()`. Edges between
the same two nodes fan apart, in either direction.

### PJXGraphControls

Zoom in, zoom out and fit buttons that float over the canvas. They work only inside a mounted
`PJXGraph`.

| Prop | Type | Default | Notes |
|---|---|---|---|
| `zoom_in_label` | `str` | `"Zoom in"` | Button text, and its `aria-label`. |
| `zoom_out_label` | `str` | `"Zoom out"` | Button text, and its `aria-label`. |
| `fit_label` | `str` | `"Fit"` | Button text, and its `aria-label`. |
| `aria_label` | `str` | `"Graph controls"` | The group's `aria-label`. |

### PJXGraphSidePanel

A floating card beside the canvas: a header and one content region.

| Prop | Type | Default | Notes |
|---|---|---|---|
| `title` | `str` | `""` | The header's `<h2>`. |
| `aria_label` | `str` | `"Graph panel"` | The `<aside>`'s `aria-label`. |
| `marker` | `bool` | `False` | Shows a dot in the accent color before the title. |
| `accent_color` | `str` | `""` | Sets `--pjx-graph-panel-accent`. Must not contain `;`. |
| `badge` | `Slot` | `""` | Raw HTML after the title. |
| `back_label` | `str` | `"Back"` | Back button text, and its `aria-label`. The button always renders `hidden`. The engine shows it when there is history to go back to. |
| `close_label` | `str` | `"Close"` | Close button text, and its `aria-label`. |
| `open` | `bool` | `False` | Sets `data-open`. A closed panel is hidden by the stylesheet. |
| `content` | children | `""` | The content region, raw HTML. It renders whether the panel is open or not. |

An `accent_color` that contains `;` or a double quote (`"`) raises a validation error.
Opening the panel is the app's job; see [Events and JavaScript API](#events-and-javascript-api).

## Interaction

- **Wheel** zooms anywhere over the canvas, about the pointer. The page does not scroll under the canvas.
- **Pressing empty canvas** and dragging pans. Double-click does not zoom.
- **Dragging a node** moves it. A press that starts on a port, a form control, a button, a link or
  editable content does not drag, and neither does a node without a valid `data-x`/`data-y`.
  Dropped positions are whole pixels.
- **Dragging from an out-port** draws a dashed wire. Releasing it over another node of the same
  stage fires `pjx:graph:wire`. Releasing it on the source node or on empty canvas cancels.
- **Clicking a node** selects it. **Clicking an edge** selects the edge. **Clicking empty canvas**
  clears the selection. One node or one edge is selected at a time. The click that ends a drag
  does not select.
- **Controls**: zoom in and zoom out step by a factor of √2 about the canvas center. Fit frames
  every visible node.
- Nodes and edges are not keyboard-focusable, so selection is pointer-only. For keyboard use, drive
  `select(id)` and `pjx.graph.panel.open` from your own controls.
- Zoom always stays within `scale_min..scale_max`. A fresh stage frames its nodes once it is laid
  out, unless it restores a stored view.

## Events and JavaScript API

### Event list

Every event is dispatched on the stage root and bubbles. A `before-*` event is cancelable:
`event.preventDefault()` stops the change. `detail` carries ids, never domain data, so graph
`before-*` events carry `{id}`, not the `{reason, trigger}` of other builtins. The node and edge
attributes (`data-node-id`, `data-x`, `data-from` and so on) keep their unprefixed names, as they
are data fields.

| Event | `detail` | Cancelable | Fired when |
|---|---|---|---|
| `pjx:graph:before-select` | `{id}` | yes | A node is about to be selected, by click or `select(id)`. |
| `pjx:graph:select` | `{id}` | no | A node was selected. |
| `pjx:graph:before-select-edge` | `{id}` | yes | An edge is about to be selected by click. |
| `pjx:graph:select-edge` | `{id}` | no | An edge was selected. |
| `pjx:graph:deselect` | `null` | no | The selection was cleared by a background click or `deselect()`. |
| `pjx:graph:move` | `{id, x, y}` | no | A node was dropped after a drag. `x`/`y` are world pixels. |
| `pjx:graph:wire` | `{from, port, to}` | no | A wire from `from`'s out-port `port` was released over node `to`. |
| `pjx:graph:rendered` | `null` | no | Edges were drawn: on mount, after each reconcile, and on `drawEdges()`. |
| `pjx:graph:panel:open` | `{id}` | no | `panel.open(root, id)` showed `id`, or `panel.back(root)` went back to `id`. |
| `pjx:graph:panel:before-close` | `{id}` | yes | The panel is about to close. `id` is the shown id, or `null` when the server rendered the panel open and nothing was opened since. |
| `pjx:graph:panel:close` | `{id}` | no | The panel closed. `id` as for `before-close`. |

Selecting the item that is already selected changes nothing and fires nothing.

### `window.pjx.graph`

| Call | Returns | Throws |
|---|---|---|
| `pjx.graph.mount(root)` | The stage instance. A stage that is already mounted returns its instance. | When `root` is not a `[data-pjx-graph]` element, when the stage is missing its canvas, viewport, edge plane or node layer, or when its scale range is invalid. |
| `pjx.graph.get(root)` | The instance, or `null` if `root` is not mounted. | Never. |
| `pjx.graph.panel.open(root, id)` | `true`. Opening the id that is already shown changes nothing. | When `id` is not a non-empty string. |
| `pjx.graph.panel.back(root)` | `true`, or `false` when there is no earlier id to go back to. | |
| `pjx.graph.panel.close(root)` | `true` (also when already closed), or `false` when `before-close` was canceled. | |

All three `panel.*` calls also throw when `root` is not a mounted stage, or when it has no panel as a
direct child. `mount()` is rarely needed, since stages boot on their own. Each stage keeps its
panel history (the ids opened, newest last) until the panel closes. Back pops it, and the back
button shows only when there is somewhere to go back to.

The instance from `mount()`/`get()` has:

| Member | Does |
|---|---|
| `root` | The stage root element. |
| `select(id)` | Selects node `id`. Returns `false` if `before-select` was canceled, `true` otherwise. Throws when `id` is not a string or names no node. |
| `deselect()` | Clears the selection and fires `deselect`. Does nothing when nothing is selected. |
| `fit()` | Frames every visible node. |
| `zoomBy(dir)` | Zooms `dir` steps of √2 about the canvas center (`1` in, `-1` out). Throws when `dir` is not a finite number. |
| `drawEdges()` | Redraws every edge and fires `rendered`. |
| `reconcile()` | Places nodes whose `data-x`/`data-y` changed and redraws every edge, as a swap does. Held while a drag or wire is in progress. |
| `box(id)` | `{x, y, width, height}` of node `id` in world pixels, or `null`. |
| `inAnchor(id)` | `{x, y}` where edges enter node `id`, or `null`. |
| `outAnchor(id, port)` | `{x, y}` where edges leave node `id` from `port`, or `null`. |

### Wiring the app

The engine never creates an edge on `wire`, and the panel never opens on `select`. Both are the
app's decisions. This is all the script an app needs for both:

```js
document.addEventListener("pjx:graph:select", (event) => {
  pjx.graph.panel.open(event.target, event.detail.id);
});

document.addEventListener("pjx:graph:panel:open", (event) => {
  htmx.ajax("GET", "/flow/panel/" + encodeURIComponent(event.detail.id), {
    target: "#flow-panel [data-pjx-graph-panel-content]",
    swap: "innerHTML",
  });
});

document.addEventListener("pjx:graph:wire", (event) => {
  htmx.ajax("POST", "/flow/edges", { values: event.detail, swap: "none" });
});
```

`event.target` is the stage root, because every event is dispatched there. The `/flow/edges` route
stores the edge, and the server swaps the edge layer back with any shape from
[Updating the graph](#updating-the-graph). The new edge is drawn without further script.

## Positions and persistence

A node shows at its server `data-x`/`data-y` unless the user dropped it somewhere else. With a
`storage_key`, the engine keeps one browser record under the localStorage key
`pjx-graph:<storage_key>`. It holds the last pan/zoom view, and each dropped node's position together
with the server position it was dragged from (its base).

- On mount, a stored view is restored (clamped to the current zoom range) instead of fitting.
- A stored drop holds as long as the server keeps sending that node's base position.
- Once the server sends a different position, the server wins and the stored drop is deleted. A
  later return to the old position does not bring it back.
- With an empty `storage_key`, nothing is stored. A drop lives only on the node element: it holds
  while that element stays in the page and the server does not move it. A swap that replaces the
  node (or its layer) puts it back at the server position, and a reload forgets it.

The engine never sends positions to the server. To persist them, listen for `pjx:graph:move` and post
`detail.x`/`detail.y` yourself. A broken or full localStorage never breaks the stage; it just
stops persisting.

## Updating the graph

Every update shape is a plain htmx swap of server-rendered markup. The engine watches its viewport
and reconciles after any swap in a layer, or a change to a node's `data-x`/`data-y` or an edge's
`data-from`, `data-to`, `data-port`, `data-state` or `data-label`: it places the nodes whose server
position changed and redraws every edge. No JavaScript call is needed. A swap that lands while the
user is dragging a node or a wire is applied when the drag ends, so nothing moves under the
pointer. The selection survives a swap as long as the selected id is still there. If that id disappears,
no `deselect` fires; the selection is kept and shows again if the id comes back.

### Reload the whole layer

Make a layer reactive by subclassing it into a `ReactiveComponent`, as in
[Making builtins reactive](../reactivity.md#making-builtins-reactive). Every mutation that dirties its
key re-renders the whole layer out-of-band.

```python
from typing import Annotated

from fastapi import Form

from pyjinhx import MutationKey, ReactiveComponent, mutates
from pyjinhx.builtins import PJXGraph, PJXGraphEdges, PJXGraphNode, PJXGraphNodes


class Keys(MutationKey):
    FLOW = "flow"


class FlowNodes(ReactiveComponent, PJXGraphNodes, react={Keys.FLOW}):
    @classmethod
    def load(cls) -> "FlowNodes":
        return cls(
            id="flow-nodes",
            nodes_html=cls.join(
                PJXGraphNode(
                    id=f"node-{n.id}", node_id=n.id, x=n.x, y=n.y, title=n.title
                ).render()
                for n in db.flow_nodes()
            ),
        )


class FlowEdges(ReactiveComponent, PJXGraphEdges, react={Keys.FLOW}):
    @classmethod
    def load(cls) -> "FlowEdges":
        return cls(id="flow-edges", edges=db.flow_edges())


@mutates(Keys.FLOW)
def connect(source: str, port: str, target: str) -> None:
    db.insert_edge(source, port, target)


@app.get("/flow")
def flow():
    return PJXGraph(id="flow", nodes=FlowNodes.load(), edges=FlowEdges.load())


@app.post("/flow/edges")
def add_edge(
    source: Annotated[str, Form(alias="from")],
    target: Annotated[str, Form(alias="to")],
    port: Annotated[str, Form()] = "",
):
    connect(source, port, target)
    return None
```

Both layers mount with stable ids (`flow-nodes`, `flow-edges`), so the reactive fan-out can find
them. `PJXGraphEdges` subclasses the same way `PJXGraphNodes` does. The trigger is the `wire`
listener from [Wiring the app](#wiring-the-app), or any htmx element:

```html
<button hx-post="/flow/edges" hx-vals='{"from": "a", "port": "next", "to": "b"}' hx-swap="none">
  Connect
</button>
```

The route returns `None`, so the response carries only the out-of-band legs: both layers, re-rendered
from `load()`. FastAPI's `Form` needs the `python-multipart` package.

### Swap one node out-of-band

To change one node without re-rendering the layer, return that node with `hx-swap-oob` next to the
route's primary response:

```python
from pyjinhx import render
from pyjinhx.builtins import PJXBadge, PJXGraphEdges, PJXGraphNode


@app.post("/flow/nodes/{node_id}/run")
def run_node(node_id: str):
    n = db.run(node_id)
    node = PJXGraphNode(
        id=f"node-{n.id}",
        node_id=n.id,
        x=n.x,
        y=n.y,
        title=n.title,
        summary=n.status,
        out_ports=("next",),
        extra_attrs={"hx-swap-oob": "true"},
    )
    return render(PJXBadge(id="run-status", label=f"Ran {n.title}")) + render(node)
```

```html
<button hx-post="/flow/nodes/a/run" hx-target="#run-status" hx-swap="outerHTML">Run</button>
<span id="run-status"></span>
```

The node needs a stable `id` (here `node-<node_id>`), the same on the page and in the response. The
swap is outerHTML-only: the whole node element is replaced. See
[ADR 0001](../decisions/0001-outerhtml-only-oob-swaps.md). To add or remove a node, swap the whole
`PJXGraphNodes` layer instead.

Adding or removing an edge works the same way: swap the whole `PJXGraphEdges` layer.

```python
@app.delete("/flow/edges/{edge_id}")
def delete_edge(edge_id: str):
    db.delete_edge(edge_id)
    return PJXGraphEdges(
        id="flow-edges", edges=db.flow_edges(), extra_attrs={"hx-swap-oob": "true"}
    )
```

```html
<button hx-delete="/flow/edges/a-b" hx-swap="none">Remove edge</button>
```

### Stream updates over SSE

To push changes the user did not ask for, stream out-of-band fragments over server-sent events. Load
the htmx 2 SSE extension yourself, since pyjinhx does not ship it:

```html
<script src="https://unpkg.com/htmx-ext-sse@2/sse.js"></script>
```

Wrap the graph in an element that connects to the stream, and give it a hidden sink that receives
each `graph` event. The sink's content is thrown away; the out-of-band fragments in it land on their
targets.

```html
<div hx-ext="sse" sse-connect="/graph/stream">
  <!-- the PJXGraph stage renders here -->
  <div hidden sse-swap="graph"></div>
</div>
```

```python
from fastapi.responses import StreamingResponse

from pyjinhx import render
from pyjinhx.builtins import PJXGraphEdges, PJXGraphNode


@app.get("/graph/stream")
async def graph_stream():
    async def events():
        async for change in db.flow_changes():
            fragments = [
                render(
                    PJXGraphNode(
                        id=f"node-{n.id}",
                        node_id=n.id,
                        x=n.x,
                        y=n.y,
                        title=n.title,
                        extra_attrs={"hx-swap-oob": "true"},
                    )
                )
                for n in change.nodes
            ]
            if change.edges_changed:
                fragments.append(
                    render(
                        PJXGraphEdges(
                            id="flow-edges",
                            edges=db.flow_edges(),
                            extra_attrs={"hx-swap-oob": "true"},
                        )
                    )
                )
            lines = "".join(fragments).splitlines()
            yield "event: graph\n" + "".join(f"data: {line}\n" for line in lines) + "\n"

    return StreamingResponse(events(), media_type="text/event-stream")
```

One event can update any number of nodes and the edge layer, since every fragment carries its own
`hx-swap-oob`. Each message is framed as SSE `data:` lines. See
[HTMX: Server-Sent Events and WebSockets](../integrations/htmx.md#server-sent-events-and-websockets)
and htmx's [SSE extension](https://htmx.org/extensions/sse/).

## Theming

The graph reads these `--pjx-graph-*` tokens, set on `:root` by default. Override them globally or
on one stage, as described in [Builtin conventions](builtin-conventions.md#theming).

| Area | Tokens |
|---|---|
| Stage | `--pjx-graph-bg`, `--pjx-graph-border`, `--pjx-graph-radius`, `--pjx-graph-grid-color`, `--pjx-graph-grid-size`, `--pjx-graph-min-height` |
| Edges | `--pjx-graph-edge-stroke`, `--pjx-graph-edge-width`, `--pjx-graph-edge-hit-width`, `--pjx-graph-edge-label-color`, `--pjx-graph-edge-label-size`, `--pjx-graph-wire-stroke`, `--pjx-graph-wire-dash` |
| Selection | `--pjx-graph-selected` |
| Nodes | `--pjx-graph-node-bg`, `--pjx-graph-node-border`, `--pjx-graph-node-radius`, `--pjx-graph-node-width`, `--pjx-graph-node-muted`, `--pjx-graph-port-size`, `--pjx-graph-port-bg` |
| Controls | `--pjx-graph-controls-bg`, `--pjx-graph-controls-border`, `--pjx-graph-controls-radius`, `--pjx-graph-controls-color`, `--pjx-graph-controls-inset`, `--pjx-graph-controls-gap` |
| Panel | `--pjx-graph-panel-bg`, `--pjx-graph-panel-border`, `--pjx-graph-panel-radius`, `--pjx-graph-panel-color`, `--pjx-graph-panel-muted`, `--pjx-graph-panel-accent`, `--pjx-graph-panel-inset`, `--pjx-graph-panel-width`, `--pjx-graph-panel-gap`, `--pjx-graph-panel-padding`, `--pjx-graph-panel-marker-size`, `--pjx-graph-panel-title-size`, `--pjx-graph-panel-control-size`, `--pjx-graph-panel-duration` |

Each node also sets `--pjx-graph-node-color` from its `color` prop. `--pjx-graph-node-x` and
`--pjx-graph-node-y` hold its position; the engine writes them, so do not set them yourself.
Edge states have no built-in colors: style `.pjx-graph__edge--<state>` in the app. The panel's open
animation honors `prefers-reduced-motion`.

## DOM contract

These classes, attributes, events and states are versioned API.

### Classes

| Class | Element |
|---|---|
| `.pjx-graph` | Stage root |
| `.pjx-graph__canvas` | The clipped, gridded surface that takes the gestures |
| `.pjx-graph__viewport` | The pan/zoom transform target |
| `.pjx-graph__edge-plane` | The SVG the engine draws edges into |
| `.pjx-graph__nodes` | Node layer root |
| `.pjx-graph__node` | Node card root |
| `.pjx-graph__node-icon`, `.pjx-graph__node-body`, `.pjx-graph__node-eyebrow`, `.pjx-graph__node-title`, `.pjx-graph__node-summary`, `.pjx-graph__node-ports` | Node parts |
| `.pjx-graph__port`, `.pjx-graph__port--in`, `.pjx-graph__port--out` | Port handles |
| `.pjx-graph__edges` | Edge layer root (hidden) |
| `.pjx-graph__edge` | A drawn edge path |
| `.pjx-graph__edge-hit` | The wide, transparent click target under each edge |
| `.pjx-graph__edge-label` | An edge label (`<text>`) |
| `.pjx-graph__wire` | The dashed wire shown while dragging from an out-port |
| `.pjx-graph__controls`, `.pjx-graph__control` | Controls group and its buttons |
| `.pjx-graph__panel` | Side panel root (`<aside>`) |
| `.pjx-graph__panel-head`, `.pjx-graph__panel-control`, `.pjx-graph__panel-marker`, `.pjx-graph__panel-title`, `.pjx-graph__panel-badge`, `.pjx-graph__panel-content` | Panel parts |

### Attributes

| Attribute | On | Meaning |
|---|---|---|
| `data-pjx-graph` | Stage root | Marks a stage. The engine mounts every one. |
| `data-pjx-graph-storage-key` | Stage root | Present only with a `storage_key`. |
| `data-pjx-graph-scale-min`, `data-pjx-graph-scale-max` | Stage root | The zoom range. |
| `data-pjx-graph-ready` | Stage root | Set by the engine once mounted and its edges are drawn. |
| `data-node-id`, `data-node-type` | Node root | The node's id and type. |
| `data-x`, `data-y` | Node root | The server position, in world pixels. |
| `data-pjx-graph-port="in"` / `"out"` | Port handle | Port direction. |
| `data-port` | Out-port handle | The port key. |
| `data-pjx-graph-edge` | Edge span | Marks one edge. |
| `data-edge-id`, `data-from`, `data-to`, `data-port`, `data-state`, `data-label` | Edge span | The edge's fields. Drawn paths repeat `data-edge-id`, and the visible path also `data-from`, `data-to`, `data-state`. |
| `data-pjx-graph-controls` | Controls root | Marks the controls group. |
| `data-pjx-graph-zoom="in"` / `"out"`, `data-pjx-graph-fit` | Control button | What the button does. Any element in the canvas with these attributes works as a control. |
| `data-pjx-graph-panel` | Panel root | Marks the panel. Must be a direct child of the stage root. |
| `data-open="true"` / `"false"` | Panel root | Whether the panel shows. |
| `data-pjx-graph-panel-head`, `data-pjx-graph-panel-back`, `data-pjx-graph-panel-close`, `data-pjx-graph-panel-marker`, `data-pjx-graph-panel-title`, `data-pjx-graph-panel-badge`, `data-pjx-graph-panel-content` | Panel parts | Mark the panel's header, buttons and content region. |

### Events

All `pjx:graph:*` events and their `detail` are listed in [Event list](#event-list).

### State

| State | Meaning |
|---|---|
| `.pjx-graph__node--selected` | The selected node. |
| `.pjx-graph__edge--selected` | The selected edge's visible path. |
| `.pjx-graph__edge--<state>` | An edge whose `state` is `<state>`. |
| `[data-open]` on the panel | `"true"` while the panel shows. |
| `[hidden]` on the panel's back button | Present while there is no history to go back to. |
| `[data-pjx-graph-ready]` on the root | The stage is mounted and drawn. |
