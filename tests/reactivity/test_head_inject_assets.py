"""Browser contracts for head-injection of missing INLINE assets on reactive OOB swaps.

Verifies that:
1. CSS injected into <head> via hx-swap-oob actually styles content (no FOUC).
2. JS injected into <head> via hx-swap-oob actually executes in the browser.
3. Duplicate tokens are NOT re-injected (idempotency guard).
"""

from __future__ import annotations

import json
import socket
import threading
import time
from pathlib import Path

import httpx
import pytest

pytest.importorskip("playwright")

from playwright.sync_api import Page, expect  # noqa: E402

pytestmark = [pytest.mark.pjx_runtime, pytest.mark.reactivity]

# ---------------------------------------------------------------------------
# Minimal swap app
# ---------------------------------------------------------------------------

_BADGE_TEMPLATE = '<span id="{{ id }}" class="swap-badge">{{ count }}</span>'

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
</body>
</html>"""


def _make_swap_app(tmp_path: Path) -> object:
    """Build a minimal FastAPI app that serves a reactive component with CSS/JS."""
    from fastapi import FastAPI, Request
    from fastapi.responses import HTMLResponse

    from pyjinhx import MutationKey, PjxSettings, ReactiveComponent, setup

    # --------------- assets -----------------------------------------------
    css_path = tmp_path / "swap-badge.css"
    js_path = tmp_path / "swap-badge.js"
    css_path.write_text(
        ".swap-badge { color: rgb(255, 0, 0); font-weight: bold; }"
    )
    js_path.write_text(
        "window.__pjxHeadInjectRan = (window.__pjxHeadInjectRan || 0) + 1;"
    )

    # --------------- mutation key -----------------------------------------
    class BadgeKey(MutationKey):
        BADGE = "badge"

    # --------------- component --------------------------------------------
    class SwapBadge(
        ReactiveComponent,
        react={BadgeKey.BADGE},
        pjx_replace=True,
    ):
        count: int = 0

        def render(self) -> str:  # type: ignore[override]
            return str(self._render(source=_BADGE_TEMPLATE))

        @classmethod
        def load(cls) -> "SwapBadge":  # type: ignore[override]
            return cls(
                id="swap-badge",
                count=0,
                css=[str(css_path)],
                js=[str(js_path)],
            )

    # --------------- app --------------------------------------------------
    app = FastAPI()
    setup(app, settings=PjxSettings())

    @app.get("/healthz")
    def healthz() -> str:
        return "ok"

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        badge = SwapBadge(
            id="swap-badge", count=0, css=[str(css_path)], js=[str(js_path)]
        )
        return _PAGE_HTML.format(badge_markup=badge.render())

    @app.post("/increment", response_class=HTMLResponse)
    async def increment(request: Request) -> str:
        from pyjinhx.client import ClientBackend
        from pyjinhx.integrations.fastapi import FastAPIClientBackend
        from pyjinhx.reactive import oob_swaps

        backend = FastAPIClientBackend(request)
        manifest_str = request.headers.get("X-PJX-Mounted", "[]")
        manifest = json.loads(manifest_str)

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


def test_head_injected_css_styles_swapped_content(swap_page: Page) -> None:
    """CSS OOB-injected into <head> must actually style the swapped element."""
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
    """<script> OOB-injected into <head> must execute in the browser."""
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
