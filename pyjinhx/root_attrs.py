"""Single-root validation and inline attribute injection for components.

A component's rendered template must contain exactly one top-level element
(React-style). Inline tag attributes collected from the component are spliced
into that root element's opening tag with override semantics.

This module is stdlib-only on purpose: it must not import ``base`` or
``renderer`` (both import each other), so it stays free of the cycle.
"""

import re
from html.parser import HTMLParser

# HTML void elements have no closing tag, so they never open a nesting level.
_VOID_ELEMENTS = frozenset(
    {
        "area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr",
    }
)


def serialize_attr(name: str, value: str) -> str:
    """Emit ``name="value"``; fall back to single quotes when the value has ``"``."""
    if '"' in value:
        if "'" in value:
            raise ValueError(
                f"attribute {name!r} value must not contain both '\"' and \"'\""
            )
        return f"{name}='{value}'"
    return f'{name}="{value}"'


class _RootScanner(HTMLParser):
    """Counts top-level elements and records the first root's opening-tag span."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self._depth = 0
        self.root_count = 0
        self.root_start: int | None = None
        self.root_tag_text: str | None = None
        self._line_offsets: list[int] = [0]

    def feed(self, data: str) -> None:
        # Map (line, col) from getpos() to absolute string offsets.
        offset = 0
        self._line_offsets = [0]
        for line in data.splitlines(keepends=True):
            offset += len(line)
            self._line_offsets.append(offset)
        super().feed(data)

    def _abs_offset(self) -> int:
        line, col = self.getpos()
        return self._line_offsets[line - 1] + col

    def _record_top_level(self) -> None:
        if self._depth == 0:
            self.root_count += 1
            if self.root_count == 1:
                self.root_start = self._abs_offset()
                self.root_tag_text = self.get_starttag_text()

    def handle_starttag(self, tag, attrs):
        self._record_top_level()
        if tag.lower() not in _VOID_ELEMENTS:
            self._depth += 1

    def handle_startendtag(self, tag, attrs):  # <tag/> — self-contained
        self._record_top_level()

    def handle_endtag(self, tag):
        if self._depth > 0:
            self._depth -= 1


def find_single_root(html: str, *, component_name: str) -> tuple[int, int]:
    """Return the (start, end) char span of the sole root element's opening tag.

    Raises ``ValueError`` unless ``html`` has exactly one top-level element.
    """
    scanner = _RootScanner()
    scanner.feed(html)
    scanner.close()
    if scanner.root_count != 1 or scanner.root_start is None or scanner.root_tag_text is None:
        raise ValueError(
            f"<{component_name}> template must render exactly one root element "
            f"(found {scanner.root_count})"
        )
    start = scanner.root_start
    return start, start + len(scanner.root_tag_text)


def _override_tag(tag_text: str, attrs: dict[str, str]) -> str:
    """Apply ``attrs`` onto a single opening-tag string with override semantics."""
    body = tag_text
    for name, value in attrs.items():
        pair = serialize_attr(name, value)
        pattern = re.compile(
            r"\s" + re.escape(name) + r"\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s/>]*)"
        )
        if pattern.search(body):
            body = pattern.sub(" " + pair, body, count=1)
        elif body.rstrip().endswith("/>"):
            idx = body.rindex("/>")
            body = body[:idx].rstrip() + " " + pair + body[idx:]  # rstrip intentional: prevents extra space before '/>' (e.g. '<br data-y="1"/>' not '<br  data-y="1"/>')
        else:
            idx = body.rindex(">")
            body = body[:idx] + " " + pair + body[idx:]
    return body


def apply_root_attrs(html: str, *, component_name: str, attrs: dict[str, str]) -> str:
    """Validate the single-root invariant and inject ``attrs`` into the root tag."""
    start, end = find_single_root(html, component_name=component_name)
    if not attrs:
        return html
    new_tag = _override_tag(html[start:end], attrs)
    return html[:start] + new_tag + html[end:]
