from pyjinhx_v0 import BaseComponent
from pyjinhx_v0.base import AttrValue


class PJXTableHead(BaseComponent):
    class_name: AttrValue = ""
    content: str | BaseComponent = ""
