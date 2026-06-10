from typing import Literal

from pydantic import Field

from pyjinhx import BaseComponent
from pyjinhx.base import AttrValue, ExtraAttrs


class Alert(BaseComponent):
    variant: Literal["info", "success", "warning", "error"] = "info"
    title: str = ""
    body: str | BaseComponent = ""
    dismissible: bool = False
    dismiss_label: str = "Dismiss"
    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
