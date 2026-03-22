from typing import Literal

from pyjinhx import BaseComponent


class Alert(BaseComponent):
    variant: Literal["info", "success", "warning", "error"] = "info"
    title: str = ""
    body: str | BaseComponent = ""
    dismissible: bool = False
