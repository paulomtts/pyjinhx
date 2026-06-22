from pyjinhx import BaseComponent
from pyjinhx.base import AttrValue


class PJXTableRow(BaseComponent):
    class_name: AttrValue = ""
    content: str | BaseComponent = ""
