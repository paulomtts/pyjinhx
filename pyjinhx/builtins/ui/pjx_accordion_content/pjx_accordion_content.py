from pyjinhx import BaseComponent
from pyjinhx.base import AttrValue


class PJXAccordionContent(BaseComponent):
    class_name: AttrValue = ""
    content: str | BaseComponent = ""
