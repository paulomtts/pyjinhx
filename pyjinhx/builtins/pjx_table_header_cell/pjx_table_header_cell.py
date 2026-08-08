from typing import Literal

from pydantic import Field

from pyjinhx._component import AttrValue, BaseComponent, ExtraAttrs, Slot


class PJXTableHeaderCell(BaseComponent):
    """A column header cell, optionally sortable."""

    sortable: bool = False
    sort: Literal["none", "asc", "desc"] = "none"
    class_name: AttrValue = ""
    content: Slot = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
