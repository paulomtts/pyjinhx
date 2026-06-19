from typing import Literal

from pyjinhx import BaseComponent
from pyjinhx.base import AttrValue


class PJXAccordionGroup(BaseComponent):
    mode: Literal["exclusive", "multi"] = "multi"
    gap: str = "0"
    default_open: Literal["none", "first", "all"] = "none"
    class_name: AttrValue = ""
    content: str | BaseComponent = ""
