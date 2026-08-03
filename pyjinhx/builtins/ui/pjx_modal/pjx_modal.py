from pyjinhx.component import AttrValue, BaseComponent, Slot


class PJXModal(BaseComponent):
    """The dialog shell; regions come from PJXModalHeader/Body/Footer, not from fields here."""

    open_on_mount: bool = False
    remove_on_close: bool = False
    class_name: AttrValue = ""
    content: Slot = ""
