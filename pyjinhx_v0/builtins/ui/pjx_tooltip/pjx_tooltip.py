from typing import Literal

from pyjinhx_v0 import BaseComponent
from pyjinhx_v0.base import AttrValue


class PJXTooltip(BaseComponent):
    placement: Literal["top", "bottom", "start", "end"] = "top"
    class_name: AttrValue = ""
    content: str | BaseComponent = ""
