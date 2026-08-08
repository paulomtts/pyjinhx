"""The page-loader builtin owns pjx.pageLoader; core keeps pjx.loader.page.

The two were colliding: the builtin wrote an object over core's ref-counted
toggle function, and its own guard read that function as truthy and bailed
out — leaving the cold-load overlay stuck active.
"""

from __future__ import annotations

from pyjinhx.assets import emit_assets
from pyjinhx.builtins.pjx_page_loader import PJXPageLoader
from pyjinhx.client.inject import inject_runtime
from pyjinhx.rendering import render
from pyjinhx.session import RenderSession, accumulate_assets


def _load(page):
    # Real order: inject_runtime's bundle (htmx, pjx.js, loading_indicator.js,
    # core's client/page_loader.js) is NOT the builtin under test — the
    # builtin's own JS only enters the page as a component-registered asset,
    # which requires actually rendering PJXPageLoader. emit_assets() puts
    # runtime_script (inject_runtime's bundle) before js_assets (the
    # component's own script), matching production load order.
    # RenderSession does not auto-subscribe accumulate_assets — it must be
    # registered explicitly for js_assets/css_assets to populate (see
    # tests/pyjinhx/builtins/test_pjx_page_loader.py).
    session = RenderSession()
    session.on_rendered.append(accumulate_assets)
    inject_runtime(session)
    body = render(PJXPageLoader(id="pl"), session)  # active_on_load defaults True
    page.set_content(f"<body>{body}{emit_assets(session)}</body>")
    return page


def test_page_loader_exports_its_object_under_pjx_pageloader(page):
    _load(page)
    for name in ("show", "hide", "wrap", "reset"):
        assert page.evaluate(f"typeof pjx.pageLoader.{name}") == "function"


def test_core_loader_page_toggle_survives_the_builtin(page):
    _load(page)
    assert page.evaluate("typeof pjx.loader.page") == "function"
    page.evaluate("pjx.loader.page(true)")
    assert page.evaluate("document.documentElement.className") == "pjx-loading--page"
    page.evaluate("pjx.loader.page(false)")
    assert page.evaluate("document.documentElement.className") == ""


def test_cold_load_clears_the_overlay(page):
    _load(page)
    assert (
        page.evaluate(
            "document.querySelector('[data-pjx-page-loader]')"
            ".classList.contains('pjx-page-loader--active')"
        )
        is False
    )
