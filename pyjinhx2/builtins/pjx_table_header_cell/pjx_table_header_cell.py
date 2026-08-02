from typing import Literal

from pyjinhx2.component import AttrValue, BaseComponent, Slot


class PJXTableHeaderCell(BaseComponent):
    """A column header cell, optionally sortable."""

    sortable: bool = False
    sort: Literal["none", "asc", "desc"] = "none"
    class_name: AttrValue = ""
    content: Slot = ""
