from pydantic import Field

from pyjinhx import BaseComponent
from pyjinhx.base import AttrValue, ExtraAttrs


class PJXChipInput(BaseComponent):
    name: str
    values: list[str] = Field(default_factory=list)
    placeholder: str = "Add…"
    remove_label: str = "Remove"
    disabled: bool = False
    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
