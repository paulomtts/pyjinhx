from typing import Literal

from pyjinhx import BaseComponent


class Divider(BaseComponent):
    orientation: Literal["horizontal", "vertical"] = "horizontal"
    label: str = ""
    class_name: str = ""
