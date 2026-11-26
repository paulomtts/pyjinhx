from typing import Literal

from pydantic import Field

from pyjinhx._component import AttrValue, BaseComponent, ExtraAttrs, Slot


class PJXDrawer(BaseComponent):
    """The slide-in dialog shell; regions come from PJXDrawerHeader/Body/Footer, not from fields here."""

    side: Literal["left", "right", "bottom"] = "right"
    open_on_mount: bool = False
    remove_on_close: bool = False
    class_name: AttrValue = ""
    content: Slot = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
