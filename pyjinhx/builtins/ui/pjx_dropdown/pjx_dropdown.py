from typing import Annotated

from pydantic import Field

from pyjinhx.builtins.ui.pjx_popover import PJXPopover
from pyjinhx._component import BaseComponent, PjxSlot, Slot


class PJXDropdown(PJXPopover):
    """A trigger button over a hidden menu panel, opened by the data-pjx-popover runtime (port of v0.x pyjinhx/builtins/ui/pjx_dropdown/pjx_dropdown.py).

    Extends PJXPopover for `align`, `class_name` and the popover runtime
    itself: the descriptor's MRO asset walk finds no `pjx_dropdown.js` beside
    this module and falls through to the ancestor's `pjx_popover.js`, so a
    rendered dropdown ships the script that its own hand-written
    `data-pjx-popover` markup has always depended on (#695). The template and
    stylesheet walks still stop here, on `pjx_dropdown.pjx`/`.css`.
    """

    trigger: Slot = ""
    items: Annotated[list[str | BaseComponent], PjxSlot()] = Field(
        default_factory=list,
        description=(
            "Menu entries. A str entry is plain text and is HTML-escaped; pass "
            "a component when the entry carries markup (a list entry is a "
            "collection member, not author-declared markup)."
        ),
    )
    menu_label: str = "Submenu"
