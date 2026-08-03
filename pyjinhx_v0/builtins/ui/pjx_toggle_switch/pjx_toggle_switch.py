from pydantic import Field

from pyjinhx_v0 import BaseComponent
from pyjinhx_v0.base import AttrValue, ExtraAttrs


class PJXToggleSwitch(BaseComponent):
    name: str = ""
    value: str = "on"
    checked: bool = False
    label: str = ""
    disabled: bool = False
    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
