"""Opaque markers for render context."""

from __future__ import annotations

import re
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
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


SLOT_TOKEN_RE = re.compile(r"pjx-slot-[0-9a-f]{32}")

# Interpolating a ComponentNode must not stringify it, so the finalize hook
# hands Jinja a placeholder instead and remembers what it stood for. The table
# is per-render and lives in a ContextVar so nested render_level calls (and
# other threads) never see each other's tokens.
_slot_tokens: ContextVar[dict[str, BaseComponent] | None] = ContextVar(
    "pjx_slot_tokens", default=None
)


def slot_token_table() -> dict[str, BaseComponent]:
    """The token table for the render currently in progress.

    Raises:
        RuntimeError: If called outside a ``collect_slot_tokens()`` scope.
    """
    table = _slot_tokens.get()
    if table is None:
        raise RuntimeError(
            "slot token table requested outside a collect_slot_tokens() scope"
        )
    return table


@contextmanager
def collect_slot_tokens() -> Iterator[dict[str, BaseComponent]]:
    """Open a fresh token table for one template render, restoring the previous one."""
    table: dict[str, BaseComponent] = {}
    reset = _slot_tokens.set(table)
    try:
        yield table
    finally:
        _slot_tokens.reset(reset)


def finalize_slot_node(value: object) -> object:
    """Jinja ``finalize`` hook: swap a ComponentNode for a placeholder token.

    Every other value is returned untouched, so ordinary interpolation — plain
    strings, numbers, None — behaves exactly as an un-hooked environment does.
    The token uses only hyphen and hex characters, so autoescape leaves it
    byte-identical and the surrounding parse sees it as ordinary text.
    """
    if not isinstance(value, ComponentNode):
        return value
    token = f"pjx-slot-{uuid.uuid4().hex}"
    slot_token_table()[token] = value.component
    return token
