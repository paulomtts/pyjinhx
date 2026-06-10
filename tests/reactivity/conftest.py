"""Fixtures for the browser-based reactivity tier.

Launches the kitchen-sink app (tests/reactivity/app.py) with uvicorn in a
background thread once per session, and skips the whole tier when playwright
or the chromium binary is unavailable so ``pytest tests/`` stays green.
"""

from __future__ import annotations

import socket
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
import uvicorn


@pytest.fixture(scope="session", autouse=True)
def _require_chromium() -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        pytest.skip("playwright is not installed")
    with sync_playwright() as playwright:
        executable = Path(playwright.chromium.executable_path)
    if not executable.exists():
        pytest.skip("chromium is not installed (run: uv run playwright install chromium)")


@pytest.fixture(scope="session")
def server_url() -> Iterator[str]:
    from tests.reactivity.app import create_app

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]

    config = uvicorn.Config(create_app(), host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, name="reactivity-app", daemon=True)
    thread.start()

    url = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + 15
    while True:
        try:
            httpx.get(f"{url}/healthz", timeout=1)
            break
        except httpx.HTTPError:
            if time.monotonic() > deadline:
                raise RuntimeError("reactivity test app did not come up within 15s")
            time.sleep(0.05)

    yield url

    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture
def sink_page(page, server_url: str):
    """The kitchen-sink page, freshly loaded."""
    page.goto(f"{server_url}/")
    return page
