from pydantic import Field

from pyjinhx.components.base import AttrValue, BaseComponent, ExtraAttrs, Slot


class PJXTableHead(BaseComponent):
    """A table header section."""

    class_name: AttrValue = ""
    content: Slot = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
