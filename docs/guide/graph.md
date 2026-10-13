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
        PJXGraphNode(id="node-a", node_id="a", x=40, y=60, title="Fetch", out_ports=("next",)),
        PJXGraphNode(id="node-b", node_id="b", x=320, y=60, title="Store", in_port=True),
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
from the document is unmounted. Once a stage is mounted, has drawn its edges and has framed its nodes,
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
| `nodes` | `Slot` | required | The node layer, normally a `PJXGraphNodes`. |
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
A non-finite `x`/`y` (`nan`, `inf`), an empty `node_id`, an empty or repeated `out_ports` key, or a
`color` that contains `;` raises a validation error.

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
or `state` contains a quote. An edge whose `from` or `to` node is missing, or hidden with
`display: none`, is not an error. It is skipped silently and drawn once both ends show. Edges between
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

An `accent_color` that contains `;` raises a validation error.
