from pyjinhx_v0 import BaseComponent
from pyjinhx_v0.base import AttrValue


class PJXTabList(BaseComponent):
    label: str = "Tabs"
    reorderable: bool = False
    class_name: AttrValue = ""
    content: str | BaseComponent = ""
