from pydantic import Field

from pyjinhx._component import AttrValue, BaseComponent, ExtraAttrs, Slot


class PJXDrawerFooter(BaseComponent):
    """The bottom action region of a drawer."""

    class_name: AttrValue = ""
    content: Slot = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
