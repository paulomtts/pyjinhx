from typing import Literal

from pyjinhx import BaseComponent
from pyjinhx.base import AttrValue


class PJXTableHeaderCell(BaseComponent):
    sortable: bool = False
    sort: Literal["none", "asc", "desc"] = "none"
    class_name: AttrValue = ""
    content: str | BaseComponent = ""
