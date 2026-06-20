"""Browser contracts for head-injection of missing INLINE assets on reactive OOB swaps.

These exercise the case the feature exists for: a region whose CSS/JS are NOT on
the page at cold load and arrive only on a later OOB swap, as
``<style|script data-pjx-asset hx-swap-oob="beforeend:head">``. htmx core silently
drops OOB swaps that target ``<head>`` (issue #105), so ``pjx.js`` must insert these
itself. Verifies that:

1. CSS delivered on the swap actually styles the swapped content (no FOUC).
2. JS delivered on the swap actually executes in the browser.
3. Duplicate tokens are NOT re-injected (idempotency guard).

To keep the swap honest, the cold-load page is served with its ``data-pjx-asset``
tags stripped: the badge marker (and its manifest entry) are present, but the CSS
and JS are absent until the swap delivers them via the head OOB. The component
lives in a temp module so its co-located template and assets are discovered the
real way (``oob_swaps`` re-renders it from the template, pulling the assets in).
"""

from __future__ import annotations

import importlib.util
import json
import re
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
from fastapi import Request  # noqa: E402
from playwright.sync_api import Page, expect  # noqa: E402

pytestmark = [pytest.mark.pjx_runtime, pytest.mark.reactivity]

# ---------------------------------------------------------------------------
# Component module written to a temp components root
# ---------------------------------------------------------------------------

_COMPONENT_MODULE = '''\
from pyjinhx import MutationKey, ReactiveComponent


class BadgeKey(MutationKey):
    BADGE = "badge"


# Bumped by the /increment route so each swap re-renders with a new state hash.
COUNT = {"value": 0}


class SwapBadge(ReactiveComponent, react={BadgeKey.BADGE}, pjx_replace=True):
    count: int = 0

    @classmethod
    def load(cls) -> "SwapBadge":
        return cls(id="swap-badge", count=COUNT["value"])
'''

_BADGE_TEMPLATE = '<span id="{{ id }}" class="swap-badge">{{ count }}</span>'

# Strip any <style|script data-pjx-asset ...> tag (the component's inline assets)
# so the cold-load page carries the badge marker but NOT its CSS/JS — they may
# only reach the page via the swap.
_ASSET_TAG_RE = re.compile(
    r"<(style|script)\b[^>]*\bdata-pjx-asset=[^>]*>.*?</\1>", re.DOTALL
)

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
{badge_markup}
<button id="inc-btn" hx-post="/increment" hx-swap="none" hx-trigger="click">Inc</button>
{runtime}
</body>
</html>"""


def _make_swap_app(tmp_path: Path) -> object:
    """Build a minimal FastAPI app that serves a reactive component with CSS/JS."""
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse

    from pyjinhx import PjxSettings, setup
    from pyjinhx.client import client_script
    from pyjinhx.renderer import Renderer

    # --------------- component + co-located template & assets -------------
    (tmp_path / "swap_badge.html").write_text(_BADGE_TEMPLATE)
    (tmp_path / "swap-badge.css").write_text(
        ".swap-badge { color: rgb(255, 0, 0); font-weight: bold; }"
    )
    (tmp_path / "swap-badge.js").write_text(
        "window.__pjxHeadInjectRan = (window.__pjxHeadInjectRan || 0) + 1;"
    )
    module_path = tmp_path / "swap_badge_component.py"
    module_path.write_text(_COMPONENT_MODULE)

    spec = importlib.util.spec_from_file_location("swap_badge_component", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["swap_badge_component"] = module
    spec.loader.exec_module(module)
    SwapBadge = module.SwapBadge
    BadgeKey = module.BadgeKey

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
        module.COUNT["value"] = 0
        # Strip the badge's inline asset tags: the region is on the page but its
        # CSS/JS are not, so the swap is the only path that can deliver them.
        badge_markup = _ASSET_TAG_RE.sub("", SwapBadge.load().render())
        return _PAGE_HTML.format(
            badge_markup=badge_markup, runtime=client_script()
        )

    @app.post("/increment", response_class=HTMLResponse)
    async def increment(request: Request) -> str:
        from pyjinhx.client import ClientBackend
        from pyjinhx.integrations.fastapi import FastAPIClientBackend
        from pyjinhx.reactive import oob_swaps

        _use_components_root()
        module.COUNT["value"] += 1  # change state so the region is actually swapped
        backend = FastAPIClientBackend(request)
        manifest = json.loads(request.headers.get("X-PJX-Mounted", "[]"))

        with ClientBackend.scope(backend):
            return str(oob_swaps({BadgeKey.BADGE}, manifest))

    return app


# ---------------------------------------------------------------------------
# Module-scoped server fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def swap_server(tmp_path_factory):
    import uvicorn

    tmp_path = tmp_path_factory.mktemp("swap_app")
    app = _make_swap_app(tmp_path)

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, name="swap-app", daemon=True)
    thread.start()

    url = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + 15
    while True:
        try:
            httpx.get(f"{url}/healthz", timeout=1)
            break
        except httpx.HTTPError:
            if time.monotonic() > deadline:
                raise RuntimeError("swap test app did not come up within 15s")
            time.sleep(0.05)

    yield url

    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture
def swap_page(page: Page, swap_server: str) -> Page:
    page.goto(f"{swap_server}/")
    return page


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_cold_load_has_no_badge_assets(swap_page: Page) -> None:
    """Guard: the badge's CSS/JS must be absent at cold load (only the swap delivers them)."""
    expect(swap_page.locator("#swap-badge")).to_be_visible()
    present = swap_page.evaluate(
        "document.querySelectorAll('[data-pjx-asset]').length"
    )
    assert present == 0, f"expected no badge assets on cold load, found {present}"
    # And the badge is unstyled (default color), proving the CSS has not arrived.
    color = swap_page.evaluate(
        "getComputedStyle(document.querySelector('#swap-badge')).color"
    )
    assert color != "rgb(255, 0, 0)", "CSS reached the page before any swap"


def test_head_injected_css_styles_swapped_content(swap_page: Page) -> None:
    """CSS delivered on the swap (head OOB) must actually style the swapped element."""
    badge = swap_page.locator("#swap-badge")
    expect(badge).to_be_visible()

    # Click the button → htmx POSTs /increment → server sends OOB assets
    swap_page.click("#inc-btn")
    swap_page.wait_for_timeout(800)

    # The OOB style should now be in <head>; computed color must be red
    color = swap_page.evaluate(
        "getComputedStyle(document.querySelector('#swap-badge')).color"
    )
    assert color == "rgb(255, 0, 0)", f"Expected red, got {color!r}"


def test_head_injected_script_executes(swap_page: Page) -> None:
    """<script> delivered on the swap (head OOB) must execute in the browser."""
    swap_page.click("#inc-btn")
    swap_page.wait_for_timeout(800)

    ran = swap_page.evaluate("window.__pjxHeadInjectRan")
    assert ran and ran >= 1, f"Expected JS to have run at least once, got {ran!r}"


def test_head_injected_assets_are_idempotent(swap_page: Page) -> None:
    """Clicking twice must not re-run the injected <script>."""
    swap_page.click("#inc-btn")
    swap_page.wait_for_timeout(800)
    first_run = swap_page.evaluate("window.__pjxHeadInjectRan")

    swap_page.click("#inc-btn")
    swap_page.wait_for_timeout(800)
    second_run = swap_page.evaluate("window.__pjxHeadInjectRan")

    assert first_run == second_run, (
        f"JS re-executed on second swap: ran {first_run} then {second_run} times"
    )
