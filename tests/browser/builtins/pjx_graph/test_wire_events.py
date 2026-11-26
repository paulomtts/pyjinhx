"""The wire lifecycle in real chromium: wire-start, before-wire, wire-end.

wire-start fires once a press on an out-port passes the slop and can cancel
the wire; before-wire fires on a release over a target and can refuse it;
wire-end closes every started wire with the reason it ended. A recorder
installed before the asset runs logs them, so the tests also see their order.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from pyjinhx.builtins.pjx_graph import PJXGraph
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
LIFECYCLE = ("wire-start", "before-wire", "wire", "wire-end")

EVENTS = """window.__events = [];
window.__refuse = new Set();
['wire-start', 'before-wire', 'wire', 'wire-end', 'select', 'move'].forEach(
    (name) => document.addEventListener('pjx:graph:' + name, (event) => {
        window.__events.push({type: name, detail: event.detail,
            cancelable: event.cancelable});
        if (window.__refuse.has(name)) event.preventDefault();
    }));"""


def _stage(session) -> str:
    nodes = [
        PJXGraphNode(
            id="g-n1", node_id="n1", x=100, y=100, title="Start", out_ports=("ok",)
        ),
        PJXGraphNode(id="g-n2", node_id="n2", x=400, y=100, title="End", in_port=True),
    ]
    layer = PJXGraphNodes(
        id="g-nodes",
        nodes_html=PJXGraphNodes.join(render(node, session) for node in nodes),
    )
    return render(PJXGraph(id="g", nodes=layer, storage_key="flow"), session)


def _serve(page: Page, session, refuse: tuple[str, ...] = ()) -> None:
    page.add_init_script(
        f"localStorage.setItem('pjx-graph:flow', {json.dumps(json.dumps(IDENTITY))});"
    )
    page.add_init_script(EVENTS)
    page.add_init_script(f"window.__refuse = new Set({json.dumps(list(refuse))});")
    asset = ASSET.read_text(encoding="utf-8")
    html = (
        f"<html><head><style>{CSS}</style></head>"
        f"<body>{_stage(session)}<div style='height:300px'></div>"
        f"<script>{asset}</script></body></html>"
    )
    page.route(URL, lambda route: route.fulfill(body=html, content_type="text/html"))
    page.goto(URL)
    page.wait_for_selector("#g[data-pjx-graph-ready]", timeout=5000)


def _events(page: Page, *kinds: str) -> list[dict]:
    return [
        e
        for e in page.evaluate("() => window.__events")
        if not kinds or e["type"] in kinds
    ]


def _center(page: Page, selector: str) -> tuple[float, float]:
    box = page.locator(selector).bounding_box()
    assert box is not None
    return box["x"] + box["width"] / 2, box["y"] + box["height"] / 2


PORT = '#g-n1 [data-pjx-graph-port="out"][data-port="ok"]'
TARGET = "#g-n2 .pjx-graph__node-title"


def _press(page: Page, end: tuple[float, float]) -> None:
    page.mouse.move(*_center(page, PORT))
    page.mouse.down()
    page.mouse.move(*end, steps=6)


def _wire(page: Page, end: tuple[float, float]) -> None:
    _press(page, end)
    page.mouse.up()


def _world(page: Page, point: tuple[float, float]) -> list[float]:
    return page.evaluate(
        """([x, y]) => { const r = document.querySelector('#g .pjx-graph__viewport')
            .getBoundingClientRect(); return [x - r.left, y - r.top]; }""",
        list(point),
    )


def _ended(detail: dict) -> dict:
    return {
        key: detail[key] for key in ("from", "port", "kind", "to", "to_port", "reason")
    }


def test_a_wire_to_a_node_fires_the_lifecycle_in_order(page, page_errors, session):
    _serve(page, session)
    _wire(page, _center(page, TARGET))
    events = _events(page, *LIFECYCLE)
    assert [(e["type"], e["cancelable"]) for e in events] == [
        ("wire-start", True),
        ("before-wire", True),
        ("wire", False),
        ("wire-end", False),
    ]
    request = {"from": "n1", "port": "ok", "to": "n2", "kind": "", "to_port": ""}
    assert events[0]["detail"] == {"from": "n1", "port": "ok", "kind": ""}
    assert events[1]["detail"] == request
    assert events[2]["detail"] == request
    assert _ended(events[3]["detail"]) == dict(request, reason="wired")
    assert page_errors == []


def test_wire_end_reports_the_release_point_in_world_pixels(page, page_errors, session):
    _serve(page, session)
    end = _center(page, TARGET)
    _wire(page, end)
    detail = _events(page, "wire-end")[0]["detail"]
    assert [detail["x"], detail["y"]] == pytest.approx(_world(page, end), abs=1)
    assert page_errors == []


def test_a_press_within_the_slop_fires_no_lifecycle_event(page, page_errors, session):
    _serve(page, session)
    x, y = _center(page, PORT)
    _press(page, (x + 3, y))
    page.mouse.up()
    assert _events(page, *LIFECYCLE) == []
    assert page_errors == []


def test_a_canceled_wire_start_draws_and_reports_nothing_more(
    page, page_errors, session
):
    _serve(page, session, refuse=("wire-start",))
    _press(page, _center(page, TARGET))
    assert page.locator("#g path.pjx-graph__wire").count() == 0
    assert (
        page.evaluate(
            "() => document.getElementById('g').hasAttribute('data-pjx-graph-wiring')"
        )
        is False
    )
    page.mouse.up()
    assert [e["type"] for e in _events(page, *LIFECYCLE, "select", "move")] == [
        "wire-start"
    ]
    assert page_errors == []


def test_a_refused_before_wire_fires_no_wire_and_ends_as_refused(
    page, page_errors, session
):
    _serve(page, session, refuse=("before-wire",))
    _wire(page, _center(page, TARGET))
    assert [e["type"] for e in _events(page, *LIFECYCLE)] == [
        "wire-start",
        "before-wire",
        "wire-end",
    ]
    assert _ended(_events(page, "wire-end")[0]["detail"]) == {
        "from": "n1",
        "port": "ok",
        "kind": "",
        "to": "n2",
        "to_port": "",
        "reason": "refused",
    }
    assert page_errors == []


def test_a_release_on_empty_canvas_ends_as_background_with_its_point(
    page, page_errors, session
):
    _serve(page, session)
    x, y = _center(page, PORT)
    _wire(page, (x + 40, y + 200))
    detail = _events(page, "wire-end")[0]["detail"]
    assert (detail["reason"], detail["to"], detail["to_port"]) == (
        "background",
        None,
        None,
    )
    assert [detail["x"], detail["y"]] == pytest.approx(
        _world(page, (x + 40, y + 200)), abs=1
    )
    assert _events(page, "before-wire", "wire") == []
    assert page_errors == []


def test_a_release_outside_the_canvas_ends_as_outside(page, page_errors, session):
    _serve(page, session)
    box = page.locator("#g > .pjx-graph__canvas").bounding_box()
    assert box is not None
    _wire(page, (box["x"] + 100, box["y"] + box["height"] + 40))
    assert _events(page, "wire-end")[0]["detail"]["reason"] == "outside"
    assert page_errors == []


def test_a_release_on_the_source_ends_as_source(page, page_errors, session):
    _serve(page, session)
    _wire(page, _center(page, "#g-n1 .pjx-graph__node-title"))
    assert _events(page, "wire-end")[0]["detail"]["reason"] == "source"
    assert page_errors == []


def test_a_cancelled_pointer_ends_as_cancel_with_no_point(page, page_errors, session):
    _serve(page, session)
    _press(page, _center(page, TARGET))
    page.evaluate(
        "() => window.dispatchEvent(new PointerEvent('pointercancel',"
        " { pointerId: 1, bubbles: true }))"
    )
    page.mouse.up()
    detail = _events(page, "wire-end")[0]["detail"]
    assert (detail["reason"], detail["x"], detail["y"]) == ("cancel", None, None)
    assert (
        page.evaluate(
            "() => document.getElementById('g').hasAttribute('data-pjx-graph-wiring')"
        )
        is False
    )
    assert page_errors == []
