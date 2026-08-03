from typing import Literal

from pyjinhx_v0 import BaseComponent
from pyjinhx_v0.base import AttrValue


class PJXDrawer(BaseComponent):
    side: Literal["left", "right", "bottom"] = "right"
    open_on_mount: bool = False
    remove_on_close: bool = False
    class_name: AttrValue = ""
    content: str | BaseComponent = ""
