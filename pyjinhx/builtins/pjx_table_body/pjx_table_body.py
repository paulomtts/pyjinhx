from pydantic import Field

from pyjinhx.components.base import AttrValue, BaseComponent, ExtraAttrs, Slot


class PJXTableBody(BaseComponent):
    """A table body section."""

    class_name: AttrValue = ""
    content: Slot = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
