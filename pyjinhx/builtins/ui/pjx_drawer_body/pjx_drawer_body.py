from pyjinhx import BaseComponent
from pyjinhx.base import AttrValue


class PJXDrawerBody(BaseComponent):
    class_name: AttrValue = ""
    content: str | BaseComponent = ""
