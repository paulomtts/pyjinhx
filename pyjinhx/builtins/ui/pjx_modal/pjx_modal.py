from typing import ClassVar

from pydantic import Field

from pyjinhx import BaseComponent, Slot
from pyjinhx.base import AttrValue, ExtraAttrs


class PJXModal(BaseComponent):
    _pjx_children_field: ClassVar[str] = "body"

    title: str | BaseComponent = ""
    header: Slot = ""
    body: str | BaseComponent = ""
    footer: Slot = ""
    close_label: str = "Close"
    close_content: Slot = "✕"
    open_on_mount: bool = False
    remove_on_close: bool = False
    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
