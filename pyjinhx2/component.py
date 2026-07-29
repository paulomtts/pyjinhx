"""The component base class: a strict Pydantic model, and nothing more (ADR 0006).

v0.x's BaseComponent was ``extra="allow"``, so every render had to walk the
undeclared keys of every instance — the walk that caused the #240 crash. Here the
core is closed: an undeclared kwarg is a ValidationError at construction, and the
renderer never has to look. Extra-field ergonomics belong on a separate open
opt-in subclass (L1), not on this class.

Imports pydantic and nothing else. component.py sits below descriptor.py and
render.py in the import graph and must never reach up into them, nor into
session.py or reactive/.
"""

import itertools
from typing import Annotated, ClassVar

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# Process-wide, never per-class: ids must be unique across every subclass, since
# they end up as HTML ids on the same page. ``count.__next__`` is atomic under
# the GIL, so concurrent construction needs no extra locking.
_auto_id_counter = itertools.count(1)


def _auto_id() -> str:
    """Generate a process-unique component id (``pjx-<n>``)."""
    return f"pjx-{next(_auto_id_counter)}"


class PjxSlot:
    """Marker (in a field's ``Annotated`` metadata) for a raw-HTML slot field —
    its string value is emitted unescaped (invariant 6, the autoescape exemption).
    Use via the ``Slot`` alias.

    ``children=True`` additionally flags the field as the target for a
    PascalCase tag's nested children (use via the ``Children`` alias).

    Purely descriptive at this layer: nothing here escapes, wraps or renders.
    The render-time half (Markup-wrapping strings, opaque component nodes) is
    L1 work and lives above component.py in the import graph.
    """

    def __init__(self, children: bool = False) -> None:
        self.children = children


def _is_slot_field(cls: type, field_name: str) -> bool:
    """True when ``field_name`` is a raw-HTML slot on ``cls``.

    A field qualifies either by being the model's designated children field, or
    by carrying a :class:`PjxSlot` marker in its ``Annotated`` metadata. Unknown
    field names are not slots.
    """
    if field_name == getattr(cls, "_pjx_children_field", None):
        return True
    fields = getattr(cls, "model_fields", {})
    field = fields.get(field_name)
    return field is not None and any(isinstance(m, PjxSlot) for m in field.metadata)


class BaseComponent(BaseModel):
    """Base for all components: declared fields only, undeclared kwargs rejected.

    Deliberately minimal otherwise. Slot, attribute coercion and quote-safety are
    separate concerns and land as their own changes. The auto-id counter is the
    single chartered construction-time side effect (ADR 0004/0009); nothing else
    here runs one.
    """

    model_config = ConfigDict(extra="forbid")

    # Construction-time control, not model data: a ClassVar is invisible to
    # model_fields, so it never collides with extra="forbid" or serialization.
    # Opt out per component class with ``class Foo(BaseComponent): auto_id = False``.
    auto_id: ClassVar[bool] = True

    id: str = Field(
        default_factory=_auto_id,
        description="The unique ID for this component. Auto-generated when omitted.",
    )

    @model_validator(mode="before")
    @classmethod
    def _require_explicit_id(cls, data: object) -> object:
        """Runs before field defaults, so it is the only hook that can see an
        omitted ``id`` and stop ``default_factory`` from silently filling it."""
        if cls.auto_id:
            return data
        if isinstance(data, dict) and data.get("id"):
            return data
        raise ValueError(f"{cls.__name__} sets auto_id = False, so id is required")

    @field_validator("id", mode="before")
    @classmethod
    def _validate_id(cls, value: object) -> str:
        if not value:
            return _auto_id()
        return str(value)


# Defined after BaseComponent so the union member resolves at definition time.
# The full ``str | BaseComponent`` union is kept at L0 even though only the
# ``str`` half gets behavior here, so the type does not change under callers
# when L1 lands opaque component nodes (ADR 0003).
Slot = Annotated[str | BaseComponent, PjxSlot()]
Children = Annotated[str | BaseComponent, PjxSlot(children=True)]
