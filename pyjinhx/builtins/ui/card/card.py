from pydantic import Field

from pyjinhx import BaseComponent
from pyjinhx.base import AttrValue, ExtraAttrs


class Card(BaseComponent):
    title: str | BaseComponent = ""
    header: str | BaseComponent = ""
    body: str | BaseComponent = ""
    footer: str | BaseComponent = ""
    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
