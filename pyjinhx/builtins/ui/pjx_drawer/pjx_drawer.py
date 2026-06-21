from typing import Literal

from pyjinhx import BaseComponent
from pyjinhx.base import AttrValue


class PJXDrawer(BaseComponent):
    side: Literal["left", "right", "bottom"] = "right"
    open_on_mount: bool = False
    remove_on_close: bool = False
    class_name: AttrValue = ""
    content: str | BaseComponent = ""
