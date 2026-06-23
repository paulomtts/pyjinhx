from pyjinhx import BaseComponent
from pyjinhx.base import AttrValue


class PJXTableCell(BaseComponent):
    class_name: AttrValue = ""
    content: str | BaseComponent = ""
