from typing import Literal

from pydantic import Field

from pyjinhx import BaseComponent
from pyjinhx.base import AttrValue, ExtraAttrs, Slot


class PJXLazyLoad(BaseComponent):
    url: str
    when: Literal["viewport", "reveal", "load"] = "viewport"
    trigger: str = ""
    swap: str = "outerHTML"
    tag: Literal["div", "li", "tr"] = "div"
    content: str | BaseComponent = ""
    error: Slot = ""
    error_text: str = "Failed to load."
    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
