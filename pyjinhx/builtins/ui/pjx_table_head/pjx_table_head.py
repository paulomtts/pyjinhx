from pyjinhx import BaseComponent
from pyjinhx.base import AttrValue


class PJXTableHead(BaseComponent):
    class_name: AttrValue = ""
    content: str | BaseComponent = ""
