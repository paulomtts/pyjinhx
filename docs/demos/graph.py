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
    return f'<div style="width: min(720px, calc(100vw - 2rem))">{stage}{panels}</div>'


DEMOS = {"PJXGraph": (graph, 480)}
