"""Fixtures shared by every browser test: the chromium guard and error capture."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from playwright.sync_api import Page


@pytest.fixture(autouse=True)
def _require_chromium(request: pytest.FixtureRequest) -> None:
    # Function-scoped, not session-scoped: a session-scoped autouse fixture
    # only runs its body once for the whole run, against whichever test
    # triggers it first, so a later browser test could hit a raw Playwright
    # launch failure instead of a clean skip. Only tests that ask for a page
    # need chromium, so avoid resolving `browser_type` (or importing
    # playwright) for the rest.
    if not {"pjx_page", "pjx_full_page", "page"} & set(request.fixturenames):
        return
    pytest.importorskip("playwright")
    browser_type: Any = request.getfixturevalue("browser_type")
    if not Path(browser_type.executable_path).exists():
        pytest.skip(
            "chromium is not installed (run: uv run playwright install chromium)"
        )


@pytest.fixture
def page_errors(page: Page) -> list[str]:
    """Every uncaught error the page throws from here on."""
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    return errors


@pytest.fixture
def console_errors(page: Page) -> list[str]:
    """The text of every console.error the page logs from here on."""
    errors: list[str] = []
    page.on(
        "console", lambda msg: errors.append(msg.text) if msg.type == "error" else None
    )
    return errors
