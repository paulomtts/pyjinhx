from typing import Literal

from pydantic import Field

from pyjinhx._component import AttrValue, BaseComponent, ExtraAttrs


class PJXDivider(BaseComponent):
    """A separator rendered as a plain rule, a vertical bar, or a labeled row."""

    orientation: Literal["horizontal", "vertical"] = "horizontal"
    label: str = ""
    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
