from pyjinhx import BaseComponent
from pyjinhx.base import AttrValue


class PJXTabList(BaseComponent):
    label: str = "Tabs"
    reorderable: bool = False
    class_name: AttrValue = ""
    content: str | BaseComponent = ""
