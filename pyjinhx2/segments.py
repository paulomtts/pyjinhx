"""Segment model: the types every other v2 module trusts (ADR 0002).

Import-pure — stdlib only. Nothing in pyjinhx2 may be imported here.
"""

import re
from dataclasses import dataclass


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
