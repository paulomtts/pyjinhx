"""Fixtures shared by every browser test: the chromium guard and error capture."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Error as PlaywrightError

if TYPE_CHECKING:
    from playwright.sync_api import Browser, Page


@pytest.fixture(scope="session")
def browser(launch_browser: Callable[[], Browser]) -> Iterator[Browser]:
    # Replaces pytest-playwright's `browser` so a missing chromium skips instead
    # of erroring. Launching is the only check that matches what it will run
    # (the headless shell, not the binary `executable_path` points at), and a
    # session fixture is set up before any function-scoped guard could run.
    # pytest caches the skip, so the launch is attempted once per session.
    try:
        browser = launch_browser()
    except PlaywrightError as error:
        pytest.skip(
            f"chromium is not installed (run: uv run playwright install chromium): "
            f"{str(error).splitlines()[0]}"
        )
    yield browser
    browser.close()


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
