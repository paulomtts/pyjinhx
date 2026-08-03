from pyjinhx_v0 import BaseComponent, Slot
from pyjinhx_v0.base import AttrValue


class PJXModalHeader(BaseComponent):
    title: str = ""
    close_label: str = "Close"
    close_content: Slot = "✕"
    class_name: AttrValue = ""
    content: str | BaseComponent = ""
