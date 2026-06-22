from pyjinhx import BaseComponent
from pyjinhx.base import AttrValue


class PJXTabList(BaseComponent):
    label: str = "Tabs"
    class_name: AttrValue = ""
    content: str | BaseComponent = ""
