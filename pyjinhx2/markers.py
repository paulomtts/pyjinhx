"""Opaque markers for render context."""

from __future__ import annotations

import re
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyjinhx2.component import BaseComponent


class SlotProps:
    """Read-only view over a slotted child's own validated field values.

    ADR 0003's single sanctioned escape hatch. Attribute and key access are
    the whole surface: a MappingProxyType would also hand back __str__,
    __len__ and iteration, reopening exactly the stringification hole the
    opaque node exists to close. Unknown names fail as ordinary lookups, so
    a typo in `{{ field.props.x }}` reads as a typo and not as an opacity
    violation.
    """

    __slots__ = ("_node", "_values")

    def __init__(self, values: dict[str, object], node: ComponentNode) -> None:
        object.__setattr__(self, "_values", values)
        object.__setattr__(self, "_node", node)

    def __getattr__(self, name: str) -> object:
        values: dict[str, object] = object.__getattribute__(self, "_values")
        if name not in values:
            raise AttributeError(name)
        return values[name]

    def __getitem__(self, key: str) -> object:
        # Guards against Python's legacy iteration protocol, which probes
        # __getitem__ with integer indices when no __iter__ is defined;
        # rejecting non-str keys keeps `list(props)` a TypeError, not a
        # KeyError that leaks internal dict iteration as a side door.
        if not isinstance(key, str):
            raise TypeError(f"slot props keys must be str, got {type(key).__name__}")
        values: dict[str, object] = object.__getattribute__(self, "_values")
        return values[key]

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("slot props are read-only")

    def __str__(self) -> str:
        node: ComponentNode = object.__getattribute__(self, "_node")
        raise node._opaque_error(".props")

    def __repr__(self) -> str:
        node: ComponentNode = object.__getattribute__(self, "_node")
        return f"SlotProps({type(node.component).__name__})"


class ComponentNode:
    """Opaque marker wrapping a component-valued Slot field.

    Not a string, so Jinja filters routed through a dunder (e.g. |length) fail
    fast. Filters that stringify first (|upper, |trim, |striptags) fall
    through to __str__ instead - a documented gap, see ADR 0003 / #368 PR
    notes. Holds enough info for L1 to skip it during child expansion, and
    enough about the component that declared the slot to name it in an error.

    ``owner_name``/``owner_template``/``field_name`` default to placeholders
    so call sites that only care about the wrapped component (e.g. token-table
    plumbing tests) don't need to supply owner identity they don't have.

    NOTE for reviewers: several pre-existing bare ``ComponentNode(x)`` call
    sites (tests/pyjinhx2/test_slot_type_v2.py, tests/pyjinhx2/
    test_render_context.py) rely on these placeholder defaults rather than
    being updated to pass real owner identity. Those tests only assert
    ``pytest.raises(TypeError)`` / opacity behavior, not error-message
    content, so the placeholders don't currently weaken any assertion - but
    if a future test starts asserting on ``_opaque_error`` message text, it
    will see ``"<unknown>"`` instead of a real component/template name unless
    those call sites are updated too.
    """

    __slots__ = ("component", "field_name", "owner_name", "owner_template")

    # Defining __eq__ blanks __hash__; restore object identity hashing so the
    # node stays usable as a dict key even though comparisons are forbidden.
    __hash__ = object.__hash__

    def __init__(
        self,
        component: BaseComponent,
        owner_name: str = "<unknown>",
        owner_template: Path | None = None,
        field_name: str = "<unknown>",
    ) -> None:
        self.component = component
        self.owner_name = owner_name
        self.owner_template = owner_template
        self.field_name = field_name

    def __bool__(self) -> bool:
        # Stated explicitly so `{% if slot %}` can never fall through to
        # __len__ (which must keep raising) or to a stringification that
        # would force the child's render (ADR 0003).
        return True

    def __repr__(self) -> str:
        return f"ComponentNode({self.component!r})"

    @property
    def props(self) -> SlotProps:
        """The wrapped child's validated field values, read-only.

        Built on each access from the child's current field values; reading
        them never touches the child's rendered output, so `{{ field.props.x }}`
        cannot force a render the way stringifying the node would.
        """
        return SlotProps(self.component.pjx_props(), self)

    def _opaque_error(self, operation: str) -> TypeError:
        """The error for any operation ADR 0003 forbids on a component slot.

        One builder for every forbidden dunder so the wording cannot drift
        between them; each caller supplies only the literal syntax the author
        wrote, so the message reads back what was attempted.
        """
        template = (
            self.owner_template if self.owner_template is not None else "<unresolved>"
        )
        field = self.field_name
        return TypeError(
            f"{self.owner_name} (template: {template}): slot '{field}' holds a "
            f"rendered component, so `{operation}` is not supported on it. "
            f"Component slots are opaque outside `{{% if %}}` and `{{{{ }}}}`: "
            f"use `{{% if {field} %}}` to test for presence, or "
            f"`{{{{ {field} }}}}` to render it directly. String filters, "
            f"slicing, membership tests, and comparisons are not available on "
            f"component slots."
        )

    def __len__(self) -> int:
        raise self._opaque_error("|length")

    def __getitem__(self, key: object) -> object:
        if isinstance(key, slice):
            start = "" if key.start is None else key.start
            stop = "" if key.stop is None else key.stop
            written = f"[{start}:{stop}]"
        else:
            written = f"[{key!r}]" if isinstance(key, str) else f"[{key}]"
        raise self._opaque_error(written)

    def __contains__(self, item: object) -> bool:
        raise self._opaque_error("in")

    def __iter__(self) -> Iterator[object]:
        raise self._opaque_error("for")

    def __eq__(self, other: object) -> bool:
        raise self._opaque_error("==")

    def __ne__(self, other: object) -> bool:
        raise self._opaque_error("!=")

    def __lt__(self, other: object) -> bool:
        raise self._opaque_error("<")

    def __le__(self, other: object) -> bool:
        raise self._opaque_error("<=")

    def __gt__(self, other: object) -> bool:
        raise self._opaque_error(">")

    def __ge__(self, other: object) -> bool:
        raise self._opaque_error(">=")


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
