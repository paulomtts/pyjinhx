from typing import Literal

from pyjinhx2.component import AttrValue, BaseComponent, Slot


class PJXAccordionGroup(BaseComponent):
    """The wrapper that scopes exclusive/multi open behavior over the PJXAccordion items inside it."""

    mode: Literal["exclusive", "multi"] = "multi"
    gap: str = "0"
    default_open: Literal["none", "first", "all"] = "none"
    class_name: AttrValue = ""
    content: Slot = ""
