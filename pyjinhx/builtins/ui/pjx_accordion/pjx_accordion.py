from pyjinhx import BaseComponent
from pyjinhx.base import AttrValue


class PJXAccordion(BaseComponent):
    open: bool = True
    group: str | None = None
    class_name: AttrValue = ""
    content: str | BaseComponent = ""
