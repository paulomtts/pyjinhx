from pyjinhx_v0 import BaseComponent
from pyjinhx_v0.base import AttrValue


class PJXTabPanel(BaseComponent):
    tab: str = ""
    class_name: AttrValue = ""
    content: str | BaseComponent = ""
