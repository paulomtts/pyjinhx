from pydantic import Field

from pyjinhx import BaseComponent
from pyjinhx.base import AttrValue, ExtraAttrs


class AvatarStack(BaseComponent):
    avatars: list[str | BaseComponent] = Field(default_factory=list)
    extra_count: int = 0
    empty_label: str = ""
    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
