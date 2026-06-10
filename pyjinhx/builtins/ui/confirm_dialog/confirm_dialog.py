from pydantic import Field

from pyjinhx import BaseComponent
from pyjinhx.base import AttrValue, ExtraAttrs


class ConfirmDialog(BaseComponent):
    confirm_label: str = "Confirm"
    cancel_label: str = "Cancel"
    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
