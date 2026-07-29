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
    descriptor: (
        object  # ClassDescriptor once #246 lands; typed loosely to stay import-pure
    )


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
    """The one parse (ADR 0005), in its lossless form: markup in, same markup out.

    Every event handler appends the *raw source text* for that event to a flat
    ``segments`` list, so ``"".join(parser.segments)`` reproduces the input
    exactly — attribute quoting, attribute order, unknown and boolean attrs,
    odd casing and intentionally malformed HTML all survive untouched. There is
    no tag tree. Top-level PascalCase tags are cut out (#254, below), the first
    tag event's raw span is recorded as ``root_span`` (#255, below), a paired
    top-level tag's body is captured into ``ChildRef.inner`` on close (below),
    and every tag event that fires at nesting depth 0 is counted so
    ``enforce_single_root`` (#257, below) can reject zero- and multi-root
    markup without a second pass.

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

    A **self-closing** top-level component tag becomes
    ``ChildRef(tag, attrs, inner=None)`` at its exact position. A **paired**
    top-level tag (``<PJXButton>body</PJXButton>``) collapses on its close tag:
    ``handle_endtag`` joins every segment appended since the open tag into one
    raw ``inner`` string, drops that run from ``segments``, and appends a single
    ``ChildRef(tag, attrs, inner)``. Either way ``segments`` stays
    ``[str, ..., ChildRef, ..., str]`` in document order.

    Only the *outermost* open component tag is a cut point. A tag nested inside a
    still-open component tag is never cut and never re-scanned (ADR 0002, opaque
    children): its close tag pops its own ``_custom_stack`` entry but, with the
    stack still non-empty, collapses nothing, so it survives verbatim inside the
    ancestor's ``inner`` for a later level's parse to deal with.

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
    validation. Single-root validation lives in ``enforce_single_root``, which
    callers invoke explicitly after ``close()`` — parsing itself never raises, so
    an unclosed root tag at EOF is still exactly one root and stays valid.

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
        # — no root validation happens here; enforce_single_root() does that,
        # only when a caller asks for it.
        self.root_span: tuple[int, int] | None = None
        self._source = ""
        self._line_starts: list[int] = [0]
        # One entry per currently-open PascalCase tag: (original-cased name, index
        # of its open tag in `segments`, the attrs parsed off that open tag).
        # Entry [0] is the only *cut point*: when it closes, handle_endtag replaces
        # the whole run from its index onward with one ChildRef. Deeper entries
        # exist purely so the matching close tag pops the right level; nothing
        # nested is ever cut or collapsed.
        #
        # An entry is popped by handle_endtag the instant its close tag matches, so
        # it is not available by reading `_custom_stack` after `close()` returns —
        # only never-closed stragglers survive that long. The collapse therefore
        # happens inside handle_endtag, off the entry it just popped.
        self._custom_stack: list[tuple[str, int, dict[str, str]]] = []
        # Single-root enforcement (#257) bookkeeping, deliberately separate from
        # `_custom_stack`: that stack only tracks PascalCase nesting for cut-gating,
        # while root counting must see plain tags too. Nothing here ever raises
        # during the feed — `enforce_single_root()` is opt-in, called after close().
        # Names of the currently-open non-void elements, outermost first. A stack
        # rather than a counter so a stray `</span>` pops nothing and an ancestor's
        # close tag pops every level it swallows — consistent with handle_endtag's
        # existing no-op-on-mismatch rule.
        self._open_elements: list[str] = []
        self._top_level_count = 0
        self._extra_root_texts: list[str] = []

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

    def _count_root_candidate(self, raw: str) -> None:
        """Count a tag event that fired at nesting depth 0 as a root candidate.

        Mirrors v0.x's ``_RootScanner._record_top_level`` (pyjinhx/root_attrs.py),
        but rides this parser's existing single feed instead of a second pass
        (ADR 0005). The raw text of every root past the first is kept so the
        error can name the offending markup rather than only count it.
        """
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
        """Raise unless the parsed markup had exactly one top-level element.

        Opt-in on purpose: the feed itself never validates, so every round-trip
        and ``root_span`` test can parse malformed markup without a raise. Call
        this after ``close()`` when the single-root guarantee is actually needed
        (render.py wires it in under #247). Raises unconditionally — there is no
        fallback and nothing is swallowed (ADR 0002 consequences, invariant 3).
        """
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
            # The raw open tag is appended below and stays in `segments` until the
            # matching close tag collapses the run; `attrs` is kept here because
            # HTMLParser only offers it on this event.
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
        # HTMLParser lowercases `tag`, which would destroy `</DIV>` and, fatally,
        # `</PJXButton>`. Recover the source text instead.
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
                # The outermost component tag just closed: everything appended
                # since its open tag is its body. Join it back into one raw
                # string, drop the run, and leave a single ChildRef in its place.
                # The isinstance filter is a type-narrowing no-op — nothing
                # nested is ever cut, so these segments are all str.
                inner = "".join(
                    segment
                    for segment in self.segments[index + 1 :]
                    if isinstance(segment, str)
                )
                del self.segments[index:]
                self.segments.append(ChildRef(tag=open_name, attrs=attrs, inner=inner))
                return
        # Deliberate non-pop on a name mismatch: popping would silently reopen
        # cutting inside a still-unclosed component's span. Root counting handles
        # mismatches on its own stack (`_close_open_element`); this one is only
        # about cut-gating and stays deliberately forgiving.
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


def splice(level: RenderedLevel, offset: int, text: str) -> RenderedLevel:
    """Insert ``text`` into ``level.segments[0]`` at ``offset``, keeping the span true.

    The one generic string-insertion primitive of the segment model — pure
    slice-and-concatenate, no re-parse (ADR 0002, invariant 1) and no attribute
    semantics. Building the text to insert (quoting, ordering, which attrs even
    apply) is the caller's job; ``splice`` only knows a position and a string.
    That makes it deliberately dumber than v0.x's ``_override_tag``, which
    search-and-replaced per attribute name over a re-scanned tag.

    ``root_span`` is rewritten so it stays truthful after the insertion: an
    endpoint at or past ``offset`` moves forward by ``len(text)``, one before it
    does not. Callers stamp just inside the root tag's closing ``>`` — at
    ``root_span[1] - 1`` — so in practice ``start`` holds still and ``end`` grows,
    and a *second* splice reading the updated span lands just inside that same
    ``>`` again. That is the whole point: the stamp mechanism splices pass-through
    attrs at render time and fan-out splices ``hx-swap-oob`` at response time —
    same offset, same primitive, two moments (architecture-overview.md §4). Get
    this arithmetic wrong and the two silently corrupt each other's insertion
    point.

    ``segments[0]`` must be a ``str``. When a level's root is itself an unresolved
    custom tag, ``segments[0]`` is a ``ChildRef``, which no offset can slice; a
    level being stamped has already rendered its own root, so that combination is
    a structural-contract violation, not user error — hence a bare ``assert``.

    Nothing here validates ``offset`` against the tag structure or bounds it:
    ordinary Python slicing semantics apply, and knowing what a sane insertion
    point is belongs to the caller. Empty ``text`` is a legal no-op. Mutates
    ``level`` in place (the dataclasses are slotted but not frozen) and returns it
    so ``render.py`` can chain the stamp step.
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
    """Join a segment tree back into one string — depth-first, in order.

    The read-side counterpart to ``splice``: where ``splice`` writes into a
    single segment, this walks the whole tree once and produces the output.
    It is *the* join — called once, at the top of the outermost render, so each
    output character is produced exactly once (architecture-overview.md §3/§5).
    Levels do not join themselves as they finish; joining early would mean a
    parent holds its child as text, and every enclosing level would then copy
    that text again on its way up.

    A nested ``RenderedLevel`` recurses rather than being flattened or re-read:
    a child is opaque by construction (ADR 0002, invariant 2), so its segments
    are its own business and only its serialized text enters the parent's output
    stream. Nothing here parses, scans or rewrites the text it passes through
    (invariant 1) — ``str`` segments go out verbatim, byte for byte as the single
    parse cut them.

    ``root_span`` is not read, and neither are ``ChildRef.attrs`` or ``inner``.
    A live ``ChildRef`` reaching this function means L1 tag expansion never
    turned that hole into a rendered child, which is a structural-contract
    violation in the caller rather than user error — hence a bare ``assert``,
    same posture as ``splice``'s ``str``-root check. Empty ``segments`` is a
    legal no-op and serializes to ``""``.
    """
    parts: list[str] = []
    for seg in level.segments:
        assert isinstance(seg, (str, RenderedLevel)), (
            f"serialize needs str or RenderedLevel segments, got {type(seg).__name__}"
        )
        parts.append(seg if isinstance(seg, str) else serialize(seg))
    return "".join(parts)
