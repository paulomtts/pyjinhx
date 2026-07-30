"""Opaque markers for render context."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyjinhx2.component import BaseComponent


class ComponentNode:
    """Opaque marker wrapping a component-valued Slot field.

    Not a string, so Jinja's string filters (|length, |upper, etc.) fail fast.
    Holds enough info for L1 to skip it during child expansion.
    """

    __slots__ = ("component",)

    def __init__(self, component: BaseComponent) -> None:
        self.component = component

    def __bool__(self) -> bool:
        # Stated explicitly so `{% if slot %}` can never fall through to
        # __len__ (which must keep raising) or to a stringification that
        # would force the child's render (ADR 0003).
        return True

    def __repr__(self) -> str:
        return f"ComponentNode({self.component!r})"
