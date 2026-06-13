from typing import Literal

from pydantic import Field

from pyjinhx import BaseComponent
from pyjinhx.base import AttrValue, ExtraAttrs


class PJXSkeleton(BaseComponent):
    variant: Literal["text", "circle", "rect"] = "text"
    lines: int = 3
    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
