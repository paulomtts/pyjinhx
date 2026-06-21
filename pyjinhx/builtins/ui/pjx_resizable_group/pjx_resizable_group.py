from typing import Literal

from pyjinhx import BaseComponent
from pyjinhx.base import AttrValue


class PJXResizableGroup(BaseComponent):
    direction: Literal["row", "column"] = "row"
    class_name: AttrValue = ""
    content: str | BaseComponent = ""
