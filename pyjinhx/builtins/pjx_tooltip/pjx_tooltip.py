from typing import Literal

from pydantic import Field

from pyjinhx._component import AttrValue, BaseComponent, ExtraAttrs, Slot


class PJXTooltip(BaseComponent):
    """The positioned root shell that anchors a trigger to its tip; the JS finds both through data-pjx-tooltip-placement (port of v0.x pyjinhx/builtins/ui/pjx_tooltip/pjx_tooltip.py)."""

    placement: Literal["top", "bottom", "start", "end"] = "top"
    backdrop: bool = False
    portal: bool = False
    class_name: AttrValue = ""
    content: Slot = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
