from pyjinhx import BaseComponent
from pyjinhx.base import AttrValue


class PJXTabPanel(BaseComponent):
    tab: str = ""
    class_name: AttrValue = ""
    content: str | BaseComponent = ""
