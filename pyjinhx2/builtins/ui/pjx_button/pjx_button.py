from typing import Literal

from pydantic import Field

from pyjinhx2.component import AttrValue, BaseComponent, ExtraAttrs, Slot


class PJXButton(BaseComponent):
    """A themeable button whose label is a freeform slot.

    ``loading`` both disables the button and overlays a ``PJXRegionLoader``,
    so an in-flight request cannot be fired twice from the same control.
    """

    variant: str = "default"
    block: bool = False
    loading: bool = False
    disabled: bool = False
    type: Literal["button", "submit", "reset"] = "button"
    class_name: AttrValue = ""
    content: Slot = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
