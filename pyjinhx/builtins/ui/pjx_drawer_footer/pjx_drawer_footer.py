from pyjinhx import BaseComponent
from pyjinhx.base import AttrValue


class PJXDrawerFooter(BaseComponent):
    class_name: AttrValue = ""
    content: str | BaseComponent = ""
