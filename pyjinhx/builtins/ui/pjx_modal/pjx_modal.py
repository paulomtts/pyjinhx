from pydantic import Field

from pyjinhx._component import AttrValue, BaseComponent, ExtraAttrs, Slot


class PJXModal(BaseComponent):
    """The dialog shell; regions come from PJXModalHeader/Body/Footer, not from fields here."""

    open_on_mount: bool = False
    remove_on_close: bool = False
    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)
    content: Slot = ""
