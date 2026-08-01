"""Browser harness for the pjx.js runtime.

Every function in pjx.js is DOM-bound, so the tests run the real file in real
chromium rather than asserting on source strings. Skips the whole module when
playwright or chromium is unavailable so `pytest tests/` stays green.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from pyjinhx2.client import read_pjx_runtime

pytest.importorskip("playwright")

from playwright.sync_api import Page  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _require_chromium(browser_type) -> None:  # noqa: ANN001
    # Check via pytest-playwright's own `browser_type` fixture rather than
    # opening a second `sync_playwright()` context here: two independent
    # sync_playwright instances in one process race and break every
    # subsequent browser test in the suite ("using Playwright Sync API
    # inside the asyncio event loop").
    executable = Path(browser_type.executable_path)
    if not executable.exists():
        pytest.skip(
            "chromium is not installed (run: uv run playwright install chromium)"
        )


@pytest.fixture
def pjx_page(page: Page) -> Iterator[Callable[..., Page]]:
    """Load `body` into the page, then run pjx.js against it.

    `head` seeds pre-existing <head> assets; `with_htmx` stubs window.htmx so the
    runtime takes its normal path (the missing-htmx case opts out).
    """

    def load(body: str, head: str = "", with_htmx: bool = True) -> Page:
        page.set_content(f"<head>{head}</head><body>{body}</body>")
        if with_htmx:
            page.evaluate("window.htmx = {}")
        page.add_script_tag(content=read_pjx_runtime())
        return page

    yield load
