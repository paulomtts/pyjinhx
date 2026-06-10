from typing import Literal

from pydantic import Field

from pyjinhx import BaseComponent
from pyjinhx.base import AttrValue, ExtraAttrs


class Notification(BaseComponent):
    content: str | BaseComponent = ""
    corner: Literal["top-right", "top-left", "bottom-right", "bottom-left"] = (
        "top-right"
    )
    timeout: int = 5000
    autoshow: bool = True
    dismiss_label: str = "Dismiss"
    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
