from typing import Literal

from pydantic import Field

from pyjinhx._component import AttrValue, BaseComponent, ExtraAttrs, Slot


class PJXStack(BaseComponent):
    """A flex row or column of its content, spaced by a step on the theme's spacing scale."""

    direction: Literal["vertical", "horizontal"] = "vertical"
    gap: Literal["1", "2", "3", "4", "5", "6", "8", "10", "12"] = "3"
    align: Literal["", "start", "center", "end", "stretch", "baseline"] = ""
    justify: Literal["", "start", "center", "end", "between", "around", "evenly"] = ""
    wrap: bool = False
    content: Slot = ""
    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
