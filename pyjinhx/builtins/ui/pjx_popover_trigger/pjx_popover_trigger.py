from typing import Literal

from pyjinhx._component import AttrValue, BaseComponent, Slot


class PJXPopoverTrigger(BaseComponent):
    """The clickable element that toggles its popover panel; a div variant carries button semantics by hand (port of v0.x pyjinhx/builtins/ui/pjx_popover/pjx_popover_trigger.html)."""

    tag: Literal["button", "div"] = "button"
    role: Literal["", "menu", "listbox", "dialog"] = ""
    class_name: AttrValue = ""
    content: Slot = ""
