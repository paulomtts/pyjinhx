from typing import Literal

from pyjinhx2.component import AttrValue, BaseComponent


class PJXBadge(BaseComponent):
    label: str = ""
    color: Literal["brand", "error", "neutral", "muted"] = "neutral"
    shape: Literal["square", "sm", "md", "full"] = "md"
    class_name: AttrValue = ""
