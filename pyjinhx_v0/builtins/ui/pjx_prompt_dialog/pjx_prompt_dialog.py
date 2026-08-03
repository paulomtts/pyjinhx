from pydantic import Field

from pyjinhx_v0 import BaseComponent
from pyjinhx_v0.base import AttrValue, ExtraAttrs


class PJXPromptDialog(BaseComponent):
    input_label: str = ""
    submit_label: str = "OK"
    cancel_label: str = "Cancel"
    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
