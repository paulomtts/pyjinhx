from pyjinhx_v0 import BaseComponent
from pyjinhx_v0.base import AttrValue


class PJXTab(BaseComponent):
    panel: str = ""
    icon: str = ""
    closeable: bool = False
    pinned: bool = False
    selected: bool = False
    close_label: str = "Close"
    class_name: AttrValue = ""
    content: str | BaseComponent = ""
