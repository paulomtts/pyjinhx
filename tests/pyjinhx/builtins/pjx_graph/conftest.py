"""Fixtures shared by the PJXGraph / PJXGraphNodes render tests."""

from __future__ import annotations

from collections.abc import Callable
from html.parser import HTMLParser

import pytest

from pyjinhx.session import RenderSession


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
    # template_dir="/" so the descriptor's absolute template path resolves,
    # same fixture shape as the sibling builtin tests.
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
