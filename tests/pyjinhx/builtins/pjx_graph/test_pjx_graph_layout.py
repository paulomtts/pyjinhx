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


# Box and anchors

VIEW = """id => {
    const viewport = document.querySelector(
        '#' + id + ' > .pjx-graph__canvas > .pjx-graph__viewport');
    const m = new DOMMatrix(getComputedStyle(viewport).transform);
    return {x: m.e, y: m.f, k: m.a};
}"""

# A client point turned into world coordinates through the computed transform,
# a different route from the engine's own.
CLIENT_TO_WORLD = """([id, x, y]) => {
    const canvas = document.querySelector('#' + id + ' > .pjx-graph__canvas');
    const r = canvas.getBoundingClientRect();
    const m = new DOMMatrix(getComputedStyle(
        canvas.querySelector(':scope > .pjx-graph__viewport')).transform);
    return {x: (x - r.left - canvas.clientLeft - m.e) / m.a,
            y: (y - r.top - canvas.clientTop - m.f) / m.a};
}"""

CALL = """([id, method, args]) => {
    const instance = pjx.graph.get(document.getElementById(id));
    return instance[method](...args);
}"""


def _view(page: Page, stage_id: str = "g") -> dict[str, float]:
    return page.evaluate(VIEW, stage_id)


def _call(page: Page, method: str, *args, stage_id: str = "g"):
    return page.evaluate(CALL, [stage_id, method, list(args)])


def _ports_stage(session, stage_id: str = "g", **graph) -> str:
    graph.setdefault("storage_key", "flow")
    node = _node(
        "a", 120, 80, stage_id, title="A", in_port=True, out_ports=("ok", "fail")
    )
    other = _node("b", 500, 300, stage_id, title="B")
    return _stage(session, [node, other], stage_id, **graph)


def test_box_reports_world_position_and_size(page, page_errors, session):
    _seed(page, IDENTITY)
    _serve(page, _ports_stage(session))
    size = page.evaluate(
        "() => { const n = document.getElementById('g-a');"
        " return {width: n.offsetWidth, height: n.offsetHeight}; }"
    )
    box = _call(page, "box", "a")
    assert (box["x"], box["y"]) == pytest.approx((120, 80), abs=0.5)
    assert (box["width"], box["height"]) == (size["width"], size["height"])
    assert page_errors == []


def _measure(page: Page, stage_id: str = "g") -> list:
    return [
        _call(page, "box", "a", stage_id=stage_id),
        _call(page, "inAnchor", "a", stage_id=stage_id),
        _call(page, "outAnchor", "a", "ok", stage_id=stage_id),
        _call(page, "outAnchor", "a", "fail", stage_id=stage_id),
        _call(page, "outAnchor", "b", stage_id=stage_id),
    ]


def test_box_and_anchors_ignore_the_view(page, page_errors, session):
    # The same nodes on two stages, one at identity and one panned and zoomed.
    _seed(page, IDENTITY)
    _seed(page, {"view": {"x": 37, "y": -12, "k": 1.5}}, key="pjx-graph:moved")
    moved = _ports_stage(session, stage_id="h", storage_key="moved")
    _serve(page, _ports_stage(session) + moved)
    assert _view(page, "h") == pytest.approx({"x": 37, "y": -12, "k": 1.5}, abs=0.01)
    for before, after in zip(_measure(page), _measure(page, "h"), strict=True):
        assert after == pytest.approx(before, abs=0.5)
    assert page_errors == []


def test_in_anchor_is_the_left_edge_midpoint(page, page_errors, session):
    _seed(page, IDENTITY)
    _serve(page, _ports_stage(session))
    box = _call(page, "box", "a")
    anchor = _call(page, "inAnchor", "a")
    assert anchor == pytest.approx({"x": box["x"], "y": box["y"] + box["height"] / 2})
    assert page_errors == []


def test_out_anchor_is_the_rendered_port_centre(page, page_errors, session):
    _seed(page, {"view": {"x": 37, "y": -12, "k": 1.5}})
    _serve(page, _ports_stage(session))
    box = _call(page, "box", "a")
    anchors = {}
    for port in ("ok", "fail"):
        dot = page.locator(f'#g-a [data-pjx-graph-port="out"][data-port="{port}"]')
        b = dot.bounding_box()
        assert b is not None
        centre = page.evaluate(
            CLIENT_TO_WORLD, ["g", b["x"] + b["width"] / 2, b["y"] + b["height"] / 2]
        )
        anchors[port] = _call(page, "outAnchor", "a", port)
        assert anchors[port] == pytest.approx(centre, abs=0.5)
        # translateX(50%) puts the dot's centre on the right edge, not inside it.
        assert anchors[port]["x"] == pytest.approx(box["x"] + box["width"], abs=0.5)
    assert anchors["ok"]["y"] < anchors["fail"]["y"]
    assert page_errors == []


def test_out_anchor_without_that_port_is_the_right_edge_midpoint(
    page, page_errors, session
):
    _seed(page, IDENTITY)
    _serve(page, _ports_stage(session))
    for node_id, args in [("a", ["nope"]), ("a", []), ("b", ["ok"])]:
        box = _call(page, "box", node_id)
        edge = {"x": box["x"] + box["width"], "y": box["y"] + box["height"] / 2}
        assert _call(page, "outAnchor", node_id, *args) == pytest.approx(edge)
    assert page_errors == []


def test_unknown_node_id_gives_null(page, page_errors, session):
    _seed(page, IDENTITY)
    other = _stage(session, [_node("only-there", 10, 10, stage_id="h", title="H")], "h")
    _serve(page, _ports_stage(session) + other)
    for node_id in ("zzz", "only-there", ""):
        assert _call(page, "box", node_id) is None
        assert _call(page, "inAnchor", node_id) is None
        assert _call(page, "outAnchor", node_id, "ok") is None
    assert _call(page, "box", "only-there", stage_id="h") is not None
    assert page_errors == []


def test_ids_with_css_special_characters_resolve(page, page_errors, session):
    _seed(page, IDENTITY)
    # PJXGraphNode refuses '"' in attributes, but other markup may carry it escaped.
    odd = 'a "b" ]c'
    html = (
        render(_node("odd", 60, 70, title="Odd", out_ports=("p",)), session)
        .replace('data-node-id="odd"', 'data-node-id="a &quot;b&quot; ]c"')
        .replace('data-port="p"', 'data-port="x&quot;]"')
    )
    layer = PJXGraphNodes(id="g-nodes", nodes_html=Markup(html))
    _serve(page, render(PJXGraph(id="g", nodes=layer, storage_key="flow"), session))
    box = _call(page, "box", odd)
    assert (box["x"], box["y"]) == pytest.approx((60, 70), abs=0.5)
    assert _call(page, "inAnchor", odd) is not None
    assert _call(page, "outAnchor", odd, 'x"]')["x"] == pytest.approx(
        box["x"] + box["width"], abs=0.5
    )
    assert page_errors == []


def test_a_nested_stage_keeps_its_own_nodes(page, page_errors, session):
    _seed(page, IDENTITY)
    inner = _stage(session, [_node("deep", 10, 10, "in", title="Deep")], "in")
    outer = _node("a", 40, 40, title="A", icon=Markup(inner))
    _serve(page, _stage(session, [outer], storage_key="flow"))
    assert _call(page, "box", "deep") is None
    assert _call(page, "box", "deep", stage_id="in") is not None
    assert page_errors == []
