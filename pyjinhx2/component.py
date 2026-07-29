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


class BaseComponent(BaseModel):
    """Base for all components: declared fields only, undeclared kwargs rejected.

    Deliberately empty otherwise. Auto-ids, Slot, attribute coercion and
    quote-safety are separate concerns and land as their own changes; nothing
    here runs a side effect at construction time (ADR 0004/0009).
    """

    model_config = ConfigDict(extra="forbid")
