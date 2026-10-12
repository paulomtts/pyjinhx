"""Fixtures shared by the graph builtin's render tests and browser tests."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from html.parser import HTMLParser
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from pyjinhx.session import RenderSession

if TYPE_CHECKING:
    from playwright.sync_api import Page

ASSET = (
    Path(__file__).resolve().parents[4]
    / "pyjinhx"
    / "builtins"
    / "ui"
    / "pjx_graph"
    / "pjx_graph.js"
)


class El:
    """One parsed element: tag, attributes (unescaped) and element children."""

    def __init__(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tag = tag
        self.attrs = dict(attrs)
        self.children: list[El] = []

    @property
    def classes(self) -> list[str]:
        return (self.attrs.get("class") or "").split()

    def descendants(self) -> list[El]:
        found: list[El] = []
        for child in self.children:
            found.append(child)
            found.extend(child.descendants())
        return found


class _TreeBuilder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.top = El("#document", [])
        self._stack = [self.top]

    def handle_starttag(self, tag, attrs):
        element = El(tag, attrs)
        self._stack[-1].children.append(element)
        self._stack.append(element)

    def handle_startendtag(self, tag, attrs):
        self._stack[-1].children.append(El(tag, attrs))

    def handle_endtag(self, tag):
        self._stack.pop()


@pytest.fixture
def session():
    return RenderSession()


@pytest.fixture
def parse_html() -> Callable[[str], list[El]]:
    """Parse markup into its top-level elements, so nesting is checked as tree facts."""

    def parse(html: str) -> list[El]:
        builder = _TreeBuilder()
        builder.feed(html)
        builder.close()
        return builder.top.children

    return parse


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


@pytest.fixture
def graph_page(page: Page, page_errors: list[str]) -> Iterator[Page]:
    """A blank page with the asset loaded once as a classic script."""
    page.set_content("<body></body>")
    page.add_script_tag(content=ASSET.read_text(encoding="utf-8"))
    yield page
