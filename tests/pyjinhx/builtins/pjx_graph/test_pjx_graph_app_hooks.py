"""App hooks in real chromium: in-node action controls and the view event.

An element marked ``data-pjx-graph-action`` inside a node is the app's own
control: pressing it never drags the node, clicking it never selects, and a
non-empty value fires ``pjx:graph:action``. ``pjx:graph:view`` reports the
view after every pan or zoom ends, and the instance's ``view()`` reads it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from markupsafe import Markup

from pyjinhx.builtins.ui.pjx_graph import PJXGraph
from pyjinhx.builtins.ui.pjx_graph_controls import PJXGraphControls
from pyjinhx.builtins.ui.pjx_graph_node import PJXGraphNode
from pyjinhx.builtins.ui.pjx_graph_nodes import PJXGraphNodes
from pyjinhx.rendering import render

if TYPE_CHECKING:
    from playwright.sync_api import Page

UI = Path(__file__).resolve().parents[4] / "pyjinhx" / "builtins" / "ui"
ASSET = UI / "pjx_graph" / "pjx_graph.js"
CSS = "".join(
    (UI / name).read_text(encoding="utf-8")
    for name in (
        "pjx_graph/pjx_graph.css",
        "pjx_graph_node/pjx_graph_node.css",
        "pjx_graph_controls/pjx_graph_controls.css",
    )
)
URL = "http://pjx.test/"
IDENTITY = {"view": {"x": 0, "y": 0, "k": 1}}

EVENTS = """window.__events = [];
['action', 'select', 'before-select', 'deselect', 'move', 'view'].forEach(
    (name) => document.addEventListener('pjx:graph:' + name, (event) => window.__events.push({
        type: name, detail: event.detail, target: event.target.id})));"""

# An app's "+" beside the ok port, and an inert badge with no action name.
CONTROLS = Markup(
    '<button type="button" data-pjx-graph-action="add" data-port="ok">+</button>'
    '<span id="badge" data-pjx-graph-action="">2 in parallel</span>'
)


def _stage(session, stage_id: str = "g", icon=CONTROLS, **graph) -> str:
    nodes = [
        PJXGraphNode(
            id=f"{stage_id}-n1",
            node_id="n1",
            x=100,
            y=100,
            title="Start",
            icon=icon,
            out_ports=("ok",),
        )
    ]
    layer = PJXGraphNodes(
        id=f"{stage_id}-nodes",
        nodes_html=PJXGraphNodes.join(render(node, session) for node in nodes),
    )
    return render(
        PJXGraph(id=stage_id, nodes=layer, storage_key=stage_id, **graph), session
    )


def _serve(page: Page, body: str, stages: tuple[str, ...] = ("g",)) -> None:
    for stage in stages:
        page.add_init_script(
            f"localStorage.setItem('pjx-graph:{stage}',"
            f" {json.dumps(json.dumps(IDENTITY))});"
        )
    page.add_init_script(EVENTS)
    asset = ASSET.read_text(encoding="utf-8")
    html = (
        f"<html><head><style>{CSS}</style></head>"
        f"<body>{body}<script>{asset}</script></body></html>"
    )
    page.route(URL, lambda route: route.fulfill(body=html, content_type="text/html"))
    page.goto(URL)
    page.wait_for_function(
        """() => Array.from(document.querySelectorAll('[data-pjx-graph]'))
            .every(s => s.hasAttribute('data-pjx-graph-ready'))""",
        timeout=5000,
    )


def _events(page: Page, *kinds: str) -> list[dict]:
    return [e for e in page.evaluate("() => window.__events") if e["type"] in kinds]


ADD = '#g-n1 [data-pjx-graph-action="add"]'
POSITION = """() => { const style = document.getElementById('g-n1').style;
    return [style.getPropertyValue('--pjx-graph-node-x'),
            style.getPropertyValue('--pjx-graph-node-y')]; }"""


# Actions


def test_clicking_an_action_fires_it_with_its_node_and_port(page, page_errors, session):
    _serve(page, _stage(session))
    page.click(ADD)
    assert _events(page, "action") == [
        {
            "type": "action",
            "detail": {"id": "n1", "action": "add", "port": "ok"},
            "target": "g",
        }
    ]
    assert _events(page, "before-select", "select") == []
    assert page_errors == []


def test_an_unnamed_action_is_inert_and_fires_nothing(page, page_errors, session):
    _serve(page, _stage(session))
    page.click("#badge")
    assert _events(page, "action", "before-select", "select") == []
    assert page_errors == []


def test_clicking_the_node_outside_its_actions_still_selects(
    page, page_errors, session
):
    _serve(page, _stage(session))
    page.click("#g-n1 .pjx-graph__node-title")
    assert [e["type"] for e in _events(page, "before-select", "select", "action")] == [
        "before-select",
        "select",
    ]
    assert page_errors == []


@pytest.mark.parametrize("selector", [ADD, "#badge"], ids=["named", "inert"])
def test_pressing_an_action_never_drags_the_node(page, page_errors, session, selector):
    _serve(page, _stage(session))
    box = page.locator(selector).bounding_box()
    assert box is not None
    page.mouse.move(box["x"] + 2, box["y"] + 2)
    page.mouse.down()
    page.mouse.move(box["x"] + 80, box["y"] + 60, steps=6)
    page.mouse.up()
    assert page.evaluate(POSITION) == ["100px", "100px"]
    assert _events(page, "move") == []
    assert page_errors == []


def test_an_action_in_a_nested_stage_belongs_to_that_stage(page, page_errors, session):
    inner = _stage(session, "in")
    outer = _stage(session, "g", icon=Markup(inner))
    css = (
        "#g-n1 { width: 640px; } #in { width: 560px; }"
        " #in > .pjx-graph__canvas { min-height: 0; height: 200px; }"
    )
    _serve(page, f"<style>{css}</style>{outer}", stages=("g", "in"))
    page.click('#in-n1 [data-pjx-graph-action="add"]')
    assert [(e["target"], e["detail"]) for e in _events(page, "action")] == [
        ("in", {"id": "n1", "action": "add", "port": "ok"})
    ]
    assert _events(page, "select") == []
    assert page_errors == []


# The view


def test_mounting_reports_no_view_and_view_reads_the_current_one(
    page, page_errors, session
):
    _serve(page, _stage(session))
    assert _events(page, "view") == []
    assert page.evaluate(
        "() => pjx.graph.get(document.getElementById('g')).view()"
    ) == {"x": 0, "y": 0, "k": 1}
    assert page_errors == []


def test_a_zoom_reports_the_view_it_ends_on(page, page_errors, session):
    _serve(page, _stage(session, controls=PJXGraphControls(id="g-controls")))
    page.click('#g [data-pjx-graph-zoom="in"]')
    page.wait_for_function("() => window.__events.some(e => e.type === 'view')")
    (event,) = _events(page, "view")
    current = page.evaluate("() => pjx.graph.get(document.getElementById('g')).view()")
    assert event["detail"] == current
    assert current["k"] == pytest.approx(2**0.5)
    assert event["target"] == "g"
    assert page_errors == []


def test_a_pan_reports_the_view_it_ends_on(page, page_errors, session):
    _serve(page, _stage(session))
    box = page.locator("#g > .pjx-graph__canvas").bounding_box()
    assert box is not None
    start = (box["x"] + box["width"] - 40, box["y"] + box["height"] - 40)
    page.mouse.move(*start)
    page.mouse.down()
    page.mouse.move(start[0] - 50, start[1] - 30, steps=5)
    page.mouse.up()
    assert [e["detail"] for e in _events(page, "view")] == [
        {"x": -50, "y": -30, "k": 1}
    ]
    assert page_errors == []
