"""Fixtures shared by the roster picker family's render tests and browser tests."""

from __future__ import annotations

from collections.abc import Callable
from html.parser import HTMLParser
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from pyjinhx.session import RenderSession

if TYPE_CHECKING:
    from playwright.sync_api import Page

# HTMLParser reports an unclosed <input> as a plain start tag, so without this
# list the tree builder would push it and nest every later sibling inside it.
VOID_ELEMENTS = frozenset(
    {
        "area",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "source",
        "track",
        "wbr",
    }
)


class El:
    """One parsed element: tag, attributes (unescaped), element children and own text."""

    def __init__(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tag = tag
        self.attrs = dict(attrs)
        self.children: list[El] = []
        self.text_parts: list[str] = []

    @property
    def classes(self) -> list[str]:
        return (self.attrs.get("class") or "").split()

    @property
    def text(self) -> str:
        """The element's own text, unescaped, without its descendants' text."""
        return "".join(self.text_parts)

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
        if tag not in VOID_ELEMENTS:
            self._stack.append(element)

    def handle_startendtag(self, tag, attrs):
        self._stack[-1].children.append(El(tag, attrs))

    def handle_endtag(self, tag):
        if tag not in VOID_ELEMENTS:
            self._stack.pop()

    def handle_data(self, data):
        self._stack[-1].text_parts.append(data)


@pytest.fixture
def session() -> RenderSession:
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
