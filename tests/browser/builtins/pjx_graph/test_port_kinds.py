"""Ports in real chromium: keyed in-ports, port sides, kinded wires.

An edge may name the in-port it enters (``to_port``); a port handle may name
its ``data-side`` and ``data-kind``. These tests draw and wire
a stage whose host node has two bottom in-ports of kind ``attach`` beside its
plain left in-port, and whose satellite node starts ``attach`` wires from a
top out-port. Stages start from a persisted identity view, so a client pixel
minus the viewport origin is a world pixel.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from markupsafe import Markup

from pyjinhx.builtins.pjx_graph import PJXGraph
from pyjinhx.builtins.pjx_graph_edges import PJXGraphEdges
from pyjinhx.builtins.pjx_graph_node import PJXGraphNode
from pyjinhx.builtins.pjx_graph_nodes import PJXGraphNodes
from pyjinhx.rendering.pipeline import render

if TYPE_CHECKING:
    from playwright.sync_api import Page

UI = Path(__file__).resolve().parents[4] / "pyjinhx" / "builtins"
ASSET = UI / "pjx_graph" / "pjx_graph.js"
CSS = (UI / "pjx_graph" / "pjx_graph.css").read_text(encoding="utf-8") + (
    UI / "pjx_graph_node" / "pjx_graph_node.css"
).read_text(encoding="utf-8")
URL = "http://pjx.test/"
IDENTITY = {"view": {"x": 0, "y": 0, "k": 1}}
NUMBER = re.compile(r"-?\d+(?:\.\d+)?(?:e[-+]?\d+)?")

# Handles placed by inline style, as an app's own node markup would.
BOTTOM = "position:absolute;bottom:0;transform:translate(-50%,50%);left:{left}"
TOP = "position:absolute;top:0;left:50%;transform:translate(-50%,-50%)"

EVENTS = """window.__events = [];
['wire-start', 'before-wire', 'wire', 'wire-end', 'select'].forEach(
    (name) => document.addEventListener('pjx:graph:' + name, (event) => window.__events.push({
        type: name, detail: event.detail, cancelable: event.cancelable})));"""

WORLD = """([x, y]) => {
    const rect = document.querySelector('#g > .pjx-graph__canvas'
        + ' > .pjx-graph__viewport').getBoundingClientRect();
    return [x - rect.left, y - rect.top];
}"""

VISIBLE = """() => Array.from(document.querySelectorAll(
    '#g svg.pjx-graph__edge-plane > *')).map(el => ({
        cls: el.getAttribute('class'), edge: el.getAttribute('data-edge-id'),
        d: el.getAttribute('d')}))"""


def _host(node_id: str = "host", x: float = 360, y: float = 60) -> str:
    """A node with a plain left in-port and bottom attach in-ports data and tools."""
    ports = "".join(
        f'<span class="pjx-graph__port" data-pjx-graph-port="in" data-port="{key}"'
        f' data-kind="attach" data-side="bottom" style="{BOTTOM.format(left=left)}"></span>'
        for key, left in (("data", "25%"), ("tools", "75%"))
    )
    return (
        f'<div id="g-{node_id}" class="pjx-graph__node" data-node-id="{node_id}"'
        f' data-x="{x}" data-y="{y}">'
        '<span class="pjx-graph__port pjx-graph__port--in" data-pjx-graph-port="in"></span>'
        f'<div class="pjx-graph__node-body"><span class="pjx-graph__node-title">'
        f"Host {node_id}</span></div>{ports}</div>"
    )


def _satellite(node_id: str = "res", x: float = 360, y: float = 300) -> str:
    """A node whose only port is a top attach out-port named socket."""
    return (
        f'<div id="g-{node_id}" class="pjx-graph__node" data-node-id="{node_id}"'
        f' data-x="{x}" data-y="{y}">'
        '<div class="pjx-graph__node-body"><span class="pjx-graph__node-title">'
        f"Satellite</span></div>"
        '<span class="pjx-graph__port" data-pjx-graph-port="out" data-port="socket"'
        f' data-kind="attach" data-side="top" style="{TOP}"></span></div>'
    )


def _flow(session) -> str:
    return render(
        PJXGraphNode(
            id="g-src", node_id="src", x=20, y=60, title="Source", out_ports=("ok",)
        ),
        session,
    )


def _stage(session, nodes_html: str, edges=None) -> str:
    graph: dict = {}
    if edges is not None:
        graph["edges"] = PJXGraphEdges(id="g-edges", edges=edges)
    layer = PJXGraphNodes(id="g-nodes", nodes_html=Markup(nodes_html))
    return render(PJXGraph(id="g", nodes=layer, storage_key="flow", **graph), session)


def _serve(page: Page, body: str) -> None:
    page.add_init_script(
        f"localStorage.setItem('pjx-graph:flow', {json.dumps(json.dumps(IDENTITY))});"
    )
    page.add_init_script(EVENTS)
    asset = ASSET.read_text(encoding="utf-8")
    html = (
        f"<html><head><style>{CSS}</style></head>"
        f"<body>{body}<script>{asset}</script></body></html>"
    )
    page.route(URL, lambda route: route.fulfill(body=html, content_type="text/html"))
    page.goto(URL)
    page.wait_for_selector("#g[data-pjx-graph-ready]", timeout=5000)


def _standard(page: Page, session, edges=None) -> None:
    _serve(page, _stage(session, _flow(session) + _host() + _satellite(), edges))


def _events(page: Page, *kinds: str) -> list[dict]:
    return [e for e in page.evaluate("() => window.__events") if e["type"] in kinds]


def _center(page: Page, selector: str) -> tuple[float, float]:
    box = page.locator(selector).bounding_box()
    assert box is not None
    return box["x"] + box["width"] / 2, box["y"] + box["height"] / 2


def _world(page: Page, selector: str) -> list[float]:
    return page.evaluate(WORLD, list(_center(page, selector)))


def _handle(node: str, key: str, direction: str = "in") -> str:
    return f'#g-{node} [data-pjx-graph-port="{direction}"][data-port="{key}"]'


def _numbers(d: str) -> list[float]:
    return [float(n) for n in NUMBER.findall(d)]


def _drawn(page: Page, edge_id: str) -> list[float]:
    paths = [
        el
        for el in page.evaluate(VISIBLE)
        if el["edge"] == edge_id and el["cls"].split()[0] == "pjx-graph__edge"
    ]
    assert len(paths) == 1
    return _numbers(paths[0]["d"])


def _wire(page: Page, start: tuple[float, float], end: tuple[float, float]) -> None:
    page.mouse.move(*start)
    page.mouse.down()
    page.mouse.move(*end, steps=6)
    page.mouse.up()


ATTACHMENT = {
    "id": "a1",
    "from": "res",
    "port": "socket",
    "to": "host",
    "to_port": "data",
}


# Drawing


def test_an_edge_with_a_to_port_ends_on_that_in_port(page, page_errors, session):
    _standard(page, session, [ATTACHMENT])
    numbers = _drawn(page, "a1")
    assert numbers[:2] == pytest.approx(
        _world(page, _handle("res", "socket", "out")), abs=0.01
    )
    assert numbers[-2:] == pytest.approx(
        _world(page, _handle("host", "data")), abs=0.01
    )
    assert page_errors == []


def test_top_and_bottom_sides_bend_the_curve_vertically(page, page_errors, session):
    _standard(page, session, [ATTACHMENT])
    x1, y1, c1x, c1y, c2x, c2y, x2, y2 = _drawn(page, "a1")
    reach = max(48, abs(y2 - y1) * 0.5)
    assert (c1x, c1y) == pytest.approx((x1, y1 - reach))
    assert (c2x, c2y) == pytest.approx((x2, y2 + reach))
    assert page_errors == []


def test_an_unknown_to_port_enters_at_the_left_middle(page, page_errors, session):
    _standard(page, session, [dict(ATTACHMENT, to_port="missing")])
    box = page.evaluate("() => pjx.graph.get(document.getElementById('g')).box('host')")
    assert _drawn(page, "a1")[-2:] == pytest.approx(
        [box["x"], box["y"] + box["height"] / 2]
    )
    assert page_errors == []


def test_in_anchor_reads_a_keyed_in_port_and_keeps_its_one_argument_form(
    page, page_errors, session
):
    _standard(page, session)
    anchors = page.evaluate(
        """() => { const g = pjx.graph.get(document.getElementById('g'));
            const b = g.box('host');
            return [g.inAnchor('host', 'tools'), g.inAnchor('host'),
                    {x: b.x, y: b.y + b.height / 2}]; }"""
    )
    keyed, plain, left_middle = anchors
    assert [keyed["x"], keyed["y"]] == pytest.approx(
        _world(page, _handle("host", "tools"))
    )
    assert plain == left_middle
    assert page_errors == []


def test_changing_an_edge_to_port_redraws_it(page, page_errors, session):
    _standard(page, session, [ATTACHMENT])
    page.evaluate(
        """() => { window.__before = document.querySelector(
            '#g path.pjx-graph__edge[data-edge-id="a1"]').getAttribute('d');
            document.querySelector('#g span[data-edge-id="a1"]')
                .setAttribute('data-to-port', 'tools'); }"""
    )
    page.wait_for_function(
        """() => { const d = document.querySelector(
            '#g path.pjx-graph__edge[data-edge-id="a1"]').getAttribute('d');
            return d !== window.__before; }"""
    )
    assert _drawn(page, "a1")[-2:] == pytest.approx(
        _world(page, _handle("host", "tools")), abs=0.01
    )
    assert page_errors == []


# Kinded wires


def _attached(to: str, to_port: str) -> dict:
    return {
        "from": "res",
        "port": "socket",
        "to": to,
        "kind": "attach",
        "to_port": to_port,
    }


def test_a_kinded_wire_released_on_a_matching_in_port_names_it(
    page, page_errors, session
):
    _standard(page, session)
    _wire(
        page,
        _center(page, _handle("res", "socket", "out")),
        _center(page, _handle("host", "data")),
    )
    assert [e["detail"] for e in _events(page, "wire")] == [_attached("host", "data")]
    assert page_errors == []


def test_a_kinded_wire_released_on_the_body_lands_on_the_nearest_matching_port(
    page, page_errors, session
):
    _standard(page, session)
    box = page.locator("#g-host").bounding_box()
    assert box is not None
    near_tools = (box["x"] + box["width"] * 0.8, box["y"] + box["height"] * 0.6)
    _wire(page, _center(page, _handle("res", "socket", "out")), near_tools)
    assert [e["detail"] for e in _events(page, "wire")] == [_attached("host", "tools")]
    assert page_errors == []


def test_an_unkinded_wire_never_lands_on_a_kinded_in_port(page, page_errors, session):
    _standard(page, session)
    _wire(
        page,
        _center(page, '#g-src [data-port="ok"]'),
        _center(page, _handle("host", "data")),
    )
    assert [e["detail"] for e in _events(page, "wire")] == [
        {"from": "src", "port": "ok", "to": "host", "kind": "", "to_port": ""}
    ]
    assert page_errors == []


def test_a_kinded_wire_on_a_node_without_its_kind_has_no_to_port(
    page, page_errors, session
):
    _standard(page, session)
    _wire(
        page,
        _center(page, _handle("res", "socket", "out")),
        _center(page, "#g-src .pjx-graph__node-title"),
    )
    assert [e["detail"] for e in _events(page, "wire")] == [_attached("src", "")]
    assert page_errors == []


def test_a_ghost_leaves_through_its_port_side(page, page_errors, session):
    _standard(page, session)
    x, y = _center(page, _handle("res", "socket", "out"))
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x + 40, y - 120, steps=5)
    ghost = page.evaluate(
        "() => document.querySelector('#g path.pjx-graph__wire').getAttribute('d')"
    )
    x1, y1, c1x, c1y = _numbers(ghost)[:4]
    assert c1x == pytest.approx(x1)
    assert c1y < y1
    page.mouse.up()
    assert page_errors == []


def test_the_stage_root_names_the_held_wire_kind(page, page_errors, session):
    _standard(page, session)
    wiring = "() => document.getElementById('g').getAttribute('data-pjx-graph-wiring')"
    x, y = _center(page, _handle("res", "socket", "out"))
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x + 40, y - 80, steps=5)
    assert page.evaluate(wiring) == "attach"
    page.mouse.up()
    assert page.evaluate(wiring) is None
    sx, sy = _center(page, '#g-src [data-port="ok"]')
    page.mouse.move(sx, sy)
    page.mouse.down()
    page.mouse.move(sx + 60, sy + 80, steps=5)
    assert page.evaluate(wiring) == ""
    page.mouse.up()
    assert page.evaluate(wiring) is None
    assert page_errors == []
