from typing import Literal

from pydantic import Field

from pyjinhx import BaseComponent
from pyjinhx._component import AttrValue, ExtraAttrs


class Button(BaseComponent):
    """A button that hands any htmx attributes it is given to the element."""

    label: str
    kind: Literal["primary", "ghost"] = "primary"
    hx_post: AttrValue = ""
    attrs: ExtraAttrs = Field(default_factory=dict)
