"""Segment model: the types every other v2 module trusts (ADR 0002).

Import-pure — stdlib only. Nothing in pyjinhx2 may be imported here.
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
    close, or None for a self-closing tag; it is filled by the paired-tag capture
    pass (#256), not by anything here.
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
    descriptor: (
        object  # ClassDescriptor once #246 lands; typed loosely to stay import-pure
    )


RE_PASCAL_CASE_TAG_NAME = re.compile(r"^[A-Z](?=[A-Za-z0-9]*[a-z])[A-Za-z0-9]*$")
RE_TAG_OPENER = re.compile(r"<\s*([A-Za-z][A-Za-z0-9]*)")
RE_RAW_END_TAG = re.compile(r"</[^>]*>")
RE_RAW_END_TAG_NAME = re.compile(r"</\s*([A-Za-z][A-Za-z0-9]*)")
RE_RAW_COMMENT = re.compile(r"<!--.*?-->|<!\[.*?\]\]?>", re.DOTALL)


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
    """The one parse (ADR 0005), in its lossless form: markup in, same markup out.

    Every event handler appends the *raw source text* for that event to a flat
    ``segments`` list, so ``"".join(parser.segments)`` reproduces the input
    exactly — attribute quoting, attribute order, unknown and boolean attrs,
    odd casing and intentionally malformed HTML all survive untouched. There is
    no tag tree. Top-level PascalCase tags are cut out (#254, below) and the
    first tag event's raw span is recorded as ``root_span`` (#255, below);
    capturing paired-tag ``inner`` (#256) and enforcing a single root (#257)
    still layer onto this harness later.

    ``root_span`` (#255) is the ``(start, end)`` offset of the very first tag
    event into the *original source string*, not an index into ``segments``.
    ``_record_root_span`` fires from both ``handle_starttag`` and
    ``handle_startendtag`` before any cutting happens, and is a no-op after the
    first call, so the outermost tag always wins even when a top-level custom
    tag wraps other tags (``test_root_span_records_the_outer_tag_not_a_nested_one``).
    ``end`` lands exactly one character past that tag's closing ``>`` — for a
    plain tag (``<div class="card">``) and for a top-level self-closing or
    paired custom tag alike (``<PJXButton label="Go">``) — enough for #258's
    attribute splice to slice and re-stitch at those offsets without a
    re-parse.

    Despite the ``RenderedLevel`` docstring's shorthand ("the offset of the
    root tag inside ``segments[0]``"), ``root_span`` is never an offset *into*
    ``segments[0]`` — it is an offset into the raw source text, recorded before
    ``segments[0]`` even exists in the self-closing top-level case. When the
    root is itself a cut custom tag, ``segments[0]`` is a ``ChildRef`` object,
    not a string, so it cannot be sliced by any offset at all; ``root_span``
    must always be read against the original markup passed to the parser,
    never against ``segments[0]`` directly.

    Cutting (#254) covers **self-closing** top-level component tags only: they
    become ``ChildRef(tag, attrs, inner=None)`` at their exact position, so
    ``segments`` is ``[str, ..., ChildRef, ..., str]`` in document order. A
    *paired* top-level tag (``<PJXButton>body</PJXButton>``) is deliberately left
    as raw passthrough — open tag, body and close tag remain separate strings.
    Collapsing that run into one ``ChildRef`` with ``inner`` populated is #256's
    job, and emitting a ``ChildRef(inner=None)`` here would falsely claim the tag
    has no body. What #254 leaves behind for #256 is ``_custom_stack``: the index
    of each open tag in ``segments``, enough to replace the run in place later.
    That index is only available while the tag is still open — ``handle_endtag``
    pops (and discards) an entry the instant its close tag matches, so #256 must
    read the top of the stack *before* the pop, from inside its own
    ``handle_endtag`` handling, not by inspecting ``_custom_stack`` after
    ``close()`` returns (by then only never-closed stragglers remain there).

    A tag nested inside a still-open component tag is never cut and never
    re-scanned (ADR 0002, opaque children): it stays raw inside the ancestor's
    span, for #256 to capture wholesale.

    Deliberate deviation from v0.x's ``pyjinhx/tags.py`` ``Parser``: ``handle_data``
    does **not** re-escape with ``markupsafe.escape``. That dependency is
    unavailable here (this module is import-pure, stdlib only) and unnecessary —
    v2 parses markup Jinja already rendered with autoescape on, not a decode /
    re-encode boundary, so escaping would double-encode. For the same reason
    ``<script>``/``<style>`` bodies need no special case: ``HTMLParser`` already
    delivers CDATA content undecoded, and passthrough never touches it.

    Also unlike v0.x, ``close()`` is not overridden and never raises on unclosed
    tags: a non-empty ``_custom_stack`` at EOF is fine here, and a mismatched
    close tag is passed through without popping. The stack is bookkeeping, not
    validation — enforcement is #257's.

    Known limitation: markup truncated mid-construct at EOF (``"<div"``,
    ``"<!-- unclosed"``) does not round-trip — ``HTMLParser`` drops or completes
    the fragment on ``close()``. Jinja never emits such output, and the
    exhaustive round-trip and adversarial suites are #260/#261.
    """

    def __init__(self) -> None:
        # convert_charrefs would decode `&amp;` into `&` inside handle_data,
        # silently unescaping markup Jinja escaped on purpose. Keep refs intact
        # and reconstruct them below.
        super().__init__(convert_charrefs=False)
        self.segments: list[str | ChildRef] = []
        # The (start, end) absolute offsets of the first tag event's raw opening-tag
        # text; None until that event fires. See the class docstring. Recording only
        # — no root validation happens here (#257 owns that).
        self.root_span: tuple[int, int] | None = None
        self._source = ""
        self._line_starts: list[int] = [0]
        # One entry per currently-open PascalCase tag: (original-cased name, index
        # of its open tag in `segments`). Entry [0] is the only *cut point* — the
        # top-level span #256 will replace in place. Deeper entries exist purely so
        # the matching close tag pops the right level; nothing nested is ever cut.
        #
        # NB for #256: an entry is popped (discarded) by handle_endtag the instant
        # its close tag matches, so it is NOT available by reading `_custom_stack`
        # after `close()` returns — only never-closed stragglers survive that long.
        # The collapse must happen inside handle_endtag itself, using the top-of-
        # stack entry *before* it is popped.
        self._custom_stack: list[tuple[str, int]] = []

    def feed(self, data: str) -> None:
        """Parse ``data``. One feed per parser instance — the source is recorded
        whole so handlers can recover raw text ``HTMLParser`` does not hand back."""
        self._source = data
        self._line_starts = [0] + [i + 1 for i, char in enumerate(data) if char == "\n"]
        super().feed(data)

    def _raw_at(self, pattern: "re.Pattern[str]") -> "str | None":
        """The source text matching ``pattern`` at the current event's offset.

        ``getpos()`` is line/column, so the line-start index converts it back to
        an absolute offset into ``_source``.
        """
        line, column = self.getpos()
        match = pattern.match(self._source, self._line_starts[line - 1] + column)
        return match.group(0) if match else None

    def _record_root_span(self, raw: str) -> None:
        """Record the first tag event's raw text span; a no-op after that.

        Same ``getpos()`` → ``_line_starts`` conversion as ``_raw_at``. ``raw`` is
        whatever ``get_starttag_text()`` returned, so ``end`` lands just past the
        tag's closing ``>`` — the offsets #258's splice stamps attributes at.
        """
        if self.root_span is not None:
            return
        line, column = self.getpos()
        start = self._line_starts[line - 1] + column
        self.root_span = (start, start + len(raw))

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        raw = self.get_starttag_text() or f"<{tag}>"
        self._record_root_span(raw)
        name = self._custom_tag_name(raw)
        if name is not None:
            self._custom_stack.append((name, len(self.segments)))
        # Paired tags stay raw passthrough here — see the class docstring.
        self.segments.append(raw)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        raw = self.get_starttag_text() or f"<{tag}/>"
        self._record_root_span(raw)
        name = self._custom_tag_name(raw)
        if name is not None and not self._custom_stack:
            self.segments.append(
                ChildRef(tag=name, attrs=_attrs_to_dict(attrs), inner=None)
            )
            return
        self.segments.append(raw)

    def handle_endtag(self, tag: str) -> None:
        # HTMLParser lowercases `tag`, which would destroy `</DIV>` and, fatally
        # for #254, `</PJXButton>`. Recover the source text instead.
        raw = self._raw_at(RE_RAW_END_TAG) or f"</{tag}>"
        name = self._custom_tag_name(raw)
        if (
            name is not None
            and self._custom_stack
            and self._custom_stack[-1][0] == name
        ):
            self._custom_stack.pop()
        # Deliberate non-pop on a name mismatch: enforcement is #257's, and
        # popping on mismatch would silently reopen cutting inside a still-
        # unclosed component's span.
        self.segments.append(raw)

    def _custom_tag_name(self, raw: str) -> "str | None":
        """The original-cased tag name in ``raw`` if it names a custom component.

        ``HTMLParser`` lowercases the ``tag`` argument it passes to the handlers,
        which would make ``PJXButton`` unmatchable, so PascalCase detection always
        goes through the source text. ``RE_TAG_OPENER`` matches an open tag
        (``<PJXIcon ...``) and deliberately does not match a close tag, which is
        why ``RE_RAW_END_TAG_NAME`` handles ``</PJXIcon>``.
        """
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
