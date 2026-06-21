from pyjinhx import BaseComponent
from pyjinhx.base import AttrValue


class PJXAccordionTrigger(BaseComponent):
    disabled: bool = False
    class_name: AttrValue = ""
    content: str | BaseComponent = ""
