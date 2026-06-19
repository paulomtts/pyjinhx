from typing import ClassVar, Literal

from pydantic import Field

from pyjinhx import BaseComponent, Slot
from pyjinhx.base import AttrValue, ExtraAttrs


class PJXDrawer(BaseComponent):
    _pjx_children_field: ClassVar[str] = "body"

    side: Literal["left", "right", "bottom"] = "right"
    title: str | BaseComponent = ""
    body: str | BaseComponent = ""
    footer: Slot = ""
    close_label: str = "Close"
    close_content: str | BaseComponent = "✕"
    open_on_mount: bool = False
    remove_on_close: bool = False
    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
