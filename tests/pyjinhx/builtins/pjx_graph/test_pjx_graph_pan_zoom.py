"""Pan, wheel zoom and the persisted view of a mounted stage, in real chromium.

d3-zoom reacts to real pointer and wheel events over laid-out boxes, so every
stage is served from a real origin with the graph CSS applied. The view is
read back from the viewport's computed transform, since d3 is not on window.
"""

from __future__ import annotations

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
# One wheel notch of deltaY -100 zooms by 2 ** 0.2 under d3's default wheelDelta.
NOTCH = 2**0.2

# Absolutely placed so it never sits over the background point the tests press.
CONTROLS = Markup(
    '<button id="fit" type="button" style="position:absolute;right:8px;bottom:8px">'
    "Fit</button>"
)

# CSSOM keeps about six significant digits, so k read back is compared loosely.
VIEW = """id => {
    const viewport = document.querySelector(
        '#' + id + ' > .pjx-graph__canvas > .pjx-graph__viewport');
    const m = new DOMMatrix(getComputedStyle(viewport).transform);
    return {x: m.e, y: m.f, k: m.a};
}"""


def _stage(session, stage_id: str = "g", **graph) -> str:
    node = PJXGraphNode(
        id=f"{stage_id}-n1",
        node_id="n1",
        x=100,
        y=100,
        title="Start",
        in_port=True,
        out_ports=("ok",),
    )
    nodes = PJXGraphNodes(id=f"{stage_id}-nodes", nodes_html=node)
    graph.setdefault("controls", CONTROLS)
    return render(PJXGraph(id=stage_id, nodes=nodes, **graph), session)


def _serve(page: Page, body: str) -> None:
    """Load body with the graph CSS and asset as a real page on a real origin."""
    asset = ASSET.read_text(encoding="utf-8")
    html = (
        f"<html><head><style>{CSS}</style></head>"
        f"<body>{body}<script>{asset}</script></body></html>"
    )
    page.route(URL, lambda route: route.fulfill(body=html, content_type="text/html"))
    page.goto(URL)


def _view(page: Page, stage_id: str = "g") -> dict[str, float]:
    return page.evaluate(VIEW, stage_id)


def _wait_for_k(page: Page, k: float, stage_id: str = "g") -> None:
    page.wait_for_function(
        f"([id, k]) => Math.abs(({VIEW})(id).k - k) < 1e-3", arg=[stage_id, k]
    )


def _center(page: Page, selector: str) -> tuple[int, int]:
    box = page.locator(selector).bounding_box()
    assert box is not None
    return round(box["x"] + box["width"] / 2), round(box["y"] + box["height"] / 2)


def _background(page: Page, stage_id: str = "g") -> tuple[int, int]:
    """A point on empty canvas, well clear of the node and the controls."""
    box = page.locator(f"#{stage_id} > .pjx-graph__canvas").bounding_box()
    assert box is not None
    return round(box["x"] + 600), round(box["y"] + 300)


def _drag(page: Page, start: tuple[int, int], button: str = "left") -> None:
    x, y = start
    page.mouse.move(x, y)
    page.mouse.down(button=button)
    page.mouse.move(x + 60, y + 40, steps=4)
    page.mouse.up(button=button)


def _wheel(page: Page, at: tuple[int, int], notches: int = 1, dy: int = -100) -> None:
    page.mouse.move(*at)
    for _ in range(notches):
        page.mouse.wheel(0, dy)


def _identity(view: dict[str, float]) -> bool:
    return view == pytest.approx({"x": 0, "y": 0, "k": 1}, abs=1e-6)


def test_mounted_viewport_carries_the_identity_transform(page, page_errors, session):
    _serve(page, _stage(session))
    style = page.evaluate(
        "() => document.querySelector('#g .pjx-graph__viewport').style.transform"
    )
    assert style == "translate(0px, 0px) scale(1)"
    assert page_errors == []


def test_dragging_the_background_pans_by_the_pointer_delta(page, page_errors, session):
    _serve(page, _stage(session))
    _drag(page, _background(page))
    assert _view(page) == pytest.approx({"x": 60, "y": 40, "k": 1}, abs=0.01)
    assert page_errors == []


def test_wheel_zooms_about_the_pointer(page, page_errors, session):
    _serve(page, _stage(session))
    x, y = _background(page)
    world = """([x, y]) => {
        const canvas = document.querySelector('#g > .pjx-graph__canvas');
        const r = canvas.getBoundingClientRect();
        const m = new DOMMatrix(getComputedStyle(
            canvas.querySelector(':scope > .pjx-graph__viewport')).transform);
        return [(x - r.left - canvas.clientLeft - m.e) / m.a,
                (y - r.top - canvas.clientTop - m.f) / m.a];
    }"""
    before = page.evaluate(world, [x, y])
    _wheel(page, (x, y))
    _wait_for_k(page, NOTCH)
    assert page.evaluate(world, [x, y]) == pytest.approx(before, abs=0.05)
    assert page_errors == []


def test_double_click_on_the_background_does_not_zoom(page, page_errors, session):
    _serve(page, _stage(session))
    page.mouse.dblclick(*_background(page))
    # d3's double-click zoom would animate over 250 ms.
    page.wait_for_timeout(400)
    assert _identity(_view(page))
    assert page_errors == []


def test_mounting_twice_attaches_one_zoom(page, page_errors, session):
    _serve(page, _stage(session))
    page.evaluate("() => pjx.graph.mount(document.getElementById('g'))")
    _wheel(page, _background(page))
    _wait_for_k(page, NOTCH)
    page.wait_for_timeout(100)
    assert _view(page)["k"] == pytest.approx(NOTCH, abs=1e-3)
    assert page_errors == []
