from typing import Literal

from pydantic import Field

from pyjinhx._component import AttrValue, BaseComponent, ExtraAttrs, Slot


class PJXPopover(BaseComponent):
    """The positioned root shell that anchors a trigger to its panel; the JS finds both through data-pjx-popover (port of v0.x pyjinhx/builtins/ui/pjx_popover/pjx_popover.py)."""

    align: Literal["start", "end"] = "start"
    portal: bool = False
    class_name: AttrValue = ""
    content: Slot = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
