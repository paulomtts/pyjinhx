from typing import Literal

from pyjinhx import BaseComponent
from pyjinhx.base import AttrValue


class PJXTable(BaseComponent):
    caption: str = ""
    striped: bool = False
    sticky_header: bool = False
    density: Literal["comfortable", "compact"] = "comfortable"
    bordered: Literal["none", "horizontal", "all"] = "none"
    class_name: AttrValue = ""
    content: str | BaseComponent = ""
