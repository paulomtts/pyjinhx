"""Segment model: the types every other v2 module trusts (ADR 0002).

Import-pure — stdlib only. Nothing in pyjinhx may be imported here.
"""

import re
from dataclasses import dataclass
from html.parser import HTMLParser


@dataclass(slots=True)
class ChildRef:
    """One opaque hole in a parent's markup: a ``<PJXButton .../>`` tag, unresolved.

    The single parse of a parent's output (ADR 0005) cuts each component tag it
    finds out of the markup and leaves a ChildRef in its place, so the parent's
    own text is never re-scanned and a child's rendered markup is never re-parsed
    by its parent (ADR 0002, opaque children by construction).

    ``tag`` and ``attrs`` are exactly what the parse saw — no registry lookup, no
    value coercion. ``inner`` is the raw markup between a paired tag's open and
    close, captured verbatim by that same parse, or None for a self-closing tag.
    It is never re-parsed, resolved or escaped here: expanding the components
    inside it is L1's job (ADR 0002, ADR 0005).
    """

    tag: str
    attrs: dict[str, str]
    inner: str | None


@dataclass(slots=True)
class RenderedLevel:
    """One component's rendered output: its own markup cut into ordered segments.

    Children enter ``segments`` as whole RenderedLevel objects, never as text.
    ``root_span`` is the (start, end) offset of the root tag inside ``segments[0]``,
    recorded by the parse that produced the cut — later attr stamping is a splice
    at that offset, never a re-parse.
    """

    segments: list["str | ChildRef | RenderedLevel"]
    root_span: tuple[int, int]
    descriptor: object  # typed loosely to stay import-pure


RE_PASCAL_CASE_TAG_NAME = re.compile(r"^[A-Z](?=[A-Za-z0-9]*[a-z])[A-Za-z0-9]*$")
RE_TAG_OPENER = re.compile(r"<\s*([A-Za-z][A-Za-z0-9]*)")
RE_RAW_END_TAG = re.compile(r"</[^>]*>")
RE_RAW_END_TAG_NAME = re.compile(r"</\s*([A-Za-z][A-Za-z0-9]*)")
RE_RAW_COMMENT = re.compile(r"<!--.*?-->|<!\[.*?\]\]?>", re.DOTALL)

# HTML void elements have no closing tag, so they never open a nesting level —
# `<img>` without a trailing slash arrives through handle_starttag but must not
# push depth. Duplicated from v0.x's pyjinhx/root_attrs.py rather than imported:
# this module is import-pure and may not reach into pyjinhx (ADR 0002).
_VOID_ELEMENTS = frozenset(
    {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }
)


def _attrs_to_dict(attrs: "list[tuple[str, str | None]]") -> dict[str, str]:
    """HTMLParser reports a bare/boolean attr with a value of None; ChildRef.attrs
    is dict[str, str], so those become "" — same convention as v0.x's
    ``Parser._attrs_to_dict`` at pyjinhx/tags.py:68-69. Values are otherwise passed
    through exactly as parsed: no coercion, no registry lookup (ADR 0002)."""
    return {name: value or "" for name, value in attrs}


def contains_custom_tag(markup: str) -> bool:
    """Cheap check: does ``markup`` contain any PascalCase-tag-looking substring?

    The gate in front of the single parse (ADR 0005): output with no component
    tag in it never pays for a parser feed. Regex-only and O(n) — it must
    never itself parse.
    """
    if "<" not in markup:
        return False
    for match in RE_TAG_OPENER.finditer(markup):
        if RE_PASCAL_CASE_TAG_NAME.match(match.group(1)):
            return True
    return False


class VerbatimParser(HTMLParser):
    """Lossless HTML parser: markup in, same markup out as a flat segment list.

    Every event handler appends the *raw source text* for that event, so
    ``"".join(parser.segments)`` reproduces the input exactly — attribute
    quoting, attribute order, unknown and boolean attrs, odd casing and
    intentionally malformed HTML all survive untouched. There is no tag tree.

    Top-level PascalCase tags are cut and replaced with ChildRef objects.
    The first tag event's raw span is recorded in ``root_span`` (start, end
    offsets into the original source), enabling later attribute splicing at
    exact positions without re-parsing.

    ``root_span`` is an offset into the raw source text, not into ``segments``.
    It is recorded before ``segments[0]`` even exists in the self-closing case.
    When the root is itself a ChildRef, ``segments[0]`` cannot be sliced by any
    offset; ``root_span`` must always be read against the original markup, never
    against ``segments[0]`` directly.

    A self-closing top-level component tag becomes ``ChildRef(tag, attrs,
    inner=None)`` at its exact position. A paired top-level tag
    (``<PJXButton>body</PJXButton>``) collapses on its close tag: the body is
    joined into one raw string, dropped from ``segments``, and replaced with a
    single ``ChildRef(tag, attrs, inner)``. Either way, ``segments`` stays
    ``[str, ..., ChildRef, ..., str]`` in document order.

    Only the outermost open component tag is a cut point. Tags nested inside a
    still-open component tag are never cut and never re-scanned: their close tag
    pops its own stack entry but collapses nothing, so the tag survives verbatim
    inside the ancestor's ``inner`` for a later level's parse to deal with.

    Unlike legacy parsers, ``handle_data`` does not re-escape with
    ``markupsafe.escape``. This module is import-pure (stdlib only) and
    unnecessary here anyway — v2 parses Jinja output with autoescape already on,
    so escaping would double-encode.

    ``close()`` is not overridden and never raises on unclosed tags: a non-empty
    stack at EOF is fine, and a mismatched close tag is passed through without
    popping. Single-root validation lives in ``enforce_single_root``, which
    callers invoke explicitly after ``close()`` — parsing itself never raises.

    Known limitation: markup truncated mid-construct at EOF (``"<div"``,
    ``"<!-- unclosed"``) does not round-trip — HTMLParser drops or completes
    the fragment on ``close()``.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.segments: list[str | ChildRef] = []
        self.root_span: tuple[int, int] | None = None
        self._source = ""
        self._line_starts: list[int] = [0]
        self._custom_stack: list[tuple[str, int, dict[str, str]]] = []
        self._open_elements: list[str] = []
        self._top_level_count = 0
        self._extra_root_texts: list[str] = []

    def feed(self, data: str) -> None:
        """Parse ``data`` and record line positions for offset recovery."""
        self._source = data
        self._line_starts = [0] + [i + 1 for i, char in enumerate(data) if char == "\n"]
        super().feed(data)

    def _raw_at(self, pattern: "re.Pattern[str]") -> "str | None":
        """Match pattern at current position, returning raw matched text or None."""
        line, column = self.getpos()
        match = pattern.match(self._source, self._line_starts[line - 1] + column)
        return match.group(0) if match else None

    def _record_root_span(self, raw: str) -> None:
        """Record first tag's span (start, end offsets into source); idempotent."""
        if self.root_span is not None:
            return
        line, column = self.getpos()
        start = self._line_starts[line - 1] + column
        self.root_span = (start, start + len(raw))

    def _count_root_candidate(self, raw: str) -> None:
        """Count top-level tag events; store extras for error reporting."""
        if self._open_elements:
            return
        self._top_level_count += 1
        if self._top_level_count > 1:
            self._extra_root_texts.append(raw)

    def _close_open_element(self, tag: str) -> None:
        """Pop the innermost open element named ``tag``, and everything under it.

        A close tag naming nothing on the stack (``</span>`` with no open span) is
        a no-op, so stray close tags can neither invent a top level nor consume a
        real one. A close tag naming an ancestor (``<div><p>hi</div>``) pops the
        levels it swallows, so the next tag is correctly seen as top-level again.
        """
        if tag not in self._open_elements:
            return
        index = len(self._open_elements) - 1 - self._open_elements[::-1].index(tag)
        del self._open_elements[index:]

    def enforce_single_root(self) -> None:
        """Raise unless the parsed markup had exactly one top-level element."""
        if self._top_level_count == 0:
            raise ValueError(
                "template must render exactly one root element, but it renders "
                f"no element at all: {self._source!r}"
            )
        if self._top_level_count > 1:
            extras = ", ".join(repr(raw) for raw in self._extra_root_texts)
            raise ValueError(
                "template must render exactly one root element, but it renders "
                f"{self._top_level_count}; the extra top-level tags are: {extras}"
            )

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        raw = self.get_starttag_text() or f"<{tag}>"
        self._record_root_span(raw)
        self._count_root_candidate(raw)
        if tag not in _VOID_ELEMENTS:
            self._open_elements.append(tag)
        name = self._custom_tag_name(raw)
        if name is not None:
            self._custom_stack.append((name, len(self.segments), _attrs_to_dict(attrs)))
        self.segments.append(raw)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        raw = self.get_starttag_text() or f"<{tag}/>"
        self._record_root_span(raw)
        self._count_root_candidate(raw)
        name = self._custom_tag_name(raw)
        if name is not None and not self._custom_stack:
            self.segments.append(
                ChildRef(tag=name, attrs=_attrs_to_dict(attrs), inner=None)
            )
            return
        self.segments.append(raw)

    def handle_endtag(self, tag: str) -> None:
        raw = self._raw_at(RE_RAW_END_TAG) or f"</{tag}>"
        self._close_open_element(tag)
        name = self._custom_tag_name(raw)
        if (
            name is not None
            and self._custom_stack
            and self._custom_stack[-1][0] == name
        ):
            open_name, index, attrs = self._custom_stack.pop()
            if not self._custom_stack:
                inner = "".join(
                    segment
                    for segment in self.segments[index + 1 :]
                    if isinstance(segment, str)
                )
                del self.segments[index:]
                self.segments.append(ChildRef(tag=open_name, attrs=attrs, inner=inner))
                return
        self.segments.append(raw)

    def _custom_tag_name(self, raw: str) -> "str | None":
        """Extract PascalCase tag name from raw text if present."""
        match = RE_TAG_OPENER.match(raw) or RE_RAW_END_TAG_NAME.match(raw)
        if match is not None and RE_PASCAL_CASE_TAG_NAME.match(match.group(1)):
            return match.group(1)
        return None

    def handle_data(self, data: str) -> None:
        self.segments.append(data)

    def handle_entityref(self, name: str) -> None:
        self.segments.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self.segments.append(f"&#{name};")

    def handle_comment(self, data: str) -> None:
        # HTMLParser routes marked sections like `<![if IE]>` here too, having
        # already rewritten them into comment form, so recover the source text.
        self.segments.append(self._raw_at(RE_RAW_COMMENT) or f"<!--{data}-->")

    def handle_decl(self, decl: str) -> None:
        self.segments.append(f"<!{decl}>")

    def handle_pi(self, data: str) -> None:
        self.segments.append(f"<?{data}>")

    def unknown_decl(self, data: str) -> None:
        # `<![CDATA[x]]>` arrives as `CDATA[x]`; the base class would drop it.
        self.segments.append(self._raw_at(RE_RAW_COMMENT) or f"<![{data}]>")


def splice(level: RenderedLevel, offset: int, text: str) -> RenderedLevel:
    """Insert ``text`` into ``level.segments[0]`` at ``offset``, updating ``root_span``.

    Generic string-insertion primitive: pure slice-and-concatenate, no re-parse,
    no attribute semantics. The caller supplies the exact text to insert and where;
    this function only handles the position arithmetic.

    ``root_span`` is updated so its endpoints remain truthful after insertion:
    endpoints at or past ``offset`` move forward by ``len(text)``.

    ``segments[0]`` must be a ``str``. Mutates ``level`` in place and returns it
    for chaining.
    """
    root = level.segments[0]
    assert isinstance(root, str), (
        f"splice needs a str root segment, got {type(root).__name__}"
    )
    level.segments[0] = root[:offset] + text + root[offset:]
    start, end = level.root_span
    shift = len(text)
    level.root_span = (
        start + shift if offset <= start else start,
        end + shift if offset <= end else end,
    )
    return level


def serialize(level: RenderedLevel) -> str:
    """Join a segment tree back into one string, depth-first in order."""
    parts: list[str] = []
    for seg in level.segments:
        assert isinstance(seg, (str, RenderedLevel)), (
            f"serialize needs str or RenderedLevel segments, got {type(seg).__name__}"
        )
        parts.append(seg if isinstance(seg, str) else serialize(seg))
    return "".join(parts)
