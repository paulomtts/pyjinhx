from typing import Literal

from pydantic import Field

from pyjinhx._component import AttrValue, BaseComponent, ExtraAttrs


class PJXSkeleton(BaseComponent):
    """A loading placeholder rendered as a shimmering text block, circle, or rectangle."""

    variant: Literal["text", "circle", "rect"] = "text"
    lines: int = 3
    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
