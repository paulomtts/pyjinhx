from typing import Literal

from pydantic import Field

from pyjinhx import BaseComponent
from pyjinhx.base import AttrValue, ExtraAttrs


class ToastHost(BaseComponent):
    position: Literal["top-right", "top-left", "bottom-right", "bottom-left"] = (
        "bottom-right"
    )
    timeout: int = 4000
    dismiss_label: str = "Dismiss"
    event_name: str = "px:toast"
    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
