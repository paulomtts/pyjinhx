"""Pan, wheel zoom and the persisted view of a mounted stage, in real chromium.

d3-zoom reacts to real pointer and wheel events over laid-out boxes, so every
stage is served from a real origin with the graph CSS applied. The view is
read back from the viewport's computed transform, since d3 is not on window.
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


@pytest.mark.parametrize(
    "selector",
    [
        "#g-n1 .pjx-graph__node-title",
        '#g-n1 [data-pjx-graph-port="in"]',
        '#g-n1 [data-pjx-graph-port="out"]',
        "#fit",
    ],
    ids=["node", "in-port", "out-port", "control"],
)
def test_a_press_off_the_background_does_not_pan(page, page_errors, session, selector):
    _serve(page, _stage(session))
    # The drag ends over empty canvas; only where it started matters.
    _drag(page, _center(page, selector))
    assert _identity(_view(page))
    assert page_errors == []


def test_a_press_on_an_edge_element_does_not_pan(page, page_errors, session):
    _serve(page, _stage(session))
    page.evaluate(
        """() => document.querySelector('#g .pjx-graph__edge-plane').insertAdjacentHTML(
            'beforeend',
            '<rect id="edge-hit" x="20" y="20" width="60" height="40"'
            + ' style="pointer-events: all"></rect>')"""
    )
    _drag(page, _center(page, "#edge-hit"))
    assert _identity(_view(page))
    assert page_errors == []


@pytest.mark.parametrize("button", ["right", "middle"])
def test_a_non_primary_button_does_not_pan(page, page_errors, session, button):
    _serve(page, _stage(session))
    _drag(page, _background(page), button=button)
    assert _identity(_view(page))
    assert page_errors == []


def test_a_ctrl_press_does_not_pan(page, page_errors, session):
    _serve(page, _stage(session))
    page.keyboard.down("Control")
    _drag(page, _background(page))
    page.keyboard.up("Control")
    assert _identity(_view(page))
    assert page_errors == []


def test_wheel_over_a_node_or_a_control_zooms(page, page_errors, session):
    _serve(page, _stage(session))
    _wheel(page, _center(page, "#g-n1 .pjx-graph__node-title"))
    _wait_for_k(page, NOTCH)
    _wheel(page, _center(page, "#fit"))
    _wait_for_k(page, NOTCH**2)
    assert page_errors == []


def test_the_side_panel_never_pans_or_zooms(page, page_errors, session):
    panel = Markup('<aside id="panel" style="height:120px">Details</aside>')
    _serve(page, _stage(session, panel=panel))
    panel_point = _center(page, "#panel")
    _drag(page, panel_point)
    _wheel(page, panel_point)
    page.wait_for_timeout(100)
    assert _identity(_view(page))
    assert page_errors == []


def test_wheel_clamps_to_the_stage_scale_range(page, page_errors, session):
    _serve(page, _stage(session, scale_min=0.5, scale_max=3))
    point = _background(page)
    _wheel(page, point, notches=20)
    _wait_for_k(page, 3)
    _wheel(page, point, notches=30, dy=100)
    _wait_for_k(page, 0.5)
    assert page_errors == []


def test_missing_scale_attributes_default_to_the_component_range(
    page, page_errors, session
):
    html = re.sub(r' data-pjx-graph-scale-(min|max)="[^"]*"', "", _stage(session))
    assert "data-pjx-graph-scale" not in html
    _serve(page, html)
    point = _background(page)
    _wheel(page, point, notches=20)
    _wait_for_k(page, 2)
    _wheel(page, point, notches=30, dy=100)
    _wait_for_k(page, 0.2)
    assert page_errors == []


def test_wheel_at_the_end_of_the_range_does_not_scroll_the_page(
    page, page_errors, session
):
    _serve(page, _stage(session, scale_min=1) + '<div style="height:3000px"></div>')
    # Wheel-out at the minimum: d3 ignores it, and the page below could scroll.
    _wheel(page, _background(page), notches=3, dy=100)
    page.wait_for_timeout(200)
    assert page.evaluate("() => window.scrollY") == 0
    assert _identity(_view(page))
    assert page_errors == []


@pytest.mark.parametrize(
    ("attribute", "value"),
    [
        ("min", "abc"),
        ("min", "0"),
        ("min", "-1"),
        ("max", "Infinity"),
        ("min", ""),
        ("min", "3"),
    ],
    ids=["not-a-number", "zero", "negative", "infinite", "empty", "min-above-max"],
)
def test_invalid_scale_attributes_fail_the_mount(
    page, page_errors, session, attribute, value
):
    html = re.sub(
        rf'data-pjx-graph-scale-{attribute}="[^"]*"',
        f'data-pjx-graph-scale-{attribute}="{value}"',
        _stage(session),
    )
    _serve(page, "")
    result = page.evaluate(
        """html => {
            const host = document.createElement('div');
            host.innerHTML = html;
            const el = host.firstElementChild;
            try {
                pjx.graph.mount(el);
            } catch (error) {
                const canvas = el.querySelector('.pjx-graph__canvas');
                return [error.message, pjx.graph.get(el), '__zoom' in canvas];
            }
            return 'did not throw';
        }""",
        html,
    )
    assert result[0].startswith("pjx.graph.mount: invalid scale range")
    assert result[1:] == [None, False]
    assert page_errors == []


def test_boot_logs_an_invalid_scale_range_and_boots_the_rest(
    page, page_errors, console_errors, session
):
    bad = _stage(session, "bad").replace(
        'data-pjx-graph-scale-min="0.2"', 'data-pjx-graph-scale-min="abc"'
    )
    _serve(page, bad + _stage(session))
    assert page.evaluate("() => pjx.graph.get(document.getElementById('g')) !== null")
    assert page.evaluate("() => pjx.graph.get(document.getElementById('bad'))") is None
    assert len(console_errors) == 1
    assert "pjx.graph.mount: invalid scale range" in console_errors[0]
    assert page_errors == []


# Persistence


def _record(page: Page) -> dict:
    raw = page.evaluate("key => localStorage.getItem(key)", RECORD)
    assert raw is not None
    return json.loads(raw)


def _wait_for_saved_k(page: Page, k: float) -> None:
    page.wait_for_function(
        """([key, k]) => {
            const view = JSON.parse(localStorage.getItem(key) || '{}').view;
            return view !== undefined && Math.abs(view.k - k) < 1e-6;
        }""",
        arg=[RECORD, k],
    )


def _seed(page: Page, value: str) -> None:
    """Store value under the record key before the page's own scripts run."""
    page.add_init_script(
        f"localStorage.setItem({json.dumps(RECORD)}, {json.dumps(value)});"
    )


def test_the_view_survives_a_reload(page, page_errors, session):
    _serve(page, _stage(session, storage_key="flow"))
    point = _background(page)
    _drag(page, point)
    _wheel(page, point)
    _wait_for_saved_k(page, NOTCH)
    before = _view(page)
    page.reload()
    assert _view(page) == pytest.approx(before, abs=0.01)
    assert page_errors == []


def test_a_pan_saves_the_view_record(page, page_errors, session):
    _serve(page, _stage(session, storage_key="flow"))
    _drag(page, _background(page))
    page.wait_for_function("key => localStorage.getItem(key) !== null", arg=RECORD)
    record = _record(page)
    assert list(record) == ["view"]
    assert record["view"] == pytest.approx({"x": 60, "y": 40, "k": 1}, abs=0.01)
    assert page_errors == []


def test_mounting_alone_writes_nothing(page, page_errors, session):
    _serve(page, _stage(session, storage_key="flow"))
    assert page.evaluate("() => localStorage.length") == 0
    assert page_errors == []


def test_saving_keeps_the_record_other_fields(page, page_errors, session):
    positions = {"n1": {"x": 5, "y": 6, "base": [100, 100]}}
    _seed(page, json.dumps({"positions": positions}))
    _serve(page, _stage(session, storage_key="flow"))
    _wheel(page, _background(page))
    _wait_for_saved_k(page, NOTCH)
    record = _record(page)
    assert record["positions"] == positions
    assert record["view"]["k"] == pytest.approx(NOTCH)
    assert page_errors == []


def test_a_stored_scale_above_the_range_is_clamped(page, page_errors, session):
    _seed(page, json.dumps({"view": {"x": 30, "y": 20, "k": 9}}))
    _serve(page, _stage(session, storage_key="flow", scale_max=3))
    assert _view(page) == pytest.approx({"x": 30, "y": 20, "k": 3}, abs=0.01)
    assert page_errors == []


@pytest.mark.parametrize(
    "stored",
    [
        "{not json",
        "null",
        "[1, 2]",
        '"view"',
        '{"view": null}',
        '{"view": {"x": "10", "y": 0, "k": 1}}',
        '{"view": {"x": 0, "y": 0, "k": 0}}',
        '{"view": {"x": 0, "y": 0, "k": -2}}',
        '{"view": {"x": 0, "y": 0}}',
    ],
)
def test_an_unusable_record_starts_at_identity_silently(
    page, page_errors, console_errors, session, stored
):
    _seed(page, stored)
    _serve(page, _stage(session, storage_key="flow"))
    assert _identity(_view(page))
    _drag(page, _background(page))
    assert _view(page) == pytest.approx({"x": 60, "y": 40, "k": 1}, abs=0.01)
    assert console_errors == []
    assert page_errors == []


def test_saving_over_an_array_record_writes_an_object(page, page_errors, session):
    _seed(page, "[1, 2]")
    _serve(page, _stage(session, storage_key="flow"))
    _drag(page, _background(page))
    page.wait_for_function(
        "key => !localStorage.getItem(key).startsWith('[')", arg=RECORD
    )
    assert list(_record(page)) == ["view"]
    assert page_errors == []


def test_without_a_storage_key_nothing_is_stored(page, page_errors, session):
    _serve(page, _stage(session))
    point = _background(page)
    _drag(page, point)
    _wheel(page, point)
    _wait_for_k(page, NOTCH)
    # Past d3's 150 ms wheel debounce, when a save would have happened.
    page.wait_for_timeout(300)
    assert page.evaluate("() => localStorage.length") == 0
    assert page_errors == []


BROKEN_STORAGE = {
    "getItem": "Storage.prototype.getItem = () => { throw new Error('denied'); };",
    "getter": (
        "Object.defineProperty(window, 'localStorage', {"
        " get() { throw new DOMException('denied', 'SecurityError'); } });"
    ),
}


@pytest.mark.parametrize("broken", list(BROKEN_STORAGE))
def test_unreadable_storage_mounts_at_identity_and_pans(
    page, page_errors, console_errors, session, broken
):
    page.add_init_script(BROKEN_STORAGE[broken])
    _serve(page, _stage(session, storage_key="flow"))
    assert _identity(_view(page))
    point = _background(page)
    _drag(page, point)
    _wheel(page, point)
    _wait_for_k(page, NOTCH)
    page.wait_for_timeout(300)
    assert console_errors == []
    assert page_errors == []


def test_unwritable_storage_keeps_pan_and_zoom_working(
    page, page_errors, console_errors, session
):
    page.add_init_script(
        "Storage.prototype.setItem = () => { throw new Error('quota'); };"
    )
    _serve(page, _stage(session, storage_key="flow"))
    point = _background(page)
    _drag(page, point)
    _wheel(page, point)
    _wait_for_k(page, NOTCH)
    page.wait_for_timeout(300)
    assert _view(page)["k"] == pytest.approx(NOTCH, abs=1e-3)
    assert console_errors == []
    assert page_errors == []


def test_a_swapped_in_stage_restores_the_saved_view(page, page_errors, session):
    _serve(page, _stage(session, storage_key="flow"))
    point = _background(page)
    _drag(page, point)
    _wheel(page, point)
    _wait_for_saved_k(page, NOTCH)
    before = _view(page)
    page.evaluate(
        """html => {
            window.oldRoot = document.getElementById('g');
            window.oldRoot.outerHTML = html;
        }""",
        _stage(session, storage_key="flow"),
    )
    page.wait_for_function(
        """() => {
            const el = document.getElementById('g');
            return el !== window.oldRoot && pjx.graph.get(el) !== null;
        }"""
    )
    assert _view(page) == pytest.approx(before, abs=0.01)
    assert page_errors == []
