from typing import Literal

from pyjinhx.component import AttrValue, BaseComponent


class PJXSpinner(BaseComponent):
    """A rotating loading indicator with a visually-hidden status label."""

    size: Literal["sm", "md", "lg"] = "md"
    label: str = "Loading"
    class_name: AttrValue = ""
