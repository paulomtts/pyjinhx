from pydantic import Field

from pyjinhx import BaseComponent
from pyjinhx.base import AttrValue, ExtraAttrs


class PasswordInput(BaseComponent):
    name: str = "password"
    placeholder: str = ""
    autocomplete: str = "current-password"
    required: bool = False
    show_label: str = "Show password"
    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
