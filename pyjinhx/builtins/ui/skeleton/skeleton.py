from typing import Literal

from pyjinhx import BaseComponent


class Skeleton(BaseComponent):
    variant: Literal["text", "circle", "rect"] = "text"
    lines: int = 3
    class_name: str = ""
