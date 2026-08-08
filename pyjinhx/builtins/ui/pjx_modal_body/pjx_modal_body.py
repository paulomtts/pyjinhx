from pydantic import Field

from pyjinhx._component import AttrValue, BaseComponent, ExtraAttrs, Slot


class PJXModalBody(BaseComponent):
    """The scrollable middle region of a modal."""

    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
    content: Slot = ""
