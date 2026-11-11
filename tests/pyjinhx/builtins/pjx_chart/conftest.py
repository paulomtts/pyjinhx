"""Fixtures for the chart's browser tests."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from playwright.sync_api import Page


@pytest.fixture(autouse=True)
def _require_chromium(request: pytest.FixtureRequest) -> None:
    # Function-scoped so a missing browser skips only the tests that ask for
    # a page, mirroring tests/pyjinhx/client/conftest.py.
    if "page" not in set(request.fixturenames):
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
