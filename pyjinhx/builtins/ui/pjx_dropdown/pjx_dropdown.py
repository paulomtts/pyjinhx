import os
from typing import Literal

from pydantic import Field

from pyjinhx import BaseComponent
from pyjinhx.base import AttrValue, ExtraAttrs


class PJXDropdown(BaseComponent):
    trigger: str | BaseComponent = ""
    items: list[str | BaseComponent] = Field(default_factory=list)
    align: Literal["start", "end"] = "start"
    menu_label: str = "Submenu"
    behavior: bool = True
    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
    # PJXDropdown ships no JS of its own; its wiring lives in pjx-popover.js,
    # shipped via the extra-asset mechanism whenever a PJXDropdown renders.
    js: list[str] = Field(
        default_factory=lambda: [
            os.path.join(os.path.dirname(__file__), "..", "pjx_popover", "pjx-popover.js")
        ]
    )
