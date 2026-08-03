from typing import Literal

from pyjinhx_v0 import BaseComponent
from pyjinhx_v0.base import AttrValue


class PJXTableHeaderCell(BaseComponent):
    sortable: bool = False
    sort: Literal["none", "asc", "desc"] = "none"
    class_name: AttrValue = ""
    content: str | BaseComponent = ""
