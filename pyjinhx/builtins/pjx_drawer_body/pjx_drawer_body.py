from pydantic import Field

from pyjinhx.components.base import AttrValue, BaseComponent, ExtraAttrs, Slot


class PJXDrawerBody(BaseComponent):
    """The scrollable middle region of a drawer."""

    class_name: AttrValue = ""
    content: Slot = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
