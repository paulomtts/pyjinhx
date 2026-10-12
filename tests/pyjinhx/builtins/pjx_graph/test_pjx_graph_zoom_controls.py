"""The zoom and fit controls and zoomBy/fit on a mounted stage, in real chromium.

d3-zoom needs real layout and real pointer events, so every stage is served
from a real origin with the graph CSS applied. The view is read back from the
viewport's computed transform, since d3 is not on window. Tests that need a
known start seed a persisted identity view, the one view a fit never overrides.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

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
    (UI / name / f"{name}.css").read_text(encoding="utf-8")
    for name in ("pjx_graph", "pjx_graph_node", "pjx_graph_controls")
)
URL = "http://pjx.test/"
RECORD = "pjx-graph:flow"
# One control step; two steps double or halve the scale.
STEP = math.sqrt(2)
# One wheel notch of deltaY -100 zooms by 2 ** 0.2 under d3's default wheelDelta.
NOTCH = 2**0.2
IDENTITY = json.dumps({"view": {"x": 0, "y": 0, "k": 1}})

# CSSOM keeps about six significant digits, so k read back is compared loosely.
VIEW = """id => {
    const viewport = document.querySelector(
        '#' + id + ' > .pjx-graph__canvas > .pjx-graph__viewport');
    const m = new DOMMatrix(getComputedStyle(viewport).transform);
    return {x: m.e, y: m.f, k: m.a};
}"""

CANVAS_SIZE = """id => {
    const canvas = document.querySelector('#' + id + ' > .pjx-graph__canvas');
    return {width: canvas.clientWidth, height: canvas.clientHeight};
}"""

BUTTONS = {
    "in": '[data-pjx-graph-zoom="in"]',
    "out": '[data-pjx-graph-zoom="out"]',
    "fit": "[data-pjx-graph-fit]",
}


def _stage(session, stage_id: str = "g", **graph) -> str:
    node = PJXGraphNode(id=f"{stage_id}-n1", node_id="n1", x=100, y=100, title="Start")
    nodes = PJXGraphNodes(id=f"{stage_id}-nodes", nodes_html=node)
    graph.setdefault("controls", PJXGraphControls(id=f"{stage_id}-controls"))
    return render(PJXGraph(id=stage_id, nodes=nodes, **graph), session)


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
    # A stage whose mount failed never gets ready, so only mounted ones count.
    page.wait_for_function(
        """() => Array.from(document.querySelectorAll('[data-pjx-graph]'))
            .every(s => !pjx.graph.get(s) || s.hasAttribute('data-pjx-graph-ready'))""",
        timeout=5000,
    )


def _seed(page: Page, value: str) -> None:
    """Store value under the record key before the page's own scripts run."""
    page.add_init_script(
        f"localStorage.setItem({json.dumps(RECORD)}, {json.dumps(value)});"
    )


def _at_identity(page: Page, session, **graph) -> str:
    """The default stage, starting from a persisted identity view so no fit moves it."""
    _seed(page, IDENTITY)
    return _stage(session, storage_key="flow", **graph)


def _view(page: Page, stage_id: str = "g") -> dict[str, float]:
    return page.evaluate(VIEW, stage_id)


def _wait_for_k(page: Page, k: float, stage_id: str = "g") -> None:
    page.wait_for_function(
        f"([id, k]) => Math.abs(({VIEW})(id).k - k) < 1e-3",
        arg=[stage_id, k],
        timeout=5000,
    )


def _centred(page: Page, k: float, stage_id: str = "g") -> dict[str, float]:
    """The view at scale k reached from identity by zooming about the canvas centre."""
    size = page.evaluate(CANVAS_SIZE, stage_id)
    return {
        "x": size["width"] / 2 * (1 - k),
        "y": size["height"] / 2 * (1 - k),
        "k": k,
    }


def _identity(view: dict[str, float]) -> bool:
    return view == pytest.approx({"x": 0, "y": 0, "k": 1}, abs=1e-6)


def _call(page: Page, method: str, *args, stage_id: str = "g") -> None:
    page.evaluate(
        """([id, method, args]) =>
            pjx.graph.get(document.getElementById(id))[method](...args)""",
        [stage_id, method, list(args)],
    )


def _center(page: Page, selector: str) -> tuple[int, int]:
    box = page.locator(selector).bounding_box()
    assert box is not None
    return round(box["x"] + box["width"] / 2), round(box["y"] + box["height"] / 2)


def _corner(page: Page, stage_id: str = "g") -> tuple[int, int]:
    """A point just inside the canvas's top-left corner, which a fit leaves empty."""
    box = page.locator(f"#{stage_id} > .pjx-graph__canvas").bounding_box()
    assert box is not None
    return round(box["x"] + 12), round(box["y"] + 12)


def _drag(page: Page, start: tuple[int, int]) -> None:
    x, y = start
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x + 60, y + 40, steps=4)
    page.mouse.up()


# zoomBy and fit


def test_zoom_by_steps_about_the_canvas_centre(page, page_errors, session):
    _serve(page, _at_identity(page, session))
    _call(page, "zoomBy", 1)
    _wait_for_k(page, STEP)
    assert _view(page) == pytest.approx(_centred(page, STEP), abs=0.05)
    _call(page, "zoomBy", -2)
    _wait_for_k(page, 1 / STEP)
    assert _view(page) == pytest.approx(_centred(page, 1 / STEP), abs=0.05)
    assert page_errors == []


def test_zoom_by_zero_changes_nothing(page, page_errors, session):
    _serve(page, _at_identity(page, session))
    _call(page, "zoomBy", 0)
    page.wait_for_timeout(100)
    assert _identity(_view(page))
    assert page_errors == []


def test_zoom_by_clamps_to_the_stage_range(page, page_errors, session):
    _serve(page, _at_identity(page, session, scale_min=0.5, scale_max=2))
    for k in (STEP, 2, 2):
        _call(page, "zoomBy", 1)
        _wait_for_k(page, k)
    assert _view(page) == pytest.approx(_centred(page, 2), abs=0.05)
    _call(page, "zoomBy", -2)
    _wait_for_k(page, 1)
    for k in (1 / STEP, 0.5, 0.5):
        _call(page, "zoomBy", -1)
        _wait_for_k(page, k)
    assert page_errors == []


def test_a_huge_step_clamps_to_the_range(page, page_errors, session):
    _serve(page, _at_identity(page, session, scale_min=0.5, scale_max=2))
    # sqrt(2) ** 5000 is Infinity and ** -5000 is 0 in float arithmetic.
    _call(page, "zoomBy", 5000)
    _wait_for_k(page, 2)
    assert _view(page) == pytest.approx(_centred(page, 2), abs=0.05)
    _call(page, "zoomBy", -5000)
    _wait_for_k(page, 0.5)
    view = _view(page)
    assert all(math.isfinite(value) for value in view.values())
    assert page_errors == []


@pytest.mark.parametrize(
    "expression",
    ["NaN", "Infinity", "-Infinity", "'in'", "'1'", "undefined", "null"],
)
def test_zoom_by_rejects_a_non_finite_dir(page, page_errors, session, expression):
    _serve(page, _at_identity(page, session))
    message = page.evaluate(
        f"""() => {{
            try {{
                pjx.graph.get(document.getElementById('g')).zoomBy({expression});
            }} catch (error) {{
                return error.message;
            }}
            return 'did not throw';
        }}"""
    )
    assert message == "pjx.graph.zoomBy: dir must be a finite number"
    page.wait_for_timeout(100)
    assert _identity(_view(page))
    assert page_errors == []


def test_fit_reframes_after_a_pan(page, page_errors, session):
    _serve(page, _stage(session))
    fitted = _view(page)
    _drag(page, _corner(page))
    assert _view(page) != pytest.approx(fitted, abs=0.05)
    _call(page, "fit")
    assert _view(page) == pytest.approx(fitted, abs=0.05)
    assert page_errors == []


def test_fit_on_a_stage_with_no_visible_node_keeps_the_view(page, page_errors, session):
    _serve(page, _at_identity(page, session))
    page.evaluate("() => { document.getElementById('g-n1').style.display = 'none'; }")
    _call(page, "fit")
    assert _identity(_view(page))
    assert page_errors == []


def test_a_zoom_by_continues_into_the_wheel(page, page_errors, session):
    _serve(page, _at_identity(page, session))
    _call(page, "zoomBy", 1)
    _wait_for_k(page, STEP)
    box = page.locator("#g > .pjx-graph__canvas").bounding_box()
    assert box is not None
    page.mouse.move(round(box["x"] + 600), round(box["y"] + 300))
    page.mouse.wheel(0, -100)
    _wait_for_k(page, STEP * NOTCH)
    assert page_errors == []
