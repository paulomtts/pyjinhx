from typing import Literal

from pyjinhx import BaseComponent


class Tooltip(BaseComponent):
    trigger: str | BaseComponent = ""
    tip: str | BaseComponent = ""
    placement: Literal["top", "bottom", "start", "end"] = "top"
