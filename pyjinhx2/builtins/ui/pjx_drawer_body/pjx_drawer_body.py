from pyjinhx2.component import AttrValue, BaseComponent, Slot


class PJXDrawerBody(BaseComponent):
    """The scrollable middle region of a drawer."""

    class_name: AttrValue = ""
    content: Slot = ""
