from typing import Literal

from pyjinhx import BaseComponent


class Drawer(BaseComponent):
    side: Literal["left", "right", "bottom"] = "right"
    title: str | BaseComponent = ""
    body: str | BaseComponent = ""
    footer: str | BaseComponent = ""
