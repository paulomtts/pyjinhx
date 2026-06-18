from typing import Literal

from pyjinhx import BaseComponent
from pyjinhx.base import AttrValue


class PJXButton(BaseComponent):
    start: str | BaseComponent | None = None
    center: str | BaseComponent | None = None
    end: str | BaseComponent | None = None
    variant: str = "default"
    block: bool = False
    loading: bool = False
    disabled: bool = False
    type: Literal["button", "submit", "reset"] = "button"
    class_name: AttrValue = ""
