from pyjinhx import BaseComponent
from pyjinhx.base import AttrValue


class PJXTableHeaderCell(BaseComponent):
    class_name: AttrValue = ""
    content: str | BaseComponent = ""
