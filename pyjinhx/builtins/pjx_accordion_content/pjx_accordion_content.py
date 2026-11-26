from pydantic import Field

from pyjinhx._component import AttrValue, BaseComponent, ExtraAttrs, Slot


class PJXAccordionContent(BaseComponent):
    """The body region revealed when its parent PJXAccordion is open."""

    class_name: AttrValue = ""
    content: Slot = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
