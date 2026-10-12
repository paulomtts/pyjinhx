"""Node placement, node boxes and port anchors, and fit-to-nodes, in real chromium.

All of it depends on real CSS layout, getBoundingClientRect and animation
frames, so every stage is served from a real origin with the graph CSS applied.
World coordinates are the viewport's untransformed pixels, the space data-x/y
are written in.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from markupsafe import Markup

from pyjinhx.builtins.ui.pjx_graph import PJXGraph
from pyjinhx.builtins.ui.pjx_graph_node import PJXGraphNode
from pyjinhx.builtins.ui.pjx_graph_nodes import PJXGraphNodes
from pyjinhx.rendering import render

if TYPE_CHECKING:
    from playwright.sync_api import Page

UI = Path(__file__).resolve().parents[4] / "pyjinhx" / "builtins" / "ui"
ASSET = UI / "pjx_graph" / "pjx_graph.js"
CSS = (UI / "pjx_graph" / "pjx_graph.css").read_text(encoding="utf-8") + (
    UI / "pjx_graph_node" / "pjx_graph_node.css"
).read_text(encoding="utf-8")
URL = "http://pjx.test/"
RECORD = "pjx-graph:flow"
IDENTITY = {"view": {"x": 0, "y": 0, "k": 1}}

# Every node's rendered rect, relative to the canvas's inner (border-less) origin.
NODE_RECTS = """id => {
    const canvas = document.querySelector('#' + id + ' > .pjx-graph__canvas');
    const c = canvas.getBoundingClientRect();
    const left = c.left + canvas.clientLeft;
    const top = c.top + canvas.clientTop;
    return Array.from(canvas.querySelectorAll('[data-node-id]')).map(node => {
        const r = node.getBoundingClientRect();
        return {id: node.getAttribute('data-node-id'), x: r.left - left,
                y: r.top - top, right: r.right - left, bottom: r.bottom - top};
    });
}"""


def _node(node_id: str, x: float, y: float, stage_id: str = "g", **kw) -> PJXGraphNode:
    return PJXGraphNode(id=f"{stage_id}-{node_id}", node_id=node_id, x=x, y=y, **kw)


def _stage(session, nodes: list, stage_id: str = "g", **graph) -> str:
    layer = PJXGraphNodes(
        id=f"{stage_id}-nodes",
        nodes_html=PJXGraphNodes.join(render(node, session) for node in nodes),
    )
    return render(PJXGraph(id=stage_id, nodes=layer, **graph), session)


def _serve(page: Page, body: str) -> None:
    """Load body with the graph CSS and asset, then wait until every mounted stage is ready."""
    asset = ASSET.read_text(encoding="utf-8")
    html = (
        f"<html><head><style>{CSS}</style></head>"
        f"<body>{body}<script>{asset}</script></body></html>"
    )
    page.route(URL, lambda route: route.fulfill(body=html, content_type="text/html"))
    page.goto(URL)
    _wait_ready(page)


def _wait_ready(page: Page) -> None:
    page.wait_for_function(
        """() => Array.from(document.querySelectorAll('[data-pjx-graph]'))
            .every(s => !pjx.graph.get(s) || s.hasAttribute('data-pjx-graph-ready'))""",
        timeout=5000,
    )


def _seed(page: Page, record: dict, key: str = RECORD) -> None:
    """Store record under key before the page's own scripts run."""
    page.add_init_script(
        f"localStorage.setItem({json.dumps(key)}, {json.dumps(json.dumps(record))});"
    )


def _rects(page: Page, stage_id: str = "g") -> list[dict]:
    return page.evaluate(NODE_RECTS, stage_id)


# Placement


def test_nodes_land_at_their_data_coordinates(page, page_errors, session):
    _seed(page, IDENTITY)
    nodes = [
        _node("a", 10, 20, title="A"),
        _node("b", 300, 40, title="B"),
        _node("c", 120.5, 260, title="C"),
    ]
    _serve(page, _stage(session, nodes, storage_key="flow"))
    rects = {r["id"]: r for r in _rects(page)}
    assert {k: (r["x"], r["y"]) for k, r in rects.items()} == {
        "a": pytest.approx((10, 20), abs=0.5),
        "b": pytest.approx((300, 40), abs=0.5),
        "c": pytest.approx((120.5, 260), abs=0.5),
    }
    assert page_errors == []


def test_data_coordinates_win_over_a_stale_inline_style(page, page_errors, session):
    _seed(page, IDENTITY)
    stale = render(_node("a", 40, 60, title="A"), session).replace(
        "--pjx-graph-node-x:40.0px;--pjx-graph-node-y:60.0px;",
        "--pjx-graph-node-x:7px;--pjx-graph-node-y:9px;",
    )
    stripped = re.sub(
        r' style="[^"]*"', "", render(_node("b", 300, 80, title="B"), session)
    )
    assert "7px" in stale and "style=" not in stripped
    layer = PJXGraphNodes(id="g-nodes", nodes_html=Markup(stale + stripped))
    _serve(page, render(PJXGraph(id="g", nodes=layer, storage_key="flow"), session))
    rects = {r["id"]: (r["x"], r["y"]) for r in _rects(page)}
    assert rects == {
        "a": pytest.approx((40, 60), abs=0.5),
        "b": pytest.approx((300, 80), abs=0.5),
    }
    assert page_errors == []


@pytest.mark.parametrize(
    "bad",
    ['data-x="abc"', 'data-x=""', 'data-x=" "', 'data-x="Infinity"', ""],
    ids=["not-a-number", "empty", "blank", "infinite", "missing"],
)
def test_a_non_numeric_coordinate_is_left_to_css(
    page, page_errors, console_errors, session, bad
):
    _seed(page, IDENTITY)
    # Inline style says (100, 5); data-y says 200, so only y should move.
    html = (
        render(_node("a", 100, 200, title="A"), session)
        .replace('data-x="100.0"', bad)
        .replace("--pjx-graph-node-y:200.0px", "--pjx-graph-node-y:5px")
    )
    layer = PJXGraphNodes(id="g-nodes", nodes_html=Markup(html))
    _serve(page, render(PJXGraph(id="g", nodes=layer, storage_key="flow"), session))
    [rect] = _rects(page)
    assert (rect["x"], rect["y"]) == pytest.approx((100, 200), abs=0.5)
    assert (
        page.evaluate(
            "() => document.getElementById('g-a').style.getPropertyValue('--pjx-graph-node-x')"
        )
        == "100.0px"
    )
    assert console_errors == []
    assert page_errors == []
