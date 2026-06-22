from pyjinhx import BaseComponent
from pyjinhx.base import AttrValue


class PJXTab(BaseComponent):
    panel: str = ""
    icon: str = ""
    closeable: bool = False
    pinned: bool = False
    selected: bool = False
    close_label: str = "Close"
    class_name: AttrValue = ""
    content: str | BaseComponent = ""
