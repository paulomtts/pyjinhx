from typing import Literal

from pyjinhx import BaseComponent
from pyjinhx.base import AttrValue


class PJXButton(BaseComponent):
    variant: str = "default"
    block: bool = False
    loading: bool = False
    disabled: bool = False
    type: Literal["button", "submit", "reset"] = "button"
    class_name: AttrValue = ""
    content: str | BaseComponent = ""
