from pydantic import Field

from pyjinhx import BaseComponent
from pyjinhx.base import AttrValue, ExtraAttrs


class EmptyState(BaseComponent):
    image: str | BaseComponent = ""
    title: str | BaseComponent = ""
    description: str | BaseComponent = ""
    action: str | BaseComponent = ""
    actions: list[str | BaseComponent] = Field(default_factory=list)
    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
