from typing import ClassVar, Literal

from pydantic import Field

from pyjinhx_v0 import BaseComponent
from pyjinhx_v0.base import AttrValue, ExtraAttrs


class PJXAlert(BaseComponent):
    _pjx_children_field: ClassVar[str] = "body"

    variant: Literal["info", "success", "warning", "error"] = "info"
    title: str = ""
    body: str | BaseComponent = ""
    dismissible: bool = False
    dismiss_label: str = "Dismiss"
    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
