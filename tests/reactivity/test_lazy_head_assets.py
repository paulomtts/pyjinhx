"""Browser contract for #182 — a ``PJXLazyLoad`` fragment that introduces a builtin
whose CSS was never collected at page render must still render styled.

The lazy content's not-yet-present ``data-pjx-asset`` style used to be emitted inline
in the swapped body, where it was stripped on the htmx swap, leaving the content
unstyled. On a swap the render now ships missing assets as
``<style data-pjx-asset hx-swap-oob="beforeend:head">``; htmx core drops the head
OOB and ``pjx.js`` promotes it to ``<head>`` (deduped against the live document).

Verifies that on reveal of the lazy panel:
1. the new builtin's CSS reaches ``<head>`` and actually styles the swapped element, and
2. the count of ``style[data-pjx-asset]`` in the DOM *increases* (the regression
   in #182 was the count *decreasing* — the asset being stripped).
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

# Imported at module scope so FastAPI can resolve the ``request: Request``
# annotation on the route below under ``from __future__ import annotations``.
from fastapi import FastAPI, Request  # noqa: E402
from playwright.sync_api import Page, expect  # noqa: E402

pytestmark = [pytest.mark.pjx_runtime, pytest.mark.reactivity]

# ---------------------------------------------------------------------------
# Component module written to a temp components root
# ---------------------------------------------------------------------------

_COMPONENT_MODULE = '''\
from pyjinhx import BaseComponent


class LazyWidget(BaseComponent):
    label: str = ""
'''

_WIDGET_TEMPLATE = '<div id="{{ id }}" class="lazy-widget">{{ label }}</div>'

# htmx loads in <head>; the pyjinhx runtime is placed at the end of <body> (where
# it lands in production) because it binds listeners on document.body at load.
_PAGE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<script src="https://cdn.jsdelivr.net/npm/htmx.org@2.0.8/dist/htmx.min.js"
        integrity="sha384-/TgkGk7p307TH7EXJDuUlgG3Ce1UVolAOFopFekQkkXihi5u/6OCvVKyz1W+idaz"
        crossorigin="anonymous"></script>
</head>
<body>
<button id="load-btn" type="button">Load</button>
{lazy_markup}
{runtime}
</body>
</html>"""


def _make_lazy_app(tmp_path: Path) -> FastAPI:
    """Build a minimal FastAPI app whose lazy fragment carries a CSS-bearing builtin."""
    from fastapi.responses import HTMLResponse

    from pyjinhx import PjxSettings, setup
    from pyjinhx.builtins import PJXLazyLoad
    from pyjinhx.client import ClientBackend, client_script
    from pyjinhx.integrations.fastapi import FastAPIClientBackend
    from pyjinhx.renderer import Renderer

    # --------------- component + co-located template & assets -------------
    (tmp_path / "lazy_widget.html").write_text(_WIDGET_TEMPLATE)
    (tmp_path / "lazy-widget.css").write_text(
        ".lazy-widget { color: rgb(0, 128, 0); font-weight: bold; }"
    )
    module_path = tmp_path / "lazy_widget_component.py"
    module_path.write_text(_COMPONENT_MODULE)

    spec = importlib.util.spec_from_file_location("lazy_widget_component", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["lazy_widget_component"] = module
    spec.loader.exec_module(module)
    LazyWidget = module.LazyWidget

    # --------------- app --------------------------------------------------
    app = FastAPI()
    setup(app, settings=PjxSettings(), components_root=tmp_path)

    def _use_components_root() -> None:
        # The autouse conftest fixture resets the default environment around
        # every test; this module-scoped server outlives it, so point the
        # renderer back at our components root on each request.
        Renderer.set_default_environment(tmp_path)

    @app.get("/healthz")
    def healthz() -> str:
        return "ok"

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        _use_components_root()
        # The lazy region reveals on a button click; the widget's CSS lives only
        # inside the lazy fragment, so it cannot reach the page before the swap.
        lazy_markup = PJXLazyLoad(
            id="lazy-region",
            url="/fragments/lazy",
            trigger="click from:#load-btn",
            content='<p id="lazy-placeholder">Loading…</p>',
        ).render()
        return _PAGE_HTML.format(lazy_markup=lazy_markup, runtime=client_script())

    @app.get("/fragments/lazy", response_class=HTMLResponse)
    def lazy_fragment(request: Request) -> str:
        _use_components_root()
        backend = FastAPIClientBackend(request)
        with ClientBackend.scope(backend):
            return str(LazyWidget(id="lazy-widget", label="Loaded").render())

    return app


# ---------------------------------------------------------------------------
# Module-scoped server fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def lazy_server(tmp_path_factory):
    import uvicorn

    tmp_path = tmp_path_factory.mktemp("lazy_app")
    app = _make_lazy_app(tmp_path)

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, name="lazy-app", daemon=True)
    thread.start()

    url = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + 15
    while True:
        try:
            httpx.get(f"{url}/healthz", timeout=1)
            break
        except httpx.HTTPError:
            if time.monotonic() > deadline:
                raise RuntimeError("lazy test app did not come up within 15s")
            time.sleep(0.05)

    yield url

    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture
def lazy_page(page: Page, lazy_server: str) -> Page:
    page.goto(f"{lazy_server}/")
    return page


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def _asset_count(page: Page) -> int:
    return page.evaluate("document.querySelectorAll('style[data-pjx-asset]').length")


def test_cold_load_has_no_widget_css(lazy_page: Page) -> None:
    """Guard: the widget's CSS is absent until the lazy swap delivers it."""
    expect(lazy_page.locator("#lazy-placeholder")).to_be_visible()
    expect(lazy_page.locator("#lazy-widget")).to_have_count(0)
    assert _asset_count(lazy_page) == 0


def test_lazy_swap_promotes_css_and_styles_content(lazy_page: Page) -> None:
    """On reveal, the builtin's CSS reaches <head> and styles the swapped element."""
    before = _asset_count(lazy_page)

    lazy_page.click("#load-btn")
    expect(lazy_page.locator("#lazy-widget")).to_be_visible()

    # The promoted style must live in <head>...
    in_head = lazy_page.evaluate(
        "document.head.querySelectorAll('style[data-pjx-asset]').length"
    )
    assert in_head >= 1, "lazy widget CSS was not promoted to <head>"

    # ...the count must have GONE UP (the #182 regression was it going down)...
    assert _asset_count(lazy_page) > before

    # ...and the widget must actually be styled.
    color = lazy_page.evaluate(
        "getComputedStyle(document.querySelector('#lazy-widget')).color"
    )
    assert color == "rgb(0, 128, 0)", f"expected green, got {color!r}"
