from pyjinhx import BaseComponent
from pyjinhx.base import AttrValue


class PJXTableRow(BaseComponent):
    selectable: bool = False
    value: str = ""
    select_label: str = "Select row"
    class_name: AttrValue = ""
    content: str | BaseComponent = ""
