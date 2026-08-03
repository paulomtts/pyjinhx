from typing import Literal

from pyjinhx_v0 import BaseComponent
from pyjinhx_v0.base import AttrValue


class PJXButton(BaseComponent):
    variant: str = "default"
    block: bool = False
    loading: bool = False
    disabled: bool = False
    type: Literal["button", "submit", "reset"] = "button"
    class_name: AttrValue = ""
    content: str | BaseComponent = ""
