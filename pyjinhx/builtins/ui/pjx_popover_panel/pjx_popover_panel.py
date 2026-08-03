from typing import Literal

from pyjinhx.component import AttrValue, BaseComponent, Slot


class PJXPopoverPanel(BaseComponent):
    """The hidden-by-default floating panel a trigger reveals, optionally a <form> so it can submit on its own (port of v0.x pyjinhx/builtins/ui/pjx_popover/pjx_popover_panel.html)."""

    as_form: bool = False
    role: Literal["", "menu", "listbox", "dialog"] = ""
    class_name: AttrValue = ""
    content: Slot = ""
