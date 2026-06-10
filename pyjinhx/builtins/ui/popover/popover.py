from typing import Literal

from pydantic import Field

from pyjinhx import BaseComponent
from pyjinhx.base import AttrValue, ExtraAttrs


class Popover(BaseComponent):
    content: str | BaseComponent = ""
    align: Literal["start", "end"] = "start"
    behavior: bool = True
    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)


class PopoverTrigger(BaseComponent):
    content: str | BaseComponent = ""
    tag: Literal["button", "div"] = "button"
    role: Literal["", "menu", "listbox", "dialog"] = ""
    behavior: bool = True
    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)


class PopoverPanel(BaseComponent):
    content: str | BaseComponent = ""
    as_form: bool = False
    role: Literal["", "menu", "listbox", "dialog"] = ""
    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
