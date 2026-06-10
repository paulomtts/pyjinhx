from typing import Literal

from pydantic import Field

from pyjinhx import BaseComponent
from pyjinhx.base import AttrValue, ExtraAttrs


class Badge(BaseComponent):
    label: str = ""
    color: Literal["brand", "error", "neutral", "muted"] = "neutral"
    shape: Literal["square", "sm", "md", "full"] = "md"
    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
