from typing import Annotated, Literal

from pyjinhx import BaseComponent
from pyjinhx.base import AttrValue, PjxSlot


class PJXButton(BaseComponent):
    start: Annotated[str | BaseComponent | None, PjxSlot()] = None
    center: str | None = None  # label text — escaped; use start/end slots for icons
    end: Annotated[str | BaseComponent | None, PjxSlot()] = None
    variant: str = "default"
    block: bool = False
    loading: bool = False
    disabled: bool = False
    type: Literal["button", "submit", "reset"] = "button"
    class_name: AttrValue = ""
