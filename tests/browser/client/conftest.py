"""Browser harness for the pjx.js runtime.

Every function in pjx.js is DOM-bound, so the tests run the real file in real
chromium rather than asserting on source strings. The chromium guard
lives in tests/browser/conftest.py.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import TYPE_CHECKING

import pytest

from pyjinhx.client import (
    read_loading_indicator_js,
    read_page_loader_js,
    read_pjx_runtime,
    read_pjx_style_css,
)

if TYPE_CHECKING:
    from playwright.sync_api import Page


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


@pytest.fixture
def pjx_full_page(page: Page) -> Iterator[Callable[..., Page]]:
    """`pjx_page` plus everything `inject_runtime` ships: artifacts and CSS.

    Separate from `pjx_page` so the core tests keep proving pjx.js alone never
    touches classList.
    """

    def load(body: str, head: str = "", with_htmx: bool = True) -> Page:
        page.set_content(f"<head>{head}</head><body>{body}</body>")
        if with_htmx:
            page.evaluate("window.htmx = {}")
        page.add_script_tag(content=read_pjx_runtime())
        page.add_script_tag(content=read_loading_indicator_js())
        page.add_script_tag(content=read_page_loader_js())
        page.add_style_tag(content=read_pjx_style_css())
        return page

    yield load
