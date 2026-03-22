from typing import Literal

from pyjinhx import BaseComponent


class Spinner(BaseComponent):
    size: Literal["sm", "md", "lg"] = "md"
    label: str = "Loading"
