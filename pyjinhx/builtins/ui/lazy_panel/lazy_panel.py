from typing import Literal

from pydantic import Field

from pyjinhx import BaseComponent
from pyjinhx.base import AttrValue, ExtraAttrs


class LazyPanel(BaseComponent):
    url: str
    when: Literal["viewport", "reveal", "load"] = "viewport"
    trigger: str = ""
    swap: str = "outerHTML"
    content: str | BaseComponent = ""
    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
