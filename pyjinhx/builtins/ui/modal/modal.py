from pydantic import Field

from pyjinhx import BaseComponent
from pyjinhx.base import AttrValue, ExtraAttrs


class Modal(BaseComponent):
    title: str | BaseComponent = ""
    header: str | BaseComponent = ""
    body: str | BaseComponent = ""
    footer: str | BaseComponent = ""
    close_label: str = "Close"
    open_on_mount: bool = False
    remove_on_close: bool = False
    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
