from pyjinhx import BaseComponent
from pyjinhx.base import AttrValue


class PJXAccordion(BaseComponent):
    label: str = ""
    header: str | BaseComponent | None = None
    open: bool = True
    disabled: bool = False
    group: str | None = None
    content: str | BaseComponent = ""
    class_name: AttrValue = ""
