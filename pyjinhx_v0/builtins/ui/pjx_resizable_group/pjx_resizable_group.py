from typing import Literal

from pyjinhx_v0 import BaseComponent
from pyjinhx_v0.base import AttrValue


class PJXResizableGroup(BaseComponent):
    direction: Literal["row", "column"] = "row"
    class_name: AttrValue = ""
    content: str | BaseComponent = ""
