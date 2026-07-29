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

from pydantic import BaseModel, ConfigDict


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


class BaseComponent(BaseModel):
    """Base for all components: declared fields only, undeclared kwargs rejected.

    Deliberately empty otherwise. Auto-ids, Slot, attribute coercion and
    quote-safety are separate concerns and land as their own changes; nothing
    here runs a side effect at construction time (ADR 0004/0009).
    """

    model_config = ConfigDict(extra="forbid")
