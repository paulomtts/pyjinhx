from typing import Literal

from pydantic import Field

from pyjinhx import BaseComponent
from pyjinhx.base import AttrValue, ExtraAttrs


class Divider(BaseComponent):
    orientation: Literal["horizontal", "vertical"] = "horizontal"
    label: str = ""
    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
