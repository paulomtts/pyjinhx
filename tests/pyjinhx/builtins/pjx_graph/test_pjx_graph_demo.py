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
