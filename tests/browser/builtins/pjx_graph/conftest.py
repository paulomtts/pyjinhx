"""Fixtures for the graph builtin's browser tests."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from playwright.sync_api import Page

ASSET = (
    Path(__file__).resolve().parents[4]
    / "pyjinhx"
    / "builtins"
    / "pjx_graph"
    / "pjx_graph.js"
)


@pytest.fixture
def graph_page(page: Page, page_errors: list[str]) -> Iterator[Page]:
    """A blank page with the asset loaded once as a classic script."""
    page.set_content("<body></body>")
    page.add_script_tag(content=ASSET.read_text(encoding="utf-8"))
    yield page
