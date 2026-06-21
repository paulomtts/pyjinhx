from pyjinhx import BaseComponent, Slot
from pyjinhx.base import AttrValue


class PJXModalHeader(BaseComponent):
    title: str = ""
    close_label: str = "Close"
    close_content: Slot = "✕"
    class_name: AttrValue = ""
    content: str | BaseComponent = ""
