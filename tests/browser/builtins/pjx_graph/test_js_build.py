"""The single pjx_graph.js asset, loaded in chromium.

Only a running page can show what the file leaves on window. The byte checks
live in tests/unit/builtins/pjx_graph/test_js_build.py.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.sync_api import Page


ROOT = Path(__file__).resolve().parents[4]


GRAPH_DIR = ROOT / "pyjinhx" / "builtins" / "pjx_graph"


ASSET = GRAPH_DIR / "pjx_graph.js"


def test_asset_defines_pjx_graph_and_leaks_no_d3(graph_page, page_errors):
    assert graph_page.evaluate("typeof window.pjx.graph") == "object"
    assert graph_page.evaluate("typeof window.__pjxD3") == "undefined"
    assert graph_page.evaluate("typeof window.d3") == "undefined"
    assert page_errors == []


def test_reloading_keeps_the_same_graph_namespace(graph_page, page_errors):
    graph_page.evaluate("window.pjx.graph.marker = 1")
    graph_page.add_script_tag(content=ASSET.read_text(encoding="utf-8"))
    assert graph_page.evaluate("window.pjx.graph.marker") == 1
    assert page_errors == []


def test_loading_keeps_an_existing_pjx_namespace(page: Page, page_errors):
    page.set_content("<body></body>")
    page.add_script_tag(content="window.pjx = {other: 1};")
    page.add_script_tag(content=ASSET.read_text(encoding="utf-8"))
    assert page.evaluate("window.pjx.other") == 1
    assert page.evaluate("typeof window.pjx.graph") == "object"
    assert page_errors == []
