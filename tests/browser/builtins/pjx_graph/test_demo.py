"""The gallery's graph demo page, built by the docs hooks and driven in real chromium.

The page is the real build output, served for a fake origin so its relative
demo-base.css link resolves, with the htmx + pjx.js runtime and the graph
engine inlined exactly as the docs site ships them.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

DOCS = Path(__file__).resolve().parents[4] / "docs"
sys.path.insert(0, str(DOCS))

import hooks

if TYPE_CHECKING:
    from playwright.sync_api import Page, Route

SITE = "http://pjx.test/"
URL = SITE + "demos/pjx-graph.html"

POSITION = """id => {
    const style = document.getElementById(id).style;
    return [style.getPropertyValue('--pjx-graph-node-x'),
            style.getPropertyValue('--pjx-graph-node-y')];
}"""


@pytest.fixture(scope="module")
def site(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A docs site_dir that on_post_build has written every demo page into."""
    root = tmp_path_factory.mktemp("site")
    hooks.on_post_build({"site_dir": str(root)})
    return root


def _serve(page: Page, site: Path) -> None:
    """Serve the built site for SITE, open the graph demo and wait for its stage."""

    def fulfill(route: Route) -> None:
        path = site / route.request.url.removeprefix(SITE)
        if path.is_file():
            route.fulfill(path=path)
        else:
            route.fulfill(status=204)

    page.route(SITE + "**", fulfill)
    page.goto(URL)
    page.wait_for_selector(
        "#demo-graph[data-pjx-graph-ready]", state="attached", timeout=5000
    )


def _center(page: Page, selector: str) -> tuple[float, float]:
    box = page.locator(selector).bounding_box()
    assert box is not None
    return box["x"] + box["width"] / 2, box["y"] + box["height"] / 2


def _drag(page: Page, start: tuple[float, float], end: tuple[float, float]) -> None:
    page.mouse.move(*start)
    page.mouse.down()
    page.mouse.move(*end, steps=6)
    page.mouse.up()


def test_the_page_boots_and_draws_its_initial_edges(
    page, page_errors, console_errors, site
):
    _serve(page, site)
    assert page.evaluate("() => typeof htmx.swap") == "function"
    assert page.locator("#demo-graph [data-node-id]").count() == 4
    assert page.locator("#demo-graph path.pjx-graph__edge").count() == 2
    assert page_errors == []
    assert console_errors == []


def test_dragging_a_node_moves_it(page, page_errors, console_errors, site):
    _serve(page, site)
    before = page.evaluate(POSITION, "demo-graph-fetch")
    x, y = _center(page, "#demo-graph-fetch .pjx-graph__node-title")
    _drag(page, (x, y), (x + 60, y + 40))
    assert page.evaluate(POSITION, "demo-graph-fetch") != before
    assert page_errors == []
    assert console_errors == []


NEW_EDGE = "transform-next-store"
INITIAL = [
    ["trigger-next-fetch", "trigger", "next", "fetch"],
    ["fetch-next-transform", "fetch", "next", "transform"],
]

# [id, from, port, to] of every edge span in the live edge layer, in order.
EDGE_SPANS = """() => Array.from(document.querySelectorAll(
    '#demo-graph-edges > [data-pjx-graph-edge]')).map((edge) => [
        edge.getAttribute('data-edge-id'), edge.getAttribute('data-from'),
        edge.getAttribute('data-port'), edge.getAttribute('data-to')])"""

KEEP_LAYER = "() => { window.__layer = document.getElementById('demo-graph-edges'); }"

PANEL_CONTENT = "#demo-graph-panel [data-pjx-graph-panel-content]"
CLOSE = "#demo-graph-panel [data-pjx-graph-panel-close]"

HOSTILE = '<b>x</b>" onclick="y'


def _wire(page: Page, source: str, target: str) -> None:
    """Drag a wire from node source's out-port onto node target's title."""
    _drag(
        page,
        _center(page, f'#demo-graph-{source} [data-pjx-graph-port="out"]'),
        _center(page, f"#demo-graph-{target} .pjx-graph__node-title"),
    )


def _wait_for_edge(page: Page, edge_id: str) -> None:
    page.wait_for_selector(
        f'#demo-graph path.pjx-graph__edge[data-edge-id="{edge_id}"]',
        state="attached",
        timeout=5000,
    )


def _panel_state(page: Page) -> str | None:
    return page.get_attribute("#demo-graph-panel", "data-open")


def _open(page: Page, node_id: str) -> None:
    page.click(f"#demo-graph-{node_id} .pjx-graph__node-title")


def test_a_wire_drop_swaps_the_edge_layer_out_of_band(
    page, page_errors, console_errors, site
):
    _serve(page, site)
    page.evaluate(KEEP_LAYER)
    _wire(page, "transform", "store")
    _wait_for_edge(page, NEW_EDGE)
    # A detached old element is what an outerHTML swap leaves behind.
    assert page.evaluate("() => window.__layer.isConnected") is False
    assert page.evaluate(EDGE_SPANS) == [
        *INITIAL,
        [NEW_EDGE, "transform", "next", "store"],
    ]
    assert page.locator("#demo-graph path.pjx-graph__edge").count() == 3
    assert page_errors == []
    assert console_errors == []


def test_repeating_a_wire_or_wiring_an_initial_edge_swaps_nothing(
    page, page_errors, console_errors, site
):
    _serve(page, site)
    _wire(page, "transform", "store")
    _wait_for_edge(page, NEW_EDGE)
    page.evaluate(KEEP_LAYER)
    _wire(page, "transform", "store")
    _wire(page, "trigger", "fetch")
    assert page.evaluate(
        "() => document.getElementById('demo-graph-edges') === window.__layer"
    )
    assert page.evaluate(EDGE_SPANS) == [
        *INITIAL,
        [NEW_EDGE, "transform", "next", "store"],
    ]
    assert page.locator("#demo-graph path.pjx-graph__edge").count() == 3
    assert page_errors == []
    assert console_errors == []


def test_clicking_nodes_fills_the_panel_and_its_close_button_closes_it(
    page, page_errors, console_errors, site
):
    _serve(page, site)
    assert _panel_state(page) == "false"
    _open(page, "trigger")
    assert _panel_state(page) == "true"
    assert "Starts a run at the top of every hour." in page.inner_text(PANEL_CONTENT)
    _open(page, "fetch")
    text = page.inner_text(PANEL_CONTENT)
    assert "Pulls the latest orders as JSON." in text
    assert "Starts a run" not in text
    page.click(CLOSE)
    assert _panel_state(page) == "false"
    # Closing resets the panel's history, so reopening fires panel:open again.
    _open(page, "trigger")
    assert _panel_state(page) == "true"
    assert "Starts a run at the top of every hour." in page.inner_text(PANEL_CONTENT)
    assert page_errors == []
    assert console_errors == []


def test_wire_detail_values_land_as_attribute_text_not_markup(
    page, page_errors, console_errors, site
):
    _serve(page, site)
    page.evaluate(
        """to => document.getElementById('demo-graph').dispatchEvent(
            new CustomEvent('pjx:graph:wire', {
                bubbles: true, detail: {from: 'transform', port: 'next', to}}))""",
        HOSTILE,
    )
    assert page.evaluate(EDGE_SPANS) == [
        *INITIAL,
        [f"transform-next-{HOSTILE}", "transform", "next", HOSTILE],
    ]
    assert page.locator("#demo-graph-edges b, #demo-graph-edges [onclick]").count() == 0
    assert page_errors == []
    assert console_errors == []


def test_a_swapped_in_edge_follows_a_dragged_node(
    page, page_errors, console_errors, site
):
    _serve(page, site)
    _wire(page, "transform", "store")
    _wait_for_edge(page, NEW_EDGE)
    edge = f'#demo-graph path.pjx-graph__edge[data-edge-id="{NEW_EDGE}"]'
    before = page.get_attribute(edge, "d")
    x, y = _center(page, "#demo-graph-store .pjx-graph__node-title")
    _drag(page, (x, y), (x + 40, y + 60))
    assert page.get_attribute(edge, "d") != before
    assert page_errors == []
    assert console_errors == []
