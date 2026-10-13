from pyjinhx.builtins.ui.pjx_graph import PJXGraph
from pyjinhx.builtins.ui.pjx_graph_controls import PJXGraphControls
from pyjinhx.builtins.ui.pjx_graph_edges import PJXGraphEdges
from pyjinhx.builtins.ui.pjx_graph_node import PJXGraphNode
from pyjinhx.builtins.ui.pjx_graph_nodes import PJXGraphNodes
from pyjinhx.builtins.ui.pjx_graph_side_panel import PJXGraphSidePanel

# (node_id, x, y, eyebrow, title, summary, panel details)
STEPS = (
    (
        "trigger",
        0,
        40,
        "Schedule",
        "Trigger",
        "Every hour, on the hour.",
        "Starts a run at the top of every hour.",
    ),
    (
        "fetch",
        240,
        120,
        "HTTP",
        "Fetch",
        "GET the orders feed.",
        "Pulls the latest orders as JSON.",
    ),
    (
        "transform",
        480,
        40,
        "Python",
        "Transform",
        "Normalise currencies.",
        "Converts every amount to EUR.",
    ),
    (
        "store",
        720,
        120,
        "Postgres",
        "Store",
        "Upsert into orders.",
        "Writes the batch in one transaction.",
    ),
)

# Transform's out-port starts unwired, so the reader has an obvious wire to draw.
EDGES = [
    {"id": "trigger-next-fetch", "from": "trigger", "port": "next", "to": "fetch"},
    {"id": "fetch-next-transform", "from": "fetch", "port": "next", "to": "transform"},
]


# The two listeners from the guide's "Wiring the app" (plus select), scoped to
# this stage. A docs page has no server, so the routes are played in-page: the
# panel route by each node's <template>, and the edge route by building the
# response a server would send, the whole edge layer marked hx-swap-oob, and
# handing it to htmx so the swap itself is real. The edge is built with DOM
# calls, so event values only ever become attribute text.
SCRIPT = """<script>
(() => {
  const stage = document.getElementById("demo-graph");
  stage.addEventListener("pjx:graph:select", (event) => {
    pjx.graph.panel.open(event.target, event.detail.id);
  });
  stage.addEventListener("pjx:graph:panel:open", (event) => {
    const template = Array.from(document.querySelectorAll("template[data-demo-panel]"))
      .find((t) => t.getAttribute("data-demo-panel") === event.detail.id);
    if (!template) return;
    htmx.swap("#demo-graph-panel [data-pjx-graph-panel-content]", template.innerHTML,
      { swapStyle: "innerHTML" });
  });
  stage.addEventListener("pjx:graph:wire", (event) => {
    const { from, port, to } = event.detail;
    const id = from + "-" + port + "-" + to;
    const layer = document.getElementById("demo-graph-edges");
    // A server would refuse a duplicate id, as PJXGraphEdges does.
    if (Array.from(layer.children).some((e) => e.getAttribute("data-edge-id") === id)) return;
    const response = layer.cloneNode(true);
    const edge = document.createElement("span");
    edge.hidden = true;
    edge.setAttribute("data-pjx-graph-edge", "");
    edge.setAttribute("data-edge-id", id);
    edge.setAttribute("data-from", from);
    edge.setAttribute("data-to", to);
    edge.setAttribute("data-port", port);
    edge.setAttribute("data-state", "");
    edge.setAttribute("data-label", "");
    response.appendChild(edge);
    response.setAttribute("hx-swap-oob", "true");
    htmx.swap(stage, response.outerHTML, { swapStyle: "none" });
  });
})();
</script>"""


def graph():
    last = len(STEPS) - 1
    nodes = [
        PJXGraphNode(
            id=f"demo-graph-{node_id}",
            node_id=node_id,
            x=x,
            y=y,
            eyebrow=eyebrow,
            title=title,
            summary=summary,
            in_port=index > 0,
            out_ports=("next",) if index < last else (),
        ).render()
        for index, (node_id, x, y, eyebrow, title, summary, _details) in enumerate(
            STEPS
        )
    ]
    stage = PJXGraph(
        id="demo-graph",
        aria_label="Order pipeline",
        # An iframe in the docs must not remember a previous visitor's drags.
        storage_key="",
        nodes=PJXGraphNodes(
            id="demo-graph-nodes", nodes_html=PJXGraphNodes.join(nodes)
        ),
        edges=PJXGraphEdges(id="demo-graph-edges", edges=EDGES),
        controls=PJXGraphControls(id="demo-graph-controls"),
        panel=PJXGraphSidePanel(id="demo-graph-panel", title="Step details"),
    ).render()
    # What the panel route would return for each node, kept inert until opened.
    panels = "".join(
        f'<template data-demo-panel="{node_id}">'
        f"<p><strong>{title}</strong></p><p>{details}</p></template>"
        for node_id, _x, _y, _eyebrow, title, _summary, details in STEPS
    )
    # The demo stage is 360px wide; four nodes and the panel need the full page.
    return (
        '<div style="width: min(720px, calc(100vw - 2rem))">'
        f"{stage}{panels}{SCRIPT}</div>"
    )


DEMOS = {"PJXGraph": (graph, 480)}
