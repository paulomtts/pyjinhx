from typing import ClassVar, Literal

from pydantic import Field

from pyjinhx import BaseComponent, Slot
from pyjinhx.base import AttrValue, ExtraAttrs


class PJXTooltip(BaseComponent):
    _pjx_children_field: ClassVar[str] = "tip"

    trigger: Slot = ""
    tip: str | BaseComponent = ""
    placement: Literal["top", "bottom", "start", "end"] = "top"
    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
