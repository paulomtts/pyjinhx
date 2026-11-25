"""Inline blocks carried inside a ``.pjx`` template as Jinja comments.

A template can hold its own stylesheet and script::

    {#def title: str #}
    <div class="card">{{ title }}</div>
    {#css
    .card { padding: 1rem; }
    #}
    {#js
    console.log("card");
    #}

Each block is one ordinary Jinja comment, so plain Jinja renders the template
unchanged and drops the block from the output. pyjinhx reads the bodies
out-of-band and hands them to the asset pipeline as ``InlineAsset`` paths.
"""

import os
import re
from pathlib import Path
from typing import NamedTuple

from jinja2 import TemplateSyntaxError

from pyjinhx.sfc import (
    BLOCK_KEYWORDS,
    LEGACY_HEADER_RE,
    SECOND_BLOCK,
    STRAY_COMMENT_CLOSE,
    BlockSyntaxError,
    comments,
    python_block,
    read_document,
    strip_to_text,
)


class BlockTemplateSyntaxError(TemplateSyntaxError):
    """A malformed css, js or def block, with the stable ``code`` naming how
    and the 1-based ``offset`` of the column it starts at."""

    def __init__(
        self, code: str, message: str, lineno: int, filename: str, offset: int
    ) -> None:
        super().__init__(message, lineno, filename=filename)
        self.code = code
        self.offset = offset


class Block(NamedTuple):
    """One inline block: its body, the 1-based line its ``{#`` opens on and the
    line its ``#}`` closes on."""

    body: str
    line: int
    close_line: int


def _is_block(comment: str, keyword: str) -> bool:
    """Whether a comment's text opens a ``keyword`` block.

    ``def`` takes whitespace or nothing after it. ``css`` and ``js`` must end
    their line, so a one-line prose comment such as ``{#js hack #}``, common
    in templates written before blocks existed, stays a comment.
    """
    rest = comment.removeprefix(keyword)
    if rest == comment:
        return False
    if keyword == "def":
        return not rest or rest[0].isspace()
    return rest.lstrip(" \t\r").startswith("\n")


def find_block(source: str, keyword: str, filename: str) -> Block | None:
    """The ``{#<keyword> ... #}`` block in ``source``, or None.

    The keyword must touch ``{#``, so a prose comment such as
    ``{# css tweaks #}`` is never mistaken for a block, and ``css``/``js``
    must end their line (see `_is_block`). An
    empty block counts as no block. Raises ``TemplateSyntaxError`` pointing at
    the second block when ``source`` holds two of the same keyword.
    """
    found: Block | None = None
    for match in comments(source):
        text = match.group(1)
        if not _is_block(text, keyword):
            continue
        rest = text.removeprefix(keyword)
        line = source.count("\n", 0, match.start()) + 1
        if found is not None:
            raise BlockTemplateSyntaxError(
                SECOND_BLOCK,
                f"a second {{#{keyword}#}} block; the first one is on line "
                f"{found.line}, and a template holds at most one of each kind",
                line,
                filename,
                match.start() - (source.rfind("\n", 0, match.start()) + 1) + 1,
            )
        found = Block(rest.strip(), line, line + text.count("\n"))
    if found is None or not found.body:
        return None
    return found


class Header(NamedTuple):
    """A ``{#def#}`` header: its signature text, where that text starts in the
    document, and the 1-based line its ``{#`` opens on."""

    signature: str
    offset: int
    line: int


def find_header(source: str, filename: str) -> Header | None:
    """The ``{#def#}`` header of ``source``, in either spelling, or None.

    Raises ``TemplateSyntaxError`` when ``source`` holds two headers.
    """
    block = find_block(source, "def", filename)
    if block is not None:
        line_start = len(source) - len(source.split("\n", block.line - 1)[-1])
        return Header(block.body, source.index(block.body, line_start), block.line)
    legacy = LEGACY_HEADER_RE.match(source)
    if legacy is None:
        return None
    offset = legacy.start("sig")
    return Header(legacy.group("sig"), offset, source.count("\n", 0, offset) + 1)


# The empty comment an inline template opens with to pad its line numbers
# (see sfc); a block right after it is still the first thing in the document.
_LINE_PADDING_RE = re.compile(r"\{#\s*#\}")


def hide_block_lines(source: str) -> str:
    """``source`` as Jinja should compile it: a block alone on its line takes
    that line's break with it, so it renders as nothing rather than as a blank
    line.

    A header, or an asset folded in from a sibling file, then leaves the
    rendered markup exactly as it was. The break moves inside the comment
    rather than being deleted, so every line keeps its number. A block that
    shares its line with anything else, and every prose comment, is left as
    written.
    """
    parts: list[str] = []
    position = 0
    for match in comments(source):
        if not any(_is_block(match.group(1), k) for k in BLOCK_KEYWORDS):
            continue
        start, end = match.span()
        line_start = source.rfind("\n", 0, start) + 1
        line_end = source.find("\n", end)
        if line_end == -1:
            line_end = len(source)
        if source[end:line_end].strip(" \t\r"):
            continue
        alone = not source[line_start:start].strip(" \t\r")
        if alone and line_start > position:
            # The break that ends the previous line goes; this line's stays
            # to end that one instead.
            cut = (line_start - 1, line_end)
        elif (alone and line_start == position) or (
            position == 0 and _LINE_PADDING_RE.fullmatch(source, 0, start)
        ):
            # First in the document, or right after a block that already took
            # the break before this line: this line's own break goes.
            cut = (line_start if alone else start, min(line_end + 1, len(source)))
        else:
            continue
        parts.append(source[position : cut[0]])
        parts.append(
            "{#" + source[cut[0] : start] + match.group(1) + source[end : cut[1]] + "#}"
        )
        position = cut[1]
    parts.append(source[position:])
    return "".join(parts)


class InlineAsset(Path):
    """The ``{#css#}`` or ``{#js#}`` block of one template, addressed as a path.

    Named ``<template>#<kind>`` (``card.pjx#css``), or
    ``<module>::<Class>#<kind>`` for a class's inline template, so the asset
    pipeline's path-keyed dedupe, sort order and ``data-pjx-asset`` token work
    on it unchanged and two classes in one module stay two assets; only
    reading it differs. The template is re-read on every read, the way a
    sibling ``.css`` file is, so an edit shows up without a restart.

    Only ``read_text()`` and ``read_bytes()`` work. No file has this path, so
    ``open()``, ``stat()``, ``exists()`` and file copies fail or answer False.

    ``str()`` keeps the ``#<kind>`` form, but ``suffix``, ``stem`` and ``name``
    answer as the sibling file would (``.css``, ``card``, ``card.css``), so
    code that classifies assets by extension keeps working. Wrapping one in
    ``Path(asset)`` goes through ``str()`` and loses the inline reading.
    """

    def __init__(
        self, template: Path, kind: str, inline_class: str | None = None
    ) -> None:
        document = (
            f"{template}" if inline_class is None else f"{template}::{inline_class}"
        )
        super().__init__(f"{document}#{kind}")
        self.template = Path(template)
        self.kind = kind
        self.inline_class = inline_class

    def with_segments(self, *pathsegments: str | os.PathLike[str]) -> Path:
        # Derived paths (parent, resolve(), ...) name real filesystem
        # locations, not a block, so they come back as plain paths.
        return Path(*pathsegments)

    @property
    def suffix(self) -> str:
        return f".{self.kind}"

    @property
    def suffixes(self) -> list[str]:
        return [self.suffix]

    @property
    def stem(self) -> str:
        return self.template.stem

    @property
    def name(self) -> str:
        return self.stem + self.suffix

    def __reduce__(self):
        return InlineAsset, (self.template, self.kind, self.inline_class)

    def read_text(
        self,
        encoding: str | None = None,
        errors: str | None = None,
        newline: str | None = None,
    ) -> str:
        """The block body, or "" when the template no longer has the block."""
        source = read_document(self.template, self.inline_class)
        block = find_block(source, self.kind, str(self.template))
        return "" if block is None else block.body

    def read_bytes(self) -> bytes:
        """The block body as UTF-8 bytes."""
        return self.read_text().encode("utf-8")


def inline_assets(
    template_path: Path, source: str, inline_class: str | None = None
) -> tuple[InlineAsset | None, InlineAsset | None]:
    """The ``(css, js)`` inline assets in ``source``, the template document at
    ``template_path``.

    ``inline_class`` names the class whose inline template that ``.py`` file
    holds, as on the class's descriptor.
    """
    filename = str(template_path)
    errors: list[BlockTemplateSyntaxError | BlockSyntaxError] = []
    blocks: dict[str, Block | None] = {}
    for kind in ("css", "js"):
        try:
            blocks[kind] = find_block(source, kind, filename)
        except BlockTemplateSyntaxError as error:
            errors.append(error)
    python = None
    try:
        python = python_block(source, filename)
    except BlockSyntaxError as error:
        errors.append(error)
    if python is not None or any(blocks.values()):
        try:
            _reject_stray_comment_close(source, filename)
        except BlockTemplateSyntaxError as error:
            errors.append(error)
    if errors:
        # Report what a reader meets first, whichever scanner found it.
        raise min(errors, key=lambda error: error.lineno or 0)
    css, js = blocks["css"], blocks["js"]
    return (
        None
        if css is None
        else InlineAsset(template_path, "css", inline_class=inline_class),
        None
        if js is None
        else InlineAsset(template_path, "js", inline_class=inline_class),
    )


def _reject_stray_comment_close(source: str, filename: str) -> None:
    """Raise when a ``#}`` is left over once every comment, tag and raw region
    is removed.

    Jinja ends a comment at the first ``#}``, so a body that contains the pair
    is cut short and its tail is rendered into the page as text.
    """
    rest = strip_to_text(source)
    index = rest.find("#}")
    if index == -1:
        return
    raise BlockTemplateSyntaxError(
        STRAY_COMMENT_CLOSE,
        "a stray '#}' ends an inline block early and the rest of it would be "
        "rendered as page text; split the pair (for example "
        '"#" + "}") or move the asset to a sibling file',
        rest.count("\n", 0, index) + 1,
        filename,
        index - (rest.rfind("\n", 0, index) + 1) + 1,
    )
