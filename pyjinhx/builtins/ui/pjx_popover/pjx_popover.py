from typing import Literal

from pyjinhx._component import AttrValue, BaseComponent, Slot


class PJXPopover(BaseComponent):
    """The positioned root shell that anchors a trigger to its panel; the JS finds both through data-pjx-popover (port of v0.x pyjinhx/builtins/ui/pjx_popover/pjx_popover.py)."""

    align: Literal["start", "end"] = "start"
    class_name: AttrValue = ""
    content: Slot = ""
