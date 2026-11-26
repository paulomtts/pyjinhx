from typing import Literal

from pydantic import Field

from pyjinhx._component import AttrValue, BaseComponent, ExtraAttrs, Slot


class PJXAccordionGroup(BaseComponent):
    """The wrapper that scopes exclusive/multi open behavior over the PJXAccordion items inside it."""

    mode: Literal["exclusive", "multi"] = "multi"
    gap: str = "0"
    default_open: Literal["none", "first", "all"] = "none"
    class_name: AttrValue = ""
    content: Slot = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
