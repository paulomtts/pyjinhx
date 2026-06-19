from typing import ClassVar

from pydantic import Field

from pyjinhx import BaseComponent, Slot
from pyjinhx.base import AttrValue, ExtraAttrs


class PJXCard(BaseComponent):
    _pjx_children_field: ClassVar[str] = "body"

    title: str = ""  # text — escaped; use the header slot for custom markup
    header: Slot = ""
    body: str | BaseComponent = ""
    footer: Slot = ""
    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
