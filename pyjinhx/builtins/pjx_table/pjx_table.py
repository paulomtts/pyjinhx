from typing import Literal

from pydantic import Field

from pyjinhx._component import AttrValue, BaseComponent, ExtraAttrs, Slot


class PJXTable(BaseComponent):
    """A data table with optional caption, striping, sticky header and borders."""

    caption: str = ""
    striped: bool = False
    sticky_header: bool = False
    density: Literal["comfortable", "compact"] = "comfortable"
    bordered: Literal["none", "horizontal", "all"] = "none"
    class_name: AttrValue = ""
    content: Slot = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
