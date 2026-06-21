from pyjinhx import BaseComponent
from pyjinhx.base import AttrValue


class PJXModal(BaseComponent):
    open_on_mount: bool = False
    remove_on_close: bool = False
    class_name: AttrValue = ""
    content: str | BaseComponent = ""
