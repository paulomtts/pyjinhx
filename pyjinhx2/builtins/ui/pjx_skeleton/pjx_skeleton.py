from typing import Literal

from pyjinhx2.component import AttrValue, BaseComponent


class PJXSkeleton(BaseComponent):
    """A loading placeholder rendered as a shimmering text block, circle, or rectangle."""

    variant: Literal["text", "circle", "rect"] = "text"
    lines: int = 3
    class_name: AttrValue = ""
