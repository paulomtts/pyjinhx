from typing import Literal

from pyjinhx._component import AttrValue, BaseComponent


class PJXDivider(BaseComponent):
    """A separator rendered as a plain rule, a vertical bar, or a labeled row."""

    orientation: Literal["horizontal", "vertical"] = "horizontal"
    label: str = ""
    class_name: AttrValue = ""
