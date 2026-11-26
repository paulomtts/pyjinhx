"""The vendored d3 subset the graph engine builds on (pjx_graph/src/d3.vendor.js).

The static checks read the committed bytes. The behaviour checks evaluate the
real minified file in chromium, since string-matching minified identifiers
proves nothing about what the bundle actually defines.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from playwright.sync_api import Page


SOURCE = (
    Path(__file__).resolve().parents[4]
    / "pyjinhx"
    / "builtins"
    / "pjx_graph"
    / "src"
    / "d3.vendor.js"
)


@pytest.fixture
def d3_page(page: Page) -> Iterator[Page]:
    """A blank page with the vendored file loaded as a classic script."""
    page.set_content(
        '<body><div id="canvas" style="width:400px;height:300px"></div></body>'
    )
    page.add_script_tag(content=SOURCE.read_text(encoding="utf-8"))
    yield page


def test_exposes_exactly_the_engine_surface(d3_page):
    kinds = d3_page.evaluate(
        "Object.fromEntries(Object.keys(__pjxD3).map(k => [k, typeof __pjxD3[k]]))"
    )
    assert kinds == {
        "select": "function",
        "pointer": "function",
        "zoom": "function",
        "zoomIdentity": "object",
        "zoomTransform": "function",
    }


def test_does_not_define_global_d3(d3_page):
    assert d3_page.evaluate("typeof window.d3") == "undefined"


def test_zoom_identity_builds_transforms(d3_page):
    assert (
        d3_page.evaluate("__pjxD3.zoomIdentity.translate(10, 20).scale(2).toString()")
        == "translate(10,20) scale(2)"
    )


def test_zoom_installs_on_an_element_and_reads_back_identity(d3_page):
    transform = d3_page.evaluate(
        """() => {
            const el = document.getElementById("canvas");
            __pjxD3.select(el).call(__pjxD3.zoom());
            const t = __pjxD3.zoomTransform(el);
            return {k: t.k, x: t.x, y: t.y};
        }"""
    )
    assert transform == {"k": 1, "x": 0, "y": 0}


def test_selection_has_transition_side_effect(d3_page):
    assert (
        d3_page.evaluate(
            'typeof __pjxD3.select(document.getElementById("canvas")).transition'
        )
        == "function"
    )


def test_evaluating_twice_does_not_throw(d3_page):
    d3_page.add_script_tag(content=SOURCE.read_text(encoding="utf-8"))
    assert d3_page.evaluate("typeof __pjxD3.zoom") == "function"


def test_binding_stays_local_inside_a_function_wrapper(page: Page):
    page.set_content("<body></body>")
    source = SOURCE.read_text(encoding="utf-8")
    page.add_script_tag(
        content=f"window.__wrapped = (function(){{\n{source}\n;return typeof __pjxD3;}})();"
    )
    assert page.evaluate("window.__wrapped") == "object"
    assert page.evaluate("typeof window.__pjxD3") == "undefined"
