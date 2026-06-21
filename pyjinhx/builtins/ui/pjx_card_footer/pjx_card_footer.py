from pyjinhx import BaseComponent
from pyjinhx.base import AttrValue


class PJXCardFooter(BaseComponent):
    class_name: AttrValue = ""
    content: str | BaseComponent = ""
