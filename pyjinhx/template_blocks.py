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

# Jinja's own comment rule: a comment runs from ``{#`` to the first ``#}``.
_COMMENT_RE = re.compile(r"\{#(.*?)#\}", re.DOTALL)


class Block(NamedTuple):
    """One inline block: its body and the 1-based line its ``{#`` opens on."""

    body: str
    line: int


def find_block(source: str, keyword: str, filename: str) -> Block | None:
    """The ``{#<keyword> ... #}`` block in ``source``, or None.

    The keyword must touch ``{#`` and be followed by whitespace, so a prose
    comment such as ``{# css tweaks #}`` is never mistaken for a block. An
    empty block counts as no block. Raises ``TemplateSyntaxError`` pointing at
    the second block when ``source`` holds two of the same keyword.
    """
    found: Block | None = None
    for match in _COMMENT_RE.finditer(source):
        text = match.group(1)
        rest = text.removeprefix(keyword)
        if rest == text or (rest and not rest[0].isspace()):
            continue
        line = source.count("\n", 0, match.start()) + 1
        if found is not None:
            raise TemplateSyntaxError(
                f"a second {{#{keyword}#}} block; the first one is on line "
                f"{found.line}, and a template holds at most one of each kind",
                line,
                filename=filename,
            )
        found = Block(rest.strip(), line)
    if found is None or not found.body:
        return None
    return found


class InlineAsset(Path):
    """The ``{#css#}`` or ``{#js#}`` block of one template, addressed as a path.

    Named ``<template>#<kind>`` (``card.pjx#css``), so the asset pipeline's
    path-keyed dedupe, sort order and ``data-pjx-asset`` token work on it
    unchanged; only reading it differs. The template is re-read on every read,
    the way a sibling ``.css`` file is, so an edit shows up without a restart.
    """

    def __init__(self, template: Path, kind: str) -> None:
        super().__init__(f"{template}#{kind}")
        self.template = Path(template)
        self.kind = kind

    def with_segments(self, *pathsegments: str | os.PathLike[str]) -> Path:
        # Derived paths (parent, resolve(), ...) name real filesystem
        # locations, not a block, so they come back as plain paths.
        return Path(*pathsegments)

    def __reduce__(self):
        return InlineAsset, (self.template, self.kind)

    def read_text(
        self,
        encoding: str | None = None,
        errors: str | None = None,
        newline: str | None = None,
    ) -> str:
        """The block body, or "" when the template no longer has the block."""
        source = self.template.read_text(encoding="utf-8")
        block = find_block(source, self.kind, str(self.template))
        return "" if block is None else block.body

    def read_bytes(self) -> bytes:
        """The block body as UTF-8 bytes."""
        return self.read_text().encode("utf-8")


def inline_assets(template_path: Path) -> tuple[InlineAsset | None, InlineAsset | None]:
    """The ``(css, js)`` inline assets the template at ``template_path`` carries.

    A missing or unreadable template carries none: the template probe may hand
    over a path nobody has proven exists, and the render reports that itself.
    """
    try:
        source = template_path.read_text(encoding="utf-8")
    except OSError:
        return None, None
    filename = str(template_path)
    css = find_block(source, "css", filename)
    js = find_block(source, "js", filename)
    if css is not None or js is not None:
        _reject_stray_comment_close(source, filename)
    return (
        None if css is None else InlineAsset(template_path, "css"),
        None if js is None else InlineAsset(template_path, "js"),
    )


def _reject_stray_comment_close(source: str, filename: str) -> None:
    """Raise when a ``#}`` is left over once every comment is removed.

    Jinja ends a comment at the first ``#}``, so a body that contains the pair
    is cut short and its tail is rendered into the page as text.
    """
    # Keep each comment's newlines so the leftover reports its real line.
    rest = _COMMENT_RE.sub(lambda m: "\n" * m.group().count("\n"), source)
    index = rest.find("#}")
    if index == -1:
        return
    raise TemplateSyntaxError(
        "a stray '#}' ends an inline block early and the rest of it would be "
        "rendered as page text; split the pair (for example "
        '"#" + "}") or move the asset to a sibling file',
        rest.count("\n", 0, index) + 1,
        filename=filename,
    )
