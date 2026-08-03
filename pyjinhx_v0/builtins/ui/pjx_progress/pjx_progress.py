from pydantic import Field

from pyjinhx_v0 import BaseComponent
from pyjinhx_v0.base import AttrValue, ExtraAttrs


class PJXProgress(BaseComponent):
    value: float | None = None
    max: float = 100
    label: str = ""
    loading_label: str = "Loading"
    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
