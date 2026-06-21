from pyjinhx import BaseComponent
from pyjinhx.base import AttrValue


class PJXResizablePanel(BaseComponent):
    size: float | None = None
    min: float = 0
    max: float = 100
    class_name: AttrValue = ""
    content: str | BaseComponent = ""
