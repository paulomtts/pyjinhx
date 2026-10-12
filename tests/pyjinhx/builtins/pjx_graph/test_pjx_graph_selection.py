"""Node and edge selection on a mounted stage, in real chromium.

Selection is pointer events, hit testing on SVG strokes and d3-zoom's click
suppression, so every stage is served from a real origin with the graph CSS
applied and starts from a persisted identity view, where nodes sit at their
data coordinates. A document-level recorder installed before the asset runs
logs every selection event, which also proves they bubble.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from markupsafe import Markup

from pyjinhx.builtins.ui.pjx_graph import PJXGraph
from pyjinhx.builtins.ui.pjx_graph_controls import PJXGraphControls
from pyjinhx.builtins.ui.pjx_graph_edges import PJXGraphEdges
from pyjinhx.builtins.ui.pjx_graph_node import PJXGraphNode
from pyjinhx.builtins.ui.pjx_graph_nodes import PJXGraphNodes
from pyjinhx.rendering import render

if TYPE_CHECKING:
    from playwright.sync_api import Page

UI = Path(__file__).resolve().parents[4] / "pyjinhx" / "builtins" / "ui"
ASSET = UI / "pjx_graph" / "pjx_graph.js"
CSS = "".join(
    (UI / name / f"{name}.css").read_text(encoding="utf-8")
    for name in ("pjx_graph", "pjx_graph_node", "pjx_graph_controls")
)
URL = "http://pjx.test/"
RECORD = "pjx-graph:flow"
IDENTITY = json.dumps({"view": {"x": 0, "y": 0, "k": 1}})

# Recorded at dispatch, from before the asset runs.
EVENTS = """window.__events = [];
['before-select', 'select', 'before-select-edge', 'select-edge', 'deselect'].forEach(
    (name) => document.addEventListener('pjx:graph:' + name, (event) => window.__events.push({
        type: name, detail: event.detail, target: event.target.id,
        cancelable: event.cancelable})));"""

# The screen point halfway along an edge's hit path in a stage's own plane.
EDGE_POINT = """([stage, id]) => {
    const plane = document.querySelector('#' + stage
        + ' > .pjx-graph__canvas > .pjx-graph__viewport > svg.pjx-graph__edge-plane');
    const hit = Array.from(plane.querySelectorAll(':scope > path.pjx-graph__edge-hit'))
        .find((path) => path.getAttribute('data-edge-id') === id);
    const mid = hit.getPointAtLength(hit.getTotalLength() / 2);
    const at = new DOMPoint(mid.x, mid.y).matrixTransform(hit.getScreenCTM());
    return [at.x, at.y];
}"""

# The class of every path a stage's own plane holds for an edge id, in DOM order.
EDGE_CLASSES = """([stage, id]) => Array.from(document.querySelectorAll('#' + stage
    + ' > .pjx-graph__canvas > .pjx-graph__viewport > svg.pjx-graph__edge-plane > path'))
    .filter((path) => path.getAttribute('data-edge-id') === id)
    .map((path) => path.getAttribute('class'))"""

# Calls an instance method; a throw comes back as its message.
CALL = """([stage, method, args]) => {
    try {
        const value = pjx.graph.get(document.getElementById(stage))[method](...args);
        return {value: value === undefined ? null : value};
    } catch (error) {
        return {error: error.message};
    }
}"""


def _node(node_id: str, x: float, y: float, stage_id: str = "g", **kw) -> PJXGraphNode:
    return PJXGraphNode(
        id=f"{stage_id}-{node_id}", node_id=node_id, x=x, y=y, title=node_id, **kw
    )


def _pair(stage_id: str = "g") -> list[PJXGraphNode]:
    # Same y, so an edge from a to b is a straight line; both ends and its
    # midpoint lie inside the plane's default 300x150 box.
    return [_node("a", 10, 10, stage_id), _node("b", 330, 10, stage_id)]


def _stage(session, nodes: list, stage_id: str = "g", edges=None, **graph) -> str:
    if edges is not None:
        graph["edges"] = edges
    graph.setdefault("storage_key", "flow")
    layer = PJXGraphNodes(
        id=f"{stage_id}-nodes",
        nodes_html=PJXGraphNodes.join(render(node, session) for node in nodes),
    )
    return render(PJXGraph(id=stage_id, nodes=layer, **graph), session)


def _edges(session, *edges: tuple[str, str, str], stage_id: str = "g") -> Markup:
    layer = PJXGraphEdges(
        id=f"{stage_id}-edges",
        edges=[{"id": e, "from": src, "to": dst} for e, src, dst in edges],
    )
    return Markup(render(layer, session))


def _serve(page: Page, body: str, css: str = "") -> None:
    """Seed an identity view, record selection events, load body; wait until ready."""
    page.add_init_script(
        f"localStorage.setItem({json.dumps(RECORD)}, {json.dumps(IDENTITY)});"
    )
    page.add_init_script(EVENTS)
    asset = ASSET.read_text(encoding="utf-8")
    html = (
        f"<html><head><style>{CSS}{css}</style></head>"
        f"<body>{body}<script>{asset}</script></body></html>"
    )
    page.route(URL, lambda route: route.fulfill(body=html, content_type="text/html"))
    page.goto(URL)
    page.wait_for_function(
        """() => Array.from(document.querySelectorAll('[data-pjx-graph]'))
            .every(s => !pjx.graph.get(s) || s.hasAttribute('data-pjx-graph-ready'))""",
        timeout=5000,
    )


def _events(page: Page) -> list[dict]:
    return page.evaluate("() => window.__events")


def _forget(page: Page) -> None:
    page.evaluate("() => { window.__events = []; }")


def _ev(kind: str, node_id: str | None = None, target: str = "g") -> dict:
    return {
        "type": kind,
        "detail": None if node_id is None else {"id": node_id},
        "target": target,
        "cancelable": kind.startswith("before-"),
    }


def _veto(page: Page, kind: str) -> None:
    page.evaluate(
        "kind => document.addEventListener('pjx:graph:' + kind,"
        " (event) => event.preventDefault())",
        kind,
    )


def _selected_nodes(page: Page) -> list[str]:
    return page.evaluate(
        """() => Array.from(document.querySelectorAll('.pjx-graph__node--selected'))
            .map((node) => node.id)"""
    )


def _edge_classes(page: Page, edge_id: str, stage_id: str = "g") -> list[str]:
    return page.evaluate(EDGE_CLASSES, [stage_id, edge_id])


def _click_edge(page: Page, edge_id: str, stage_id: str = "g") -> None:
    x, y = page.evaluate(EDGE_POINT, [stage_id, edge_id])
    page.mouse.click(x, y)


def _background(page: Page, stage_id: str = "g") -> tuple[int, int]:
    """A point just inside the canvas's bottom-left corner, clear of nodes and controls."""
    box = page.locator(f"#{stage_id} > .pjx-graph__canvas").bounding_box()
    assert box is not None
    return round(box["x"] + 20), round(box["y"] + box["height"] - 20)


def _click_background(page: Page, stage_id: str = "g") -> None:
    page.mouse.click(*_background(page, stage_id))


def _call(page: Page, method: str, *args, stage_id: str = "g") -> dict:
    return page.evaluate(CALL, [stage_id, method, list(args)])


# Node clicks


def test_clicking_a_node_selects_it_and_fires_before_select_then_select(
    page, page_errors, session
):
    _serve(page, _stage(session, _pair()))
    page.click("#g-a")
    assert _events(page) == [_ev("before-select", "a"), _ev("select", "a")]
    assert _selected_nodes(page) == ["g-a"]
    assert page_errors == []


def test_clicking_a_port_selects_its_node(page, page_errors, session):
    nodes = [_node("a", 10, 10, out_ports=("ok",)), _node("b", 330, 10, in_port=True)]
    _serve(page, _stage(session, nodes))
    page.click("#g-b [data-pjx-graph-port='in']")
    assert _events(page) == [_ev("before-select", "b"), _ev("select", "b")]
    assert _selected_nodes(page) == ["g-b"]
    assert page_errors == []


def test_a_prevented_before_select_selects_nothing(page, page_errors, session):
    _serve(page, _stage(session, _pair()))
    _veto(page, "before-select")
    page.click("#g-a")
    assert _events(page) == [_ev("before-select", "a")]
    assert _selected_nodes(page) == []
    assert page_errors == []


def test_clicking_another_node_moves_the_selection_without_a_deselect(
    page, page_errors, session
):
    _serve(page, _stage(session, _pair()))
    page.click("#g-a")
    _forget(page)
    page.click("#g-b")
    assert _events(page) == [_ev("before-select", "b"), _ev("select", "b")]
    assert _selected_nodes(page) == ["g-b"]
    assert page_errors == []


def test_a_prevented_switch_keeps_the_previous_node(page, page_errors, session):
    _serve(page, _stage(session, _pair()))
    page.click("#g-a")
    _veto(page, "before-select")
    _forget(page)
    page.click("#g-b")
    assert _events(page) == [_ev("before-select", "b")]
    assert _selected_nodes(page) == ["g-a"]
    assert page_errors == []


def test_clicking_the_selected_node_again_fires_nothing(page, page_errors, session):
    _serve(page, _stage(session, _pair()))
    page.click("#g-a")
    _forget(page)
    page.click("#g-a")
    assert _events(page) == []
    assert _selected_nodes(page) == ["g-a"]
    assert page_errors == []


def test_a_repeated_node_id_selects_the_first_node_with_it(page, page_errors, session):
    nodes = [
        _node("a", 10, 10),
        PJXGraphNode(id="g-a2", node_id="a", x=10, y=200, title="a2"),
    ]
    _serve(page, _stage(session, nodes))
    page.click("#g-a2")
    assert _events(page) == [_ev("before-select", "a"), _ev("select", "a")]
    assert _selected_nodes(page) == ["g-a"]
    assert page_errors == []


def test_mounting_twice_still_fires_once_per_click(page, page_errors, session):
    _serve(page, _stage(session, _pair()))
    page.evaluate("() => pjx.graph.mount(document.getElementById('g'))")
    page.click("#g-a")
    assert _events(page) == [_ev("before-select", "a"), _ev("select", "a")]
    assert page_errors == []


# Nested stages


NESTED_CSS = (
    "#g-a { width: 700px; } #in { width: 600px; }"
    " #in > .pjx-graph__canvas { min-height: 0; height: 200px; }"
)


def _nested(session) -> str:
    """Stage g whose node a holds stage in; both reuse the node ids a and b."""
    inner = _stage(session, _pair("in"), "in")
    outer = [_node("a", 20, 20, icon=Markup(inner)), _node("b", 800, 20)]
    return _stage(session, outer)


def test_a_nested_stage_selects_its_own_node_and_the_outer_stage_ignores_it(
    page, page_errors, session
):
    _serve(page, _nested(session), NESTED_CSS)
    page.click("#g-b")
    _forget(page)
    page.click("#in-b")
    assert _events(page) == [
        _ev("before-select", "b", "in"),
        _ev("select", "b", "in"),
    ]
    assert sorted(_selected_nodes(page)) == ["g-b", "in-b"]
    assert page_errors == []


# Background clicks


def test_a_background_click_deselects_once(page, page_errors, session):
    _serve(page, _stage(session, _pair()))
    page.click("#g-a")
    _forget(page)
    _click_background(page)
    assert _events(page) == [_ev("deselect")]
    assert _selected_nodes(page) == []
    _click_background(page)
    assert _events(page) == [_ev("deselect")]
    assert page_errors == []


def test_a_background_click_with_nothing_selected_fires_nothing(
    page, page_errors, session
):
    _serve(page, _stage(session, _pair()))
    _click_background(page)
    assert _events(page) == []
    assert page_errors == []


@pytest.mark.parametrize(
    "button",
    [
        '[data-pjx-graph-zoom="in"]',
        '[data-pjx-graph-zoom="out"]',
        "[data-pjx-graph-fit]",
    ],
    ids=["in", "out", "fit"],
)
def test_the_controls_keep_the_selection(page, page_errors, session, button):
    controls = PJXGraphControls(id="g-controls")
    _serve(page, _stage(session, _pair(), controls=controls))
    page.click("#g-a")
    _forget(page)
    page.click(f"#g-controls {button}")
    assert _events(page) == []
    assert _selected_nodes(page) == ["g-a"]
    assert page_errors == []


def test_a_background_pan_keeps_the_selection(page, page_errors, session):
    _serve(page, _stage(session, _pair()))
    page.click("#g-a")
    _forget(page)
    x, y = _background(page)
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x + 60, y - 40, steps=4)
    page.mouse.up()
    page.wait_for_timeout(100)
    assert _events(page) == []
    assert _selected_nodes(page) == ["g-a"]
    assert page_errors == []


def test_a_background_click_leaves_a_sibling_stage_selected(page, page_errors, session):
    _serve(page, _stage(session, _pair("s")) + _stage(session, _pair("t"), "t"))
    page.click("#s-a")
    _forget(page)
    _click_background(page, "t")
    assert _events(page) == []
    assert _selected_nodes(page) == ["s-a"]
    assert page_errors == []


def test_a_nested_stage_background_click_deselects_inside_and_selects_outside(
    page, page_errors, session
):
    _serve(page, _nested(session), NESTED_CSS)
    page.click("#in-b")
    _forget(page)
    _click_background(page, "in")
    # The inner canvas's listener runs first: it is deeper on the bubble path.
    assert _events(page) == [
        _ev("deselect", target="in"),
        _ev("before-select", "a"),
        _ev("select", "a"),
    ]
    assert _selected_nodes(page) == ["g-a"]
    assert page_errors == []


# Edge clicks


def test_clicking_an_edge_selects_its_visible_path_and_clears_the_node(
    page, page_errors, session
):
    _serve(page, _stage(session, _pair(), edges=_edges(session, ("e1", "a", "b"))))
    page.click("#g-a")
    _forget(page)
    _click_edge(page, "e1")
    assert _events(page) == [_ev("before-select-edge", "e1"), _ev("select-edge", "e1")]
    assert _edge_classes(page, "e1") == [
        "pjx-graph__edge-hit",
        "pjx-graph__edge pjx-graph__edge--selected",
    ]
    assert _selected_nodes(page) == []
    assert page_errors == []


def test_a_prevented_before_select_edge_keeps_the_node(page, page_errors, session):
    _serve(page, _stage(session, _pair(), edges=_edges(session, ("e1", "a", "b"))))
    page.click("#g-a")
    _veto(page, "before-select-edge")
    _forget(page)
    _click_edge(page, "e1")
    assert _events(page) == [_ev("before-select-edge", "e1")]
    assert _edge_classes(page, "e1") == ["pjx-graph__edge-hit", "pjx-graph__edge"]
    assert _selected_nodes(page) == ["g-a"]
    assert page_errors == []


def test_clicking_the_selected_edge_again_fires_nothing(page, page_errors, session):
    _serve(page, _stage(session, _pair(), edges=_edges(session, ("e1", "a", "b"))))
    _click_edge(page, "e1")
    _forget(page)
    _click_edge(page, "e1")
    assert _events(page) == []
    assert _edge_classes(page, "e1") == [
        "pjx-graph__edge-hit",
        "pjx-graph__edge pjx-graph__edge--selected",
    ]
    assert page_errors == []


def test_an_edge_selection_survives_a_redraw(page, page_errors, session):
    _serve(page, _stage(session, _pair(), edges=_edges(session, ("e1", "a", "b"))))
    _click_edge(page, "e1")
    _forget(page)
    _call(page, "drawEdges")
    assert _edge_classes(page, "e1") == [
        "pjx-graph__edge-hit",
        "pjx-graph__edge pjx-graph__edge--selected",
    ]
    assert _events(page) == []
    assert page_errors == []


def test_a_selected_edge_that_leaves_and_returns_is_selected_again(
    page, page_errors, session
):
    _serve(page, _stage(session, _pair(), edges=_edges(session, ("e1", "a", "b"))))
    _click_edge(page, "e1")
    _forget(page)
    page.evaluate(
        """() => {
            window.__span = document.querySelector('#g-edges [data-edge-id="e1"]');
            window.__span.remove();
            pjx.graph.get(document.getElementById('g')).drawEdges();
        }"""
    )
    assert _edge_classes(page, "e1") == []
    page.evaluate(
        """() => {
            document.getElementById('g-edges').append(window.__span);
            pjx.graph.get(document.getElementById('g')).drawEdges();
        }"""
    )
    assert _edge_classes(page, "e1") == [
        "pjx-graph__edge-hit",
        "pjx-graph__edge pjx-graph__edge--selected",
    ]
    assert _events(page) == []
    assert page_errors == []


def test_an_edge_with_an_empty_id_is_not_selectable(page, page_errors, session):
    span = '<span hidden data-pjx-graph-edge data-edge-id="" data-from="a" data-to="b"></span>'
    _serve(page, _stage(session, _pair(), edges=Markup(span)))
    page.click("#g-a")
    _forget(page)
    _click_edge(page, "")
    assert _events(page) == []
    assert _selected_nodes(page) == ["g-a"]
    assert _edge_classes(page, "") == ["pjx-graph__edge-hit", "pjx-graph__edge"]
    assert page_errors == []


def test_a_node_and_an_edge_sharing_an_id_are_different_selections(
    page, page_errors, session
):
    _serve(page, _stage(session, _pair(), edges=_edges(session, ("a", "a", "b"))))
    page.click("#g-a")
    _forget(page)
    _click_edge(page, "a")
    assert _events(page) == [_ev("before-select-edge", "a"), _ev("select-edge", "a")]
    assert _selected_nodes(page) == []
    assert _edge_classes(page, "a") == [
        "pjx-graph__edge-hit",
        "pjx-graph__edge pjx-graph__edge--selected",
    ]
    assert page_errors == []


# select() and deselect()


def test_select_runs_the_click_sequence_and_returns_true(page, page_errors, session):
    _serve(page, _stage(session, _pair()))
    assert _call(page, "select", "b") == {"value": True}
    assert _events(page) == [_ev("before-select", "b"), _ev("select", "b")]
    assert _selected_nodes(page) == ["g-b"]
    _forget(page)
    assert _call(page, "select", "b") == {"value": True}
    assert _events(page) == []
    assert page_errors == []


def test_a_prevented_select_returns_false(page, page_errors, session):
    _serve(page, _stage(session, _pair()))
    _call(page, "select", "a")
    _veto(page, "before-select")
    _forget(page)
    assert _call(page, "select", "b") == {"value": False}
    assert _events(page) == [_ev("before-select", "b")]
    assert _selected_nodes(page) == ["g-a"]
    assert page_errors == []


def test_select_replaces_an_edge_selection(page, page_errors, session):
    _serve(page, _stage(session, _pair(), edges=_edges(session, ("e1", "a", "b"))))
    _click_edge(page, "e1")
    _forget(page)
    assert _call(page, "select", "a") == {"value": True}
    assert _events(page) == [_ev("before-select", "a"), _ev("select", "a")]
    assert _edge_classes(page, "e1") == ["pjx-graph__edge-hit", "pjx-graph__edge"]
    assert _selected_nodes(page) == ["g-a"]
    assert page_errors == []


def test_deselect_fires_once_and_returns_nothing(page, page_errors, session):
    _serve(page, _stage(session, _pair()))
    _call(page, "select", "a")
    _forget(page)
    assert _call(page, "deselect") == {"value": None}
    assert _events(page) == [_ev("deselect")]
    assert _selected_nodes(page) == []
    assert _call(page, "deselect") == {"value": None}
    assert _events(page) == [_ev("deselect")]
    assert page_errors == []


@pytest.mark.parametrize("bad", [42, None, True], ids=["number", "null", "bool"])
def test_select_rejects_a_non_string_id(page, page_errors, session, bad):
    _serve(page, _stage(session, _pair()))
    _call(page, "select", "a")
    _forget(page)
    assert _call(page, "select", bad) == {
        "error": "pjx.graph.select: expected a string id"
    }
    assert _events(page) == []
    assert _selected_nodes(page) == ["g-a"]
    assert page_errors == []


def test_select_rejects_an_unknown_id(page, page_errors, session):
    _serve(page, _stage(session, _pair()))
    _call(page, "select", "a")
    _forget(page)
    assert _call(page, "select", "nope") == {
        "error": 'pjx.graph.select: no node "nope"'
    }
    assert _events(page) == []
    assert _selected_nodes(page) == ["g-a"]
    assert page_errors == []


def test_select_ignores_a_nested_stage_node(page, page_errors, session):
    inner = _stage(session, [_node("x", 10, 10, "in")], "in")
    outer = [_node("a", 20, 20, icon=Markup(inner))]
    _serve(page, _stage(session, outer), NESTED_CSS)
    assert _call(page, "select", "x") == {"error": 'pjx.graph.select: no node "x"'}
    assert _events(page) == []
    assert page_errors == []
