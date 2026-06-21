from pyjinhx import BaseComponent
from pyjinhx.base import AttrValue


class PJXCardHeader(BaseComponent):
    title: str = ""
    class_name: AttrValue = ""
    content: str | BaseComponent = ""
