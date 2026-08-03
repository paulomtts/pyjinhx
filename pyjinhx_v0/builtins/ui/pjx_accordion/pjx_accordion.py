from pyjinhx_v0 import BaseComponent
from pyjinhx_v0.base import AttrValue


class PJXAccordion(BaseComponent):
    open: bool = True
    group: str | None = None
    class_name: AttrValue = ""
    content: str | BaseComponent = ""
