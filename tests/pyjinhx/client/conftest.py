"""Browser harness for the pjx.js runtime.

Every function in pjx.js is DOM-bound, so the tests run the real file in real
chromium rather than asserting on source strings. Skips the browser fixtures
when playwright or chromium is unavailable so `pytest tests/` stays green —
the guard lives in the fixtures, not at module scope, because a module-scope
importorskip would also skip the plain-Python tests in this package.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from pyjinhx.client import read_pjx_runtime

if TYPE_CHECKING:
    from playwright.sync_api import Page


@pytest.fixture(autouse=True)
def _require_chromium(request: pytest.FixtureRequest) -> None:
    # Function-scoped, not session-scoped: a session-scoped autouse fixture
    # only runs its body once for the whole run, against whichever test
    # triggers it first — if that first test doesn't need pjx_page, the
    # chromium check would never fire again and a later browser test would
    # hit a raw Playwright launch failure instead of a clean skip. Only the
    # browser tests need chromium, so still avoid resolving `browser_type`
    # (or importing playwright) for a test that never asked for a page.
    if "pjx_page" not in request.fixturenames:
        return
    pytest.importorskip("playwright")
    browser_type: Any = request.getfixturevalue("browser_type")
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
