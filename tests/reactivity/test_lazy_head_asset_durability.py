"""Regression for #184 — a builtin (PJXBreadcrumb) eagerly rendered on the cold
page *inside* a region that later re-renders must stay styled across the swap.

Cold renders emit the builtin's <style data-pjx-asset> inline in the body, inside
the region's subtree. pjxLoadedAssets reports that token as loaded, so on the swap
the server dedups it away and the swap deletes the only copy -> unstyled (count
drops to 0). The fix promotes the initial document's inline styles into <head> on
load, where they are durable.

Verifies:
1. After load, the breadcrumb CSS is promoted to <head> (0 inside the region).
2. After a swap that re-renders the region, the breadcrumb stays styled
   (.pjx-breadcrumb__list computes list-style-type: none, not decimal).
"""

from __future__ import annotations

import importlib.util
import socket
import sys
import threading
import time
from pathlib import Path

import httpx
import pytest

pytest.importorskip("playwright")

# Module scope so FastAPI resolves the `request: Request` annotation under
# `from __future__ import annotations`.
from fastapi import FastAPI  # noqa: E402
from playwright.sync_api import Page, expect  # noqa: E402

pytestmark = [pytest.mark.pjx_runtime, pytest.mark.reactivity]

_OUTER_MODULE = """\
from pyjinhx import BaseComponent


class Outer(BaseComponent):
    pass
"""

# {{ render_inner() }} is a jinja global returning a *separately* rendered
# breadcrumb (a fresh root render). Its inline <style> lands INSIDE #outer.
_OUTER_TEMPLATE = '<div id="{{ id }}" class="outer">{{ render_inner() }}</div>'

_PAGE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<script src="https://cdn.jsdelivr.net/npm/htmx.org@2.0.8/dist/htmx.min.js"
        integrity="sha384-/TgkGk7p307TH7EXJDuUlgG3Ce1UVolAOFopFekQkkXihi5u/6OCvVKyz1W+idaz"
        crossorigin="anonymous"></script>
</head>
<body>
<button id="refresh-btn" type="button"
        hx-get="/refresh" hx-target="#outer" hx-swap="outerHTML">Refresh</button>
{outer_markup}
{runtime}
</body>
</html>"""


def _make_app(tmp_path: Path) -> FastAPI:
    from fastapi.responses import HTMLResponse

    from pyjinhx import PjxSettings, setup
    from pyjinhx.builtins import PJXBreadcrumb
    from pyjinhx.client import client_script
    from pyjinhx.renderer import Renderer

    (tmp_path / "outer.html").write_text(_OUTER_TEMPLATE)
    module_path = tmp_path / "outer_component.py"
    module_path.write_text(_OUTER_MODULE)

    spec = importlib.util.spec_from_file_location("outer_component", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["outer_component"] = module
    spec.loader.exec_module(module)
    Outer = module.Outer

    def render_inner():
        # Fresh root render -> its inline <style data-pjx-asset> lands inside #outer.
        return PJXBreadcrumb(
            id="bc", items=[("Library", None), ("Finance", None)]
        ).render()

    app = FastAPI()
    setup(app, settings=PjxSettings(), components_root=tmp_path)

    def _use_components_root() -> None:
        Renderer.set_default_environment(tmp_path)
        Renderer.get_default_environment().globals["render_inner"] = render_inner

    @app.get("/healthz")
    def healthz() -> str:
        return "ok"

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        _use_components_root()
        outer_markup = Outer(id="outer").render()
        return _PAGE_HTML.format(outer_markup=outer_markup, runtime=client_script())

    @app.get("/refresh", response_class=HTMLResponse)
    def refresh() -> str:
        _use_components_root()
        # Re-render the same region. The htmx request carries X-PJX-Assets (incl.
        # the breadcrumb token, now in <head>), so the server dedups the CSS away.
        return str(Outer(id="outer").render())

    return app


@pytest.fixture(scope="module")
def durability_server(tmp_path_factory):
    import uvicorn

    tmp_path = tmp_path_factory.mktemp("durability_app")
    app = _make_app(tmp_path)

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, name="durability-app", daemon=True)
    thread.start()

    url = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + 15
    while True:
        try:
            httpx.get(f"{url}/healthz", timeout=1)
            break
        except httpx.HTTPError:
            if time.monotonic() > deadline:
                raise RuntimeError("durability test app did not come up within 15s")
            time.sleep(0.05)

    yield url

    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture
def durability_page(page: Page, durability_server: str) -> Page:
    page.goto(f"{durability_server}/")
    return page


def _list_style(page: Page) -> str:
    return page.evaluate(
        "getComputedStyle(document.querySelector('.pjx-breadcrumb__list'))"
        ".listStyleType"
    )


def _asset_count(page: Page) -> int:
    return page.evaluate("document.querySelectorAll('style[data-pjx-asset]').length")


def test_initial_inline_asset_is_promoted_to_head(durability_page: Page) -> None:
    """On load, the breadcrumb CSS is relocated from inside #outer into <head>."""
    expect(durability_page.locator(".pjx-breadcrumb__list")).to_be_visible()

    in_head = durability_page.evaluate(
        "document.head.querySelectorAll('style[data-pjx-asset]').length"
    )
    in_region = durability_page.evaluate(
        "document.querySelectorAll('#outer style[data-pjx-asset]').length"
    )
    assert in_head >= 1, "breadcrumb CSS was not promoted to <head>"
    assert in_region == 0, "breadcrumb CSS still lives inside the swappable region"
    assert _list_style(durability_page) == "none"


def test_breadcrumb_stays_styled_after_region_swap(durability_page: Page) -> None:
    """Re-rendering the region must not strip the breadcrumb's promoted CSS."""
    assert _list_style(durability_page) == "none"
    before = _asset_count(durability_page)

    # Grab the current breadcrumb node so we can wait for the swap to actually
    # complete (the old node detaches) before reading style — otherwise the
    # assertion can race the htmx swap and read the stale, pre-swap DOM.
    old_list = durability_page.query_selector("#outer .pjx-breadcrumb__list")
    assert old_list is not None
    durability_page.click("#refresh-btn")
    durability_page.wait_for_function("(old) => !old.isConnected", arg=old_list)
    expect(durability_page.locator("#outer .pjx-breadcrumb__list")).to_be_visible()

    # Still styled (the #184 regression made this compute 'decimal')...
    assert _list_style(durability_page) == "none"
    # ...and the asset count never collapsed to 0.
    assert _asset_count(durability_page) >= 1
    assert (
        _asset_count(durability_page) <= before
    )  # promoted copy reused, not duplicated
