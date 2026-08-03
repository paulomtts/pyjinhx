from typing import Literal

from pyjinhx_v0 import BaseComponent
from pyjinhx_v0.base import AttrValue


class PJXTable(BaseComponent):
    caption: str = ""
    striped: bool = False
    sticky_header: bool = False
    density: Literal["comfortable", "compact"] = "comfortable"
    bordered: Literal["none", "horizontal", "all"] = "none"
    class_name: AttrValue = ""
    content: str | BaseComponent = ""
