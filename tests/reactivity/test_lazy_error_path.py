"""Browser contract for #191 — a ``PJXLazyLoad`` whose own request fails
terminally must replace its placeholder with an inline error affordance.

htmx never swaps on a non-2xx response, and the lazy trigger is usually
consumed (``once``), so without a driver the placeholder (skeleton/spinner)
reads "loading…" forever. ``pjx-lazy-load.js`` listens for the element's own
terminal ``htmx:afterRequest`` (``!detail.successful``) and swaps in either the
author's ``error`` slot or a default ``role="alert"`` message.
"""

from __future__ import annotations

import socket
import threading
import time
from pathlib import Path

import httpx
import pytest

pytest.importorskip("playwright")

from fastapi import FastAPI, Request  # noqa: E402
from playwright.sync_api import Page, expect  # noqa: E402

pytestmark = [pytest.mark.pjx_runtime, pytest.mark.reactivity]

# htmx in <head>; the pyjinhx runtime at the end of <body> (binds on body).
_PAGE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<script src="https://cdn.jsdelivr.net/npm/htmx.org@2.0.8/dist/htmx.min.js"
        integrity="sha384-/TgkGk7p307TH7EXJDuUlgG3Ce1UVolAOFopFekQkkXihi5u/6OCvVKyz1W+idaz"
        crossorigin="anonymous"></script>
</head>
<body>
<button id="btn-default" type="button">Load default</button>
<button id="btn-custom" type="button">Load custom</button>
{default_markup}
{custom_markup}
{runtime}
</body>
</html>"""


def _make_app() -> FastAPI:
    from fastapi.responses import HTMLResponse

    from pyjinhx import PjxSettings, setup
    from pyjinhx.builtins import PJXLazyLoad
    from pyjinhx.client import client_script

    app = FastAPI()
    setup(app, settings=PjxSettings())

    @app.get("/healthz")
    def healthz() -> str:
        return "ok"

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        default_markup = PJXLazyLoad(
            id="lazy-default",
            url="/fragments/fail",
            trigger="click from:#btn-default",
            content='<p id="ph-default">Loading…</p>',
        ).render()
        custom_markup = PJXLazyLoad(
            id="lazy-custom",
            url="/fragments/fail",
            trigger="click from:#btn-custom",
            content='<p id="ph-custom">Loading…</p>',
            error='<p class="custom-error">Custom boom</p>',
        ).render()
        return _PAGE_HTML.format(
            default_markup=default_markup,
            custom_markup=custom_markup,
            runtime=client_script(),
        )

    @app.get("/fragments/fail", response_class=HTMLResponse)
    def fail(request: Request) -> HTMLResponse:
        return HTMLResponse("<p>boom</p>", status_code=500)

    return app


@pytest.fixture(scope="module")
def error_server(tmp_path_factory):
    import uvicorn

    app = _make_app()

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, name="lazy-error-app", daemon=True)
    thread.start()

    url = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + 15
    while True:
        try:
            httpx.get(f"{url}/healthz", timeout=1)
            break
        except httpx.HTTPError:
            if time.monotonic() > deadline:
                raise RuntimeError("lazy error test app did not come up within 15s")
            time.sleep(0.05)

    yield url

    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture
def error_page(page: Page, error_server: str) -> Page:
    page.goto(f"{error_server}/")
    return page


def test_placeholder_present_before_any_request(error_page: Page) -> None:
    """Guard: placeholders are shown and not yet in an error state."""
    expect(error_page.locator("#ph-default")).to_be_visible()
    expect(error_page.locator("#lazy-default.pjx-lazy-load--error")).to_have_count(0)


def test_terminal_failure_shows_default_error(error_page: Page) -> None:
    error_page.click("#btn-default")

    region = error_page.locator("#lazy-default")
    expect(region).to_have_class("pjx-lazy-load pjx-lazy-load--error")
    alert = region.locator(".pjx-lazy-load__error")
    expect(alert).to_be_visible()
    expect(alert).to_have_text("Failed to load.")
    assert alert.get_attribute("role") == "alert"
    # The placeholder is gone — never a forever-spinner.
    expect(error_page.locator("#ph-default")).to_have_count(0)


def test_terminal_failure_uses_custom_error_slot(error_page: Page) -> None:
    error_page.click("#btn-custom")

    region = error_page.locator("#lazy-custom")
    expect(region).to_have_class("pjx-lazy-load pjx-lazy-load--error")
    custom = region.locator(".custom-error")
    expect(custom).to_be_visible()
    expect(custom).to_have_text("Custom boom")
    expect(error_page.locator("#ph-custom")).to_have_count(0)
