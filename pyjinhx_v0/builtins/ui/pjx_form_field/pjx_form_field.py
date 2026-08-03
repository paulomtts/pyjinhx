from pydantic import Field

from pyjinhx_v0 import BaseComponent
from pyjinhx_v0.base import AttrValue, ExtraAttrs


class PJXFormField(BaseComponent):
    label: str = ""
    for_id: str = ""
    content: str | BaseComponent = ""
    help: str = ""
    error: str = ""
    required: bool = False
    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
