from pyjinhx import BaseComponent
from pyjinhx.base import AttrValue


class PJXModalBody(BaseComponent):
    class_name: AttrValue = ""
    content: str | BaseComponent = ""
