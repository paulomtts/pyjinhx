from pyjinhx_v0 import BaseComponent
from pyjinhx_v0.base import AttrValue


class PJXAccordionTrigger(BaseComponent):
    disabled: bool = False
    class_name: AttrValue = ""
    content: str | BaseComponent = ""
