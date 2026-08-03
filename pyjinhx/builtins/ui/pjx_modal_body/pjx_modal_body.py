from pyjinhx.component import AttrValue, BaseComponent, Slot


class PJXModalBody(BaseComponent):
    """The scrollable middle region of a modal."""

    class_name: AttrValue = ""
    content: Slot = ""
