from typing import Literal

from pyjinhx import BaseComponent


class Popover(BaseComponent):
    content: str | BaseComponent = ""
    card_content: str | BaseComponent = ""
    position: Literal["follow", "anchor"] = "anchor"
    backdrop: bool = False
