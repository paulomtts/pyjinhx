from pyjinhx_v0 import BaseComponent
from pyjinhx_v0.base import AttrValue


class PJXTableRow(BaseComponent):
    selectable: bool = False
    value: str = ""
    select_label: str = "Select row"
    class_name: AttrValue = ""
    content: str | BaseComponent = ""
