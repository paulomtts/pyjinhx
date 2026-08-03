from typing import Literal

from pyjinhx.component import AttrValue, BaseComponent, Slot


class PJXDrawer(BaseComponent):
    """The slide-in dialog shell; regions come from PJXDrawerHeader/Body/Footer, not from fields here."""

    side: Literal["left", "right", "bottom"] = "right"
    open_on_mount: bool = False
    remove_on_close: bool = False
    class_name: AttrValue = ""
    content: Slot = ""
