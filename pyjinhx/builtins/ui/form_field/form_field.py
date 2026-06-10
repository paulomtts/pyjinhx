from pydantic import Field

from pyjinhx import BaseComponent
from pyjinhx.base import AttrValue, ExtraAttrs


class FormField(BaseComponent):
    label: str = ""
    for_id: str = ""
    content: str | BaseComponent = ""
    help: str = ""
    error: str = ""
    required: bool = False
    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
