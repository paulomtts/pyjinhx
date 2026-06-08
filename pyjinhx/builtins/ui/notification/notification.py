from typing import Literal

from pyjinhx import BaseComponent


class Notification(BaseComponent):
    content: str | BaseComponent = ""
    corner: Literal["top-right", "top-left", "bottom-right", "bottom-left"] = (
        "top-right"
    )
    timeout: int = 5000
