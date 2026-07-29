"""Segment model: the types every other v2 module trusts (ADR 0002).

Import-pure — stdlib only. Nothing in pyjinhx2 may be imported here.
"""

from dataclasses import dataclass


@dataclass(slots=True)
class RenderedLevel:
    """One component's rendered output: its own markup cut into ordered segments.

    Children enter ``segments`` as whole RenderedLevel objects, never as text.
    ``root_span`` is the (start, end) offset of the root tag inside ``segments[0]``,
    recorded by the parse that produced the cut — later attr stamping is a splice
    at that offset, never a re-parse.
    """

    segments: list["str | RenderedLevel"]
    root_span: tuple[int, int]
    descriptor: object  # ClassDescriptor once #246 lands; typed loosely to stay import-pure
