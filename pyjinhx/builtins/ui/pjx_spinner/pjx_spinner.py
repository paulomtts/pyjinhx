from typing import Literal

from pydantic import Field

from pyjinhx._component import AttrValue, BaseComponent, ExtraAttrs


class PJXSpinner(BaseComponent):
    """A rotating loading indicator with a visually-hidden status label."""

    size: Literal["sm", "md", "lg"] = "md"
    label: str = "Loading"
    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
