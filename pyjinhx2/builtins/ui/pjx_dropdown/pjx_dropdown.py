from typing import Annotated, Literal

from pydantic import Field

from pyjinhx2.component import AttrValue, BaseComponent, PjxSlot, Slot


class PJXDropdown(BaseComponent):
    """A trigger button over a hidden menu panel, opened by the data-pjx-popover runtime (port of v0.x pyjinhx/builtins/ui/pjx_dropdown/pjx_dropdown.py)."""

    trigger: Slot = ""
    items: Annotated[list[str | BaseComponent], PjxSlot()] = Field(default_factory=list)
    align: Literal["start", "end"] = "start"
    menu_label: str = "Submenu"
    class_name: AttrValue = ""
