from pydantic import Field

from pyjinhx_v0 import BaseComponent
from pyjinhx_v0.base import AttrValue, ExtraAttrs


class PJXPageLoader(BaseComponent):
    nav_targets: str = "app-content"
    active_on_load: bool = True
    loading_label: str = "Loading"
    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
